"""Response formatting utilities — text shaping, reference extraction, command stripping."""
import re

_CMD_RE = r"\[(?:LAUNCH|TASK|EVENT|SPOTIFY|BROWSE|MAP|WIDGET):[^\]]+\]"


def format_luna_response(response: str) -> str:
    """Keep casual Luna replies split into small chat chunks. Commands are always preserved."""
    text = response.strip()
    text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL).strip()
    text = re.sub(r'\.{3,}', '', text).strip()

    commands = re.findall(_CMD_RE, text)
    visible = re.sub(r"\s*" + _CMD_RE, "", text).strip()

    def _reattach(formatted_visible: str) -> str:
        if commands:
            return f"{formatted_visible}\n{' '.join(commands)}"
        return formatted_visible

    if not visible or "\n\n" in visible:
        parts = [p.strip() for p in re.split(r"\n{2,}", visible) if p.strip()]
        truncated = "\n\n".join(parts[:2]) if len(parts) > 2 else visible
        return _reattach(truncated)
    if "```" in visible or re.search(r"^\s*[-*]\s+", visible, re.MULTILINE):
        return _reattach(visible)

    sentences = re.split(r"(?<=[.!?])\s+", visible)
    sentences = [s.strip() for s in sentences if s.strip()]
    if len(sentences) == 2 and len(sentences[0].split()) <= 4:
        return _reattach("\n\n".join(sentences))
    if len(sentences) >= 3 and len(sentences[0].split()) <= 4:
        return _reattach(f"{sentences[0]}\n\n{' '.join(sentences[1:])}")
    if len(visible.split()) <= 22:
        return _reattach(visible)

    chunks: list[str] = []
    current: list[str] = []
    current_words = 0
    for sentence in sentences:
        words = len(sentence.split())
        if current and current_words + words > 12:
            chunks.append(" ".join(current).strip())
            current = [sentence]
            current_words = words
        else:
            current.append(sentence)
            current_words += words
    if current:
        chunks.append(" ".join(current).strip())

    if len(chunks) <= 1:
        return _reattach(visible)
    return _reattach("\n\n".join(chunks[:2]))


def _extract_references_section(text: str) -> str:
    match = re.search(r"References:\s*(.*)$", text, flags=re.IGNORECASE | re.DOTALL)
    if not match:
        source = re.search(r"Source:\s*(https?://\S+)", text)
        return f"References:\n[1] {source.group(1)}" if source else ""
    refs = []
    for line in match.group(1).splitlines():
        clean = line.strip()
        if re.match(r"^\[\d+\]\s+.+https?://", clean):
            refs.append(clean)
    return "References:\n" + "\n".join(refs[:6]) if refs else ""


def _strip_reference_noise(answer: str) -> str:
    """Remove malformed inline source lists before adding canonical references."""
    if not answer:
        return answer
    match = re.search(r"\bReferences:\s*", answer, flags=re.IGNORECASE)
    head = answer[:match.start()] if match else answer

    clean_lines = []
    for line in head.splitlines():
        clean = line.strip()
        if re.match(r"^\d+\.\s+\[.+?\]\(https?://", clean):
            continue
        if re.match(r"^\d+\.\s+\[.+?\]\s*$", clean):
            continue
        if re.match(r"^\[\d+\]\s+.+https?://", clean):
            continue
        if re.match(r"^\d+\.\s+.+https?://", clean):
            continue
        clean_lines.append(line)
    text = "\n".join(clean_lines)
    text = re.sub(r"\s*\(https?://[^)\s]+\)", "", text)
    text = re.sub(r"\s+[A-Z][^\n.]{8,140}\s+-\s+https?://\S+\s*$", "", text)
    return text.strip()


def ensure_references(answer: str, tool_result: str) -> str:
    answer_refs = _extract_references_section(answer)
    clean_answer = _strip_reference_noise(answer)
    if answer_refs:
        return clean_answer.rstrip() + "\n\n" + answer_refs.strip()
    refs = _extract_references_section(tool_result)
    if not refs:
        return clean_answer or answer
    return clean_answer.rstrip() + "\n\n" + refs.strip()

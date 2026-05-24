"""Research and dataset query extraction."""
import re


def extract_direct_research_query(message: str) -> str | None:
    """Return a query when the user is asking for current/web-sourced info."""
    text = (message or "").strip()
    if not text:
        return None

    explicit = re.search(
        r"\b(research|investigate|source-backed|sources?|references?|citations?|citings?|sitations?)\b",
        text, flags=re.IGNORECASE,
    )
    live = re.search(
        r"\b(latest|recent|current|today|this week|this month|right now|news|happening|update[sd]?|"
        r"announce[d]?|release[d]?|launch(?:ed)?|what(?:'s| is) new|just|broke|breaking)\b",
        text, flags=re.IGNORECASE,
    )
    compare = re.search(
        r"\b(compare|vs|versus|difference between|better|which is best)\b.{0,60}"
        r"\b(gpt|claude|gemini|llama|mistral|model|llm|ai|version)\b",
        text, flags=re.IGNORECASE,
    )

    if not (explicit or live or compare):
        return None

    query = re.sub(
        r"^\s*(please\s+)?(can you\s+|could you\s+|would you\s+)?"
        r"(research|investigate|look up|search for|find out about|find out|tell me about|"
        r"what(?:'s| is|are)|show me|give me)\b\s*(?:the\s+)?(?:latest\s+|current\s+|recent\s+)?",
        "", text, flags=re.IGNORECASE,
    )
    query = re.sub(
        r"\b(and\s+)?(include|show|add|give|provide|cite|citing|with)\s+(the\s+)?"
        r"(citations?|citings?|sitations?|references?|sources?)\b.*$",
        "", query, flags=re.IGNORECASE,
    )
    query = query.strip(" .?!:;-")
    if len(query) < 3:
        query = text
    return query


def extract_direct_dataset_query(message: str) -> str | None:
    """Return a query when the user is asking for a dataset or data file."""
    text = (message or "").strip()
    if not text:
        return None
    match = re.search(
        r"\b(find|get|download|fetch|locate|give me|search for)\b.{0,60}"
        r"\b(dataset|data\s*set|data\s*file|training data|csv|parquet|data\s*for)\b",
        text, flags=re.IGNORECASE,
    )
    if not match:
        return None
    query = re.sub(
        r"^\s*(please\s+)?(can you\s+|could you\s+)?"
        r"(find|get|download|fetch|locate|give me|search for)\s+(me\s+)?(?:a\s+|an\s+|the\s+)?",
        "", text, flags=re.IGNORECASE,
    ).strip(" .?!:;-")
    return query if len(query) >= 3 else text

"""Web search (DuckDuckGo) and page fetch for Luna tool calls."""
import re

import httpx

_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36"
_TIMEOUT = 12.0


def _strip_html(html: str) -> str:
    for tag in ("script", "style", "nav", "header", "footer", "aside"):
        html = re.sub(rf"<{tag}[^>]*>.*?</{tag}>", "", html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r"<[^>]+>", " ", html)
    for ent, ch in [("&nbsp;", " "), ("&amp;", "&"), ("&lt;", "<"), ("&gt;", ">"),
                    ("&quot;", '"'), ("&#39;", "'")]:
        html = html.replace(ent, ch)
    html = re.sub(r"&#\d+;", "", html)
    html = re.sub(r"\s{3,}", "\n\n", html)
    return html.strip()


async def web_search(query: str, max_results: int = 6) -> str:
    """Search DuckDuckGo HTML and return text snippets."""
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT, follow_redirects=True) as c:
            r = await c.get(
                "https://html.duckduckgo.com/html/",
                params={"q": query},
                headers={"User-Agent": _UA, "Accept-Language": "en-US,en;q=0.9"},
            )
            r.raise_for_status()

        titles   = re.findall(r'class="result__a"[^>]*>(.*?)</a>',       r.text, re.DOTALL)
        snippets = re.findall(r'class="result__snippet"[^>]*>(.*?)</a>', r.text, re.DOTALL)

        lines = []
        for t, s in zip(titles[:max_results], snippets[:max_results]):
            title   = re.sub(r"<[^>]+>", "", t).strip()
            snippet = re.sub(r"<[^>]+>", "", s).strip()
            if title:
                lines.append(f"• {title}: {snippet}")

        print(f"[web] search '{query}': {len(lines)} results")
        return "\n".join(lines) if lines else "No results found."
    except Exception as e:
        print(f"[web] search failed: {e}")
        return f"Search failed: {e}"


async def web_fetch(url: str, max_chars: int = 3000) -> str:
    """Fetch a URL and extract readable text content."""
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT, follow_redirects=True) as c:
            r = await c.get(url, headers={"User-Agent": _UA})
            r.raise_for_status()
        text = _strip_html(r.text)
        text = text[:max_chars] if len(text) > max_chars else text
        print(f"[web] fetch '{url}': {len(text)} chars")
        return text
    except Exception as e:
        print(f"[web] fetch failed: {e}")
        return f"Fetch failed: {e}"

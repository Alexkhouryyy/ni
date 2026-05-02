"""Web search and browsing tools.

Primary backend: Anthropic's built-in web_search tool (routes via Claude).
Fallback: ddgs (DuckDuckGo) for direct searches.
"""
import json
import requests
from bs4 import BeautifulSoup
import config

_search_client = None


def _get_client():
    global _search_client
    if _search_client is None:
        import anthropic
        _search_client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    return _search_client


def search(query: str, num_results: int = None) -> list[dict]:
    """Search the web. Returns list of {title, url, snippet}."""
    num_results = num_results or config.MAX_SEARCH_RESULTS

    # Try Anthropic web_search first (works in restricted envs)
    try:
        return _search_via_anthropic(query, num_results)
    except Exception:
        pass

    # Fallback: ddgs
    try:
        from ddgs import DDGS
        results = DDGS().text(query, max_results=num_results)
        return [
            {"title": r.get("title", ""), "url": r.get("href", ""), "snippet": r.get("body", "")}
            for r in (results or [])
        ]
    except Exception as e:
        return [{"title": "Search unavailable", "url": "", "snippet": str(e)}]


def _search_via_anthropic(query: str, num_results: int) -> list[dict]:
    """Use Anthropic's web_search built-in tool to run a search."""
    client = _get_client()
    resp = client.messages.create(
        model=config.PROACTIVE_MODEL,
        max_tokens=2048,
        tools=[{"type": "web_search_20250305", "name": "web_search", "max_uses": 1}],
        messages=[{"role": "user", "content": (
            f"Search for: {query}\n\n"
            f"Return the top {num_results} results as a JSON array with fields: title, url, snippet. "
            "Output ONLY the JSON array, nothing else."
        )}],
    )

    # Extract text from response
    text = ""
    for block in resp.content:
        if getattr(block, "type", "") == "text":
            text += block.text

    # Parse the JSON array from response
    start = text.find("[")
    end = text.rfind("]") + 1
    if start != -1 and end > start:
        return json.loads(text[start:end])

    # If no JSON, build results from the text itself
    return [{"title": f"Result for: {query}", "url": "", "snippet": text[:500]}]


def browse(url: str, max_chars: int = None) -> str:
    """Fetch a URL and return cleaned text content."""
    max_chars = max_chars or config.MAX_PAGE_CONTENT_CHARS
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
    }
    try:
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        for tag in soup(["script", "style", "nav", "footer", "header", "aside", "form"]):
            tag.decompose()

        text = soup.get_text(separator="\n", strip=True)
        lines = [l for l in text.splitlines() if l.strip()]
        content = "\n".join(lines)
        return content[:max_chars] + ("..." if len(content) > max_chars else "")
    except Exception as e:
        return f"Error fetching {url}: {e}"


def deep_research(topic: str) -> str:
    """Search + browse top results and compile a research summary."""
    results = search(topic, num_results=4)
    compiled = [f"Research on: {topic}\n"]

    for i, r in enumerate(results, 1):
        compiled.append(f"\n--- Source {i}: {r['title']} ---")
        compiled.append(f"URL: {r['url']}")
        compiled.append(f"Snippet: {r['snippet']}")
        if r.get("url"):
            content = browse(r["url"], max_chars=2000)
            compiled.append(f"Content:\n{content}")

    return "\n".join(compiled)

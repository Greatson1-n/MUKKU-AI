import re
import logging
from typing import List, Dict, Any, Optional
import httpx
from duckduckgo_search import DDGS

logger = logging.getLogger(__name__)

def clean_html(html_text: str) -> str:
    """Strip HTML tags and condense whitespace."""
    text = re.sub(r'<script.*?</script>', '', html_text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<style.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def search_web(query: str, max_results: int = 4) -> List[Dict[str, str]]:
    """
    Searches DuckDuckGo and returns a list of result items:
    [{'title': ..., 'snippet': ..., 'url': ...}]
    """
    results = []
    try:
        ddgs = DDGS()
        raw_results = list(ddgs.text(query, max_results=max_results))
        for item in raw_results:
            results.append({
                "title": item.get("title", ""),
                "snippet": item.get("body", ""),
                "url": item.get("href", "")
            })
    except Exception as e:
        logger.warning(f"DuckDuckGo search error: {e}")
        # Graceful fallback: return empty or note error
    return results

async def fetch_url(url: str, max_length: int = 3000) -> Dict[str, Any]:
    """Fetches the text content of a given webpage URL."""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True, headers=headers) as client:
            res = await client.get(url)
            if res.status_code == 200:
                text = clean_html(res.text)
                if len(text) > max_length:
                    text = text[:max_length] + "..."
                return {"url": url, "content": text, "status": "success"}
            return {"url": url, "content": "", "status": f"HTTP {res.status_code}"}
    except Exception as e:
        return {"url": url, "content": "", "status": f"Error: {str(e)}"}

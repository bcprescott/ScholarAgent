import re
import random
import requests
import fitz  # PyMuPDF
import asyncio
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError, BrowserContext
from playwright_stealth import Stealth
from src.state import ScientificDiscoveryState, Paper
from typing import Dict, Any, List
from tenacity import retry, stop_after_attempt, wait_exponential

MAX_CONCURRENT_FETCH = 4

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
]

# Words too common to be useful for relevance matching
_STOP_WORDS = frozenset({
    "a", "an", "the", "in", "on", "of", "for", "and", "or", "to", "is",
    "are", "was", "were", "be", "been", "by", "with", "from", "at", "as",
    "this", "that", "it", "its", "not", "but", "which", "what", "how",
    "can", "do", "does", "has", "have", "had", "will", "would", "may",
    "using", "based", "new", "study", "research", "paper", "results",
    "we", "our", "their", "these", "those", "between", "through", "about",
})


def _keyword_relevant(paper: Paper, query: str) -> bool:
    """Fast keyword-based pre-check — returns False if paper is clearly unrelated."""
    text = (paper.abstract or "") + " " + (paper.title or "")
    if not text.strip():
        return True  # No info, give benefit of the doubt

    query_words = set(re.findall(r'\w+', query.lower())) - _STOP_WORDS
    text_lower = text.lower()
    matches = sum(1 for w in query_words if w in text_lower)
    return matches >= 1


def get_random_header():
    return {"User-Agent": random.choice(USER_AGENTS)}

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def fetch_pdf_text(url: str) -> str:
    """Downloads PDF and extracts text using PyMuPDF with retries."""
    try:
        response = requests.get(url, headers=get_random_header(), timeout=15)
        response.raise_for_status()

        with fitz.open(stream=response.content, filetype="pdf") as doc:
            text = ""
            for page in doc:
                text += page.get_text()
        return text
    except Exception as e:
        print(f"Error fetching PDF {url}: {e}")
        raise e

async def fetch_web_text_with_context(context: BrowserContext, url: str) -> str:
    """Fetches web page content using an existing Playwright context."""
    text = None
    page = await context.new_page()
    await Stealth().apply_stealth_async(page)

    try:
        await page.goto(url, timeout=30000, wait_until="domcontentloaded")
        await asyncio.sleep(2)  # Wait for JS
        text = await page.evaluate("document.body.innerText")
    except Exception as e:
        print(f"Playwright error fetching {url}: {e}")
        raise e
    finally:
        await page.close()

    return text


async def fetcher_agent(state: ScientificDiscoveryState) -> Dict[str, Any]:
    papers = state.get("papers", [])
    query = state['query']
    logs = []

    # Pre-filter: skip papers that are clearly irrelevant based on keyword overlap
    to_fetch = []
    skipped = 0
    for paper in papers:
        if paper.full_text:
            to_fetch.append(paper)  # Already has content, no fetch needed
        elif _keyword_relevant(paper, query):
            to_fetch.append(paper)
        else:
            skipped += 1
            to_fetch.append(paper)  # Keep in list but mark as not worth fetching

    if skipped > 0:
        msg = f"Pre-filter: skipping full-text fetch for {skipped} clearly irrelevant papers."
        print(f"--- {msg} ---")
        logs.append(msg)

    fetch_count = sum(1 for p in to_fetch if not p.full_text and _keyword_relevant(p, query))
    print(f"--- Fetcher Agent: Fetching {fetch_count} papers ({MAX_CONCURRENT_FETCH} concurrent) ---")

    sem = asyncio.Semaphore(MAX_CONCURRENT_FETCH)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled"])
        context = await browser.new_context(
            user_agent=random.choice(USER_AGENTS),
            viewport={"width": 1280, "height": 720}
        )

        async def fetch_one(paper: Paper) -> Paper:
            if paper.full_text:
                return paper

            # Skip fetch for clearly irrelevant papers (they'll be analyzed on abstract only)
            if not _keyword_relevant(paper, query):
                return paper

            async with sem:
                print(f"Fetching: {paper.title} ({paper.url})")
                content = None
                try:
                    if paper.url and (paper.url.lower().endswith('.pdf') or '/pdf/' in paper.url.lower()):
                        content = await asyncio.to_thread(fetch_pdf_text, paper.url)
                    elif paper.url:
                        content = await fetch_web_text_with_context(context, paper.url)
                except Exception as e:
                    print(f"Failed to fetch {paper.url}: {e}")
                    logs.append(f"Failed to fetch {paper.title}: {str(e)}")

                if content:
                    paper.full_text = content
                    logs.append(f"Successfully fetched {paper.title}")
                    print(f"Successfully fetched {paper.title}")
                else:
                    logs.append(f"No content for {paper.title}")

                return paper

        # Fetch all papers concurrently (bounded by semaphore)
        updated_papers = await asyncio.gather(*[fetch_one(p) for p in to_fetch])

        await browser.close()

    return {"papers": list(updated_papers), "logs": logs}

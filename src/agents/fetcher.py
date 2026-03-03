import time
import random
import requests
import fitz  # PyMuPDF
import asyncio
from playwright.sync_api import sync_playwright
from src.state import ScientificDiscoveryState, Paper
from typing import Dict, Any, List
from tenacity import retry, stop_after_attempt, wait_exponential

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
]

def get_random_header():
    return {"User-Agent": random.choice(USER_AGENTS)}

@retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, min=1, max=5))
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


def fetch_web_text_simple(url: str) -> str:
    """Fast web fetch using plain HTTP requests (no browser needed)."""
    response = requests.get(url, headers=get_random_header(), timeout=15, allow_redirects=True)
    response.raise_for_status()
    content_type = response.headers.get('content-type', '')

    # If it's a PDF disguised as a web page
    if 'application/pdf' in content_type or url.lower().endswith('.pdf'):
        with fitz.open(stream=response.content, filetype="pdf") as doc:
            return "".join(page.get_text() for page in doc)

    # For HTML, do a basic text extraction
    from html.parser import HTMLParser

    class TextExtractor(HTMLParser):
        def __init__(self):
            super().__init__()
            self.text_parts = []
            self._skip = False
            self._skip_tags = {'script', 'style', 'nav', 'footer', 'header'}

        def handle_starttag(self, tag, attrs):
            if tag in self._skip_tags:
                self._skip = True

        def handle_endtag(self, tag):
            if tag in self._skip_tags:
                self._skip = False

        def handle_data(self, data):
            if not self._skip:
                stripped = data.strip()
                if stripped:
                    self.text_parts.append(stripped)

    extractor = TextExtractor()
    extractor.feed(response.text)
    return '\n'.join(extractor.text_parts)


def fetch_web_text_playwright(url: str) -> str:
    """Fallback: fetches web page content using Playwright (heavy, slow)."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled"])
        context = browser.new_context(
            user_agent=random.choice(USER_AGENTS),
            viewport={"width": 1280, "height": 720}
        )
        page = context.new_page()
        text = None
        try:
            page.goto(url, timeout=20000, wait_until="domcontentloaded")
            time.sleep(1)  # Reduced from 2s
            text = page.evaluate("document.body.innerText")
        except Exception as e:
            print(f"Playwright error fetching {url}: {e}")
            raise e
        finally:
            page.close()
            browser.close()
    return text


async def fetch_single_paper(paper: Paper, semaphore: asyncio.Semaphore) -> tuple:
    """Fetch a single paper's content with concurrency control."""
    async with semaphore:
        if paper.full_text:
            return paper, None, True

        print(f"Fetching: {paper.title} ({paper.url})")
        content = None

        try:
            is_pdf = paper.url and (paper.url.lower().endswith('.pdf') or '/pdf/' in paper.url.lower())

            if is_pdf:
                content = await asyncio.to_thread(fetch_pdf_text, paper.url)
            else:
                # Try fast HTTP first, fall back to Playwright only if needed
                try:
                    content = await asyncio.wait_for(
                        asyncio.to_thread(fetch_web_text_simple, paper.url),
                        timeout=15
                    )
                    # If we got very little text, the page probably needs JS rendering
                    if content and len(content.strip()) < 200:
                        print(f"  Simple fetch got minimal text, trying Playwright for {paper.title}")
                        content = await asyncio.wait_for(
                            asyncio.to_thread(fetch_web_text_playwright, paper.url),
                            timeout=25
                        )
                except Exception:
                    # Fall back to Playwright
                    print(f"  Simple fetch failed, trying Playwright for {paper.title}")
                    try:
                        content = await asyncio.wait_for(
                            asyncio.to_thread(fetch_web_text_playwright, paper.url),
                            timeout=25
                        )
                    except Exception as e2:
                        print(f"  Playwright also failed for {paper.title}: {e2}")

        except Exception as e:
            print(f"Failed to fetch {paper.url}: {e}")
            return paper, f"Failed to fetch {paper.title}: {str(e)}", False

        if content:
            paper.full_text = content
            print(f"Successfully fetched {paper.title}")
            return paper, f"Successfully fetched {paper.title}", True
        else:
            return paper, f"Failed to fetch content for {paper.title} (empty result)", False


async def fetcher_agent(state: ScientificDiscoveryState) -> Dict[str, Any]:
    papers = state.get("papers", [])
    logs = []

    print(f"--- Fetcher Agent: Processing {len(papers)} papers (parallel) ---")

    # Fetch up to 4 papers concurrently
    semaphore = asyncio.Semaphore(4)
    tasks = [fetch_single_paper(paper, semaphore) for paper in papers]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    updated_papers = []
    for result in results:
        if isinstance(result, Exception):
            print(f"Fetch task failed: {result}")
            logs.append(f"Fetch error: {str(result)}")
            continue
        paper, log_msg, success = result
        updated_papers.append(paper)
        if log_msg:
            logs.append(log_msg)

    return {"papers": updated_papers, "logs": logs}

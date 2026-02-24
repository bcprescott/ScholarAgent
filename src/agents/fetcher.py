import time
import random
import requests
import fitz  # PyMuPDF
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError, BrowserContext
from playwright_stealth import Stealth
from src.state import ScientificDiscoveryState, Paper
from typing import Dict, Any, List
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
]

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

def fetch_web_text_with_context(context: BrowserContext, url: str) -> str:
    """Fetches web page content using an existing Playwright context."""
    text = None
    page = context.new_page()
    Stealth().apply_stealth_sync(page)  # Apply stealth

    try:
        # We can implement retry logic manually here or use tenacity on a wrapper
        # Since we want to reuse context, let's just do a simple try/except or wrap this logic
        # But tenacity decorator works best on functions.
        # Let's use a nested function or manual loop for backoff inside here if needed?
        # Or better: make this function retryable.

        page.goto(url, timeout=30000, wait_until="domcontentloaded")
        time.sleep(2) # Wait for JS
        text = page.evaluate("document.body.innerText")

    except Exception as e:
        print(f"Playwright error fetching {url}: {e}")
        raise e
    finally:
        page.close()

    return text

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def fetch_web_text_retry_wrapper(context: BrowserContext, url: str) -> str:
    return fetch_web_text_with_context(context, url)

def fetcher_agent(state: ScientificDiscoveryState) -> Dict[str, Any]:
    papers = state.get("papers", [])
    updated_papers = []
    logs = []

    print(f"--- Fetcher Agent: Processing {len(papers)} papers ---")

    # Launch browser once
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled"])
        context = browser.new_context(
            user_agent=random.choice(USER_AGENTS),
            viewport={"width": 1280, "height": 720}
        )

        for i, paper in enumerate(papers):
            # Basic rate limiting
            if i > 0:
                time.sleep(random.uniform(1, 3))

            if paper.full_text:
                updated_papers.append(paper)
                continue

            print(f"Fetching: {paper.title} ({paper.url})")
            content = None

            try:
                # Determine strategy
                # Arxiv URLs often don't end in .pdf but contain /pdf/
                if paper.url and (paper.url.lower().endswith('.pdf') or '/pdf/' in paper.url.lower()):
                    content = fetch_pdf_text(paper.url)
                elif paper.url:
                    content = fetch_web_text_retry_wrapper(context, paper.url)
            except Exception as e:
                print(f"Failed to fetch {paper.url} after retries: {e}")
                logs.append(f"Failed to fetch {paper.title}: {str(e)}")

            if content:
                paper.full_text = content
                logs.append(f"Successfully fetched {paper.title}")
                print(f"Successfully fetched {paper.title}")
            else:
                if not content: # Log only if not already logged via exception
                     logs.append(f"Failed to fetch content for {paper.title} (empty result)")

            updated_papers.append(paper)

        browser.close()

    return {"papers": updated_papers, "logs": logs}

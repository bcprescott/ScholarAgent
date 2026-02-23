# Scientific Discovery Engine

A multi-agent system built with LangGraph that mimics the 'Manus' architecture to retrieve, validate, and synthesize scientific papers.

## Features

*   **Supervisor Agent**: Decomposes natural language queries into optimized keywords for different repositories (ArXiv, Semantic Scholar, Web).
*   **Scout Agents**: Parallel execution of searches across ArXiv, Semantic Scholar, and general web (via Tavily).
*   **Fetcher Agent**: Robustly fetches full text from PDFs and web pages.
    *   Uses `pymupdf` for PDF text extraction.
    *   Uses `playwright` with `playwright-stealth` for web scraping to avoid bot detection.
    *   Implements exponential backoff and browser context reuse.
*   **Analyst Agent**: Analyzes papers for relevance, key findings, methodology, and limitations using LLM (Azure OpenAI).
*   **Writer Agent**: Generates a comprehensive Markdown report with citations.

## Prerequisites

*   Python 3.9+
*   Playwright Browsers (`playwright install chromium`)
*   Azure OpenAI API Key
*   Tavily API Key (for web search)

## Installation

1.  Clone the repository.
2.  Install dependencies:
    ```bash
    pip install -r requirements.txt
    playwright install chromium
    ```

## Configuration

Set the following environment variables:

```bash
export AZURE_OPENAI_API_KEY="your_key"
export AZURE_OPENAI_ENDPOINT="your_endpoint"
export AZURE_OPENAI_DEPLOYMENT_NAME="gpt-4" # or similar
export AZURE_OPENAI_API_VERSION="2023-05-15"
export TAVILY_API_KEY="your_tavily_key"
```

## Usage

Run the engine with a query:

```bash
python src/main.py "LLM applications in oncology"
```

## Output

Results are saved in the `outputs/` directory:
*   `report.md`: The final scientific report.
*   `logs.txt`: Execution logs.

## Testing

Run the test suite (uses mocks, so no API keys required):

```bash
PYTHONPATH=. python tests/test_flow.py
```

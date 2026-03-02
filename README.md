# Scientific Discovery Engine

A multi-agent system built with LangGraph that mimics the 'Manus' architecture to retrieve, validate, and synthesize scientific papers.

## Features

*   **Supervisor Agent**: Decomposes natural language queries into optimized keywords for different repositories (ArXiv, PubMed, Web).
*   **Scout Agents**: Parallel execution of searches across ArXiv, Semantic Scholar, PubMed, and general web (via Tavily).
*   **Fetcher Agent**: Robustly fetches full text from PDFs and web pages.
    *   Uses `pymupdf` for PDF text extraction.
    *   Uses `playwright` with `playwright-stealth` for web scraping to avoid bot detection.
    *   Implements exponential backoff and browser context reuse.
*   **Analyst Agent**: Analyzes papers for relevance, key findings, methodology, and limitations using LLM (Azure OpenAI or local LM Studio).
*   **Writer Agent**: Generates a comprehensive Markdown report with citations.

## Prerequisites

*   Python 3.9+
*   Playwright Browsers (`playwright install chromium`)
*   LLM Provider: Azure OpenAI API Key OR a running LM Studio server
*   Tavily API Key (for web search)

## Installation

1.  Clone the repository.
2.  Install dependencies:
    ```bash
    pip install -r requirements.txt
    python -m playwright install chromium
    ```

## Configuration

Set the following environment variables (or create a `.env` file):

```bash
# LLM Configuration
USE_LMSTUDIO=false
LMSTUDIO_MODEL_NAME="local-model"
MOCK_LLM=false

# Azure OpenAI (Required if USE_LMSTUDIO and MOCK_LLM are false)
AZURE_OPENAI_API_KEY="your_key"
AZURE_OPENAI_ENDPOINT="your_endpoint"
AZURE_OPENAI_DEPLOYMENT_NAME="gpt-4" # or similar
AZURE_OPENAI_API_VERSION="2024-05-01-preview"

# Web Search
TAVILY_API_KEY="your_tavily_key"
```

## Usage

Run the engine with a query:

```bash
python src/main.py "LLM applications in oncology"
```

### Web Interface (Recommended)

Launch the animated web UI powered by FastAPI:

```bash
uvicorn src.web_app:app --reload
```
Then open [http://localhost:8000](http://localhost:8000). The interface shows a real-time animated pipeline as each agent executes, with expandable detail cards and a rendered markdown report at the end.

### Chainlit Interface (Legacy)

You can also run the system with the Chainlit chat interface:

```bash
chainlit run src/app.py -w
```

## Output

Results are saved in the `outputs/` directory:
*   `report.md`: The final scientific report.
*   `logs.txt`: Execution logs.

## Testing

Run the test suite (uses mock LLM functionality, so no API keys are strictly required if Mocking is enabled):

```bash
PYTHONPATH=. python tests/test_flow.py
```

# ScholarAgent

An AI-powered multi-agent research discovery engine built with [LangGraph](https://github.com/langchain-ai/langgraph). ScholarAgent searches across 6 academic databases in parallel, fetches and analyzes papers, and synthesizes a comprehensive literature review — all in real-time through a web UI with live progress streaming.

## How It Works

```
                          ┌─────────────────┐
                          │   User Query    │
                          └────────┬────────┘
                                   │
                          ┌────────▼────────┐
                          │   Supervisor    │  Generates optimized search
                          │     Agent       │  queries for each source
                          └────────┬────────┘
                                   │
              ┌──────────┬─────────┼──────────┬──────────┬──────────┐
              ▼          ▼         ▼          ▼          ▼          ▼
          ┌───────┐ ┌────────┐ ┌───────┐ ┌────────┐ ┌────────┐ ┌───────┐
          │ ArXiv │ │ PubMed │ │ Sem.  │ │  Web   │ │OpenAlex│ │bioRxiv│
          │ Scout │ │ Scout  │ │Scholar│ │ Scout  │ │ Scout  │ │ Scout │
          └───┬───┘ └───┬────┘ └───┬───┘ └───┬────┘ └───┬────┘ └───┬───┘
              └──────────┴─────────┼──────────┴──────────┴──────────┘
                                   │  Papers merged & deduplicated
                          ┌────────▼────────┐
                          │  Fetcher Agent  │  Fetches full text (PDF
                          │   (parallel)    │  or web) for each paper
                          └────────┬────────┘
                                   │
                          ┌────────▼────────┐
                          │  Analyst Agent  │  Parallel LLM analysis:
                          │   (parallel)    │  relevance, evidence grading,
                          │                 │  study type, key findings
                          └────────┬────────┘
                                   │
                          ┌────────▼────────┐
                          │  Writer Agent   │  Synthesizes thematic
                          │                 │  literature review report
                          └────────┬────────┘
                                   │
                          ┌────────▼────────┐
                          │  Markdown Report│
                          └─────────────────┘
```

### Pipeline Stages

1. **Supervisor Agent** — Takes the user's research question and generates tailored search queries for each of the 6 academic sources, using the current year to ensure recent results.

2. **Scout Agents** (parallel) — Six scouts search simultaneously across ArXiv, PubMed, Semantic Scholar, Web (Tavily), OpenAlex, and bioRxiv. Results are merged with deduplication by URL, DOI, and fuzzy title matching.

3. **Fetcher Agent** (parallel) — Retrieves full-text content for each paper. Uses plain HTTP first for speed, falling back to Playwright for JavaScript-rendered pages. PDFs are extracted via PyMuPDF.

4. **Analyst Agent** (parallel) — Analyzes each paper using LLM calls with concurrency control (semaphore). Extracts relevance score, key findings, methodology, limitations, study type, evidence level, and sample size. Uses a separate prompt for abstract-only papers.

5. **Writer Agent** — Synthesizes all analyzed papers into a structured literature review with thematic grouping, evidence consensus, research gaps, practical implications, and numbered citations.

## Features

- **6 Academic Sources** — ArXiv, PubMed, Semantic Scholar, Tavily (web), OpenAlex (250M+ works), and bioRxiv (preprints)
- **Parallel Execution** — Scouts, fetcher, and analyst all run concurrently for speed
- **Structured Evidence Grading** — Each paper gets a study type classification and evidence level rating
- **Smart Deduplication** — Papers are deduplicated by URL, DOI, and fuzzy title similarity
- **Real-Time Web UI** — Live SSE streaming shows progress through each pipeline stage
- **Configurable Pipeline** — Adjust results per source, relevance threshold, and enabled sources
- **JSON Mode LLM Calls** — Structured output format eliminates JSON parsing failures

## Prerequisites

- Python 3.9+
- Playwright Browsers: `playwright install chromium`
- **LLM Provider**: Azure OpenAI API key **or** a running [LM Studio](https://lmstudio.ai/) server
- **Tavily API Key** for web search ([tavily.com](https://tavily.com))

## Installation

```bash
# Clone and install dependencies
pip install -r requirements.txt
python -m playwright install chromium
```

## Configuration

Create a `.env` file in the project root:

```bash
# --- LLM Configuration ---
# Option 1: Azure OpenAI
AZURE_OPENAI_API_KEY="your_key"
AZURE_OPENAI_ENDPOINT="your_endpoint"
AZURE_OPENAI_DEPLOYMENT_NAME="gpt-4"
AZURE_OPENAI_API_VERSION="2025-01-01-preview"

# Option 2: LM Studio (local)
# USE_LMSTUDIO=true
# LMSTUDIO_MODEL_NAME="local-model"

# Option 3: Mock LLM (for testing)
# MOCK_LLM=true

# --- Web Search ---
TAVILY_API_KEY="your_tavily_key"
```

### Pipeline Settings

Defaults can be adjusted in `src/state.py` via `ResearchConfig`:

| Setting | Default | Description |
|---------|---------|-------------|
| `max_results_per_source` | 10 | Papers fetched per scout |
| `relevance_threshold` | 50.0 | Minimum score to include in report |
| `enabled_sources` | all 6 | Which scouts to run |
| `max_paper_chars` | 20000 | Max text sent to analyst LLM |

These can also be passed as URL parameters: `/api/research?query=...&max_results=5&threshold=60`

## Usage

### Web Interface (Recommended)

```bash
python -m uvicorn src.web_app:app --reload
```

Open [http://localhost:8000](http://localhost:8000). The interface shows a real-time animated pipeline with expandable detail cards for each agent stage and a rendered markdown report.

### Command Line

```bash
python src/main.py "your research question"
```

Results are saved in `outputs/report.md` and `outputs/logs.txt`.

## Testing

```bash
python -m unittest discover -s tests -v
```

Tests use a mock LLM — no API keys required. The test suite covers the full pipeline flow, DOI/title deduplication, and config defaults.

## Project Structure

```
ScholarAgent/
├── public/              # Web UI (HTML, CSS, JS)
├── src/
│   ├── agents/
│   │   ├── supervisor.py   # Query generation for 6 sources
│   │   ├── scouts.py       # ArXiv, PubMed, Semantic Scholar, Web, OpenAlex, bioRxiv
│   │   ├── fetcher.py      # Parallel full-text retrieval (HTTP + Playwright)
│   │   └── analyst.py      # Parallel LLM analysis + report writer
│   ├── state.py            # Paper model, ResearchConfig, deduplication
│   ├── graph.py            # LangGraph pipeline definition
│   ├── llm.py              # LLM provider abstraction (Azure/LM Studio/Mock)
│   ├── web_app.py          # FastAPI + SSE streaming
│   └── main.py             # CLI entry point
├── tests/
│   └── test_flow.py        # Full pipeline + unit tests
├── outputs/                # CLI output directory
├── requirements.txt
└── .env                    # API keys (not committed)
```

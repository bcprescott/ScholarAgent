# ScholarAgent — Product Requirements Document (PRD)

**Version:** 1.0
**Date:** March 2026

---

## 1. Overview

### 1.1 Product Vision

ScholarAgent is an AI-powered research discovery engine that automates the process of searching, retrieving, analyzing, and synthesizing scientific literature. It replaces the manual workflow of a researcher querying multiple databases, reading abstracts, fetching papers, and writing a literature review — compressing hours of work into minutes.

### 1.2 Problem Statement

Researchers and professionals conducting literature reviews face several challenges:

- **Fragmented sources** — Academic papers are spread across ArXiv, PubMed, Semantic Scholar, bioRxiv, and many other repositories, each with different interfaces and query syntaxes
- **Time-intensive retrieval** — Manually searching, downloading, and reading papers across multiple sources is slow
- **Shallow coverage** — Due to time constraints, researchers often search only 1-2 databases, missing relevant work from other disciplines
- **Inconsistent analysis** — Evaluating paper quality, extracting key findings, and comparing across studies requires domain expertise and significant effort
- **Synthesis gap** — Combining findings from dozens of papers into a coherent narrative is the hardest and most time-consuming step

### 1.3 Target Users

| User Type | Use Case |
|-----------|----------|
| Academic researchers | Rapid literature reviews for grant proposals, papers, and thesis work |
| Clinical professionals | Evidence-based reviews of treatments, drugs, and clinical methodologies |
| Research analysts | Market and technology landscape scanning across scientific disciplines |
| Students | Thesis research, coursework literature reviews |
| R&D teams | Staying current on advances in specific technical domains |

---

## 2. Product Requirements

### 2.1 Core Functional Requirements

#### FR-1: Natural Language Query Input
- Users submit a research question in plain English
- No knowledge of API-specific syntax or Boolean operators required
- The system translates the query into optimized search terms for each data source

#### FR-2: Multi-Source Parallel Search
- Search across **at minimum 4** academic sources simultaneously
- Sources must include a mix of: preprint servers, peer-reviewed databases, open-access aggregators, and general web
- Searches execute in parallel to minimize latency
- Each source receives a query tailored to its domain and strengths

**Implemented sources:**

| Source | Type | Coverage | Cost |
|--------|------|----------|------|
| ArXiv | Preprint server | Physics, CS, math, quantitative biology | Free |
| PubMed | Peer-reviewed | Biomedical, clinical, life sciences | Free |
| Semantic Scholar | Aggregator | 200M+ papers across all fields | Free |
| Tavily (Web) | Web search | Grey literature, news, reports | API key required |
| OpenAlex | Open aggregator | 250M+ works, all disciplines | Free |
| bioRxiv | Preprint server | Biology, medical preprints | Free |

#### FR-3: Full-Text Retrieval
- Automatically fetch full-text content for discovered papers
- Support PDF download and text extraction
- Support HTML/web page content retrieval
- Handle paywalls gracefully (fall back to abstract if full text unavailable)
- Implement retry logic and rate limiting

#### FR-4: AI-Powered Paper Analysis
- Analyze each paper against the user's original research question
- Extract structured data per paper:
  - **Relevance score** (0–100)
  - **Key findings** summary
  - **Methodology** description
  - **Limitations** assessment
  - **Study type** classification (meta-analysis, RCT, review, case study, etc.)
  - **Evidence level** rating (Level I through Level V)
  - **Sample size** (when applicable)
  - **Confidence notes** explaining evidence strength/weakness

#### FR-5: Synthesized Report Generation
- Produce a structured literature review report in Markdown
- Report must be **thematically organized**, not paper-by-paper
- Required report sections:
  1. Executive Summary
  2. Background & Context
  3. Key Findings (thematic)
  4. Strength of Evidence
  5. Contradictions & Debates
  6. Research Gaps
  7. Practical Implications
  8. Methodology Notes
  9. References with DOIs/URLs

#### FR-6: Real-Time Progress Visibility
- Users see live progress as each pipeline stage executes
- Per-stage updates: Supervisor → Scouts → Fetcher → Analyst → Writer
- Expandable detail cards showing results from each stage

#### FR-7: Deduplication
- Papers appearing in multiple sources must be deduplicated
- Deduplication by URL, DOI, and fuzzy title similarity
- When duplicates are found, retain the version with the most metadata

#### FR-8: Configurable Pipeline
- Users can adjust without changing code:
  - Number of results per source
  - Relevance score threshold for report inclusion
  - Which sources are enabled/disabled

### 2.2 Non-Functional Requirements

#### NFR-1: Performance
- Scouts must execute in parallel (not serial)
- Paper analysis must be parallelized with concurrency control
- Full-text fetching should use fast HTTP before falling back to browser rendering
- Pipeline timeout of 300 seconds to prevent indefinite hangs

#### NFR-2: Reliability
- LLM calls must use structured JSON output mode to prevent parsing failures
- Each scout, fetch, and analysis operation must be independently error-handled (one failure must not crash the pipeline)
- Safe accessors for all XML/API parsing (no uncaught null dereferences)

#### NFR-3: LLM Flexibility
- Support Azure OpenAI as primary LLM provider
- Support LM Studio for local/offline usage
- Support mock LLM mode for testing without API costs
- LLM provider must be configurable via environment variables

#### NFR-4: Testability
- Full pipeline must be testable with mocked external services
- Unit tests for deduplication logic
- Unit tests for configuration defaults

---

## 3. Architecture

### 3.1 Technology Stack

| Component | Technology |
|-----------|-----------|
| Pipeline orchestration | LangGraph (StateGraph) |
| LLM integration | OpenAI Python SDK (Azure + standard) |
| Web framework | FastAPI |
| Real-time streaming | Server-Sent Events (SSE) |
| Full-text extraction | PyMuPDF (PDF), Playwright (JS-rendered pages) |
| Frontend | Vanilla HTML/CSS/JS with Marked.js for Markdown |
| Testing | Python unittest with mocks |

### 3.2 Pipeline Architecture

The system follows a **linear multi-agent pipeline** orchestrated by LangGraph:

```
User Query → Supervisor → Scouts (parallel) → Fetcher (parallel)
           → Analyst (parallel) → Writer → Report
```

**State management:** A shared `ScientificDiscoveryState` TypedDict flows through the pipeline, with custom reducers for paper merging (deduplication) and log accumulation.

### 3.3 Data Model

The core data model is the `Paper` entity:

```
Paper:
  - title, url, abstract, full_text
  - source, doi, authors, publication_date
  - relevance_score, key_findings, methodology, limitations
  - study_type, evidence_level, sample_size, confidence_notes
```

---

## 4. User Interface

### 4.1 Web Interface

- **Search bar** with example query hints
- **Animated pipeline visualization** showing 5 stages (Supervisor → Scouts → Fetcher → Analyst → Writer) with active/completed states
- **Expandable detail cards** for each stage:
  - Supervisor: shows generated queries per source
  - Scouts: source distribution bars + scrollable paper list
  - Fetcher: progress bar of successfully fetched papers
  - Analyst: scrollable list of all papers with relevance scores, study type, evidence level, and findings preview
  - Writer: completion confirmation
- **Rendered Markdown report** with full formatting (headings, tables, links, code blocks, citations)
- **New Search** button to reset and start over

### 4.2 Command Line Interface

- Single command with query argument
- Output saved to `outputs/report.md` and `outputs/logs.txt`

---

## 5. Future Considerations

The following capabilities were identified as valuable extensions but are not in the current scope:

- **Citation graph traversal** — Follow references and citations of top papers to find related work
- **Iterative query refinement** — After initial results, generate follow-up queries to fill gaps
- **Interactive follow-up** — Allow users to ask questions about specific papers or request deeper dives
- **Export formats** — BibTeX, PDF, CSV, and JSON export of results
- **Query history** — Store and revisit past research sessions
- **Caching layer** — Cache search results, fetched papers, and analysis to avoid redundant API calls
- **Additional sources** — Google Scholar (SerpAPI), IEEE Xplore, Springer, CORE, CrossRef, Europe PMC

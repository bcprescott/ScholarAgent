# ScholarAgent — Review & Improvement Recommendations

## Executive Summary

ScholarAgent is a well-architected multi-agent scientific discovery engine. The LangGraph pipeline design is clean, the parallel scout pattern is effective, and the web UI with SSE streaming provides a satisfying real-time experience. The recommendations below are organized from highest to lowest impact, focusing on three themes: **broader and smarter search**, **deeper analysis and insight**, and **production readiness**.

---

## 1. Search Breadth & Depth

### 1.1 Add More Academic Sources

The current four scouts (ArXiv, PubMed, Semantic Scholar, Web) cover physics/CS and biomedical literature well, but leave significant gaps:

| Proposed Source | What It Adds | API |
|---|---|---|
| **OpenAlex** | 250M+ works across all disciplines; fully open, no API key needed | `https://api.openalex.org` |
| **CORE** | 300M+ open-access papers; full-text links for many | `https://core.ac.uk/api-v3` (free key) |
| **CrossRef** | DOI metadata, citation counts, funding info for 150M+ records | `https://api.crossref.org` |
| **Europe PMC** | Broader than PubMed — includes preprints, patents, WHO guidelines | `https://www.ebi.ac.uk/europepmc/webservices/rest` |
| **Google Scholar (via SerpAPI)** | The widest academic coverage; captures grey literature | Requires SerpAPI key |
| **bioRxiv/medRxiv** | Preprints that haven't hit PubMed yet — critical for cutting-edge research | `https://api.biorxiv.org` |
| **IEEE Xplore / Springer** | Engineering and applied sciences (paid APIs, but valuable) | Key required |

**Recommendation:** Start with **OpenAlex** and **bioRxiv** — both are free, well-documented, and fill the biggest gaps. OpenAlex alone would dramatically widen coverage across social sciences, humanities, engineering, and more.

### 1.2 Increase Results Per Source

Each scout currently returns only **5 results**. This is conservative — a 10–15 result limit per source would meaningfully improve recall without proportionally increasing LLM costs (since the analyst can filter aggressively). Consider making this configurable per query.

### 1.3 Smarter Query Decomposition

The supervisor currently generates 3 queries (one per repo). This could be much more sophisticated:

- **Generate more queries per source** — e.g., a broad query AND a narrow/specific query for each scout, doubling coverage.
- **Generate queries in phases** — after the first round of results, have the supervisor review what was found and generate *follow-up* queries to fill gaps (an "iterative refinement" loop).
- **Include date/field constraints** — the supervisor prompt says "cover the current year" but doesn't actually enforce date filters. ArXiv, PubMed, and Semantic Scholar all support date range parameters. Wire those through.
- **Add a `semantic_scholar` key** — the supervisor generates `arxiv`, `pubmed`, and `web`, but Semantic Scholar silently reuses the raw query since there's no key for it in `scout_queries`. Give it its own optimized query.

### 1.4 Citation Graph Traversal

One of the most powerful research strategies is "snowball searching" — once you find a highly relevant paper, follow its references and citations:

- **Semantic Scholar's API** already supports fetching `references` and `citations` for a paper.
- After the analyst scores papers, take the top 3–5 and fetch their references/citers.
- Run those through the analyst too. This often surfaces foundational or recent breakthrough papers that keyword search misses.

---

## 2. Deeper Analysis & More Insightful Reports

### 2.1 Multi-Pass Analysis

Currently each paper gets a single LLM call that returns relevance, findings, methodology, and limitations. Consider a richer pipeline:

1. **Classification pass** — categorize papers by type (RCT, meta-analysis, review, case study, computational, etc.) and by sub-topic.
2. **Deep extraction pass** — for high-relevance papers, extract specific data: sample sizes, effect sizes, statistical significance, specific drug names, gene targets, etc.
3. **Cross-paper synthesis pass** — explicitly ask the LLM to compare/contrast findings across papers. Where do they agree? Where do they conflict? What's the emerging consensus?

### 2.2 Structured Evidence Grading

Add an evidence quality assessment to each paper:

```python
class Paper(BaseModel):
    # ... existing fields ...
    study_type: Optional[str] = None        # e.g., "meta-analysis", "RCT", "case study"
    evidence_level: Optional[str] = None     # e.g., "Level I", "Level II", etc.
    sample_size: Optional[int] = None
    confidence_notes: Optional[str] = None   # Why this evidence is strong or weak
```

This lets the writer agent weight findings appropriately — a meta-analysis of 50 RCTs should carry more weight than a single case report.

### 2.3 Richer Report Structure

The current report template (Executive Summary, Key Findings, Methodologies, Limitations, References) is solid but could be elevated:

- **Thematic grouping** — cluster papers by sub-topic and present findings thematically rather than paper-by-paper.
- **Evidence consensus map** — a section that explicitly calls out where the literature agrees vs. where there's active debate.
- **Research gaps** — identify what's *not* covered in the literature. What questions remain open?
- **Timeline/trend analysis** — if papers span multiple years, describe how the field has evolved.
- **Practical implications** — a "So what?" section translating findings into actionable takeaways.
- **Suggested next searches** — recommend follow-up queries the user might want to explore.

### 2.4 Improve the Writer Prompt

The current writer prompt is generic. A more specific prompt would produce dramatically better output:

```
Structure your report as follows:
1. Executive Summary (2-3 paragraphs answering the query directly)
2. Background & Context (why this question matters)
3. Key Findings (organized thematically, NOT paper-by-paper)
4. Strength of Evidence (which findings are well-supported vs. preliminary)
5. Contradictions & Debates (where studies disagree and why)
6. Research Gaps (what remains unknown)
7. Practical Implications (actionable takeaways)
8. Methodology Notes (common approaches in the literature)
9. References (formatted as numbered citations)

IMPORTANT: Do NOT just summarize each paper sequentially. Synthesize across
papers — compare, contrast, and draw connections. Write like a review article
author, not a bibliography compiler.
```

### 2.5 Abstract-Only Fallback Analysis

Currently, if full text can't be fetched, the analyst still works with the abstract, but the same prompt is used. Consider a separate, abstract-optimized prompt that acknowledges the limited information and adjusts expectations accordingly.

---

## 3. Architecture & Performance

### 3.1 Make Scouts Truly Async

The current `ThreadPoolExecutor` approach works but doesn't scale well. Since the fetcher is already async, convert scouts to async too:

```python
async def scouts_node(state):
    tasks = [
        asyncio.create_task(arxiv_scout(state)),
        asyncio.create_task(pubmed_scout(state)),
        asyncio.create_task(semantic_scholar_scout(state)),
        asyncio.create_task(web_scout(state)),
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    # merge results...
```

This is cleaner, avoids thread overhead, and integrates better with LangGraph's async runtime.

### 3.2 Parallelize the Analyst

The analyst currently processes papers **serially** — one LLM call per paper, sequentially. With 15-20 papers, this is the slowest stage of the pipeline. Use `asyncio.gather` or batch LLM calls to analyze papers concurrently (respecting rate limits with a semaphore):

```python
sem = asyncio.Semaphore(5)  # max 5 concurrent LLM calls

async def analyze_paper_async(paper, query, llm):
    async with sem:
        # ... LLM call ...

results = await asyncio.gather(*[analyze_paper_async(p, query, llm) for p in papers])
```

This could cut analyst stage time by 3-5x.

### 3.3 Add a Caching Layer

Re-running the same or similar queries currently starts from scratch every time:

- **Search result cache** — cache scout results by query hash (TTL: 24h). SQLite is fine for this.
- **Full-text cache** — cache fetched paper content by URL. This is the most expensive operation to repeat.
- **Analysis cache** — cache LLM analysis by (paper_url, query) pair. Same paper for the same query doesn't need re-analysis.

Even a simple `shelve` or SQLite cache would eliminate redundant API calls and fetches.

### 3.4 Configurable Pipeline

Let users control the pipeline without changing code:

```python
class ResearchConfig(BaseModel):
    max_results_per_source: int = 10
    relevance_threshold: float = 50.0
    enable_citation_traversal: bool = False
    enabled_sources: List[str] = ["arxiv", "pubmed", "semantic_scholar", "web"]
    fetch_full_text: bool = True
    max_paper_chars: int = 20000
```

Expose this in the web UI as an "Advanced Settings" panel.

---

## 4. Robustness & Error Handling

### 4.1 Structured LLM Output

The current regex-based JSON parsing (`re.search(r'\{.*\}', text, re.DOTALL)`) is fragile — it grabs the first `{` to the last `}`, which breaks if the LLM produces nested JSON or extra text. Options:

- **Use OpenAI's JSON mode** — set `response_format={"type": "json_object"}` in the API call. This guarantees valid JSON output.
- **Use Pydantic for validation** — parse the JSON into a Pydantic model, getting type checking and default values for free.
- **Fallback chain** — try JSON mode first, then regex extraction, then ask the LLM to fix its own output.

### 4.2 PubMed XML Parsing Safety

`article_element.find('.//PMID').text` at line 75 of `scouts.py` will throw `AttributeError` if `<PMID>` is missing. Wrap this in a safe accessor like the other fields.

### 4.3 Pipeline Timeout

There's no overall timeout for the pipeline. If one agent hangs (e.g., a DNS issue causes Playwright to stall), the whole pipeline blocks indefinitely. Add a top-level timeout:

```python
try:
    result = await asyncio.wait_for(graph.ainvoke(state), timeout=300)
except asyncio.TimeoutError:
    # Return partial results
```

### 4.4 Deduplication Improvements

The current dedup is URL-based, but the same paper can appear with different URLs across sources (e.g., DOI link vs. ArXiv PDF vs. Semantic Scholar page). Add DOI-based and title-similarity-based dedup:

```python
def merge_papers(existing, new):
    # Dedup by URL, DOI, and fuzzy title match
    existing_dois = {p.doi for p in existing if p.doi}
    existing_titles = {p.title.lower().strip() for p in existing}
    for p in new:
        if p.url in existing_urls:
            continue
        if p.doi and p.doi in existing_dois:
            continue
        if p.title.lower().strip() in existing_titles:
            continue
        # ... add paper
```

---

## 5. User Experience

### 5.1 Progress Granularity

The web UI shows stage-level progress (supervisor → scouts → fetcher → analyst → writer), but within each stage, the user has no visibility. Add per-paper progress events:

```python
# In the fetcher, emit an event per paper
yield {"event": "fetching_paper", "title": paper.title, "index": i, "total": len(papers)}
```

This makes the long fetcher and analyst stages feel much less like a black box.

### 5.2 Interactive Refinement

After the report is generated, let the user:
- **Ask follow-up questions** about specific papers or findings
- **Request deeper dives** — "Tell me more about the methodology of paper X"
- **Adjust and re-run** — "Search again but focus on clinical trials only"

This turns ScholarAgent from a one-shot tool into a research conversation partner.

### 5.3 Export Options

Add export beyond markdown:
- **BibTeX** — for citation managers (easy to generate from Paper fields)
- **PDF** — render the markdown report as a formatted PDF
- **JSON** — structured data dump of all papers and analyses for programmatic use
- **CSV** — spreadsheet of papers with scores, findings, etc.

### 5.4 Query History & Saved Sessions

Store previous queries and their results so users can:
- Return to past research
- Compare results across different queries
- Build on previous searches without re-running

---

## 6. Quick Wins (Low Effort, High Impact)

These are changes that could be implemented quickly:

| Change | File(s) | Impact |
|---|---|---|
| Add `semantic_scholar` key to supervisor prompt | `supervisor.py:22` | Semantic Scholar gets an optimized query instead of the raw user query |
| Increase `max_results` from 5 to 10 | `scouts.py:115,137,200,218` | ~2x more papers with minimal extra cost |
| Add `response_format={"type": "json_object"}` to LLM calls | `analyst.py:40`, `supervisor.py:26` | Eliminates JSON parsing failures |
| Safe-access PMID in PubMed parser | `scouts.py:75` | Prevents crashes on malformed PubMed XML |
| Add date range parameters to scout queries | `scouts.py` (all scouts) | Get actually recent papers, not just keyword-matched |
| Make relevance threshold configurable | `analyst.py:90` | Users can tune strictness |
| Add OpenAlex scout | New file + `graph.py` | Massive coverage expansion, zero API cost |

---

## Summary

ScholarAgent has a strong foundation. The highest-leverage improvements are:

1. **Add OpenAlex + bioRxiv scouts** — dramatically broadens coverage across all disciplines
2. **Citation graph traversal** — finds papers that keyword search can never reach
3. **Parallelize the analyst** — cuts the longest pipeline stage by 3-5x
4. **Improve report synthesis** — thematic grouping and cross-paper comparison instead of paper-by-paper summarization
5. **Structured LLM output** — eliminates the #1 source of silent failures
6. **Iterative query refinement** — a second search round based on what was found in the first

These six changes would transform ScholarAgent from a good literature search tool into an exceptional AI research assistant.

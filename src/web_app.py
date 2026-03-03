import asyncio
import json
import traceback
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from src.graph import build_graph
from src.state import ScientificDiscoveryState, ResearchConfig

app = FastAPI(title="ScholarAgent")

PUBLIC_DIR = Path(__file__).resolve().parent.parent / "public"
app.mount("/static", StaticFiles(directory=str(PUBLIC_DIR)), name="static")

# Pipeline timeout in seconds (Section 4.3)
PIPELINE_TIMEOUT = 300


@app.get("/", response_class=HTMLResponse)
async def index():
    return (PUBLIC_DIR / "index.html").read_text()


@app.get("/api/research")
async def research(query: str, max_results: int = None, threshold: float = None):
    """SSE endpoint that streams agent progress events.

    Query params:
        query: The research question
        max_results: Max results per source (default from ResearchConfig)
        threshold: Relevance score threshold (default from ResearchConfig)
    """

    # Build config — only override defaults if explicitly provided
    config_kwargs = {}
    if max_results is not None:
        config_kwargs['max_results_per_source'] = max_results
    if threshold is not None:
        config_kwargs['relevance_threshold'] = threshold
    config = ResearchConfig(**config_kwargs)

    async def event_stream():
        initial_state = ScientificDiscoveryState(
            query=query,
            scout_queries={},
            papers=[],
            report="",
            logs=[],
            config=config,
        )
        graph = build_graph()

        try:
            stream = graph.astream(initial_state, stream_mode="updates")
            async for event in _consume_stream_with_timeout(stream, PIPELINE_TIMEOUT):
                yield event

            yield f"data: {json.dumps({'event': 'done'})}\n\n"

        except asyncio.TimeoutError:
            yield f"data: {json.dumps({'event': 'error', 'message': f'Pipeline timed out after {PIPELINE_TIMEOUT}s. Partial results may be available.'})}\n\n"
        except Exception as exc:
            traceback.print_exc()
            yield f"data: {json.dumps({'event': 'error', 'message': str(exc)})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


async def _consume_stream_with_timeout(stream, timeout):
    """Async generator that yields SSE strings from graph stream, with an overall timeout."""
    import time
    deadline = time.monotonic() + timeout
    async for event in stream:
        if time.monotonic() > deadline:
            raise asyncio.TimeoutError()
        for node, values in event.items():
            payload = _build_payload(node, values)
            if payload:
                yield f"data: {json.dumps(payload)}\n\n"


def _build_payload(node: str, values: dict) -> dict | None:
    """Convert a LangGraph node update into a JSON-serialisable event dict."""

    if node == "supervisor":
        queries = values.get("scout_queries", {})
        return {
            "event": "supervisor",
            "queries": queries,
        }

    if node == "scouts":
        papers = values.get("papers", [])
        sources: dict[str, int] = {}
        paper_list = []
        for p in papers:
            sources[p.source] = sources.get(p.source, 0) + 1
            paper_list.append({"title": p.title, "source": p.source, "url": p.url})
        return {
            "event": "scouts",
            "total": len(papers),
            "sources": sources,
            "papers": paper_list,
        }

    if node == "fetcher":
        papers = values.get("papers", [])
        fetched = sum(1 for p in papers if p.full_text)
        return {
            "event": "fetcher",
            "fetched": fetched,
            "total": len(papers),
        }

    if node == "analyst":
        papers = values.get("papers", [])
        analyzed = sum(1 for p in papers if p.relevance_score > 0 or p.key_findings)
        all_sorted = sorted(papers, key=lambda p: p.relevance_score, reverse=True)
        return {
            "event": "analyst",
            "analyzed": analyzed,
            "top_papers": [
                {
                    "title": p.title,
                    "score": p.relevance_score,
                    "findings": p.key_findings or "",
                    "url": p.url,
                    "study_type": p.study_type,
                    "evidence_level": p.evidence_level,
                }
                for p in all_sorted
            ],
        }

    if node == "writer":
        return {
            "event": "writer",
            "report": values.get("report", ""),
        }

    return None

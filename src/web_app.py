import asyncio
import json
import traceback
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from src.graph import build_graph
from src.state import ScientificDiscoveryState

app = FastAPI(title="ScholarAgent")

PUBLIC_DIR = Path(__file__).resolve().parent.parent / "public"
app.mount("/static", StaticFiles(directory=str(PUBLIC_DIR)), name="static")


@app.get("/", response_class=HTMLResponse)
async def index():
    return (PUBLIC_DIR / "index.html").read_text()


@app.get("/api/research")
async def research(query: str):
    """SSE endpoint that streams agent progress events."""

    async def event_stream():
        initial_state = ScientificDiscoveryState(
            query=query,
            scout_queries={},
            papers=[],
            report="",
            logs=[],
        )
        graph = build_graph()

        try:
            stream = graph.astream(initial_state, stream_mode="updates")
            async for event in stream:
                for node, values in event.items():
                    payload = _build_payload(node, values)
                    if payload:
                        yield f"data: {json.dumps(payload)}\n\n"

            yield f"data: {json.dumps({'event': 'done'})}\n\n"

        except Exception as exc:
            traceback.print_exc()
            yield f"data: {json.dumps({'event': 'error', 'message': str(exc)})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


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
        top = sorted(papers, key=lambda p: p.relevance_score, reverse=True)[:5]
        return {
            "event": "analyst",
            "analyzed": analyzed,
            "top_papers": [
                {"title": p.title, "score": p.relevance_score, "findings": p.key_findings or "", "url": p.url}
                for p in top
            ],
        }

    if node == "citation_explorer":
        papers = values.get("papers", [])
        return {
            "event": "citation_explorer",
            "discovered": len(papers),
            "papers": [
                {"title": p.title, "source": p.source, "url": p.url}
                for p in papers
            ],
        }

    if node == "writer":
        return {
            "event": "writer",
            "report": values.get("report", ""),
        }

    return None

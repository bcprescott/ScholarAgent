import asyncio
from typing import Dict, Any, List
from langgraph.graph import StateGraph, END
from src.state import ScientificDiscoveryState
from src.agents.supervisor import supervisor_agent
from src.agents.scouts import (
    arxiv_scout, pubmed_scout, web_scout,
    semantic_scholar_scout, openalex_scout, europe_pmc_scout,
)
from src.agents.citation_explorer import citation_explorer_agent
from src.agents.fetcher import fetcher_agent
from src.agents.analyst import analyst_agent, writer_agent


async def scouts_node(state: ScientificDiscoveryState) -> Dict[str, Any]:
    """Run all 6 scouts in parallel using asyncio."""
    print("--- Scouts Node: Launching 6 parallel scouts ---")

    tasks = [
        asyncio.to_thread(arxiv_scout, state),
        asyncio.to_thread(pubmed_scout, state),
        asyncio.to_thread(semantic_scholar_scout, state),
        asyncio.to_thread(web_scout, state),
        asyncio.to_thread(openalex_scout, state),
        asyncio.to_thread(europe_pmc_scout, state),
    ]

    results = await asyncio.gather(*tasks, return_exceptions=True)

    all_papers = []
    all_logs = []

    for res in results:
        if isinstance(res, Exception):
            print(f"Scout thread execution failed: {res}")
            all_logs.append(f"Scout error: {str(res)}")
        elif res:
            all_papers.extend(res.get("papers", []))
            all_logs.extend(res.get("logs", []))

    print(f"Scouts complete: {len(all_papers)} papers found across all sources.")
    return {"papers": all_papers, "logs": all_logs}


def build_graph():
    workflow = StateGraph(ScientificDiscoveryState)

    # Add nodes
    workflow.add_node("supervisor", supervisor_agent)
    workflow.add_node("scouts", scouts_node)
    workflow.add_node("citation_explorer", citation_explorer_agent)
    workflow.add_node("fetcher", fetcher_agent)
    workflow.add_node("analyst", analyst_agent)
    workflow.add_node("writer", writer_agent)

    # Pipeline: supervisor → scouts → citation_explorer → fetcher → analyst → writer
    # Note: fetcher includes built-in keyword pre-filtering to skip irrelevant papers
    workflow.set_entry_point("supervisor")
    workflow.add_edge("supervisor", "scouts")
    workflow.add_edge("scouts", "citation_explorer")
    workflow.add_edge("citation_explorer", "fetcher")
    workflow.add_edge("fetcher", "analyst")
    workflow.add_edge("analyst", "writer")
    workflow.add_edge("writer", END)

    return workflow.compile()

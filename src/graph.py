import asyncio
from typing import Dict, Any, List
from langgraph.graph import StateGraph, END
from src.state import ScientificDiscoveryState, ResearchConfig
from src.agents.supervisor import supervisor_agent
from src.agents.scouts import (
    arxiv_scout, pubmed_scout, web_scout,
    semantic_scholar_scout, openalex_scout, biorxiv_scout
)
from src.agents.fetcher import fetcher_agent
from src.agents.analyst import analyst_agent, writer_agent


# Map of scout name -> function
SCOUT_REGISTRY = {
    "arxiv": arxiv_scout,
    "pubmed": pubmed_scout,
    "semantic_scholar": semantic_scholar_scout,
    "web": web_scout,
    "openalex": openalex_scout,
    "biorxiv": biorxiv_scout,
}


async def scouts_node(state: ScientificDiscoveryState) -> Dict[str, Any]:
    """Run all enabled scouts in parallel using asyncio (Section 3.1)."""
    print("--- Scouts Node: Launching parallel async scouts ---")

    config = state.get('config') or ResearchConfig()
    enabled = config.enabled_sources

    # Build async tasks for each enabled scout
    async def run_scout(name, scout_fn, st):
        try:
            # Scouts are sync functions, run them in threads
            return await asyncio.wait_for(
                asyncio.to_thread(scout_fn, st),
                timeout=30
            )
        except asyncio.TimeoutError:
            print(f"Warning: {name} scout timed out after 30 seconds.")
            return {"papers": [], "logs": [f"{name} scout timed out."]}
        except Exception as e:
            print(f"Scout {name} failed: {e}")
            return {"papers": [], "logs": [f"{name} error: {str(e)}"]}

    tasks = []
    for name in enabled:
        if name in SCOUT_REGISTRY:
            tasks.append(run_scout(name, SCOUT_REGISTRY[name], state))
        else:
            print(f"Warning: Unknown scout '{name}', skipping.")

    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Merge results
    all_papers = []
    all_logs = []

    for res in results:
        if isinstance(res, Exception):
            print(f"Scout task failed: {res}")
            all_logs.append(f"Scout error: {str(res)}")
            continue
        if res:
            all_papers.extend(res.get("papers", []))
            all_logs.extend(res.get("logs", []))

    return {"papers": all_papers, "logs": all_logs}


def build_graph():
    workflow = StateGraph(ScientificDiscoveryState)

    # Add nodes
    workflow.add_node("supervisor", supervisor_agent)
    workflow.add_node("scouts", scouts_node)
    workflow.add_node("fetcher", fetcher_agent)
    workflow.add_node("analyst", analyst_agent)
    workflow.add_node("writer", writer_agent)

    # Add edges
    workflow.set_entry_point("supervisor")
    workflow.add_edge("supervisor", "scouts")
    workflow.add_edge("scouts", "fetcher")
    workflow.add_edge("fetcher", "analyst")
    workflow.add_edge("analyst", "writer")
    workflow.add_edge("writer", END)

    return workflow.compile()

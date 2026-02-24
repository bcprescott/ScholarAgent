import concurrent.futures
from typing import Dict, Any, List
from langgraph.graph import StateGraph, END
from src.state import ScientificDiscoveryState
from src.agents.supervisor import supervisor_agent
from src.agents.scouts import arxiv_scout, pubmed_scout, web_scout
from src.agents.fetcher import fetcher_agent
from src.agents.analyst import analyst_agent, writer_agent

def scouts_node(state: ScientificDiscoveryState) -> Dict[str, Any]:
    print("--- Scouts Node: Launching parallel scouts ---")
    # Run scouts in parallel, preventing hung threads from blocking
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=3)
    
    future_arxiv = executor.submit(arxiv_scout, state)
    future_pub = executor.submit(pubmed_scout, state)
    future_web = executor.submit(web_scout, state)

    futures = [future_arxiv, future_pub, future_web]

    # Wait for all
    results = []
    try:
        for future in concurrent.futures.as_completed(futures, timeout=30):
            try:
                results.append(future.result())
            except Exception as e:
                print(f"Scout thread execution failed: {e}")
    except concurrent.futures.TimeoutError:
        print("Warning: One or more scout threads timed out after 30 seconds!")
    
    executor.shutdown(wait=False)

    # Merge results
    all_papers = []
    all_logs = []

    for res in results:
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

import os
import arxiv
from typing import List, Dict, Any
from tavily import TavilyClient
from semanticscholar import SemanticScholar
from src.state import ScientificDiscoveryState, Paper

# --- Helpers ---

def create_paper_from_arxiv(result: arxiv.Result) -> Paper:
    return Paper(
        title=result.title,
        url=result.pdf_url, # Prefer PDF URL for fetching
        abstract=result.summary,
        source="arxiv",
        doi=result.doi,
        authors=[a.name for a in result.authors],
        publication_date=str(result.published)
    )

def create_paper_from_semanticscholar(paper: dict) -> Paper:
    # Semantic Scholar returns a dict-like object
    # handle potential missing fields
    url = paper.get('url') or (paper.get('openAccessPdf') or {}).get('url')
    if not url:
        # If no URL, try to construct one or use DOI
        if paper.get('externalIds', {}).get('DOI'):
            url = f"https://doi.org/{paper['externalIds']['DOI']}"
        else:
            url = f"https://www.semanticscholar.org/paper/{paper['paperId']}"

    return Paper(
        title=paper.get('title', 'Unknown Title'),
        url=url,
        abstract=paper.get('abstract'),
        source="semantic_scholar",
        doi=paper.get('externalIds', {}).get('DOI'),
        authors=[a['name'] for a in paper.get('authors', [])],
        publication_date=paper.get('publicationDate')
    )

def create_paper_from_tavily(result: dict) -> Paper:
    return Paper(
        title=result.get('title', 'Unknown Title'),
        url=result.get('url'),
        abstract=result.get('content'), # Tavily returns snippets in 'content'
        source="web",
        doi=None # Web search might not provide DOI easily
    )

# --- Scouts ---

def arxiv_scout(state: ScientificDiscoveryState) -> Dict[str, Any]:
    query = state.get('scout_queries', {}).get('arxiv', state['query'])
    print(f"--- ArXiv Scout searching for: {query} ---")

    try:
        client = arxiv.Client()
        search = arxiv.Search(
            query=query,
            max_results=5,
            sort_by=arxiv.SortCriterion.Relevance
        )
        results = list(client.results(search))
        papers = [create_paper_from_arxiv(r) for r in results]
        return {"papers": papers, "logs": [f"ArXiv found {len(papers)} papers."]}
    except Exception as e:
        return {"papers": [], "logs": [f"ArXiv error: {str(e)}"]}

def semantic_scholar_scout(state: ScientificDiscoveryState) -> Dict[str, Any]:
    query = state.get('scout_queries', {}).get('semantic_scholar', state['query'])
    print(f"--- Semantic Scholar Scout searching for: {query} ---")

    try:
        sch = SemanticScholar()
        # limit=5
        results = sch.search_paper(query, limit=5, fields=['title', 'url', 'abstract', 'authors', 'publicationDate', 'externalIds', 'openAccessPdf'])
        papers = []
        if results:
            for item in results:
                try:
                    # Depending on library version, item might be object or dict
                    # The latest library usually returns objects, but let's be safe
                    if hasattr(item, 'raw_data'):
                         data = item.raw_data
                    else:
                         data = item

                    # If it's an object, try to access attributes or convert to dict
                    # The library usually returns `Paper` objects which are dict-like or have attributes
                    # Let's try to treat it as a dict first if possible or use attributes

                    # For safety with the library, let's assume it behaves like a dict or object with attributes matching the fields requested
                    # Actually, let's just use the `raw_data` if available, or construct dict

                    paper_dict = {}
                    for field in ['title', 'url', 'abstract', 'authors', 'publicationDate', 'externalIds', 'openAccessPdf', 'paperId']:
                        if hasattr(item, field):
                            paper_dict[field] = getattr(item, field)
                        elif isinstance(item, dict):
                            paper_dict[field] = item.get(field)

                    papers.append(create_paper_from_semanticscholar(paper_dict))
                except Exception as e:
                    print(f"Error processing semantic scholar item: {e}")
                    continue

        return {"papers": papers, "logs": [f"Semantic Scholar found {len(papers)} papers."]}
    except Exception as e:
        return {"papers": [], "logs": [f"Semantic Scholar error: {str(e)}"]}

def web_scout(state: ScientificDiscoveryState) -> Dict[str, Any]:
    query = state.get('scout_queries', {}).get('web', state['query'])
    print(f"--- Web Scout searching for: {query} ---")

    api_key = os.environ.get("TAVILY_API_KEY")
    if not api_key:
        print("Warning: TAVILY_API_KEY not found. Skipping web search.")
        return {"papers": [], "logs": ["Web Scout skipped (no API key)."]}

    try:
        client = TavilyClient(api_key=api_key)
        response = client.search(query, search_depth="advanced", max_results=5)
        results = response.get('results', [])
        papers = [create_paper_from_tavily(r) for r in results]
        # Filter out papers that are clearly not academic if possible?
        # For now, just accept them as "General Web" findings.
        return {"papers": papers, "logs": [f"Web Scout found {len(papers)} results."]}
    except Exception as e:
        return {"papers": [], "logs": [f"Web Scout error: {str(e)}"]}

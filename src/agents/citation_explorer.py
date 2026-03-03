import asyncio
import json
import urllib.request
import urllib.parse
from typing import Dict, Any, List, Tuple
from src.state import ScientificDiscoveryState, Paper
from src.agents.scouts import create_paper_from_semanticscholar

SEEDS_LIMIT = 3
REFS_PER_SEED = 5
CITES_PER_SEED = 5
S2_API_BASE = "https://api.semanticscholar.org/graph/v1/paper"
S2_FIELDS = "title,abstract,authors,externalIds,url,publicationDate,openAccessPdf"
S2_RATE_DELAY = 0.3  # Semantic Scholar allows ~100 req/sec for unauthenticated


def _s2_api_get(url: str) -> dict:
    """Make a Semantic Scholar API request with basic error handling."""
    req = urllib.request.Request(url, headers={
        'User-Agent': 'ScholarAgent/1.0',
        'Accept': 'application/json',
    })
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode())


def _resolve_paper_id(paper: Paper) -> str:
    """Try to get a Semantic Scholar-compatible paper ID (DOI preferred)."""
    if paper.doi:
        return paper.doi
    # Fall back to title search
    try:
        encoded = urllib.parse.quote(paper.title)
        url = f"{S2_API_BASE}/search?query={encoded}&limit=1&fields=paperId"
        data = _s2_api_get(url)
        if data.get('data'):
            return data['data'][0].get('paperId')
    except Exception:
        pass
    return None


def _fetch_refs(paper_id: str) -> List[dict]:
    """Fetch references for a paper (blocking)."""
    ref_url = f"{S2_API_BASE}/{paper_id}/references?fields={S2_FIELDS}&limit={REFS_PER_SEED}"
    ref_data = _s2_api_get(ref_url)
    papers = []
    for item in ref_data.get('data', []):
        cited = item.get('citedPaper', {})
        if cited and cited.get('title'):
            papers.append(create_paper_from_semanticscholar(cited))
    return papers


def _fetch_cites(paper_id: str) -> List[dict]:
    """Fetch citations for a paper (blocking)."""
    cite_url = f"{S2_API_BASE}/{paper_id}/citations?fields={S2_FIELDS}&limit={CITES_PER_SEED}"
    cite_data = _s2_api_get(cite_url)
    papers = []
    for item in cite_data.get('data', []):
        citing = item.get('citingPaper', {})
        if citing and citing.get('title'):
            papers.append(create_paper_from_semanticscholar(citing))
    return papers


async def _explore_seed(seed: Paper) -> Tuple[List[Paper], List[str]]:
    """Explore one seed paper's citation graph. Returns (papers, logs)."""
    papers = []
    logs = []

    paper_id = await asyncio.to_thread(_resolve_paper_id, seed)
    if not paper_id:
        logs.append(f"Citation Explorer: Could not resolve ID for '{seed.title}'")
        return papers, logs

    # Fetch references and citations in parallel
    try:
        refs_task = asyncio.to_thread(_fetch_refs, paper_id)
        cites_task = asyncio.to_thread(_fetch_cites, paper_id)
        ref_papers, cite_papers = await asyncio.gather(refs_task, cites_task, return_exceptions=True)

        if isinstance(ref_papers, Exception):
            logs.append(f"Citation Explorer: Error fetching references for '{seed.title}': {ref_papers}")
            ref_papers = []
        if isinstance(cite_papers, Exception):
            logs.append(f"Citation Explorer: Error fetching citations for '{seed.title}': {cite_papers}")
            cite_papers = []

        papers.extend(ref_papers)
        papers.extend(cite_papers)

        logs.append(
            f"Citation Explorer: Found {len(ref_papers)} references + {len(cite_papers)} citations "
            f"for '{seed.title}'"
        )
        print(f"Citation Explorer: {len(ref_papers)} refs + {len(cite_papers)} cites for '{seed.title}'")
    except Exception as e:
        logs.append(f"Citation Explorer: Error for '{seed.title}': {e}")

    return papers, logs


async def citation_explorer_agent(state: ScientificDiscoveryState) -> Dict[str, Any]:
    """Discover related papers by traversing the citation graph of top results.
    All seeds are explored in parallel, and refs+cites per seed are fetched concurrently."""
    papers = state.get('papers', [])

    if not papers:
        return {"papers": [], "logs": ["Citation Explorer: No papers to explore."]}

    # Select seed papers — prefer those with DOIs for reliable lookup
    seeds_with_doi = [p for p in papers if p.doi][:SEEDS_LIMIT]
    remaining = SEEDS_LIMIT - len(seeds_with_doi)
    if remaining > 0:
        seeds_without = [p for p in papers if not p.doi][:remaining]
        seeds = seeds_with_doi + seeds_without
    else:
        seeds = seeds_with_doi

    print(f"--- Citation Explorer: Exploring citations for {len(seeds)} seed papers (parallel) ---")

    # Explore all seeds in parallel
    results = await asyncio.gather(*[_explore_seed(s) for s in seeds])

    all_papers = []
    all_logs = []
    for seed_papers, seed_logs in results:
        all_papers.extend(seed_papers)
        all_logs.extend(seed_logs)

    all_logs.append(f"Citation Explorer: Discovered {len(all_papers)} papers total via citation traversal.")
    print(f"Citation Explorer: {len(all_papers)} papers discovered total.")

    return {"papers": all_papers, "logs": all_logs}

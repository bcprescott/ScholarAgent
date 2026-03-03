import time
import json
import urllib.request
import urllib.parse
from typing import Dict, Any
from src.state import ScientificDiscoveryState, Paper
from src.agents.scouts import create_paper_from_semanticscholar

SEEDS_LIMIT = 3
REFS_PER_SEED = 5
CITES_PER_SEED = 5
S2_API_BASE = "https://api.semanticscholar.org/graph/v1/paper"
S2_FIELDS = "title,abstract,authors,externalIds,url,publicationDate,openAccessPdf"


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


def citation_explorer_agent(state: ScientificDiscoveryState) -> Dict[str, Any]:
    """Discover related papers by traversing the citation graph of top results."""
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

    new_papers = []
    logs = []

    print(f"--- Citation Explorer: Exploring citations for {len(seeds)} seed papers ---")

    for seed in seeds:
        paper_id = _resolve_paper_id(seed)
        if not paper_id:
            logs.append(f"Citation Explorer: Could not resolve ID for '{seed.title}'")
            continue

        ref_count = 0
        cite_count = 0

        # Fetch references (papers this one cites)
        try:
            ref_url = f"{S2_API_BASE}/{paper_id}/references?fields={S2_FIELDS}&limit={REFS_PER_SEED}"
            ref_data = _s2_api_get(ref_url)
            for item in ref_data.get('data', []):
                cited = item.get('citedPaper', {})
                if cited and cited.get('title'):
                    new_papers.append(create_paper_from_semanticscholar(cited))
                    ref_count += 1
        except Exception as e:
            logs.append(f"Citation Explorer: Error fetching references for '{seed.title}': {e}")

        time.sleep(1)  # Rate limiting between API calls

        # Fetch citations (papers that cite this one)
        try:
            cite_url = f"{S2_API_BASE}/{paper_id}/citations?fields={S2_FIELDS}&limit={CITES_PER_SEED}"
            cite_data = _s2_api_get(cite_url)
            for item in cite_data.get('data', []):
                citing = item.get('citingPaper', {})
                if citing and citing.get('title'):
                    new_papers.append(create_paper_from_semanticscholar(citing))
                    cite_count += 1
        except Exception as e:
            logs.append(f"Citation Explorer: Error fetching citations for '{seed.title}': {e}")

        logs.append(
            f"Citation Explorer: Found {ref_count} references + {cite_count} citations "
            f"for '{seed.title}'"
        )
        print(f"Citation Explorer: {ref_count} refs + {cite_count} cites for '{seed.title}'")

        time.sleep(1)  # Rate limiting between seeds

    logs.append(f"Citation Explorer: Discovered {len(new_papers)} papers total via citation traversal.")
    print(f"Citation Explorer: {len(new_papers)} papers discovered total.")

    return {"papers": new_papers, "logs": logs}

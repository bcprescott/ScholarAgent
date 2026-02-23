from typing import List, Optional, TypedDict, Dict, Any, Annotated
import operator
from pydantic import BaseModel, Field

def merge_papers(existing: List['Paper'], new: List['Paper']) -> List['Paper']:
    if existing is None:
        return new

    existing_map = {p.url: p for p in existing}

    for p in new:
        # If the new paper has more info (like full_text), we want to keep it.
        # Simple replacement strategy: if URL matches, use the new one (assuming it's an update)
        # or merge fields. For simplicity, we assume 'new' is the latest version.
        existing_map[p.url] = p

    return list(existing_map.values())

class Paper(BaseModel):
    title: str
    url: str
    abstract: Optional[str] = None
    full_text: Optional[str] = None
    source: str  # 'arxiv', 'semantic_scholar', 'web'
    doi: Optional[str] = None
    authors: Optional[List[str]] = None
    publication_date: Optional[str] = None

    # Analysis fields
    relevance_score: float = 0.0
    key_findings: Optional[str] = None
    methodology: Optional[str] = None
    limitations: Optional[str] = None

    def __hash__(self):
        return hash(self.url)

class ScientificDiscoveryState(TypedDict):
    query: str
    scout_queries: Dict[str, str] # e.g. {'arxiv': 'query', ...}
    papers: Annotated[List[Paper], merge_papers]
    report: str
    logs: Annotated[List[str], operator.add]

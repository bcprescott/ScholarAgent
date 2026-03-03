from typing import List, Optional, TypedDict, Dict, Any, Annotated
import operator
from pydantic import BaseModel, Field


def merge_papers(existing: List['Paper'], new: List['Paper']) -> List['Paper']:
    """Merge paper lists, deduplicating by URL, DOI, and normalized title."""
    if existing is None:
        return new

    existing_map = {p.url: p for p in existing}
    existing_dois = {p.doi.lower().strip() for p in existing if p.doi}
    existing_titles = {p.title.lower().strip() for p in existing if p.title}

    for p in new:
        # Skip if we already have this paper (by URL, DOI, or title)
        if p.url in existing_map:
            # Update existing entry if new has more info (e.g., full_text)
            existing_paper = existing_map[p.url]
            if p.full_text and not existing_paper.full_text:
                existing_map[p.url] = p
            continue
        if p.doi and p.doi.lower().strip() in existing_dois:
            continue
        if p.title and p.title.lower().strip() in existing_titles:
            continue

        existing_map[p.url] = p
        if p.doi:
            existing_dois.add(p.doi.lower().strip())
        if p.title:
            existing_titles.add(p.title.lower().strip())

    return list(existing_map.values())


class Paper(BaseModel):
    title: str
    url: str
    abstract: Optional[str] = None
    full_text: Optional[str] = None
    source: str  # 'arxiv', 'semantic_scholar', 'web', 'pubmed', 'openalex', 'europe_pmc'
    doi: Optional[str] = None
    authors: Optional[List[str]] = None
    publication_date: Optional[str] = None

    # Analysis fields
    relevance_score: float = 0.0
    key_findings: Optional[str] = None
    methodology: Optional[str] = None
    limitations: Optional[str] = None
    study_type: Optional[str] = None
    evidence_level: Optional[str] = None
    confidence_notes: Optional[str] = None

    def __hash__(self):
        return hash(self.url)


class ScientificDiscoveryState(TypedDict):
    query: str
    scout_queries: Dict[str, str]  # e.g. {'arxiv': 'query', 'semantic_scholar': 'query', ...}
    papers: Annotated[List[Paper], merge_papers]
    report: str
    logs: Annotated[List[str], operator.add]

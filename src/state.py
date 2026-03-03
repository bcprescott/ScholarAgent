from typing import List, Optional, TypedDict, Dict, Any, Annotated
import operator
from pydantic import BaseModel, Field

try:
    from rapidfuzz import fuzz
    HAS_RAPIDFUZZ = True
except ImportError:
    HAS_RAPIDFUZZ = False


class ResearchConfig(BaseModel):
    """User-configurable pipeline settings."""
    max_results_per_source: int = 10
    relevance_threshold: float = 50.0
    enabled_sources: List[str] = [
        "arxiv", "pubmed", "semantic_scholar", "web", "openalex", "biorxiv"
    ]
    fetch_full_text: bool = True
    max_paper_chars: int = 20000


class Paper(BaseModel):
    title: str
    url: str
    abstract: Optional[str] = None
    full_text: Optional[str] = None
    source: str  # 'arxiv', 'semantic_scholar', 'web', 'pubmed', 'openalex', 'biorxiv'
    doi: Optional[str] = None
    authors: Optional[List[str]] = None
    publication_date: Optional[str] = None

    # Analysis fields
    relevance_score: float = 0.0
    key_findings: Optional[str] = None
    methodology: Optional[str] = None
    limitations: Optional[str] = None

    # Structured evidence grading (Section 2.2)
    study_type: Optional[str] = None        # e.g., "meta-analysis", "RCT", "case study"
    evidence_level: Optional[str] = None     # e.g., "Level I", "Level II", etc.
    sample_size: Optional[int] = None
    confidence_notes: Optional[str] = None   # Why this evidence is strong or weak

    def __hash__(self):
        return hash(self.url)


def _normalize_title(title: str) -> str:
    """Normalize a title for comparison."""
    return title.lower().strip()


def _titles_match(a: str, b: str, threshold: int = 90) -> bool:
    """Check if two titles are similar enough to be considered duplicates."""
    if HAS_RAPIDFUZZ:
        return fuzz.ratio(_normalize_title(a), _normalize_title(b)) >= threshold
    # Fallback to exact match if rapidfuzz not installed
    return _normalize_title(a) == _normalize_title(b)


def merge_papers(existing: List['Paper'], new: List['Paper']) -> List['Paper']:
    """Merge paper lists with deduplication by URL, DOI, and fuzzy title match."""
    if existing is None:
        return new

    existing_map = {p.url: p for p in existing}

    for p in new:
        # 1. URL-based dedup
        if p.url in existing_map:
            # Keep whichever has more info (prefer new if it has full_text)
            if p.full_text and not existing_map[p.url].full_text:
                existing_map[p.url] = p
            continue

        # 2. DOI-based dedup
        if p.doi:
            existing_dois = {ep.doi: ep.url for ep in existing_map.values() if ep.doi}
            if p.doi in existing_dois:
                continue

        # 3. Fuzzy title-based dedup
        is_dup = False
        for ep in existing_map.values():
            if _titles_match(p.title, ep.title):
                is_dup = True
                break
        if is_dup:
            continue

        existing_map[p.url] = p

    return list(existing_map.values())


class ScientificDiscoveryState(TypedDict):
    query: str
    scout_queries: Dict[str, str]  # e.g. {'arxiv': 'query', 'semantic_scholar': 'query', ...}
    papers: Annotated[List[Paper], merge_papers]
    report: str
    logs: Annotated[List[str], operator.add]
    config: ResearchConfig

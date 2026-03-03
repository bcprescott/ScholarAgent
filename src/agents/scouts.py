import os
import time
import urllib.request
import urllib.parse
import json
import xml.etree.ElementTree as ET
import arxiv
from datetime import datetime, timedelta
from typing import List, Dict, Any
from tavily import TavilyClient
from semanticscholar import SemanticScholar
from src.state import ScientificDiscoveryState, Paper

# --- Helpers ---

def _get_max_results(state: ScientificDiscoveryState) -> int:
    """Get max results from config, defaulting to 10."""
    config = state.get('config')
    if config and hasattr(config, 'max_results_per_source'):
        return config.max_results_per_source
    return 10


def create_paper_from_arxiv(result: arxiv.Result) -> Paper:
    return Paper(
        title=result.title,
        url=result.pdf_url,  # Prefer PDF URL for fetching
        abstract=result.summary,
        source="arxiv",
        doi=result.doi,
        authors=[a.name for a in result.authors],
        publication_date=str(result.published)
    )

def create_paper_from_semanticscholar(paper: dict) -> Paper:
    # Semantic Scholar returns a dict-like object
    url = paper.get('url') or (paper.get('openAccessPdf') or {}).get('url')
    if not url:
        if paper.get('externalIds', {}).get('DOI'):
            url = f"https://doi.org/{paper['externalIds']['DOI']}"
        else:
            url = f"https://www.semanticscholar.org/paper/{paper['paperId']}"

    pub_date = paper.get('publicationDate')

    return Paper(
        title=paper.get('title', 'Unknown Title'),
        url=url,
        abstract=paper.get('abstract'),
        source="semantic_scholar",
        doi=paper.get('externalIds', {}).get('DOI'),
        authors=[a['name'] for a in paper.get('authors', [])],
        publication_date=str(pub_date) if pub_date is not None else None
    )

def create_paper_from_tavily(result: dict) -> Paper:
    return Paper(
        title=result.get('title', 'Unknown Title'),
        url=result.get('url'),
        abstract=result.get('content'),  # Tavily returns snippets in 'content'
        source="web",
        doi=None
    )

def create_paper_from_pubmed(article_element) -> Paper:
    # Basic XML parsing for Pubmed Article
    title = "Unknown Title"
    article_title_element = article_element.find('.//ArticleTitle')
    if article_title_element is not None and article_title_element.text:
        title = article_title_element.text

    abstractText = ""
    for abs_text in article_element.findall('.//AbstractText'):
        if abs_text.text:
            abstractText += abs_text.text + " "

    doi = None
    for elId in article_element.findall('.//ArticleId'):
        if elId.get('IdType') == 'doi':
            doi = elId.text
            break

    # Safe PMID access (Section 4.2 fix)
    pmid_element = article_element.find('.//PMID')
    pmid = pmid_element.text if pmid_element is not None and pmid_element.text else None

    if doi:
        url = f"https://doi.org/{doi}"
    elif pmid:
        url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
    else:
        url = f"https://pubmed.ncbi.nlm.nih.gov/"

    authors = []
    for author in article_element.findall('.//Author'):
        last_name = author.find('LastName')
        initials = author.find('Initials')
        if last_name is not None and last_name.text:
            name = last_name.text
            if initials is not None and initials.text:
                name += f" {initials.text}"
            authors.append(name)

    pub_date = ""
    pub_date_el = article_element.find('.//PubDate/Year')
    if pub_date_el is not None:
        pub_date = pub_date_el.text

    return Paper(
        title=title,
        url=url,
        abstract=abstractText.strip(),
        source="pubmed",
        doi=doi,
        authors=authors,
        publication_date=pub_date
    )


def create_paper_from_openalex(work: dict) -> Paper:
    """Create a Paper from an OpenAlex work record."""
    title = work.get('title', 'Unknown Title')

    # Best URL: open access first, then DOI, then OpenAlex page
    oa_url = None
    best_oa = work.get('best_oa_location') or {}
    if best_oa.get('pdf_url'):
        oa_url = best_oa['pdf_url']
    elif best_oa.get('landing_page_url'):
        oa_url = best_oa['landing_page_url']

    doi_raw = work.get('doi')  # e.g. "https://doi.org/10.1234/..."
    doi = doi_raw.replace('https://doi.org/', '') if doi_raw else None

    url = oa_url or doi_raw or work.get('id', '')

    # Authors
    authors = []
    for authorship in work.get('authorships', []):
        author_name = authorship.get('author', {}).get('display_name')
        if author_name:
            authors.append(author_name)

    # Abstract — OpenAlex returns an inverted index, reconstruct it
    abstract = None
    abstract_inv = work.get('abstract_inverted_index')
    if abstract_inv:
        try:
            word_positions = []
            for word, positions in abstract_inv.items():
                for pos in positions:
                    word_positions.append((pos, word))
            word_positions.sort()
            abstract = ' '.join(w for _, w in word_positions)
        except Exception:
            abstract = None

    return Paper(
        title=title,
        url=url,
        abstract=abstract,
        source="openalex",
        doi=doi,
        authors=authors[:10],  # Limit to first 10 authors
        publication_date=work.get('publication_date')
    )


def create_paper_from_biorxiv(paper: dict) -> Paper:
    """Create a Paper from a bioRxiv API record."""
    doi = paper.get('doi', '')
    url = f"https://doi.org/{doi}" if doi else paper.get('jatsxml', '')

    authors_raw = paper.get('authors', '')
    authors = [a.strip() for a in authors_raw.split(';') if a.strip()] if authors_raw else []

    return Paper(
        title=paper.get('title', 'Unknown Title'),
        url=url,
        abstract=paper.get('abstract'),
        source="biorxiv",
        doi=doi if doi else None,
        authors=authors[:10],
        publication_date=paper.get('date')
    )


# --- Scouts ---

def arxiv_scout(state: ScientificDiscoveryState) -> Dict[str, Any]:
    query = state.get('scout_queries', {}).get('arxiv', state['query'])
    max_results = _get_max_results(state)
    print(f"--- ArXiv Scout searching for: {query} (max: {max_results}) ---")

    try:
        client = arxiv.Client()
        search = arxiv.Search(
            query=query,
            max_results=max_results,
            sort_by=arxiv.SortCriterion.Relevance
        )
        results = list(client.results(search))
        papers = [create_paper_from_arxiv(r) for r in results]
        print(f"ArXiv Scout found {len(papers)} papers.")
        return {"papers": papers, "logs": [f"ArXiv found {len(papers)} papers."]}
    except Exception as e:
        print(f"ArXiv error: {e}")
        return {"papers": [], "logs": [f"ArXiv error: {str(e)}"]}

def semantic_scholar_scout(state: ScientificDiscoveryState) -> Dict[str, Any]:
    query = state.get('scout_queries', {}).get('semantic_scholar', state['query'])
    max_results = _get_max_results(state)
    print(f"--- Semantic Scholar Scout searching for: {query} (max: {max_results}) ---")

    try:
        sch = SemanticScholar(timeout=10, retry=False)
        max_retries = 3
        results = None
        for attempt in range(max_retries):
            try:
                results = sch.search_paper(query, limit=max_results, fields=['title', 'url', 'abstract', 'authors', 'publicationDate', 'externalIds', 'openAccessPdf'])
                break  # Success
            except Exception as search_val_e:
                if "429" in str(search_val_e) or "Too Many Requests" in str(search_val_e):
                    if attempt < max_retries - 1:
                        sleep_time = 2 ** attempt * 2
                        print(f"Semantic Scholar rate limited (429). Retrying in {sleep_time} seconds...")
                        time.sleep(sleep_time)
                    else:
                        print(f"Semantic Scholar rate limit exceeded after {max_retries} attempts.")
                        raise search_val_e
                else:
                    raise search_val_e

        papers = []
        if results:
            for item in results:
                try:
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

        print(f"Semantic Scholar Scout found {len(papers)} papers.")
        return {"papers": papers, "logs": [f"Semantic Scholar found {len(papers)} papers."]}
    except Exception as e:
        print(f"Semantic Scholar error: {e}")
        return {"papers": [], "logs": [f"Semantic Scholar error: {str(e)}"]}

def web_scout(state: ScientificDiscoveryState) -> Dict[str, Any]:
    query = state.get('scout_queries', {}).get('web', state['query'])
    max_results = _get_max_results(state)
    print(f"--- Web Scout searching for: {query} (max: {max_results}) ---")

    api_key_env = os.environ.get("TAVILY_API_KEY")
    api_key = api_key_env.strip().strip('"').strip("'") if api_key_env else None
    if not api_key:
        print("Warning: TAVILY_API_KEY not found. Skipping web search.")
        return {"papers": [], "logs": ["Web Scout skipped (no API key)."]}

    try:
        client = TavilyClient(api_key=api_key)
        response = client.search(query, search_depth="advanced", max_results=max_results)
        results = response.get('results', [])
        papers = [create_paper_from_tavily(r) for r in results]
        print(f"Web Scout found {len(papers)} papers.")
        return {"papers": papers, "logs": [f"Web Scout found {len(papers)} results."]}
    except Exception as e:
        print(f"Web Scout error: {e}")
        return {"papers": [], "logs": [f"Web Scout error: {str(e)}"]}

def pubmed_scout(state: ScientificDiscoveryState) -> Dict[str, Any]:
    query = state.get('scout_queries', {}).get('pubmed', state['query'])
    max_results = _get_max_results(state)
    print(f"--- PubMed Scout searching for: {query} (max: {max_results}) ---")

    try:
        search_query = urllib.parse.quote(query)
        search_url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=pubmed&term={search_query}&retmode=json&retmax={max_results}"

        req = urllib.request.Request(search_url, headers={'User-Agent': "Mozilla/5.0"})
        with urllib.request.urlopen(req) as response:
            search_data = json.loads(response.read().decode())

        pmids = search_data.get('esearchresult', {}).get('idlist', [])
        papers = []

        if pmids:
            fetch_url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=pubmed&id={','.join(pmids)}&retmode=xml"
            fetch_req = urllib.request.Request(fetch_url, headers={'User-Agent': "Mozilla/5.0"})
            with urllib.request.urlopen(fetch_req) as fetch_response:
                xml_data = fetch_response.read()

            root = ET.fromstring(xml_data)
            for article in root.findall('.//PubmedArticle'):
                try:
                    papers.append(create_paper_from_pubmed(article))
                except Exception as e:
                    print(f"Error processing pubmed article: {e}")
                    continue

        print(f"PubMed Scout found {len(papers)} papers.")
        return {"papers": papers, "logs": [f"PubMed found {len(papers)} papers."]}
    except Exception as e:
        print(f"PubMed error: {e}")
        return {"papers": [], "logs": [f"PubMed error: {str(e)}"]}


def openalex_scout(state: ScientificDiscoveryState) -> Dict[str, Any]:
    """OpenAlex scout — 250M+ works across all disciplines, free, no API key needed."""
    query = state.get('scout_queries', {}).get('openalex', state['query'])
    max_results = _get_max_results(state)
    print(f"--- OpenAlex Scout searching for: {query} (max: {max_results}) ---")

    try:
        params = urllib.parse.urlencode({
            'search': query,
            'per_page': max_results,
            'sort': 'relevance_score:desc',
            'filter': f'from_publication_date:{datetime.now().year - 1}-01-01',
            'select': 'id,doi,title,authorships,publication_date,abstract_inverted_index,best_oa_location'
        })
        url = f"https://api.openalex.org/works?{params}"

        req = urllib.request.Request(url, headers={
            'User-Agent': 'ScholarAgent/1.0 (mailto:scholar@example.com)',
            'Accept': 'application/json'
        })

        with urllib.request.urlopen(req, timeout=15) as response:
            data = json.loads(response.read().decode())

        works = data.get('results', [])
        papers = [create_paper_from_openalex(w) for w in works]

        print(f"OpenAlex Scout found {len(papers)} papers.")
        return {"papers": papers, "logs": [f"OpenAlex found {len(papers)} papers."]}
    except Exception as e:
        print(f"OpenAlex error: {e}")
        return {"papers": [], "logs": [f"OpenAlex error: {str(e)}"]}


def biorxiv_scout(state: ScientificDiscoveryState) -> Dict[str, Any]:
    """bioRxiv scout — preprints for cutting-edge biological/medical research, free."""
    query = state.get('scout_queries', {}).get('biorxiv', state['query'])
    max_results = _get_max_results(state)
    print(f"--- bioRxiv Scout searching for: {query} (max: {max_results}) ---")

    try:
        # bioRxiv content API uses date ranges; search last 60 days
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=60)).strftime('%Y-%m-%d')

        # The bioRxiv API endpoint for details by date range
        # We'll use the search endpoint via the NCBI-style interface
        search_query = urllib.parse.quote(query)
        url = f"https://api.biorxiv.org/details/biorxiv/{start_date}/{end_date}/0/json"

        req = urllib.request.Request(url, headers={
            'User-Agent': 'ScholarAgent/1.0',
            'Accept': 'application/json'
        })

        with urllib.request.urlopen(req, timeout=15) as response:
            data = json.loads(response.read().decode())

        all_papers = data.get('collection', [])

        # bioRxiv details API doesn't support keyword search, so we filter client-side
        query_terms = query.lower().split()
        scored_papers = []
        for paper in all_papers:
            text = f"{paper.get('title', '')} {paper.get('abstract', '')}".lower()
            score = sum(1 for term in query_terms if term in text)
            if score > 0:
                scored_papers.append((score, paper))

        # Sort by relevance (term match count) and take top N
        scored_papers.sort(key=lambda x: x[0], reverse=True)
        top_papers = [p for _, p in scored_papers[:max_results]]

        papers = [create_paper_from_biorxiv(p) for p in top_papers]

        print(f"bioRxiv Scout found {len(papers)} papers.")
        return {"papers": papers, "logs": [f"bioRxiv found {len(papers)} papers."]}
    except Exception as e:
        print(f"bioRxiv error: {e}")
        return {"papers": [], "logs": [f"bioRxiv error: {str(e)}"]}

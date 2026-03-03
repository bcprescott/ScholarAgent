import os
import time
import urllib.request
import urllib.parse
import json
import xml.etree.ElementTree as ET
import arxiv
from typing import List, Dict, Any
from tavily import TavilyClient
from semanticscholar import SemanticScholar
from src.state import ScientificDiscoveryState, Paper

MAX_RESULTS = 10

# --- Helpers ---

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
    url = paper.get('url') or (paper.get('openAccessPdf') or {}).get('url')
    if not url:
        if paper.get('externalIds', {}).get('DOI'):
            url = f"https://doi.org/{paper['externalIds']['DOI']}"
        elif paper.get('paperId'):
            url = f"https://www.semanticscholar.org/paper/{paper['paperId']}"
        else:
            url = f"https://www.semanticscholar.org/search?q={urllib.parse.quote(paper.get('title', ''))}"

    pub_date = paper.get('publicationDate')

    return Paper(
        title=paper.get('title', 'Unknown Title'),
        url=url,
        abstract=paper.get('abstract'),
        source="semantic_scholar",
        doi=paper.get('externalIds', {}).get('DOI'),
        authors=[a['name'] for a in paper.get('authors', []) if isinstance(a, dict) and 'name' in a],
        publication_date=str(pub_date) if pub_date is not None else None
    )

def create_paper_from_tavily(result: dict) -> Paper:
    return Paper(
        title=result.get('title', 'Unknown Title'),
        url=result.get('url'),
        abstract=result.get('content'),
        source="web",
        doi=None
    )

def create_paper_from_pubmed(article_element) -> Paper:
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

    pmid = None
    pmid_el = article_element.find('.//PMID')
    if pmid_el is not None and pmid_el.text:
        pmid = pmid_el.text

    url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else None
    if doi:
        url = f"https://doi.org/{doi}"
    if not url:
        url = f"https://pubmed.ncbi.nlm.nih.gov/?term={urllib.parse.quote(title)}"

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


def reconstruct_abstract_from_inverted_index(inverted_index: dict) -> str:
    """OpenAlex stores abstracts as inverted indexes. Reconstruct to plain text."""
    if not inverted_index:
        return None
    word_positions = []
    for word, positions in inverted_index.items():
        for pos in positions:
            word_positions.append((pos, word))
    word_positions.sort(key=lambda x: x[0])
    return " ".join(word for _, word in word_positions)


def create_paper_from_openalex(work: dict) -> Paper:
    doi_raw = work.get('doi')  # e.g. "https://doi.org/10.1234/xxx"
    doi = doi_raw.replace("https://doi.org/", "") if doi_raw else None

    # Find the best URL
    primary_loc = work.get('primary_location') or {}
    pdf_url = primary_loc.get('pdf_url')
    landing_url = primary_loc.get('landing_page_url')
    oa_url = (work.get('open_access') or {}).get('oa_url')
    url = pdf_url or oa_url or landing_url or (f"https://doi.org/{doi}" if doi else work.get('id', ''))

    authors = []
    for authorship in work.get('authorships', []):
        author = authorship.get('author', {})
        name = author.get('display_name')
        if name:
            authors.append(name)

    abstract = reconstruct_abstract_from_inverted_index(work.get('abstract_inverted_index'))

    return Paper(
        title=work.get('title') or work.get('display_name') or 'Unknown Title',
        url=url,
        abstract=abstract,
        source="openalex",
        doi=doi,
        authors=authors,
        publication_date=work.get('publication_date')
    )


def create_paper_from_europe_pmc(result: dict) -> Paper:
    doi = result.get('doi')
    pmid = result.get('pmid')

    # Find best URL
    url = None
    if doi:
        url = f"https://doi.org/{doi}"
    elif pmid:
        url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
    else:
        url = f"https://europepmc.org/article/{result.get('source', 'MED')}/{result.get('id', '')}"

    # Try to get full-text PDF URL
    full_text_urls = result.get('fullTextUrlList', {}).get('fullTextUrl', [])
    for ft in full_text_urls:
        if ft.get('documentStyle') == 'pdf' and ft.get('url'):
            url = ft['url']
            break

    authors = []
    author_str = result.get('authorString', '')
    if author_str:
        authors = [a.strip() for a in author_str.split(',')]

    return Paper(
        title=result.get('title', 'Unknown Title'),
        url=url,
        abstract=result.get('abstractText'),
        source="europe_pmc",
        doi=doi,
        authors=authors,
        publication_date=result.get('pubYear')
    )


# --- Scouts ---

def arxiv_scout(state: ScientificDiscoveryState) -> Dict[str, Any]:
    query = state.get('scout_queries', {}).get('arxiv', state['query'])
    print(f"--- ArXiv Scout searching for: {query} ---")

    try:
        client = arxiv.Client()
        search = arxiv.Search(
            query=query,
            max_results=MAX_RESULTS,
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
    print(f"--- Semantic Scholar Scout searching for: {query} ---")

    try:
        sch = SemanticScholar(timeout=10, retry=False)
        max_retries = 3
        results = None
        for attempt in range(max_retries):
            try:
                results = sch.search_paper(query, limit=MAX_RESULTS, fields=['title', 'url', 'abstract', 'authors', 'publicationDate', 'externalIds', 'openAccessPdf'])
                break
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
    print(f"--- Web Scout searching for: {query} ---")

    api_key_env = os.environ.get("TAVILY_API_KEY")
    api_key = api_key_env.strip().strip('"').strip("'") if api_key_env else None
    if not api_key:
        print("Warning: TAVILY_API_KEY not found. Skipping web search.")
        return {"papers": [], "logs": ["Web Scout skipped (no API key)."]}

    try:
        client = TavilyClient(api_key=api_key)
        response = client.search(query, search_depth="advanced", max_results=MAX_RESULTS)
        results = response.get('results', [])
        papers = [create_paper_from_tavily(r) for r in results]
        print(f"Web Scout found {len(papers)} papers.")
        return {"papers": papers, "logs": [f"Web Scout found {len(papers)} results."]}
    except Exception as e:
        print(f"Web Scout error: {e}")
        return {"papers": [], "logs": [f"Web Scout error: {str(e)}"]}

def pubmed_scout(state: ScientificDiscoveryState) -> Dict[str, Any]:
    query = state.get('scout_queries', {}).get('pubmed', state['query'])
    print(f"--- PubMed Scout searching for: {query} ---")

    try:
        search_query = urllib.parse.quote(query)
        search_url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=pubmed&term={search_query}&retmode=json&retmax={MAX_RESULTS}"

        req = urllib.request.Request(search_url, headers={'User-Agent': "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as response:
            search_data = json.loads(response.read().decode())

        pmids = search_data.get('esearchresult', {}).get('idlist', [])
        papers = []

        if pmids:
            fetch_url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=pubmed&id={','.join(pmids)}&retmode=xml"
            fetch_req = urllib.request.Request(fetch_url, headers={'User-Agent': "Mozilla/5.0"})
            with urllib.request.urlopen(fetch_req, timeout=15) as fetch_response:
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
    """Search OpenAlex — 250M+ works across all academic disciplines (free, no key)."""
    query = state.get('scout_queries', {}).get('semantic_scholar', state['query'])
    print(f"--- OpenAlex Scout searching for: {query} ---")

    try:
        encoded_query = urllib.parse.quote(query)
        url = (
            f"https://api.openalex.org/works?"
            f"search={encoded_query}"
            f"&per_page={MAX_RESULTS}"
            f"&sort=relevance_score:desc"
            f"&select=id,title,doi,authorships,publication_date,abstract_inverted_index,"
            f"primary_location,open_access,type"
        )

        headers = {
            'User-Agent': 'ScholarAgent/1.0 (mailto:scholar-agent@example.com)',
            'Accept': 'application/json',
        }
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as response:
            data = json.loads(response.read().decode())

        results = data.get('results', [])
        papers = []
        for work in results:
            try:
                papers.append(create_paper_from_openalex(work))
            except Exception as e:
                print(f"Error processing OpenAlex work: {e}")
                continue

        print(f"OpenAlex Scout found {len(papers)} papers.")
        return {"papers": papers, "logs": [f"OpenAlex found {len(papers)} papers."]}
    except Exception as e:
        print(f"OpenAlex error: {e}")
        return {"papers": [], "logs": [f"OpenAlex error: {str(e)}"]}


def europe_pmc_scout(state: ScientificDiscoveryState) -> Dict[str, Any]:
    """Search Europe PMC — covers PubMed, bioRxiv, medRxiv preprints, and more (free, no key)."""
    query = state.get('scout_queries', {}).get('pubmed', state['query'])
    print(f"--- Europe PMC Scout searching for: {query} ---")

    try:
        encoded_query = urllib.parse.quote(query)
        # SRC:PPR filters for preprints (bioRxiv, medRxiv, etc.)
        # We search broadly but boost preprints to complement PubMed
        url = (
            f"https://www.ebi.ac.uk/europepmc/webservices/rest/search?"
            f"query={encoded_query}"
            f"&resultType=core"
            f"&pageSize={MAX_RESULTS}"
            f"&format=json"
            f"&sort=RELEVANCE"
        )

        headers = {
            'User-Agent': 'ScholarAgent/1.0',
            'Accept': 'application/json',
        }
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as response:
            data = json.loads(response.read().decode())

        results = data.get('resultList', {}).get('result', [])
        papers = []
        for result in results:
            try:
                papers.append(create_paper_from_europe_pmc(result))
            except Exception as e:
                print(f"Error processing Europe PMC result: {e}")
                continue

        print(f"Europe PMC Scout found {len(papers)} papers.")
        return {"papers": papers, "logs": [f"Europe PMC found {len(papers)} papers."]}
    except Exception as e:
        print(f"Europe PMC error: {e}")
        return {"papers": [], "logs": [f"Europe PMC error: {str(e)}"]}

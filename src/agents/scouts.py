import os
import time
import urllib.request
import json
import xml.etree.ElementTree as ET
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
        abstract=result.get('content'), # Tavily returns snippets in 'content'
        source="web",
        doi=None # Web search might not provide DOI easily
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
            
    pmid = article_element.find('.//PMID').text
    url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
    if doi:
        url = f"https://doi.org/{doi}"
        
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
        # We will manually handle retries for 429s here instead of relying on the library's internal retry to avoid infinite hanging.
        max_retries = 3
        results = None
        for attempt in range(max_retries):
            try:
                results = sch.search_paper(query, limit=5, fields=['title', 'url', 'abstract', 'authors', 'publicationDate', 'externalIds', 'openAccessPdf'])
                break # Success
            except Exception as search_val_e:
                # If we get rate limited, sleep and retry
                if "429" in str(search_val_e) or "Too Many Requests" in str(search_val_e):
                    if attempt < max_retries - 1:
                        sleep_time = 2 ** attempt * 2 # Exponential backoff: 2s, 4s, 8s
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
        response = client.search(query, search_depth="advanced", max_results=5)
        results = response.get('results', [])
        papers = [create_paper_from_tavily(r) for r in results]
        # Filter out papers that are clearly not academic if possible?
        # For now, just accept them as "General Web" findings.
        print(f"Web Scout found {len(papers)} papers.")
        return {"papers": papers, "logs": [f"Web Scout found {len(papers)} results."]}
    except Exception as e:
        print(f"Web Scout error: {e}")
        return {"papers": [], "logs": [f"Web Scout error: {str(e)}"]}

def pubmed_scout(state: ScientificDiscoveryState) -> Dict[str, Any]:
    query = state.get('scout_queries', {}).get('pubmed', state['query'])
    print(f"--- PubMed Scout searching for: {query} ---")
    
    try:
        # Search PubMed for PMIDs
        search_query = urllib.parse.quote(query)
        search_url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=pubmed&term={search_query}&retmode=json&retmax=5"
        
        req = urllib.request.Request(search_url, headers={'User-Agent': "Mozilla/5.0"})
        with urllib.request.urlopen(req) as response:
            search_data = json.loads(response.read().decode())
            
        pmids = search_data.get('esearchresult', {}).get('idlist', [])
        papers = []
        
        if pmids:
            # Fetch details for the PMIDs
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

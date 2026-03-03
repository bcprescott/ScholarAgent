import asyncio
import os
import unittest
from unittest.mock import patch, MagicMock, AsyncMock
from src.state import ScientificDiscoveryState, Paper
from src.graph import build_graph


def _make_mock_paper(title, url, source, doi=None, abstract="Mock abstract"):
    return Paper(
        title=title,
        url=url,
        source=source,
        doi=doi,
        abstract=abstract,
        authors=["Author A"],
        publication_date="2024-01-01",
    )


class TestScientificDiscovery(unittest.TestCase):

    @patch('src.agents.scouts.arxiv.Client')
    @patch('src.agents.scouts.SemanticScholar')
    @patch('src.agents.scouts.TavilyClient')
    @patch('src.agents.scouts.urllib.request.urlopen')
    @patch('src.agents.citation_explorer.urllib.request.urlopen')
    @patch('src.agents.fetcher.async_playwright')
    @patch('src.agents.fetcher.requests.get')
    @patch('src.agents.fetcher.fitz.open')
    @patch('src.llm.AzureOpenAI')
    def test_full_flow(
        self, mock_openai, mock_fitz, mock_requests,
        mock_async_pw, mock_cite_urlopen, mock_scout_urlopen,
        mock_tavily, mock_sem, mock_arxiv,
    ):
        print("Starting Test...")
        os.environ["MOCK_LLM"] = "true"
        os.environ["TAVILY_API_KEY"] = "mock_key"

        # --- MOCK SCOUTS ---

        # Mock ArXiv
        mock_arxiv_instance = mock_arxiv.return_value
        mock_arxiv_result = MagicMock()
        mock_arxiv_result.title = "Arxiv Paper Title"
        mock_arxiv_result.pdf_url = "http://arxiv.org/pdf/1234.pdf"
        mock_arxiv_result.summary = "Summary of Arxiv Paper"
        author_mock = MagicMock()
        author_mock.name = "Author A"
        mock_arxiv_result.authors = [author_mock]
        mock_arxiv_result.published = "2023-01-01"
        mock_arxiv_result.doi = "10.1234/arxiv"
        mock_arxiv_instance.results.return_value = [mock_arxiv_result]

        # Mock Semantic Scholar
        mock_sem_instance = mock_sem.return_value
        mock_sem_paper = MagicMock()
        mock_sem_paper.title = "Semantic Paper Title"
        mock_sem_paper.url = "http://semantic.org/paper"
        mock_sem_paper.abstract = "Abstract of Semantic Paper"
        mock_sem_paper.authors = [{'name': "Author B"}]
        mock_sem_paper.publicationDate = "2023-02-01"
        mock_sem_paper.externalIds = {'DOI': "10.1234/sem"}
        mock_sem_paper.paperId = '123'
        mock_sem_paper.openAccessPdf = None
        mock_sem_instance.search_paper.return_value = [mock_sem_paper]

        # Mock Tavily
        mock_tavily_instance = mock_tavily.return_value
        mock_tavily_instance.search.return_value = {
            'results': [{
                'title': "Web Paper Title",
                'url': "http://web.org/paper",
                'content': "Content of Web Paper"
            }]
        }

        # Mock urllib.request.urlopen for PubMed, OpenAlex, Europe PMC
        import json
        import io

        def mock_urlopen_for_scouts(req, timeout=None):
            url = req.full_url if hasattr(req, 'full_url') else str(req)

            if 'eutils.ncbi.nlm.nih.gov' in url and 'esearch' in url:
                data = json.dumps({'esearchresult': {'idlist': ['12345']}}).encode()
            elif 'eutils.ncbi.nlm.nih.gov' in url and 'efetch' in url:
                data = b"""<PubmedArticleSet>
                    <PubmedArticle>
                        <MedlineCitation>
                            <PMID>12345</PMID>
                            <Article>
                                <ArticleTitle>PubMed Paper Title</ArticleTitle>
                                <Abstract><AbstractText>PubMed abstract text.</AbstractText></Abstract>
                                <AuthorList><Author><LastName>Smith</LastName><Initials>J</Initials></Author></AuthorList>
                            </Article>
                        </MedlineCitation>
                        <PubmedData>
                            <ArticleIdList>
                                <ArticleId IdType="doi">10.1234/pubmed</ArticleId>
                            </ArticleIdList>
                            <History><PubMedPubDate PubStatus="pubmed"><Year>2024</Year></PubMedPubDate></History>
                        </PubmedData>
                    </PubmedArticle>
                </PubmedArticleSet>"""
            elif 'api.openalex.org' in url:
                data = json.dumps({
                    'results': [{
                        'id': 'https://openalex.org/W1',
                        'title': 'OpenAlex Paper Title',
                        'doi': 'https://doi.org/10.1234/openalex',
                        'authorships': [{'author': {'display_name': 'Author C'}}],
                        'publication_date': '2024-03-01',
                        'abstract_inverted_index': {'This': [0], 'is': [1], 'an': [2], 'abstract': [3]},
                        'primary_location': {'landing_page_url': 'http://openalex.org/paper', 'pdf_url': None},
                        'open_access': {'oa_url': 'http://openalex.org/paper'},
                        'type': 'article',
                    }]
                }).encode()
            elif 'europepmc.org' in url:
                data = json.dumps({
                    'resultList': {'result': [{
                        'title': 'Europe PMC Paper Title',
                        'doi': '10.1234/europepmc',
                        'pmid': '67890',
                        'abstractText': 'Europe PMC abstract.',
                        'authorString': 'Author D, Author E',
                        'pubYear': '2024',
                        'source': 'MED',
                        'id': '67890',
                    }]}
                }).encode()
            else:
                data = json.dumps({}).encode()

            mock_response = MagicMock()
            mock_response.read.return_value = data
            mock_response.__enter__ = MagicMock(return_value=mock_response)
            mock_response.__exit__ = MagicMock(return_value=False)
            return mock_response

        mock_scout_urlopen.side_effect = mock_urlopen_for_scouts

        # Mock urllib for citation explorer — return empty results to keep test fast
        def mock_urlopen_for_citations(req, timeout=None):
            url = req.full_url if hasattr(req, 'full_url') else str(req)
            if '/references' in url or '/citations' in url:
                data = json.dumps({'data': []}).encode()
            elif '/search' in url:
                data = json.dumps({'data': []}).encode()
            else:
                data = json.dumps({}).encode()

            mock_response = MagicMock()
            mock_response.read.return_value = data
            mock_response.__enter__ = MagicMock(return_value=mock_response)
            mock_response.__exit__ = MagicMock(return_value=False)
            return mock_response

        mock_cite_urlopen.side_effect = mock_urlopen_for_citations

        # --- MOCK FETCHER ---

        # Mock requests (for PDF fetch)
        mock_resp = MagicMock()
        mock_resp.content = b"%PDF-1.4..."
        mock_resp.raise_for_status = MagicMock()
        mock_requests.return_value = mock_resp

        # Mock PyMuPDF (fitz)
        mock_doc = MagicMock()
        mock_page = MagicMock()
        mock_page.get_text.return_value = "Full text from PDF."
        mock_doc.__enter__.return_value = [mock_page]
        mock_fitz.return_value = mock_doc

        # Mock async Playwright
        mock_browser = AsyncMock()
        mock_context = AsyncMock()
        mock_page_pw = AsyncMock()
        mock_page_pw.evaluate.return_value = "Full text from web via Playwright."

        mock_context.new_page.return_value = mock_page_pw
        mock_browser.new_context.return_value = mock_context

        mock_pw = AsyncMock()
        mock_pw.chromium.launch.return_value = mock_browser

        mock_async_pw.return_value.__aenter__ = AsyncMock(return_value=mock_pw)
        mock_async_pw.return_value.__aexit__ = AsyncMock(return_value=False)

        # --- BUILD & RUN ---

        print("Building Graph...")
        app = build_graph()

        initial_state = ScientificDiscoveryState(
            query="LLM in oncology",
            scout_queries={},
            papers=[],
            report="",
            logs=[]
        )

        print("Running Graph...")
        final_state = asyncio.run(app.ainvoke(initial_state))

        # --- ASSERTIONS ---

        print("Asserting Results...")

        # Papers were found
        self.assertGreater(len(final_state['papers']), 0)
        print(f"  Found {len(final_state['papers'])} papers")

        # Supervisor generated queries with new keys
        self.assertIn('arxiv', final_state['scout_queries'])
        print(f"  Scout queries: {list(final_state['scout_queries'].keys())}")

        # Multiple sources contributed
        sources = set(p.source for p in final_state['papers'])
        print(f"  Paper sources: {sources}")
        self.assertTrue(len(sources) >= 2, f"Expected multiple sources, got: {sources}")

        # Papers were analyzed (relevance score > 0)
        analyzed = [p for p in final_state['papers'] if p.relevance_score > 0]
        self.assertGreater(len(analyzed), 0)
        print(f"  Analyzed {len(analyzed)} papers")

        # Check new analysis fields are populated
        for p in analyzed:
            self.assertIsNotNone(p.key_findings)
            print(f"  Paper '{p.title}': score={p.relevance_score}, type={p.study_type}")

        # Report was generated
        self.assertIn("Research Synthesis", final_state['report'])
        print(f"  Report length: {len(final_state['report'])} chars")

        # Logs were collected
        self.assertGreater(len(final_state['logs']), 0)
        print(f"  Collected {len(final_state['logs'])} log entries")

        print("Test Passed!")


class TestMergePapers(unittest.TestCase):
    """Test the improved paper deduplication logic."""

    def test_dedup_by_url(self):
        from src.state import merge_papers
        papers1 = [_make_mock_paper("Paper A", "http://a.com", "arxiv")]
        papers2 = [_make_mock_paper("Paper A Copy", "http://a.com", "web")]
        result = merge_papers(papers1, papers2)
        self.assertEqual(len(result), 1)

    def test_dedup_by_doi(self):
        from src.state import merge_papers
        papers1 = [_make_mock_paper("Paper A", "http://a.com", "arxiv", doi="10.1234/test")]
        papers2 = [_make_mock_paper("Paper A", "http://b.com", "pubmed", doi="10.1234/test")]
        result = merge_papers(papers1, papers2)
        self.assertEqual(len(result), 1)

    def test_dedup_by_title(self):
        from src.state import merge_papers
        papers1 = [_make_mock_paper("Some Paper Title", "http://a.com", "arxiv")]
        papers2 = [_make_mock_paper("Some Paper Title", "http://b.com", "openalex")]
        result = merge_papers(papers1, papers2)
        self.assertEqual(len(result), 1)

    def test_unique_papers_kept(self):
        from src.state import merge_papers
        papers1 = [_make_mock_paper("Paper A", "http://a.com", "arxiv")]
        papers2 = [_make_mock_paper("Paper B", "http://b.com", "pubmed")]
        result = merge_papers(papers1, papers2)
        self.assertEqual(len(result), 2)

    def test_full_text_update(self):
        from src.state import merge_papers
        p1 = _make_mock_paper("Paper A", "http://a.com", "arxiv")
        p2 = _make_mock_paper("Paper A", "http://a.com", "arxiv")
        p2.full_text = "Full text content here"
        result = merge_papers([p1], [p2])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].full_text, "Full text content here")


class TestOpenAlexAbstract(unittest.TestCase):
    """Test the OpenAlex inverted index abstract reconstruction."""

    def test_reconstruct(self):
        from src.agents.scouts import reconstruct_abstract_from_inverted_index
        inverted = {"Hello": [0], "world": [1], "this": [2], "is": [3], "a": [4], "test": [5]}
        result = reconstruct_abstract_from_inverted_index(inverted)
        self.assertEqual(result, "Hello world this is a test")

    def test_empty(self):
        from src.agents.scouts import reconstruct_abstract_from_inverted_index
        self.assertIsNone(reconstruct_abstract_from_inverted_index(None))
        self.assertIsNone(reconstruct_abstract_from_inverted_index({}))


if __name__ == '__main__':
    unittest.main()

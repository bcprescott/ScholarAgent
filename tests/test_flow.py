import os
import unittest
from unittest.mock import patch, MagicMock
from src.state import ScientificDiscoveryState, Paper
from src.graph import build_graph

class TestScientificDiscovery(unittest.TestCase):
    @patch('src.agents.scouts.arxiv.Client')
    @patch('src.agents.scouts.SemanticScholar')
    @patch('src.agents.scouts.TavilyClient')
    @patch('src.agents.fetcher.requests.get')
    @patch('src.agents.fetcher.sync_playwright')
    @patch('src.agents.fetcher.Stealth')  # Patch Stealth class
    @patch('src.agents.fetcher.fitz.open')
    @patch('src.llm.AzureChatOpenAI')
    def test_full_flow(self, mock_openai, mock_fitz, mock_stealth, mock_playwright, mock_requests, mock_tavily, mock_sem, mock_arxiv):

        print("Starting Test...")
        # Force MOCK_LLM
        os.environ["MOCK_LLM"] = "true"
        os.environ["TAVILY_API_KEY"] = "mock_key"

        # --- MOCK SCOUTS ---

        # Mock Arxiv
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

        # Ensure results() returns an iterator
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
        # Emulate hasattr(item, 'raw_data') logic - not strictly needed if mock behaves well

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

        # --- MOCK FETCHER ---

        # Mock requests (for PDF fetch)
        mock_resp = MagicMock()
        mock_resp.content = b"%PDF-1.4..."
        mock_requests.return_value = mock_resp

        # Mock PyMuPDF (fitz)
        mock_doc = MagicMock()
        mock_page = MagicMock()
        mock_page.get_text.return_value = "Full text from PDF."
        mock_doc.__enter__.return_value = [mock_page]
        mock_fitz.return_value = mock_doc

        # Mock Playwright (for Web fetch)
        mock_p_ctx = mock_playwright.return_value.__enter__.return_value
        mock_browser = mock_p_ctx.chromium.launch.return_value
        mock_context = mock_browser.new_context.return_value
        mock_page_pw = mock_context.new_page.return_value
        mock_page_pw.evaluate.return_value = "Full text from web via Playwright."

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
        final_state = app.invoke(initial_state)

        # --- ASSERTIONS ---

        print("Asserting Results...")
        self.assertGreater(len(final_state['papers']), 0)

        # Check if Supervisor ran
        self.assertTrue('arxiv' in final_state['scout_queries'])

        # Check if papers were fetched
        fetched_texts = [p.full_text for p in final_state['papers'] if p.full_text]
        self.assertGreater(len(fetched_texts), 0)
        self.assertTrue(any("Full text from PDF" in t for t in fetched_texts))

        # Check if analyzed (relevance score > 0)
        analyzed = [p for p in final_state['papers'] if p.relevance_score > 0]
        # In mock LLM, we return a fixed JSON with score 85
        self.assertGreater(len(analyzed), 0)

        # Check Report
        self.assertIn("Report", final_state['report'])

        print("Test Passed!")

if __name__ == '__main__':
    unittest.main()

import os
import asyncio
import unittest
from unittest.mock import patch, MagicMock
from src.state import ScientificDiscoveryState, Paper, ResearchConfig
from src.graph import build_graph

class TestScientificDiscovery(unittest.TestCase):
    @patch('src.agents.scouts.arxiv.Client')
    @patch('src.agents.scouts.SemanticScholar')
    @patch('src.agents.scouts.TavilyClient')
    @patch('src.agents.fetcher.requests.get')
    @patch('src.agents.fetcher.sync_playwright')
    @patch('src.agents.fetcher.fitz.open')
    @patch('src.llm.AzureOpenAI')
    def test_full_flow(self, mock_openai, mock_fitz, mock_playwright, mock_requests, mock_tavily, mock_sem, mock_arxiv):

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

        # Only enable the scouts that have mocks
        config = ResearchConfig(
            max_results_per_source=5,
            enabled_sources=["arxiv", "pubmed", "semantic_scholar", "web"]
        )

        initial_state = ScientificDiscoveryState(
            query="LLM in oncology",
            scout_queries={},
            papers=[],
            report="",
            logs=[],
            config=config,
        )

        print("Running Graph (async)...")
        # Graph now has async nodes, so we must use ainvoke
        final_state = asyncio.run(app.ainvoke(initial_state))

        # --- ASSERTIONS ---

        print("Asserting Results...")
        self.assertGreater(len(final_state['papers']), 0)

        # Check if Supervisor ran — should include all scout keys
        self.assertTrue('arxiv' in final_state['scout_queries'])
        self.assertTrue('semantic_scholar' in final_state['scout_queries'])
        self.assertTrue('openalex' in final_state['scout_queries'])
        self.assertTrue('biorxiv' in final_state['scout_queries'])

        # Check if papers were fetched
        fetched_texts = [p.full_text for p in final_state['papers'] if p.full_text]
        self.assertGreater(len(fetched_texts), 0)
        self.assertTrue(any("Full text from PDF" in t for t in fetched_texts))

        # Check if analyzed (relevance score > 0)
        analyzed = [p for p in final_state['papers'] if p.relevance_score > 0]
        self.assertGreater(len(analyzed), 0)

        # Check new evidence grading fields
        for paper in analyzed:
            self.assertIsNotNone(paper.study_type, f"study_type should be set for {paper.title}")
            self.assertIsNotNone(paper.evidence_level, f"evidence_level should be set for {paper.title}")

        # Check Report
        self.assertIn("Report", final_state['report'])

        print("Test Passed!")

    def test_paper_dedup_by_doi(self):
        """Test that merge_papers deduplicates by DOI."""
        from src.state import merge_papers

        paper1 = Paper(title="Paper A", url="http://a.com", source="arxiv", doi="10.1234/test")
        paper2 = Paper(title="Paper A (copy)", url="http://b.com", source="pubmed", doi="10.1234/test")
        paper3 = Paper(title="Paper B", url="http://c.com", source="web", doi="10.5678/other")

        result = merge_papers([paper1], [paper2, paper3])
        self.assertEqual(len(result), 2)  # paper2 should be deduped via DOI
        urls = {p.url for p in result}
        self.assertIn("http://a.com", urls)
        self.assertIn("http://c.com", urls)
        print("DOI dedup test passed!")

    def test_paper_dedup_by_title(self):
        """Test that merge_papers deduplicates by fuzzy title match."""
        from src.state import merge_papers

        paper1 = Paper(title="Deep Learning for Cancer Detection", url="http://a.com", source="arxiv")
        paper2 = Paper(title="deep learning for cancer detection", url="http://b.com", source="pubmed")  # same title, different case
        paper3 = Paper(title="Something Completely Different", url="http://c.com", source="web")

        result = merge_papers([paper1], [paper2, paper3])
        self.assertEqual(len(result), 2)  # paper2 should be deduped via title
        print("Title dedup test passed!")

    def test_research_config_defaults(self):
        """Test ResearchConfig default values."""
        config = ResearchConfig()
        self.assertEqual(config.max_results_per_source, 10)
        self.assertEqual(config.relevance_threshold, 50.0)
        self.assertEqual(len(config.enabled_sources), 6)
        self.assertTrue(config.fetch_full_text)
        self.assertEqual(config.max_paper_chars, 20000)
        print("Config defaults test passed!")


if __name__ == '__main__':
    unittest.main()

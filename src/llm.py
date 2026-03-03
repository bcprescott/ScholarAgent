import os
from openai import AzureOpenAI, OpenAI

class MockChatCompletions:
    def create(self, model=None, messages=None, response_format=None, **kwargs):
        class MockMessage:
            def __init__(self, content):
                self.content = content
        class MockChoice:
            def __init__(self, message):
                self.message = message
        class MockResponse:
            def __init__(self, choices):
                self.choices = choices

        combined_text = "\n".join([m["content"] for m in messages if isinstance(m, dict) and "content" in m])
        response = "Mock response"

        if "research supervisor" in combined_text.lower() or "generate optimized search queries" in combined_text.lower():
             response = json.dumps({
                 "arxiv": "LLM oncology",
                 "pubmed": "large language models cancer treatment",
                 "semantic_scholar": "LLM applications in cancer treatment",
                 "web": "LLM oncology recent developments",
                 "openalex": "artificial intelligence oncology clinical",
                 "biorxiv": "machine learning cancer genomics"
             })
        elif "scientific analyst" in combined_text.lower() or "relevance_score" in combined_text.lower():
             response = json.dumps({
                 "relevance_score": 85,
                 "key_findings": "Found interesting things.",
                 "methodology": "Survey.",
                 "limitations": "Limited scope.",
                 "study_type": "review",
                 "evidence_level": "Level III",
                 "sample_size": None,
                 "confidence_notes": "Moderate confidence based on review methodology."
             })
        elif "scientific writer" in combined_text.lower():
             response = "# Report\n\n## Executive Summary\n\nThis is a mock report.\n\n## Key Findings\n\nMock findings.\n\n## Research Gaps\n\nMock gaps."

        return MockResponse(choices=[MockChoice(message=MockMessage(content=response))])

class MockChat:
    def __init__(self):
        self.completions = MockChatCompletions()

class MockAzureOpenAI:
    def __init__(self):
        self.chat = MockChat()

def get_model_name():
    if os.environ.get("USE_LMSTUDIO") == "true":
        return os.environ.get("LMSTUDIO_MODEL_NAME", "local-model")
    return os.environ.get("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4")

def get_llm():
    if os.environ.get("MOCK_LLM") == "true":
        print("Using Mock LLM")
        return MockAzureOpenAI()

    if os.environ.get("USE_LMSTUDIO") == "true":
        print("Using LM Studio API")
        return OpenAI(base_url="http://localhost:1234/v1", api_key="lm-studio")

    api_version = os.environ.get("AZURE_OPENAI_API_VERSION", "2024-12-01-preview").strip().strip('"').strip("'")
    azure_endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT", "https://ragapp-openai.openai.azure.com/").strip().strip('"').strip("'")
    api_key_env = os.environ.get("AZURE_OPENAI_API_KEY")
    api_key = api_key_env.strip().strip('"').strip("'") if api_key_env else None

    return AzureOpenAI(
        api_version=api_version,
        azure_endpoint=azure_endpoint,
        api_key=api_key
    )

# Need json import for mock
import json

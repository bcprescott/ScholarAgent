import os
from openai import AzureOpenAI, OpenAI

class MockChatCompletions:
    def create(self, model=None, messages=None, **kwargs):
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

        if "generate optimized search queries" in combined_text:
             response = '{"arxiv": "LLM oncology", "pubmed": "LLM cancer treatment clinical", "semantic_scholar": "LLM applications in cancer treatment", "web": "LLM oncology recent developments"}'
        elif "relevance_score" in combined_text or "scientific analyst" in combined_text.lower():
             response = '{"relevance_score": 85, "key_findings": "Found interesting things.", "methodology": "Survey.", "limitations": "Limited scope.", "study_type": "literature review", "evidence_level": "moderate", "confidence_notes": "Based on a review of existing literature."}'
        elif "scientific review writer" in combined_text.lower() or "research synthesis" in combined_text.lower():
             response = "# Research Synthesis: LLM in Oncology\n\n## Executive Summary\nThis is a mock report.\n\n## References\n[1] Mock Paper"

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

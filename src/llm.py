import os
from langchain_openai import AzureChatOpenAI
from langchain_core.language_models import BaseChatModel

class MockChatModel(BaseChatModel):
    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        from langchain_core.outputs import ChatGeneration, ChatResult
        from langchain_core.messages import AIMessage

        # Simple mock logic
        # messages is a list of BaseMessage
        combined_text = "\n".join([m.content for m in messages])

        response = "Mock response"

        if "generate optimized search queries" in combined_text:
             response = '{"arxiv": "LLM oncology", "semantic_scholar": "LLM applications in cancer treatment", "web": "LLM oncology pdf"}'
        elif "Analyze the provided text" in combined_text or "relevance_score" in combined_text:
             response = '{"relevance_score": 85, "key_findings": "Found interesting things.", "methodology": "Survey.", "limitations": "Limited scope."}'
        elif "scientific writer" in combined_text:
             response = "# Report\n\nThis is a mock report."

        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=response))])

    @property
    def _llm_type(self) -> str:
        return "mock"

def get_llm() -> BaseChatModel:
    if os.environ.get("MOCK_LLM") == "true" or not os.environ.get("AZURE_OPENAI_API_KEY"):
        print("Using Mock LLM")
        return MockChatModel()

    return AzureChatOpenAI(
        azure_deployment=os.environ.get("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4"),
        openai_api_version=os.environ.get("AZURE_OPENAI_API_VERSION", "2023-05-15"),
        azure_endpoint=os.environ.get("AZURE_OPENAI_ENDPOINT"),
        api_key=os.environ.get("AZURE_OPENAI_API_KEY"),
        temperature=0
    )

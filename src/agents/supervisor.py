from src.state import ScientificDiscoveryState
from src.llm import get_llm, get_model_name
import json
import re
import os

def parse_json(text):
    try:
        # Try finding JSON block in ```json ... ``` first
        match = re.search(r'```json\s*(.*?)\s*```', text, re.DOTALL)
        if match:
            return json.loads(match.group(1))
        # Try finding any JSON object
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            return json.loads(match.group(0))
        return json.loads(text)
    except Exception:
        return None

def supervisor_agent(state: ScientificDiscoveryState):
    llm = get_llm()
    query = state['query']

    messages = [
        {"role": "system", "content": (
            "You are a research supervisor. Given the user query, generate optimized search queries "
            "for each of these academic repositories:\n"
            "1. 'arxiv' — technical/scientific terms, focus on CS, physics, math, quantitative biology\n"
            "2. 'pubmed' — medical/clinical keywords, MeSH-style terms\n"
            "3. 'semantic_scholar' — broad academic terms covering all disciplines\n"
            "4. 'web' — broad search for recent developments, news, reviews, or grey literature\n\n"
            "Make sure all queries are optimized for their target repository and will return "
            "the most recent and relevant papers. Include year references where appropriate.\n\n"
            "Return strictly valid JSON with keys: 'arxiv', 'pubmed', 'semantic_scholar', 'web'."
        )},
        {"role": "user", "content": f"Query: {query}"}
    ]

    response = llm.chat.completions.create(
        model=get_model_name(),
        messages=messages,
        response_format={"type": "json_object"}
    )
    result_content = response.choices[0].message.content

    scout_queries = parse_json(result_content)

    if not scout_queries:
        print(f"Failed to parse JSON from supervisor: {result_content}")
        # Fallback
        scout_queries = {
            'arxiv': query,
            'pubmed': query,
            'semantic_scholar': query,
            'web': query,
        }

    return {"scout_queries": scout_queries, "logs": [f"Supervisor generated queries: {scout_queries}"]}

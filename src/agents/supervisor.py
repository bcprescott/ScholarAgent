from src.state import ScientificDiscoveryState
from src.llm import get_llm, get_model_name
import json
import re
import os

def parse_json(text):
    try:
        # Try finding JSON block
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
        {"role": "system", "content": "You are a research supervisor. Given the user query, generate 3 optimized search queries, one for each repository: 1. 'arxiv' (focus on technical/scientific terms), 2. 'pubmed' (medical/clinical keywords), 3. 'web' (broad search for recent developments or missed papers). Make sure all queries cover the current year and will return the most recent and relevant papers first. Return strictly valid JSON with keys: 'arxiv', 'pubmed', 'web'."},
        {"role": "user", "content": f"Query: {query}"}
    ]

    response = llm.chat.completions.create(
        model=get_model_name(),
        messages=messages
        # ,
        # temperature=0
    )
    result_content = response.choices[0].message.content

    scout_queries = parse_json(result_content)

    if not scout_queries:
        print(f"Failed to parse JSON from supervisor: {result_content}")
        # Fallback
        scout_queries = {'arxiv': query, 'pubmed': query, 'web': query}

    return {"scout_queries": scout_queries, "logs": [f"Supervisor generated queries: {scout_queries}"]}

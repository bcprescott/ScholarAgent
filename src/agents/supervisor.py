from langchain_core.prompts import ChatPromptTemplate
from src.state import ScientificDiscoveryState
from src.llm import get_llm
import json
import re

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

    # Prompt for keyword generation
    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are a research supervisor. Given the user query, generate 3 optimized search queries, one for each repository: 1. 'arxiv' (focus on technical/scientific terms), 2. 'semantic_scholar' (academic keywords), 3. 'web' (broad search for recent developments or missed papers). Return strictly valid JSON with keys: 'arxiv', 'semantic_scholar', 'web'."),
        ("human", "Query: {query}")
    ])

    chain = prompt | llm
    result = chain.invoke({"query": query})

    scout_queries = parse_json(result.content)

    if not scout_queries:
        print(f"Failed to parse JSON from supervisor: {result.content}")
        # Fallback
        scout_queries = {'arxiv': query, 'semantic_scholar': query, 'web': query}

    return {"scout_queries": scout_queries, "logs": [f"Supervisor generated queries: {scout_queries}"]}

from src.state import ScientificDiscoveryState
from src.llm import get_llm, get_model_name
import json
import re
import os
from datetime import datetime

ALL_SCOUT_KEYS = ['arxiv', 'pubmed', 'semantic_scholar', 'web', 'openalex', 'biorxiv']

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
    current_year = datetime.now().year
    previous_year = current_year - 1

    messages = [
        {"role": "system", "content": (
            f"You are a research supervisor. The current year is {current_year}. "
            "Given the user query, generate optimized search queries "
            "for each of the following 6 academic repositories:\n"
            "1. 'arxiv' — focus on technical/scientific terms, physics, CS, math\n"
            "2. 'pubmed' — medical/clinical/biomedical keywords\n"
            "3. 'semantic_scholar' — broad academic search with precise terminology\n"
            "4. 'web' — broad search for recent developments, news, or grey literature\n"
            "5. 'openalex' — cross-disciplinary academic search, social sciences, humanities, engineering\n"
            "6. 'biorxiv' — preprint search for cutting-edge biological/medical research\n\n"
            "CRITICAL RULES:\n"
            "- Generate PLAIN TEXT keyword queries ONLY. Do NOT use any API-specific syntax.\n"
            f"- By default, include '{current_year}' and '{previous_year}' in queries to get recent papers, "
            "unless the user specifies a different time period.\n"
            "- Do NOT include field prefixes (e.g., title:, abstract:, submittedDate:), date filters, "
            "boolean operators (AND/OR), or any special query language.\n"
            "- Just use natural language keywords and phrases that describe what to search for.\n"
            "- Each query should be a short phrase of 3-8 words tailored to that repository's domain.\n\n"
            "Return strictly valid JSON with keys: 'arxiv', 'pubmed', 'semantic_scholar', "
            "'web', 'openalex', 'biorxiv'."
        )},
        {"role": "user", "content": f"Query: {query}"}
    ]

    try:
        response = llm.chat.completions.create(
            model=get_model_name(),
            messages=messages,
            response_format={"type": "json_object"}
        )
        result_content = response.choices[0].message.content
        scout_queries = parse_json(result_content)
    except Exception as e:
        print(f"Supervisor LLM error: {e}")
        scout_queries = None

    if not scout_queries:
        print(f"Failed to parse JSON from supervisor, using fallback queries.")
        scout_queries = {key: query for key in ALL_SCOUT_KEYS}

    # Ensure all keys exist (fill in missing ones with raw query)
    for key in ALL_SCOUT_KEYS:
        if key not in scout_queries:
            scout_queries[key] = query

    return {"scout_queries": scout_queries, "logs": [f"Supervisor generated queries: {scout_queries}"]}

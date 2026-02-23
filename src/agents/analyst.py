import json
import re
from langchain_core.prompts import ChatPromptTemplate
from src.state import ScientificDiscoveryState, Paper
from src.llm import get_llm
from typing import List, Dict, Any

def parse_json(text):
    try:
        # Try finding JSON block
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            return json.loads(match.group(0))
        # Sometimes LLM returns ```json ... ```
        match = re.search(r'```json\s*(.*?)\s*```', text, re.DOTALL)
        if match:
            return json.loads(match.group(1))
        return json.loads(text)
    except Exception:
        return None

def analyze_paper(paper: Paper, query: str, llm) -> Paper:
    # If no text, can't analyze deeply, but use abstract
    text = paper.full_text if paper.full_text else paper.abstract
    if not text:
        return paper

    # Truncate to avoid context limits (e.g., 8k tokens)
    # Estimate 1 token ~= 4 chars, so 30k chars is safe-ish for 128k context, but let's be conservative
    # For GPT-4o-mini or similar, we have large context.
    # Let's cap at 20000 chars for safety/cost.
    text_snippet = text[:20000]

    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are a scientific analyst. Analyze the provided text in relation to the query: '{query}'. "
                   "Extract the following information as a JSON object: "
                   "1. relevance_score (integer 0-100), "
                   "2. key_findings (string summary), "
                   "3. methodology (string summary), "
                   "4. limitations (string summary). "
                   "If the text is not relevant, give a low score."),
        ("human", "Text: {text}")
    ])

    try:
        chain = prompt | llm
        result = chain.invoke({"query": query, "text": text_snippet})
        data = parse_json(result.content)

        if data:
            paper.relevance_score = float(data.get('relevance_score', 0))
            paper.key_findings = data.get('key_findings', "Not found")
            paper.methodology = data.get('methodology', "Not found")
            paper.limitations = data.get('limitations', "Not found")
        else:
             print(f"Failed to parse analysis JSON for {paper.title}: {result.content}")

    except Exception as e:
        print(f"Error analyzing paper {paper.title}: {e}")

    return paper

def analyst_agent(state: ScientificDiscoveryState) -> Dict[str, Any]:
    llm = get_llm()
    query = state['query']
    papers = state.get('papers', [])
    updated_papers = []
    logs = []

    print(f"--- Analyst Agent: Analyzing {len(papers)} papers ---")

    for paper in papers:
        # Skip if already analyzed (optimization)
        if paper.relevance_score > 0 or paper.key_findings:
             updated_papers.append(paper)
             continue

        analyzed_paper = analyze_paper(paper, query, llm)
        updated_papers.append(analyzed_paper)
        logs.append(f"Analyzed {paper.title} (Score: {paper.relevance_score})")

    return {"papers": updated_papers, "logs": logs}

def writer_agent(state: ScientificDiscoveryState) -> Dict[str, Any]:
    llm = get_llm()
    query = state['query']
    papers = state.get('papers', [])

    # Filter relevant papers
    relevant_papers = [p for p in papers if p.relevance_score >= 50]
    if not relevant_papers:
        # Fallback to top 3 by score even if low
        relevant_papers = sorted(papers, key=lambda p: p.relevance_score, reverse=True)[:3]

    print(f"--- Writer Agent: Synthesizing report from {len(relevant_papers)} papers ---")

    context = ""
    for p in relevant_papers:
        context += f"## {p.title}\n"
        context += f"Source: {p.source}\n"
        context += f"URL: {p.url}\n"
        context += f"DOI: {p.doi}\n"
        context += f"Score: {p.relevance_score}\n"
        context += f"Findings: {p.key_findings}\n"
        context += f"Methodology: {p.methodology}\n"
        context += f"Limitations: {p.limitations}\n\n"

    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are a scientific writer. Write a comprehensive Markdown report answering the query: '{query}'. "
                   "Use the provided analysis of relevant papers. "
                   "Cite sources using the provided DOIs or URLs. "
                   "Structure the report with: Executive Summary, Key Findings, Methodologies, Limitations, and References."),
        ("human", "Papers Analysis:\n{context}")
    ])

    try:
        chain = prompt | llm
        result = chain.invoke({"query": query, "context": context})
        report = result.content
        logs = ["Report generated successfully."]
    except Exception as e:
        report = f"Error generating report: {str(e)}"
        logs = [f"Writer error: {str(e)}"]

    return {"report": report, "logs": logs}

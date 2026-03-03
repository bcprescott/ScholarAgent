import asyncio
import json
import re
import os
from src.state import ScientificDiscoveryState, Paper
from src.llm import get_llm, get_model_name
from typing import List, Dict, Any

MAX_CONCURRENT_ANALYSES = 5
MAX_PAPER_CHARS = 20000
RELEVANCE_THRESHOLD = 50.0


def parse_json(text):
    try:
        match = re.search(r'```json\s*(.*?)\s*```', text, re.DOTALL)
        if match:
            return json.loads(match.group(1))
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            return json.loads(match.group(0))
        return json.loads(text)
    except Exception:
        return None


def analyze_paper(paper: Paper, query: str, llm) -> Paper:
    """Analyze a single paper using the LLM. Returns the paper with analysis fields populated."""
    text = paper.full_text if paper.full_text else paper.abstract
    if not text:
        return paper

    text_snippet = text[:MAX_PAPER_CHARS]

    messages = [
        {"role": "system", "content": (
            f"You are a scientific analyst. Analyze the provided text in relation to the query: '{query}'.\n\n"
            "Extract the following information as a JSON object:\n"
            "1. relevance_score (integer 0-100): How relevant is this to the query? "
            "If the general topic aligns, score 70-100. Only score low if completely unrelated.\n"
            "2. key_findings (string): Summarize the main findings and contributions.\n"
            "3. methodology (string): Describe the research methods used.\n"
            "4. limitations (string): Note any limitations or caveats.\n"
            "5. study_type (string): Classify the study type — e.g., 'meta-analysis', 'randomized controlled trial', "
            "'systematic review', 'observational study', 'case study', 'computational study', "
            "'literature review', 'commentary', 'preprint', or 'other'.\n"
            "6. evidence_level (string): Rate evidence quality — 'high' (meta-analyses, large RCTs), "
            "'moderate' (smaller RCTs, strong observational), 'low' (case studies, expert opinion), "
            "or 'preliminary' (preprints, early-stage research).\n"
            "7. confidence_notes (string): Brief note on why evidence is strong or weak.\n\n"
            "Return strictly valid JSON with these keys."
        )},
        {"role": "user", "content": f"Text: {text_snippet}"}
    ]

    try:
        response = llm.chat.completions.create(
            model=get_model_name(),
            messages=messages,
            response_format={"type": "json_object"}
        )
        result_content = response.choices[0].message.content
        data = parse_json(result_content)

        if data:
            paper.relevance_score = float(data.get('relevance_score', 0))
            paper.key_findings = data.get('key_findings', "Not found")
            paper.methodology = data.get('methodology', "Not found")
            paper.limitations = data.get('limitations', "Not found")
            paper.study_type = data.get('study_type')
            paper.evidence_level = data.get('evidence_level')
            paper.confidence_notes = data.get('confidence_notes')
        else:
            print(f"Failed to parse analysis JSON for {paper.title}: {result_content}")

    except Exception as e:
        print(f"Error analyzing paper {paper.title}: {e}")

    return paper


async def analyst_agent(state: ScientificDiscoveryState) -> Dict[str, Any]:
    """Analyze all papers in parallel using asyncio + thread pool for LLM calls."""
    llm = get_llm()
    query = state['query']
    papers = state.get('papers', [])

    print(f"--- Analyst Agent: Analyzing {len(papers)} papers (up to {MAX_CONCURRENT_ANALYSES} concurrent) ---")

    sem = asyncio.Semaphore(MAX_CONCURRENT_ANALYSES)

    async def analyze_one(paper: Paper) -> Paper:
        # Skip if already analyzed
        if paper.relevance_score > 0 or paper.key_findings:
            return paper
        async with sem:
            return await asyncio.to_thread(analyze_paper, paper, query, llm)

    tasks = [analyze_one(p) for p in papers]
    updated_papers = await asyncio.gather(*tasks)

    logs = []
    for p in updated_papers:
        if p.relevance_score > 0:
            logs.append(f"Analyzed '{p.title}' — Score: {p.relevance_score}, Type: {p.study_type or 'unknown'}")
            print(f"Analyzed '{p.title}' (Score: {p.relevance_score})")

    return {"papers": list(updated_papers), "logs": logs}


def writer_agent(state: ScientificDiscoveryState) -> Dict[str, Any]:
    llm = get_llm()
    query = state['query']
    papers = state.get('papers', [])

    # Filter relevant papers
    relevant_papers = [p for p in papers if p.relevance_score >= RELEVANCE_THRESHOLD]
    if not relevant_papers:
        # Fallback to top papers by score even if below threshold
        relevant_papers = sorted(papers, key=lambda p: p.relevance_score, reverse=True)[:5]

    print(f"--- Writer Agent: Synthesizing report from {len(relevant_papers)} papers ---")

    # Build rich context for the writer
    context = ""
    for i, p in enumerate(relevant_papers, 1):
        context += f"[{i}] {p.title}\n"
        context += f"  Source: {p.source}\n"
        context += f"  URL: {p.url}\n"
        if p.doi:
            context += f"  DOI: {p.doi}\n"
        if p.authors:
            context += f"  Authors: {', '.join(p.authors[:5])}\n"
        if p.publication_date:
            context += f"  Published: {p.publication_date}\n"
        context += f"  Relevance Score: {p.relevance_score}\n"
        if p.study_type:
            context += f"  Study Type: {p.study_type}\n"
        if p.evidence_level:
            context += f"  Evidence Level: {p.evidence_level}\n"
        if p.confidence_notes:
            context += f"  Confidence: {p.confidence_notes}\n"
        context += f"  Key Findings: {p.key_findings}\n"
        context += f"  Methodology: {p.methodology}\n"
        context += f"  Limitations: {p.limitations}\n\n"

    messages = [
        {"role": "system", "content": (
            f"You are an expert scientific review writer producing a comprehensive research synthesis.\n\n"
            f"Write a detailed Markdown report answering the research query: '{query}'\n\n"
            "CRITICAL INSTRUCTIONS:\n"
            "- Do NOT just summarize each paper sequentially. SYNTHESIZE across papers.\n"
            "- Compare, contrast, and draw connections between findings from different studies.\n"
            "- Write like the author of a systematic review article, not a bibliography compiler.\n"
            "- Weight findings by evidence quality — meta-analyses and large RCTs carry more weight "
            "than case studies or preliminary preprints.\n"
            "- Cite sources inline using [N] notation matching the reference numbers provided.\n\n"
            "Structure your report as follows:\n\n"
            f"# Research Synthesis: {query}\n\n"
            "## Executive Summary\n"
            "2-3 paragraphs directly answering the research question based on the evidence found.\n\n"
            "## Background & Context\n"
            "Why this question matters and the current state of knowledge.\n\n"
            "## Key Findings\n"
            "Organize THEMATICALLY by sub-topic. Under each theme, discuss what multiple papers found, "
            "where they agree, and where they differ.\n\n"
            "## Strength of Evidence\n"
            "Which findings are well-supported by multiple high-quality studies? "
            "Which are preliminary or based on limited evidence?\n\n"
            "## Contradictions & Open Debates\n"
            "Where do studies disagree? What might explain the discrepancies?\n\n"
            "## Research Gaps\n"
            "What questions remain unanswered? What areas need more investigation?\n\n"
            "## Practical Implications\n"
            "Actionable takeaways for researchers, clinicians, or practitioners.\n\n"
            "## Methodology Overview\n"
            "Common approaches used across the literature.\n\n"
            "## Limitations\n"
            "Limitations of the evidence base and of this review itself.\n\n"
            "## References\n"
            "Numbered list of all cited papers with title, authors, source, year, and DOI/URL.\n"
        )},
        {"role": "user", "content": f"Papers Analysis:\n{context}"}
    ]

    try:
        response = llm.chat.completions.create(
            model=get_model_name(),
            messages=messages,
        )
        report = response.choices[0].message.content
        logs = ["Report generated successfully."]
        print("Report generated successfully.")
    except Exception as e:
        report = f"Error generating report: {str(e)}"
        logs = [f"Writer error: {str(e)}"]

    return {"report": report, "logs": logs}

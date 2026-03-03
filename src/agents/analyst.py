import json
import re
import os
import asyncio
from src.state import ScientificDiscoveryState, Paper, ResearchConfig
from src.llm import get_llm, get_model_name
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


def _get_config(state: ScientificDiscoveryState) -> ResearchConfig:
    """Get config from state, or return defaults."""
    config = state.get('config')
    if config:
        return config
    return ResearchConfig()


FULL_TEXT_ANALYSIS_PROMPT = (
    "You are a scientific analyst. Analyze the provided text in relation to the query: '{query}'.\n\n"
    "Extract the following information as a JSON object:\n"
    "1. relevance_score (integer 0-100) — if the general topic aligns with the query, score 70-100; only score low if completely unrelated\n"
    "2. key_findings (string) — main results and conclusions\n"
    "3. methodology (string) — research methods used\n"
    "4. limitations (string) — weaknesses, gaps, caveats\n"
    "5. study_type (string) — classify as one of: 'meta-analysis', 'systematic-review', 'RCT', "
    "'cohort-study', 'case-control', 'case-study', 'computational', 'review', 'editorial', 'other'\n"
    "6. evidence_level (string) — rate as: 'Level I' (systematic reviews/meta-analyses), "
    "'Level II' (RCTs), 'Level III' (controlled studies), 'Level IV' (case series/cohort), "
    "'Level V' (expert opinion/case reports)\n"
    "7. sample_size (integer or null) — number of participants/samples if applicable\n"
    "8. confidence_notes (string) — brief explanation of why the evidence is strong or weak\n\n"
    "Return ONLY valid JSON."
)

ABSTRACT_ONLY_PROMPT = (
    "You are a scientific analyst. You have ONLY the abstract of a paper (full text was unavailable). "
    "Analyze it in relation to the query: '{query}'.\n\n"
    "Because you only have the abstract, be conservative in your assessments and note this limitation. "
    "Extract the following as JSON:\n"
    "1. relevance_score (integer 0-100) — based on abstract alignment with query\n"
    "2. key_findings (string) — findings mentioned in the abstract\n"
    "3. methodology (string) — any methods mentioned, or 'Not available from abstract'\n"
    "4. limitations (string) — note that full text was unavailable, plus any mentioned limitations\n"
    "5. study_type (string) — best guess from abstract: 'meta-analysis', 'systematic-review', 'RCT', "
    "'cohort-study', 'case-control', 'case-study', 'computational', 'review', 'editorial', 'other'\n"
    "6. evidence_level (string) — 'Level I' through 'Level V' (best guess from abstract)\n"
    "7. sample_size (integer or null)\n"
    "8. confidence_notes (string) — note limited confidence due to abstract-only analysis\n\n"
    "Return ONLY valid JSON."
)


async def analyze_paper_async(paper: Paper, query: str, llm, config: ResearchConfig, semaphore: asyncio.Semaphore) -> Paper:
    """Analyze a single paper with concurrency control."""
    async with semaphore:
        # Determine if we have full text or just abstract
        has_full_text = bool(paper.full_text)
        text = paper.full_text if has_full_text else paper.abstract
        if not text:
            return paper

        # Truncate to configured limit
        max_chars = config.max_paper_chars
        text_snippet = text[:max_chars]

        # Choose prompt based on available text
        if has_full_text:
            system_prompt = FULL_TEXT_ANALYSIS_PROMPT.format(query=query)
        else:
            system_prompt = ABSTRACT_ONLY_PROMPT.format(query=query)

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Text: {text_snippet}"}
        ]

        try:
            # Run the synchronous LLM call in a thread to not block the event loop
            response = await asyncio.to_thread(
                llm.chat.completions.create,
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
                sample = data.get('sample_size')
                paper.sample_size = int(sample) if sample and str(sample).isdigit() else None
                paper.confidence_notes = data.get('confidence_notes')
            else:
                print(f"Failed to parse analysis JSON for {paper.title}: {result_content}")

        except Exception as e:
            print(f"Error analyzing paper {paper.title}: {e}")

        return paper


async def analyst_agent(state: ScientificDiscoveryState) -> Dict[str, Any]:
    llm = get_llm()
    query = state['query']
    papers = state.get('papers', [])
    config = _get_config(state)
    logs = []

    print(f"--- Analyst Agent: Analyzing {len(papers)} papers (parallel) ---")

    # Separate already-analyzed from needing-analysis
    already_analyzed = []
    to_analyze = []
    for paper in papers:
        if paper.relevance_score > 0 or paper.key_findings:
            already_analyzed.append(paper)
        else:
            to_analyze.append(paper)

    # Parallel analysis with semaphore (max 5 concurrent LLM calls)
    semaphore = asyncio.Semaphore(5)
    tasks = [
        analyze_paper_async(paper, query, llm, config, semaphore)
        for paper in to_analyze
    ]
    analyzed = await asyncio.gather(*tasks, return_exceptions=True)

    updated_papers = list(already_analyzed)
    for result in analyzed:
        if isinstance(result, Exception):
            print(f"Analysis task failed: {result}")
            continue
        updated_papers.append(result)
        logs.append(f"Analyzed {result.title} (Score: {result.relevance_score})")
        print(f"Analyzed {result.title} (Score: {result.relevance_score})")

    return {"papers": updated_papers, "logs": logs}


WRITER_SYSTEM_PROMPT = """You are a scientific writer producing a comprehensive literature review report.

Structure your report as follows:

1. **Executive Summary** (2-3 paragraphs directly answering the query)
2. **Background & Context** (why this question matters, brief field overview)
3. **Key Findings** (organized THEMATICALLY, NOT paper-by-paper — group related findings together)
4. **Strength of Evidence** (which findings are well-supported by multiple studies vs. preliminary/single-study findings; reference study types and evidence levels)
5. **Contradictions & Debates** (where studies disagree and possible reasons why)
6. **Research Gaps** (what questions remain unanswered in the current literature)
7. **Practical Implications** (actionable takeaways for researchers, clinicians, or practitioners)
8. **Methodology Notes** (common approaches in the reviewed literature, their strengths and weaknesses)
9. **References** (formatted as numbered citations with DOIs/URLs)

IMPORTANT RULES:
- Do NOT just summarize each paper sequentially. SYNTHESIZE across papers — compare, contrast, and draw connections.
- Write like a review article author, not a bibliography compiler.
- Weight findings by evidence quality: a meta-analysis of 50 RCTs carries more weight than a single case report.
- Use proper Markdown formatting with headers, bold text, and bullet points for readability.
- Cite sources inline using [Author, Year] or numbered references.

Query: '{query}'"""


def writer_agent(state: ScientificDiscoveryState) -> Dict[str, Any]:
    llm = get_llm()
    query = state['query']
    papers = state.get('papers', [])
    config = _get_config(state)

    # Filter relevant papers using configurable threshold
    threshold = config.relevance_threshold
    relevant_papers = [p for p in papers if p.relevance_score >= threshold]
    if not relevant_papers:
        # Fallback to top 5 by score even if low
        relevant_papers = sorted(papers, key=lambda p: p.relevance_score, reverse=True)[:5]

    print(f"--- Writer Agent: Synthesizing report from {len(relevant_papers)} papers ---")

    context = ""
    for i, p in enumerate(relevant_papers, 1):
        context += f"## [{i}] {p.title}\n"
        context += f"Source: {p.source}\n"
        context += f"URL: {p.url}\n"
        context += f"DOI: {p.doi}\n"
        context += f"Relevance Score: {p.relevance_score}\n"
        context += f"Study Type: {p.study_type or 'Not classified'}\n"
        context += f"Evidence Level: {p.evidence_level or 'Not assessed'}\n"
        context += f"Sample Size: {p.sample_size or 'N/A'}\n"
        context += f"Findings: {p.key_findings}\n"
        context += f"Methodology: {p.methodology}\n"
        context += f"Limitations: {p.limitations}\n"
        context += f"Confidence: {p.confidence_notes or 'N/A'}\n\n"

    messages = [
        {"role": "system", "content": WRITER_SYSTEM_PROMPT.format(query=query)},
        {"role": "user", "content": f"Papers Analysis:\n{context}"}
    ]

    try:
        response = llm.chat.completions.create(
            model=get_model_name(),
            messages=messages
        )
        report = response.choices[0].message.content
        logs = ["Report generated successfully."]
        print("Report generated successfully.")
    except Exception as e:
        report = f"Error generating report: {str(e)}"
        logs = [f"Writer error: {str(e)}"]

    return {"report": report, "logs": logs}

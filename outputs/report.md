Executive Summary
Recent work applying large language models (LLMs) to liver disease research is primarily exploratory and concept-proving, aiming to augment risk prediction, guideline-consistent decision support, and knowledge retrieval within hepatology. Notable developments include: (1) proof-of-concept use of GPT-4 and GPT-3.5 to predict advanced MASLD-related fibrosis from seven clinical variables with high AUROC and good calibration, though external validation remains essential; (2) development of LiVersa, a liver-disease–specific, retrieval-augmented LLM that negotiates PHI-compliant guideline content to answer liver-health questions, achieving perfect performance on a forced yes/no task but with incomplete rationales in some HBV/HCC scenarios; (3) broad AI/hepatology reviews highlighting potential roles for LLMs in case identification, data extraction, and decision support across modalities (imaging, histology, multi-omics), while emphasizing stringent validation, interpretability, and ethical/regulatory considerations; (4) real-world evidence from a nationwide registry showing LLMs can mirror physician treatment decisions in a subset of straightforward early-stage cases in HCC, with survival associations suggesting LLMs may supplement but not substitute clinical judgment in complex situations; and (5) media/synthesis pieces echoing the same translational limitations and need for prospective validation. Across these works, the consensus is that LLMs show promise as decision-support and knowledge-access tools in liver disease research, but are not yet ready for broad clinical adoption without further rigorous validation, generalizability testing, and careful integration into workflows.

Key Findings
- Prediction of advanced liver fibrosis using seven clinical variables
  - Source: Cureus analysis of NHANES 2017–2020 data
  - Findings: GPT-4 and GPT-3.5 can predict advanced MASLD fibrosis (≥F3) with AUROCs of 0.91 and 0.90, respectively; GPT-4 showed superior specificity versus traditional scores like FIB-4; outputs included interpretable risk percentages and brief rationales.
  - Significance: Demonstrates feasibility of parsimonious, prompt-based LLMs for noninvasive fibrosis risk stratification using routine clinical data.
  - Caveats: Derivation cohort (N=162 MASLD participants) from a single public dataset; cross-sectional design; reliance on composite MASLD/fibrosis definitions rather than universal biopsy standards; external validation in diverse populations is needed.
  - References: https://www.cureus.com/articles/438782-using-large-language-models-to-predict-advanced-liver-fibrosis-in-metabolic-dysfunction-associated-steatotic-liver-disease-masld-a-proof-of-concept-analysis.pdf

- Liver-disease–specific LLM with retrieval augmentation (LiVersa)
  - Source: LiVersa study (PMC10659484)
  - Findings: A liver-disease–specific LLM (LiVersa) using retrieval-augmented generation (RAG) embedded 30 AASLD guideline documents; content retrieved in real time and answered with GPT-3.5-turbo or GPT-4-32k. In evaluation, LiVersa achieved perfect performance on a forced yes/no assessment (10/10) but produced incompletely correct rationales for three HBV/HCC scenarios.
  - Significance: Demonstrates feasibility of distilling liver guidelines into a PHI-compliant, domain-focused LLM and leveraging real-time content retrieval to support clinical questions.
  - Caveats: Limited to 30 guideline documents; evaluation centered on HBV/HCC case vignettes; preprint at the time with subsequent peer-reviewed updates; performance depends on the quality and scope of the embedded document set; PHI compliance may constrain broader data sources.
  - References: https://pmc.ncbi.nlm.nih.gov/articles/PMC10659484/

- Opportunities and challenges of AI in hepatology (narrative review)
  - Source: Nature Communications 2024/2025 review
  - Findings: AI/ML/DL approaches across EHRs, imaging, histology, and multi-omics offer diagnostic, prognostic, and therapeutic insights in hepatology. NLP/text-mining and LLMs can enhance case identification, data extraction, and decision support. Image- and omics-driven methods improve noninvasive fibrosis staging, tumor detection, histopathology quantification, and risk stratification. Emphasizes need for large-scale, multi-centre validation, interpretability, ethics, privacy, and regulatory compliance before clinical adoption.
  - Caveats: Narrative synthesis with potential biases toward positive results; many cited studies are retrospective or single-centre with limited external validation; detailed, liver-disease–specific LLM implementations remain limited.
  - References: https://www.nature.com/articles/s44355-025-00052-w

- LLM-generated treatment recommendations for hepatocellular carcinoma (HCC): nationwide retrospective assessment
  - Source: PLOS Medicine (Korean Primary Liver Cancer Registry, 2008–2020)
  - Findings: In 13,614 treatment-naive HCC patients, LLM-generated recommendations (ChatGPT-4o, Gemini 2.0, Claude 3.5) concorded with actual physician treatment decisions in ~26.8–32.7% of cases. Concordance associated with improved overall survival in early-stage HCC (BCLC-A) but worse survival in advanced-stage HCC (BCLC-C). Physicians prioritized liver function; LLMs emphasized tumor characteristics.
  - Significance: Suggests LLMs may support guideline-concordant decisions in straightforward cases but are not reliable for complex, individualized management; they should supplement rather than replace clinician judgment.
  - Caveats: Retrospective registry data lacking imaging inputs and granular treatment details; outputs were not used to treat patients; three LLMs evaluated without fine-tuning to guidelines; potential unmeasured confounding; context limited to Korea and to retrospective data.
  - References: https://journals.plos.org/plosmedicine/article?id=10.1371/journal.pmed.1004855

- AI treatment suggestions for liver cancer more accurate at early stages (media overview)
  - Source: Inside Precision Medicine summary of the PLOS study
  - Findings: Reiterates that LLMs matched physician decisions in a subset of early-stage HCC cases and that early-stage matches correlated with better survival; advanced-stage matches correlated with worse outcomes.
  - Significance: Confirms main PLOS findings for a broader audience; highlights that LLMs may be useful for straightforward, guideline-concordant decisions, while caution is warranted for complex scenarios.
  - Caveats: Media synthesis; not a primary research source; interpret with the same cautions as the original registry study.
  - References: https://www.insideprecisionmedicine.com/topics/oncology/ai-treatment-suggestions-for-liver-cancer-more-accurate-at-early-stages/

Methodologies
- Seven-variable fibrosis prediction with LLMs (Cureus)
  - Data source: NHANES 2017–2020, MASLD defined by CAP and cardiometabolic risk factors
  - Features: age, platelet count, HbA1c, eGFR, BMI, AST, ALT
  - Models: GPT-4 and GPT-3.5; prompts produced risk percentage and rationale
  - Evaluation: AUROC, Brier score, sensitivity, specificity, F1; bootstrap 95% CIs; Youden’s index for thresholds; batch prompting; multiple runs with fixed temperature
  - Output: risk scores and brief reasoning; good calibration

- LiVersa (liver-disease–specific LLM with retrieval) (LiVersa study)
  - Architecture: PHI-compliant framework embedding 30 AASLD documents; vectorized content via text-embedding-ada-002; real-time retrieval from Azure Cognitive Search; answer generation using GPT-3.5-turbo or GPT-4-32k
  - Evaluation: case-vignettes for HBV/HCC; forced yes/no assessment; comparison to trainee knowledge
  - Output: generated answers with content sourced from guideline embeddings; evaluation included accuracy on yes/no questions; rationales sometimes incomplete or imperfect

- AI in hepatology (Nature Communications review)
  - Scope: narrative synthesis of AI across data modalities (EHRs, imaging, histology, multi-omics) and introduction of LLMs as emerging tools
  - Evaluation considerations: emphasis on validation, interpretability, ethics, privacy, and regulatory readiness; general guidance rather than a single model evaluation

- LLMs for HCC treatment decisions (PLOS Medicine registry)
  - Data source: Korean Primary Liver Cancer Registry (2008–2020)
  - Models: ChatGPT 4o, Gemini 2.0, Claude 3.5; prompts based on AASLD/EASL guidelines
  - Outcome measures: concordance with actual treatments; survival analyses (Kaplan–Meier, Cox models); IPTW for baseline differences; decision-tree to identify drivers
  - Output: concordance rates in a real-world, nationwide cohort; insights into stage-dependent value and limitations

- Media synthesis (Inside Precision Medicine)
  - Role: distills PLOS findings for a broader audience
  - Emphasis: early-stage congruence; advanced-stage challenges; the need for clinician oversight

Limitations
- Generalizability and external validation
  - Cureus study: small derivation cohort from NHANES with MASLD subset; cross-sectional design; need external validation across diverse populations and settings
  - LiVersa: evaluation limited to 30 guidelines and HBV/HCC case vignettes; may not generalize to broader liver disease questions or evolving guidelines
  - PLOS Medicine: registry-based, retrospective; lack of imaging inputs and granular treatment data; not prospective; context limited to Korea and guideline eras
  - Narrative review: synthesis of existing studies with potential publication bias; variable study quality across modalities and settings
- Model and data limitations
  - Prompt-driven inputs and reliance on LLM outputs may introduce bias or variability; risk of overconfidence in model outputs without robust interpretability
  - Retrieval-augmented approaches depend on the quality and scope of embedded documents; gaps in guidelines or updates can lead to incomplete rationales
  - PHI/compliance requirements may restrict data sources and deployment in non-PHI-compliant environments
- Clinical adoption barriers
  - None of the studies demonstrate prospective clinical benefit or integration into standard workflows
  - The concordance between LLMs and physician decisions does not prove causality or improved outcomes across diverse populations
  - Regulatory, privacy, and ethical considerations require careful governance before clinical deployment

References
- Using Large Language Models to Predict Advanced Liver Fibrosis in Metabolic Dysfunction-Associated Steatotic Liver Disease (MASLD) – A Proof-of-Concept Analysis
  - URL: https://www.cureus.com/articles/438782-using-large-language-models-to-predict-advanced-liver-fibrosis-in-metabolic-dysfunction-associated-steatotic-liver-disease-masld-a-proof-of-concept-analysis.pdf

- Development of a Liver Disease-Specific Large Language Model (LiVersa) with Retrieval-Augmented Generation
  - URL: https://pmc.ncbi.nlm.nih.gov/articles/PMC10659484/

- Opportunities and challenges of artificial intelligence in hepatology
  - URL: https://www.nature.com/articles/s44355-025-00052-w

- A nationwide retrospective registry study | PLOS Medicine
  - URL: https://journals.plos.org/plosmedicine/article?id=10.1371/journal.pmed.1004855

- AI Treatment Suggestions for Liver Cancer More Accurate at Early Stages
  - URL: https://www.insideprecisionmedicine.com/topics/oncology/ai-treatment-suggestions-for-liver-cancer-more-accurate-at-early-stages/

Notes on interpretation
- The field is in an early, exploratory phase. While results are encouraging for specific tasks (e.g., risk stratification with few inputs, guideline-based retrieval of information, and prospective support in straightforward clinical decisions), the evidence base for broad clinical implementation remains limited. Prospective validation, multi-centre studies, standardized evaluation frameworks, model interpretability, and governance for privacy and ethics will be essential steps before LLMs can be routinely integrated into hepatology research or patient care.
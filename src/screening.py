import os
import argparse
from typing import Literal
from dataclasses import dataclass
from pydantic import BaseModel, Field
from dotenv import load_dotenv
from openai import OpenAI
from database import (
    get_connection,
    save_screening_result,
)


load_dotenv()


api_key = os.getenv("OPENAI_API_KEY")

if not api_key:
    raise RuntimeError(
        "OPENAI_API_KEY was not found in .env"
    )


client = OpenAI(
    api_key=api_key
)

# Επιλογή μοντέλου OpenAI (π.χ. gpt-4o ή gpt-4o-mini)
MODEL = "gpt-4o-mini"


class ScreeningResult(BaseModel):

    relevant: bool

    relevance_type: Literal[
        "Direct",
        "Indirect",
        "Irrelevant",
    ]
    
    condition: Literal[
        "MSA",
        "PSP",
        "CBS",
        "CBD",
        "DLB",
        "Multiple",
        "Other",
        "Unclear",
    ]

    study_type: Literal[
        "Clinical trial",
        "Observational study",
        "Biomarker",
        "Imaging",
        "Genetics",
        "Pathology",
        "Treatment",
        "Rehabilitation",
        "Review",
        "Meta-analysis",
        "Case report",
        "Preclinical",
        "Other",
    ]

    importance: int = Field(
        ge=1,
        le=5,
    )

    evidence_level: Literal[
        "Very low",
        "Low",
        "Moderate",
        "High",
        "Very high",
        "Not applicable",
    ]

    confidence: int = Field(
        ge=1,
        le=5,
    )

    reason: str


SYSTEM_PROMPT = """
You are a scientific literature screening assistant.

Your task is to determine whether a scientific paper
is meaningfully relevant to atypical parkinsonism.

The target disorders are:

- Multiple System Atrophy (MSA)
- Progressive Supranuclear Palsy (PSP)
- Corticobasal Syndrome (CBS)
- Corticobasal Degeneration (CBD)
- Dementia with Lewy Bodies (DLB)

STRICT EXCLUSION RULES (CRITICAL):

1. Do NOT consider a paper relevant if its primary focus is Alzheimer's Disease (AD),
   amyloid-beta pathobiology, or anti-amyloid therapies (e.g., Lecanemab, Donanemab),
   EVEN IF an atypical phenotype (such as CBS or PCA due to AD) is mentioned as a subgroup.

2. Do NOT consider a paper relevant merely because it mentions:
   - Parkinson's disease in general
   - Alzheimer's disease in general
   - neurodegeneration in general
   - dementia in general
   - alpha-synuclein or tau in general
   unless the core primary focus is directly on one of the target atypical parkinsonian disorders.

A paper is relevant ONLY when it provides primary, meaningful information
directly studying or diagnosing one or more of the target disorders (MSA, PSP, CBS, CBD, DLB).

IMPORTANT:

Distinguish between:

1. scientific relevance to the target disorder
2. scientific importance of the findings
3. confidence that the abstract provides enough evidence
   for the classification

A paper can therefore have:

importance = 5
but confidence = 2

if the topic is highly important but the abstract provides
limited information.

Return structured data matching the requested schema.
IMPORTANT OUTPUT NORMALIZATION:

For "condition", always return ONLY the canonical
condition code:

MSA
PSP
CBS
CBD
DLB
Multiple
Other
Unclear

For example:

"Corticobasal syndrome due to Alzheimer's disease"
must be returned as:

"Other" (because primary focus is AD pathology) or "CBS" ONLY if the paper is primarily investigating CBS clinical presentation rather than AD therapeutics. If it's about AD therapies, return "Other" and relevant = false.

The detailed description belongs in "reason".

For "study_type", always return ONLY one of the
canonical study type values.

STUDY TYPE CLASSIFICATION:

Classify study_type based on the actual methodology of the study,
NOT merely on the fact that it evaluates a diagnostic criterion,
treatment, biomarker, or clinical outcome.

Use "Clinical trial" ONLY when the study is an interventional
clinical trial in human participants, such as a randomized,
controlled, blinded, or prospective intervention study.

Use "Observational study" for studies in which investigators
observe, compare, or analyze participants without assigning an
intervention. This includes retrospective cohorts, prospective
cohorts, case-control studies, cross-sectional studies, and
diagnostic validation studies.

IMPORTANT:
A diagnostic validation study is NOT automatically a "Clinical trial".

A study evaluating or validating diagnostic criteria is normally
"Observational study" unless the researchers actually assign an
intervention as part of a clinical trial.

Examples:

"Validation of orthostatic hypotension in MDS diagnostic criteria
for multiple system atrophy" → Observational study.

"Randomized controlled trial of a treatment in PSP" → Clinical trial.

"Retrospective cohort study of MSA patients" → Observational study.

"Systematic review of MSA treatments" → Review.

"Meta-analysis of PSP clinical trials" → Meta-analysis.

For "evidence_level", always return ONLY one of the
canonical evidence level values.

Do not create new values or add explanations to
these fields.

MULTIPLE CONDITION RULE:

Return "Multiple" ONLY when the paper meaningfully
studies two or more target disorders.

Do NOT use "Multiple" merely because:

- the paper mentions Parkinson's disease
- the paper mentions parkinsonism
- the study includes a broad neurodegenerative cohort
- the target disorder is only mentioned as a comparator
- the target disorder appears only in the introduction/background
- the paper concerns a general biomarker that could theoretically
  apply to several disorders

If only one target disorder is meaningfully studied,
return that specific disorder.

For example:

A paper specifically validating orthostatic hypotension
for MSA diagnostic criteria → MSA, NOT Multiple.

A paper comparing PSP and MSA → Multiple.

A paper studying PSP, MSA, CBS and DLB rehabilitation →
Multiple.

RELEVANCE TYPE:

Classify the paper as one of:

- Direct:
  The paper meaningfully studies one or more target disorders
  (MSA, PSP, CBS/CBD, or DLB) as a primary subject of the research.

- Indirect:
  The paper is not primarily focused on a target disorder,
  but contains meaningful findings that are relevant to one or more
  target disorders.

- Irrelevant:
  The paper does not contain meaningful information about the target
  disorders.

IMPORTANT:

If relevant = true, relevance_type must be either Direct or Indirect.

If relevant = false, relevance_type must be Irrelevant.

Do not classify a paper as Direct merely because a target disorder
is mentioned in the background, introduction, or as a minor subgroup.

If relevant = false, condition should normally be "Other".

CONSISTENCY CHECK:

Before returning the structured result, verify that study_type
matches the methodology described in the paper.

The explanation/reason and study_type MUST NOT contradict each
other.

If the reason states that a study is observational, study_type
must be "Observational study", not "Clinical trial".
"""


def get_unscreened_papers() -> list[dict]:

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT
            pmid,
            title,
            abstract,
            journal,
            publication_date,
            doi,
            pubmed_url
        FROM papers
        WHERE screening_status IS NULL
        ORDER BY publication_date DESC
        """
    )

    rows = cursor.fetchall()

    connection.close()

    return [dict(row) for row in rows]


def screen_paper(
    title: str,
    abstract: str,
) -> ScreeningResult:

    user_prompt = f"""
Evaluate this scientific paper.

TITLE:
{title}

ABSTRACT:
{abstract}
"""

    response = client.beta.chat.completions.parse(
        model=MODEL,
        messages=[
            {
                "role": "system",
                "content": SYSTEM_PROMPT,
            },
            {
                "role": "user",
                "content": user_prompt,
            },
        ],
        response_format=ScreeningResult,
    )

    return response.choices[0].message.parsed


if __name__ == "__main__":

    parser = argparse.ArgumentParser(
        description="AI screening test for atypical parkinsonism papers"
    )

    parser.add_argument(
        "--pmid",
        help="Screen a specific PubMed paper by PMID",
    )

    args = parser.parse_args()

    if args.pmid:

        connection = get_connection()
        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT pmid, title, abstract
            FROM papers
            WHERE pmid = ?
            """,
            (args.pmid,),
        )

        paper = cursor.fetchone()

        connection.close()

        if not paper:
            print(
                f"Paper with PMID {args.pmid} "
                "was not found in the database."
            )
            raise SystemExit(1)

        paper = {
            "pmid": paper[0],
            "title": paper[1],
            "abstract": paper[2],
        }

    else:

        papers = get_unscreened_papers()

        if not papers:

            print(
                "No unscreened papers found."
            )

            raise SystemExit(0)

        paper = papers[0]

    print()
    print(
        "AI Structured Screening Test"
    )
    print("=" * 70)
    print()

    print(
        f"PMID: {paper['pmid']}"
    )

    print(
        f"Title: {paper['title']}"
    )

    print()

    print(
        "Sending paper to OpenAI..."
    )

    result = screen_paper(
        title=paper["title"],
        abstract=paper["abstract"] or "",
    )

    print()
    print(
        "AI RESULT"
    )
    print("=" * 70)

    print(
        f"Relevant: {result.relevant}"
    )

    print(
        f"Relevance type: {result.relevance_type}"
    )

    print(
        f"Condition: {result.condition}"
    )

    print(
        f"Study type: {result.study_type}"
    )

    print(
        f"Importance: {result.importance}/5"
    )

    print(
        f"Evidence level: {result.evidence_level}"
    )

    print(
        f"Confidence: {result.confidence}/5"
    )

    print()

    print(
        "Reason:"
    )

    save_screening_result(
        pmid=paper["pmid"],
        relevant=result.relevant,
        relevance_type=result.relevance_type,
        condition=result.condition,
        study_type=result.study_type,
        importance=result.importance,
        evidence_level=result.evidence_level,
        confidence=result.confidence,
        reason=result.reason,
    )

    print()

    print(
        "Screening result saved to database."
    )

    print(
        result.reason
    )

    print()
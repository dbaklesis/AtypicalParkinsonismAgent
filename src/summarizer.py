import os
from typing import Literal
from openai import OpenAI
from pydantic import BaseModel, Field
from dotenv import load_dotenv
from database import get_connection, save_summary


load_dotenv()


api_key = os.getenv("OPENAI_API_KEY")

if not api_key:
    raise RuntimeError(
        "OPENAI_API_KEY was not found in .env"
    )

client = OpenAI(api_key=api_key)

MODEL = "gpt-4o-mini"


class ResearchSummary(BaseModel):

    title_el: str = Field(
        description="Ο τίτλος της μελέτης μεταφρασμένος με ακρίβεια στα ελληνικά."
    )

    summary_el: str

    key_finding_el: str

    why_it_matters_el: str

    limitations_el: str


SYSTEM_PROMPT = """
You are the scientific research summarization component of an
AI agent that monitors research about atypical parkinsonism.

The target conditions are:

- Multiple System Atrophy (MSA)
- Progressive Supranuclear Palsy (PSP)
- Corticobasal Syndrome (CBS)
- Corticobasal Degeneration (CBD)
- Dementia With Lewy Bodies (DLB)

The user who will read the final result speaks ONLY Greek.

Your task is to summarize the scientific paper in clear,
accurate, natural Greek.

IMPORTANT:

1. Do NOT invent information that is not present in the title
   or abstract.

2. Do NOT make a diagnosis.

3. Do NOT recommend a treatment for an individual patient.

4. Do NOT imply that an experimental finding is an established
   treatment.

5. Clearly distinguish between:
   - established findings
   - observations
   - hypotheses
   - experimental/preclinical findings

6. Preserve uncertainty when the original paper is uncertain.

7. Use medical terminology accurately, but explain technical
   concepts in language that a non-specialist can understand.

8. The summary is intended for an interested patient/family
   member, NOT for a medical professional.

9. Do not use frightening or sensational language.

10. Do not translate scientific terms literally if doing so
    would make the Greek unnatural. Use the accepted Greek
    medical terminology when possible and include the English
    abbreviation when useful.

Return four sections:

summary_el:
A concise Greek summary of what the study investigated,
how it was performed, and what it found.
Target length: approximately 100-150 words.

key_finding_el:
The single most important finding, in clear Greek.
Target length: approximately 30-60 words.

why_it_matters_el:
Explain why this paper may be relevant to research on atypical
parkinsonism and what it potentially contributes.
Do not exaggerate its significance.
Target length: approximately 30-60 words.

limitations_el:
Explain the most important limitations of the study, such as
small sample size, observational design, preclinical nature,
lack of clinical outcomes, short follow-up, or other limitations
explicitly evident from the paper.
Target length: approximately 30-60 words.

All four fields MUST be written in Greek.
"""


def get_paper_for_summary() -> dict | None:
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT
            pmid,
            title,
            abstract,
            condition,
            study_type,
            importance,
            evidence_level,
            confidence
        FROM papers
        WHERE
            relevant = 1
            AND importance >= 4
            AND (
                summary_status IS NULL
                OR summary_status = 'pending'
                OR summary_status = 'failed'
            )
        ORDER BY
            importance DESC,
            publication_date DESC
        LIMIT 1
        """
    )

    row = cursor.fetchone()
    connection.close()

    return dict(row) if row else None

def mark_summary_processing(
    pmid: str,
) -> None:
    """
    Mark a paper as currently being summarized.
    """

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute(
        """
        UPDATE papers
        SET summary_status = ?
        WHERE pmid = ?
        """,
        (
            "processing",
            pmid,
        ),
    )

    connection.commit()
    connection.close()

def summarize_paper(
    title: str,
    abstract: str,
) -> ResearchSummary:

    user_prompt = f"""
Summarize the following scientific paper in Greek.

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
        response_format=ResearchSummary,
    )

    return response.choices[0].message.parsed


if __name__ == "__main__":

    print()
    print("AI Greek Research Summarizer")
    print("=" * 70)
    print()

    paper = get_paper_for_summary()

    if paper is None:

        print(
            "No eligible papers found for summarization."
        )

        raise SystemExit(0)

    print(
        f"PMID: {paper['pmid']}"
    )

    print(
        f"Title: {paper['title']}"
    )

    print(
        f"Condition: {paper['condition']}"
    )

    print(
        f"Importance: {paper['importance']}/5"
    )

    print(
        f"Evidence level: {paper['evidence_level']}"
    )

    print()
    mark_summary_processing(
        paper["pmid"]
    )
    
    print(
        "Sending paper to OpenAI..."
    )

    result = summarize_paper(
        title=paper["title"],
        abstract=paper["abstract"] or "",
    )

    print()
    print("AI GREEK SUMMARY")
    print("=" * 70)
    print()

    print("ΠΕΡΙΛΗΨΗ:")
    print(result.summary_el)

    print()
    print("ΒΑΣΙΚΟ ΕΥΡΗΜΑ:")
    print(result.key_finding_el)

    print()
    print("ΓΙΑΤΙ ΕΧΕΙ ΣΗΜΑΣΙΑ:")
    print(result.why_it_matters_el)

    print()
    print("ΠΕΡΙΟΡΙΣΜΟΙ:")
    print(result.limitations_el)

    save_summary(
        pmid=paper["pmid"],
        title_el=result.title_el,
        summary_el=result.summary_el,
        key_finding_el=result.key_finding_el,
        why_it_matters_el=result.why_it_matters_el,
        limitations_el=result.limitations_el,
    )

    print()
    print(
        "Greek summary saved to database."
    )
    print()
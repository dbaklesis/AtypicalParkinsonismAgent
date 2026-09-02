import os
import sqlite3
from openai import OpenAI
from dotenv import load_dotenv
from database import get_connection

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

EXEC_SYSTEM_PROMPT = """
You are a senior scientific research analyst specializing in atypical parkinsonism 
(MSA, PSP, CBS/CBD, DLB).

Your job is to read a collection of individual research paper summaries and synthesize 
them into a single, cohesive, high-level Executive Summary written in clear, professional Greek.

Structure your output as follows:

1. 🎯 Κύρια Συμπεράσματα (Top Takeaways):
   A bulleted list highlighting 2-4 major themes or breakthroughs across all studies.

2. 🔬 Εξελίξεις ανά Πάθηση (Updates by Condition):
   Group key findings under relevant disorders (MSA, PSP, CBS, DLB).

3. 🔮 Κλινική Σημασία & Μέλλον (Clinical Outlook):
   A concise 2-sentence summary of what these findings collectively mean for research or therapeutic development.

Keep it scannable, direct, and actionable. Do not repeat full abstracts.
"""

def generate_executive_summary(days_back: int = 7) -> str | None:
    """
    Fetches all completed high-importance papers from the past N days
    and generates a synthesized Greek Executive Summary.
    """
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT pmid, condition, title_el, key_finding_el, why_it_matters_el
        FROM papers
        WHERE relevant = 1 
          AND importance >= 4 
          AND summary_status = 'completed'
          AND created_at >= datetime('now', ?)
        ORDER BY importance DESC, publication_date DESC
        """,
        (f"-{days_back} days",)
    )
    
    rows = cursor.fetchall()
    connection.close()

    if not rows:
        print("[EXEC SUMMARY] No recent high-importance papers found.")
        return None

    # Format paper summaries into a clean text block for the LLM
    context_blocks = []
    for r in rows:
        block = (
            f"- [PMID: {r['pmid']}] ({r['condition']}) {r['title_el']}\n"
            f"  Εύρημα: {r['key_finding_el']}\n"
            f"  Σημασία: {r['why_it_matters_el']}"
        )
        context_blocks.append(block)

    user_prompt = "Σύνθεσε μια Εκτελεστική Σύνοψη (Executive Summary) για τις ακόλουθες πρόσφατες μελέτες:\n\n" + "\n\n".join(context_blocks)

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": EXEC_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.3,
    )

    return response.choices[0].message.content


if __name__ == "__main__":
    summary = generate_executive_summary(days_back=7)
    if summary:
        print("\n=== ΕΒΔΟΜΑΔΙΑΙΑ ΕΚΤΕΛΕΣΤΙΚΗ ΣΥΝΟΨΗ ===")
        print(summary)
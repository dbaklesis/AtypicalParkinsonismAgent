import sys
import json
from pathlib import Path
from openai import OpenAI
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
SRC_DIR = BASE_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from database import get_connection

load_dotenv()
client = OpenAI()

SYSTEM_PROMPT = """
Είσαι ένας εξειδικευμένος ιατρικός μεταφραστής και ερευνητής νευρολογίας.
Σου δίνεται ο τίτλος και η περίληψη μιας κλινικής δοκιμής για άτυπο παρκινσονισμό.
Πρέπει να επιστρέψεις JSON με τα εξής πεδία στα Ελληνικά:
1. "title_el": Ακριβής μετάφραση του τίτλου της δοκιμής στα Ελληνικά.
2. "summary_el": Σύντομη και σαφής περίληψη του στόχου της δοκιμής στα Ελληνικά (2-3 προτάσεις).

Απάντησε ΑΠΟΚΛΕΙΣΤΙΚΑ σε έγκυρη μορφή JSON.
"""

def summarize_trial(title: str, summary: str) -> dict:
    user_prompt = f"Τίτλος: {title}\nΠερίληψη: {summary}"
    
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt}
        ],
        response_format={"type": "json_object"},
        temperature=0.3
    )
    return json.loads(response.choices[0].message.content)

def main(limit: int = 5):
    connection = get_connection()
    cursor = connection.cursor()

    # Επιλογή σχετικών δοκιμών που δεν έχουν ακόμα ελληνικό τίτλο
    cursor.execute("""
        SELECT nct_id, title, summary
        FROM clinical_trials
        WHERE relevant = 1 AND (title_el IS NULL OR title_el = '')
        LIMIT ?
    """, (limit,))
    
    trials = cursor.fetchall()
    connection.close()

    if not trials:
        print("[ClinicalTrials Summarizer] Δεν υπάρχουν νέες σχετικές δοκιμές για μετάφραση.")
        return

    print(f"\n[ClinicalTrials Summarizer] Έναρξη μετάφρασης για {len(trials)} δοκιμές...")

    for t in trials:
        nct_id = t["nct_id"]
        print(f"   Μετάφραση [{nct_id}]...")
        try:
            res = summarize_trial(t["title"], t["summary"] or "")
            
            conn = get_connection()
            c = conn.cursor()
            c.execute("""
                UPDATE clinical_trials
                SET title_el = ?, summary_el = ?
                WHERE nct_id = ?
            """, (res.get("title_el"), res.get("summary_el"), nct_id))
            conn.commit()
            conn.close()
            print(f"   [OK] {nct_id} μεταφράστηκε επιτυχώς.")
        except Exception as e:
            print(f"   [ERROR] Αποτυχία μετάφρασης {nct_id}: {e}")

if __name__ == "__main__":
    main()
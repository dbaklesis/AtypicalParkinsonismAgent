import sys
import logging
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
SRC_DIR = BASE_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from database import get_connection, save_trial_screening
from screening import screen_paper


def main(limit: int = 20):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT nct_id, title, summary, condition
        FROM clinical_trials
        WHERE relevant IS NULL OR relevant = 0
        LIMIT ?
        """,
        (limit,),
    )

    trials = cursor.fetchall()
    connection.close()

    if not trials:
        print("[ClinicalTrials] Δεν υπάρχουν νέες ανεπεξέργαστες δοκιμές για screening.")
        return

    print(f"\n[ClinicalTrials] Έναρξη AI Screening για {len(trials)} δοκιμές...")

    for t in trials:
        nct_id = t["nct_id"]
        summary_text = t["summary"] if t["summary"] else ""
        
        trial_dict = {
            "pmid": nct_id,
            "title": t["title"],
            "condition": t["condition"] if t["condition"] else ""
        }

        try:
            result = screen_paper(trial_dict, summary_text)
            
            save_trial_screening(nct_id, result.relevant, result.importance)

            status_str = "Σχετική" if result.relevant else "Απορρίφθηκε"
            print(f"   [{nct_id}] -> {status_str} | Πάθηση: {result.condition} | Σημαντικότητα: {result.importance}/5")

        except Exception as e:
            print(f"   [ERROR] Αποτυχία screening για {nct_id}: {e}")


if __name__ == "__main__":
    main()
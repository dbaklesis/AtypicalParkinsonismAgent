import sys
import logging
from pathlib import Path

# Ρύθμιση Paths
BASE_DIR = Path(__file__).resolve().parent.parent
SRC_DIR = BASE_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from pubmed import run_scan
from clinical_trials import fetch_clinical_trials
from screen_all import main as run_screening
from screen_trials import main as run_trials_screening
from summarizer_all import main as run_summarizer
from summarize_trials import main as run_trials_summarizer
from europe_pmc import fetch_europe_pmc_papers
from database import save_paper # Your database insert function

# Logging Configuration (UTF-8 encoding για αποφυγή cp1253 σφαλμάτων)
stream_handler = logging.StreamHandler(sys.stdout)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[stream_handler],
)


def execute_pipeline(screen_limit: int = 100, summary_limit: int = 100):
    logging.info("=== ΕΝΑΡΞΗ ΑΥΤΟΜΑΤΟΠΟΙΗΜΕΝΗΣ ΔΙΑΔΙΚΑΣΙΑΣ AGENT ===")

    # Βήμα 1α: PubMed
    logging.info("Βήμα 1α: Αναζήτηση δημοσιεύσεων στο PubMed...")
    try:
        run_scan()
        logging.info("[OK] Ολοκληρώθηκε η αναζήτηση στο PubMed.")
    except Exception as err:
        logging.error(f"[ERROR] Σφάλμα στο PubMed: {err}")

    # Βήμα 1β: ClinicalTrials.gov
    logging.info("Βήμα 1β: Αναζήτηση δοκιμών στο ClinicalTrials.gov...")
    try:
        fetch_clinical_trials(max_results_per_query=3)
        logging.info("[OK] Ολοκληρώθηκε η αναζήτηση στο ClinicalTrials.gov.")
    except Exception as err:
        logging.error(f"[ERROR] Σφάλμα στο ClinicalTrials.gov: {err}")

    # Step 1c: Fetch Europe PMC Preprints & Papers
    logging.info("Βήμα 1γ: Αναζήτηση στο Europe PMC...")
    try:
        epmc_records = fetch_europe_pmc_papers(days_back=8)
        for record in epmc_records:
            save_paper(record) # Insert into SQLite DB
        logging.info("[OK] Ολοκληρώθηκε η αναζήτηση στο Europe PMC.")
    except Exception as err:
        logging.error(f"[ERROR] Σφάλμα στο Europe PMC: {err}")

    # Βήμα 2: AI Screening (Papers & Trials)
    logging.info("Βήμα 2: AI Screening...")
    try:
        run_screening(limit=screen_limit)
        logging.info("[OK] Ολοκληρώθηκε το AI Screening δημοσιεύσεων.")
    except Exception as err:
        logging.error(f"[ERROR] Σφάλμα στο AI Screening δημοσιεύσεων: {err}")

    try:
        run_trials_screening(limit=screen_limit)
        logging.info("[OK] Ολοκληρώθηκε το AI Screening κλινικών δοκιμών.")
    except Exception as err:
        logging.error(f"[ERROR] Σφάλμα στο AI Screening κλινικών δοκιμών: {err}")

    # Βήμα 3: AI Summaries
    logging.info("Βήμα 3: Παραγωγή Ελληνικών Περιλήψεων...")
    try:
        run_summarizer(limit=summary_limit)
        logging.info("[OK] Ολοκληρώθηκε η παραγωγή περιλήψεων δημοσιεύσεων.")
    except Exception as err:
        logging.error(f"[ERROR] Σφάλμα κατά την παραγωγή περιλήψεων δημοσιεύσεων: {err}")

    try:
        run_trials_summarizer(limit=summary_limit)
        logging.info("[OK] Ολοκληρώθηκε η παραγωγή περιλήψεων κλινικών δοκιμών.")
    except Exception as err:
        logging.error(f"[ERROR] Σφάλμα κατά την παραγωγή περιλήψεων κλινικών δοκιμών: {err}")

    logging.info("=== ΟΛΟΚΛΗΡΩΣΗ ΔΙΑΔΙΚΑΣΙΑΣ AGENT ===")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run full research pipeline")
    parser.add_argument("--screen-limit", type=int, default=300, help="Όριο screening (300 για όλα)")
    parser.add_argument("--summary-limit", type=int, default=100, help="Όριο συνόψεων")
    
    args = parser.parse_args()

    # Καλούμε το pipeline περνώντας τις νέες παραμέτρους
    execute_pipeline(screen_limit=args.screen_limit, summary_limit=args.summary_limit)
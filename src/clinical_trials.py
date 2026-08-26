import requests
import logging
from database import save_clinical_trial

BASE_URL = "https://clinicaltrials.gov/api/v2/studies"
TARGET_SEARCHES = [
    ("MSA", "Multiple System Atrophy"),
    ("PSP", "Progressive Supranuclear Palsy"),
    ("CBS", "Corticobasal Syndrome OR Corticobasal Degeneration"),
    ("DLB", "Dementia with Lewy Bodies")
]

def fetch_clinical_trials(max_results_per_query: int = 5):
    """
    Φέρνει πρόσφατες κλινικές δοκιμές από το ClinicalTrials.gov.
    Για οικονομία στις δοκιμές, το max_results_per_query είναι πολύ χαμηλό (π.χ. 3-5).
    """
    total_new = 0
    logging.info("Έναρξη αναζήτησης στο ClinicalTrials.gov...")

    for code, query in TARGET_SEARCHES:
        params = {
            "query.cond": query,
            "pageSize": max_results_per_query,
            "sort": "LastUpdatePostDate:desc"  # Παίρνουμε τις πιο πρόσφατα ενημερωμένες
        }
        
        try:
            response = requests.get(BASE_URL, params=params, timeout=10)
            if response.status_code != 200:
                continue
            
            data = response.json()
            studies = data.get("studies", [])

            for item in studies:
                protocol = item.get("protocolSection", {})
                ident = protocol.get("identificationModule", {})
                status_mod = protocol.get("statusModule", {})
                design_mod = protocol.get("designModule", {})
                elig_mod = protocol.get("eligibilityModule", {})
                
                nct_id = ident.get("nctId")
                title = ident.get("briefTitle", "")
                status = status_mod.get("overallStatus", "UNKNOWN")
                
                # Φάση δοκιμής (π.χ. PHASE2, PHASE3)
                phases = design_mod.get("phases", ["Not Specified"])
                phase_str = ", ".join(phases)
                
                # Παρεμβάσεις / Φάρμακα
                arms = protocol.get("armsInterventionsModule", {}).get("interventions", [])
                interventions = ", ".join([i.get("name", "") for i in arms])
                
                summary = protocol.get("descriptionModule", {}).get("briefSummary", "")

                trial_record = {
                    "nct_id": nct_id,
                    "title": title,
                    "condition": code,
                    "status": status,
                    "phase": phase_str,
                    "interventions": interventions if interventions else "N/A",
                    "summary": summary
                }

                if save_clinical_trial(trial_record):
                    total_new += 1

        except Exception as e:
            logging.error(f"Σφάλμα κατά την αναζήτηση {code}: {e}")

    print(f"[ClinicalTrials] Βρέθηκαν {total_new} νέες δοκιμές.")
    return total_new

if __name__ == "__main__":
    fetch_clinical_trials()
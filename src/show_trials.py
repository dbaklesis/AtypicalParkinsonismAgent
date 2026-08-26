from database import get_connection

# Λεξικό μετάφρασης για Status και Phase
STATUS_MAP = {
    "RECRUITING": "Στρατολόγηση σε εξέλιξη",
    "ENROLLING_BY_INVITATION": "Στρατολόγηση κατόπιν πρόσκλησης",
    "ACTIVE_NOT_RECRUITING": "Ενεργή (Χωρίς νέα στρατολόγηση)",
    "COMPLETED": "Ολοκληρώθηκε",
    "NOT_YET_RECRUITING": "Δεν ξεκίνησε η στρατολόγηση",
    "TERMINATED": "Διακόπηκε",
    "SUSPENDED": "Σε αναστολή",
    "UNKNOWN": "Άγνωστη"
}

PHASE_MAP = {
    "PHASE1": "Φάση 1",
    "PHASE2": "Φάση 2",
    "PHASE3": "Φάση 3",
    "PHASE4": "Φάση 4",
    "PHASE1, PHASE2": "Φάση 1/2",
    "PHASE2, PHASE3": "Φάση 2/3",
    "NA": "Δεν εφαρμόζεται (N/A)",
    "Not Specified": "Δεν καθορίζεται"
}

INTERVENTION_MAP = {
    "Placebo": "Εικονικό φάρμακο (Placebo)",
    "Matching Placebo": "Εικονικό φάρμακο (Placebo)",
    "Placebo Comparator": "Εικονικό φάρμακο (Placebo)",
    "N/A": "Δεν υπάρχει"
}

def translate_interventions(text: str) -> str:
    if not text:
        return "Δεν υπάρχει"
    result = text
    for key, val in INTERVENTION_MAP.items():
        result = result.replace(key, val)
    return result

def main():
    connection = get_connection()
    cursor = connection.cursor()

    query = """
        SELECT nct_id, condition, status, phase, interventions, title, title_el, summary_el, relevant
        FROM clinical_trials
        WHERE relevant = 1
        ORDER BY created_at DESC
    """

    cursor.execute(query)
    rows = cursor.fetchall()
    connection.close()

    if not rows:
        print("Δεν βρέθηκαν σχετικές κλινικές δοκιμές στη βάση.")
        return

    print("=" * 80)
    print(f"ΣΧΕΤΙΚΕΣ ΚΛΙΝΙΚΕΣ ΔΟΚΙΜΕΣ ΣΤΗ ΒΑΣΗ ({len(rows)}/18 - ClinicalTrials.gov)")
    print("=" * 80)

    for i, row in enumerate(rows, 1):
        t = dict(row)
        display_title = t.get('title_el') if t.get('title_el') else t['title']
        
        status_el = STATUS_MAP.get(t['status'], t['status'])
        phase_el = PHASE_MAP.get(t['phase'], t['phase'])
        interventions_el = translate_interventions(t['interventions'])

        print(f"\n[{i}/{len(rows)}] NCT ID: {t['nct_id']} | Πάθηση: {t['condition']}")
        print(f"   Κατάσταση: {status_el} | Φάση: {phase_el}")
        print(f"   Παρεμβάσεις / Φάρμακα: {interventions_el}")
        print(f"   Τίτλος (GR): {display_title}")
        if t.get('title_el'):
            print(f"   Πρωτότυπος Τίτλος (EN): {t['title']}")
        if t.get('summary_el'):
            print(f"\n   📝 Ελληνική Περίληψη:\n   {t['summary_el']}")
        print("-" * 80)

if __name__ == "__main__":
    main()
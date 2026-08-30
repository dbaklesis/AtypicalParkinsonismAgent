from database import get_connection

def main():
    connection = get_connection()
    cursor = connection.cursor()

    # Έλεγχος αν υπάρχει η στήλη title_el στη βάση
    cursor.execute("PRAGMA table_info(papers)")
    columns = {row["name"] for row in cursor.fetchall()}

    if "title_el" in columns:
        query = """
            SELECT pmid, title_el, title, condition, importance, summary_el, key_finding_el, why_it_matters_el, limitations_el 
            FROM papers 
            WHERE relevant = 1 AND summary_status = 'completed'
            ORDER BY publication_date DESC
        """
    else:
        query = """
            SELECT pmid, NULL as title_el, title, condition, importance, summary_el, key_finding_el, why_it_matters_el, limitations_el 
            FROM papers 
            WHERE relevant = 1 AND summary_status = 'completed'
            ORDER BY publication_date DESC
        """

    cursor.execute(query)
    rows = cursor.fetchall()
    connection.close()

    if not rows:
        print("Δεν βρέθηκαν ολοκληρωμένες περιλήψεις στη βάση.")
        return

    for p in rows:
        display_title = p['title_el'] if p['title_el'] else p['title']

        print("=" * 70)
        print(f"PMID: {p['pmid']} | Πάθηση: {p['condition']} | Σημαντικότητα: {p['importance']}/5")
        print(f"Τίτλος: {display_title}")
        print(f"\n📌 Βασικό Ευρημα:\n{p['key_finding_el']}")
        print(f"\n💡 Γιατί έχει σημασία:\n{p['why_it_matters_el']}")
        print(f"\n🔍 Περίληψη:\n{p['summary_el']}")
        print(f"\n⚠️ Περιορισμοί:\n{p['limitations_el']}\n")

if __name__ == "__main__":
    main()
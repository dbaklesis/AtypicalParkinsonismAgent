import os
import sys
import json
import smtplib
from pathlib import Path
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv
from openai import OpenAI

BASE_DIR = Path(__file__).resolve().parent.parent
SRC_DIR = BASE_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from database import get_connection, mark_paper_as_sent
from show_trials import STATUS_MAP, PHASE_MAP, translate_interventions

load_dotenv()
client = OpenAI()

def generate_layman_summary(papers: list, trials: list) -> str:
    """
    Δημιουργεί μια σύντομη, εκλαϊκευμένη σύνοψη όλων των ευρημάτων.
    """
    content_text = ""
    if papers:
        content_text += "ΔΗΜΟΣΙΕΥΣΕΙΣ:\n"
        for p in papers:
            content_text += f"- {p['title_el']}: {p['summary_el']}\n"
    if trials:
        content_text += "\nΚΛΙΝΙΚΕΣ ΔΟΚΙΜΕΣ:\n"
        for t in trials:
            content_text += f"- {t['title_el']}: {t['summary_el']}\n"

    prompt = f"""
Είσαι ένας έμπειρος επιστημονικός δημοσιογράφος που εξηγεί νευρολογικές εξελίξεις στο ευρύ κοινό.
Διάβασε τα παρακάτω ευρήματα για τον άτυπο παρκινσονισμό και γράψε μια αναλυτική σύνοψη(350-450 λέξεις)
με έμφαση στα φάρμακα, που είναι σε στάδιο άμεσης ή/και μελλοντικής κυκλοφορίας στην αγορά και αυτά που είναι σε πειραματικό στάδιο,
και σε στάδιο έρευνας.

⚠️ ΣΗΜΑΝΤΙΚΗ ΟΔΗΓΙΑ ΜΟΡΦΟΠΟΙΗΣΗΣ:
Επίστρεψε το κείμενο ΑΠΟΚΛΕΙΣΤΙΚΑ σε μορφή HTML code (χωρίς ```html codeblocks). 
Χρησιμοποίησε tags όπως <h2>, <h3>, <p>, <ul>, <li>, <strong>, <br> για να διασφαλίσεις ότι το email θα εμφανιστεί με παραγράφους και λίστες.

Ακολούθησε αυστηρά την παρακάτω δομή HTML:

<h2>🎯 Κύριο Συμπέρασμα </h2>
<p>[2-3 προτάσεις που συνοψίζουν την πιο σημαντική εξέλιξη όλων των ευρημάτων μαζί.]</p>

<h2>🔬 Σημαντικότερα Ευρήματα & Ανακαλύψεις (Αναλυτικά)</h2>
<ul>
  <li>
    <strong>[Τίτλος Έρευνας / Ουσία]:</strong> [Συγκεκριμένα στοιχεία και αποτελέσματα].
    <br><em>👉 Τι σημαίνει αυτό για τον ασθενή;</em> [Πρακτική ερμηνεία].
  </li>
  <!-- Επανάληψη για κάθε βασικό εύρημα -->
</ul>

<h2>🧪 Κλινικές Δοκιμές & Νέες Θεραπείες</h2>
<p>[Σε τι στάδιο βρίσκονται οι δοκιμές και τι περιμένουμε στη συνέχεια.]</p>

<h2>💡 Τι Κρατάμε (Επόμενα βήματα)</h2>
<ul>
  <li>[Πρακτικό συμπέρασμα 1]</li>
  <li>[Πρακτικό συμπέρασμα 2]</li>
</ul>

Οδηγίες Στυλ:
- Χρησιμοποίησε απλή, καθημερινή γλώσσα.
- Απέφευγε ασαφείς φράσεις. Εξήγησε ΣΥΓΚΕΚΡΙΜΕΝΑ τα αποτελέσματα.
- Διατήρησε έναν ενθαρρυντικό αλλά αντικειμενικό τόνο.

Ευρήματα:
{content_text}
"""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.5,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"[ERROR] Αποτυχία δημιουργίας εκλαϊκευμένης σύνοψης: {e}")
        return "Ακολουθεί η αναλυτική ενημέρωση για τις νέες δημοσιεύσεις και κλινικές δοκιμές."

def build_email_body():
    connection = get_connection()
    cursor = connection.cursor()

    # 1. Ανάκτηση Δημοσιεύσεων (PubMed)
    cursor.execute("""
        SELECT pmid, title_el, summary_el, key_finding_el, why_it_matters_el, limitations_el, condition, importance
        FROM papers
        WHERE relevant = 1 AND summary_status = 'completed' AND (sent_at IS NULL OR sent_at = '')
        ORDER BY importance DESC
    """)
    papers = [dict(r) for r in cursor.fetchall()]

    # 2. Ανάκτηση Κλινικών Δοκιμών (ClinicalTrials.gov)
    cursor.execute("""
        SELECT nct_id, title_el, summary_el, condition, status, phase, interventions, importance
        FROM clinical_trials
        WHERE relevant = 1 AND title_el IS NOT NULL AND title_el != ''
        ORDER BY created_at DESC
    """)
    trials = [dict(r) for r in cursor.fetchall()]
    connection.close()

    if not papers and not trials:
        return None

    # Δημιουργία της εκλαϊκευμένης σύνοψης μέσω OpenAI
    print("[AI] Δημιουργία εκλαϊκευμένης σύνοψης...")
    layman_summary = generate_layman_summary(papers, trials)

    html = f"""
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            h2 {{ color: #1a365d; border-bottom: 2px solid #2b6cb0; padding-bottom: 5px; }}
            h3 {{ color: #2c5282; margin-bottom: 5px; }}
            .summary-box {{ background: #ebf8ff; border-left: 4px solid #3182ce; padding: 15px; margin-bottom: 25px; border-radius: 6px; }}
            .summary-title {{ font-size: 1.1em; font-weight: bold; color: #2b6cb0; margin-bottom: 8px; }}
            .card {{ background: #f7fafc; border-left: 4px solid #4299e1; padding: 15px; margin-bottom: 20px; border-radius: 4px; }}
            .trial-card {{ background: #f0fff4; border-left: 4px solid #38a169; padding: 15px; margin-bottom: 20px; border-radius: 4px; }}
            .badge {{ background: #e2e8f0; color: #2d3748; padding: 3px 8px; border-radius: 3px; font-size: 0.85em; font-weight: bold; }}
            .meta {{ font-size: 0.9em; color: #4a5568; margin-bottom: 10px; }}
            .label {{ font-weight: bold; color: #2d3748; }}
        </style>
    </head>
    <body>
        <h2>🧠 Ημερήσια Ενημέρωση Άτυπου Παρκινσονισμού</h2>
        
        <!-- Εκλαϊκευμένη Σύνοψη -->
        <div class="summary-box">
            <div class="summary-title">💡 Σύνοψη της Ημέρας (Με απλά λόγια)</div>
            <p>{layman_summary}</p>
        </div>
    """

    # Ενότητα Δημοσιεύσεων
    if papers:
        html += f"<h3>📚 Νέες Δημοσιεύσεις PubMed ({len(papers)})</h3>"
        for p in papers:
            html += f"""
            <div class="card">
                <div class="meta">
                    <span class="badge">{p['condition']}</span> | Σημαντικότητα: {p['importance']}/5 | PMID: {p['pmid']}
                </div>
                <h3>{p['title_el']}</h3>
                <p><span class="label">Περίληψη:</span> {p['summary_el']}</p>
                <p><span class="label">Κύριο Εύρημα:</span> {p['key_finding_el']}</p>
                <p><span class="label">Γιατί Έχει Σημασία:</span> {p['why_it_matters_el']}</p>
            </div>
            """

    # Ενότητα Κλινικών Δοκιμών
    if trials:
        html += f"<h3>🔬 Εξελισσόμενες Κλινικές Δοκιμές - ClinicalTrials.gov ({len(trials)})</h3>"
        for t in trials:
            status_el = STATUS_MAP.get(t['status'], t['status'])
            phase_el = PHASE_MAP.get(t['phase'], t['phase'])
            interventions_el = translate_interventions(t['interventions'])
            
            html += f"""
            <div class="trial-card">
                <div class="meta">
                    <span class="badge">{t['condition']}</span> | Κατάσταση: {status_el} | Φάση: {phase_el} | NCT: {t['nct_id']}
                </div>
                <h3>{t['title_el']}</h3>
                <p><span class="label">Παρεμβάσεις / Φάρμακα:</span> {interventions_el}</p>
                <p><span class="label">Στόχος Δοκιμής:</span> {t['summary_el']}</p>
            </div>
            """

    html += """
        <hr style="border: 0; border-top: 1px solid #eee; margin-top: 30px;">
        <p style="font-size: 0.8em; color: #718096; text-align: center;">Αυτοματοποιημένη ενημέρωση από τον Atypical Parkinsonism Research Agent.</p>
    </body>
    </html>
    """

    return html, [p['pmid'] for p in papers]

def send_email():
    result = build_email_body()
    if not result:
        print("Δεν υπάρχουν νέα δεδομένα για αποστολή.")
        return

    html_body, pmids = result

    smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", 587))
    sender_email = os.getenv("SENDER_EMAIL")
    sender_password = os.getenv("SENDER_PASSWORD")
    receiver_email_raw = os.getenv("RECEIVER_EMAIL", "")

    # Μετατροπή του string σε πραγματική λίστα Python (π.χ. ["email1@gmail.com", "email2@gmail.com"])
    # Το strip() αφαιρεί τυχόν κενά διαστήματα πριν ή μετά από κάθε email.
    receiver_emails = [email.strip() for email in receiver_email_raw.split(",") if email.strip()]

    msg = MIMEMultipart("alternative")
    msg["Subject"] = "🧠 Ενημέρωση Έρευνας: Νέες Δημοσιεύσεις & Κλινικές Δοκιμές"
    msg["From"] = sender_email
    # Στο header "To" περνάμε το string διαχωρισμένο με κόμμα για να φαίνονται όλοι οι παραλήπτες:
    msg["To"] = ", ".join(receiver_emails)
    msg.attach(MIMEText(html_body, "html"))

    try:
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(sender_email, sender_password)
        # ΕΔΩ: Περνάμε τη ΛΙΣΤΑ receiver_emails αντί για το απλό string
        server.sendmail(sender_email, receiver_emails, msg.as_string())
        server.quit()
        print("Το email στάλθηκε επιτυχώς!")
    except Exception as e:
        print(f"[ERROR] Αποτυχία αποστολής email: {e}")
    
if __name__ == "__main__":
    send_email()
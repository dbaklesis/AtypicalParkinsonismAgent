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
    Δημιουργεί μια εκτενή, πλούσια και δομημένη εκλαϊκευμένη σύνοψη
    όλων των ευρημάτων από PubMed, Europe PMC και ClinicalTrials.gov.
    """
    content_text = ""
    if papers:
        content_text += "=== ΔΗΜΟΣΙΕΥΣΕΙΣ & PREPRINTS (PubMed & Europe PMC) ===\n"
        for p in papers:
            pmid_str = str(p['pmid'])
            source = "Europe PMC" if pmid_str.startswith("EPMC_") else "PubMed"
            content_text += f"- [{source} | {p['condition']} | ID: {p['pmid']}]\n"
            content_text += f"  Τίτλος: {p['title_el']}\n"
            content_text += f"  Περίληψη: {p['summary_el']}\n"
            content_text += f"  Κύριο Εύρημα: {p['key_finding_el']}\n"
            content_text += f"  Γιατί Έχει Σημασία: {p['why_it_matters_el']}\n\n"

    if trials:
        content_text += "=== ΚΛΙΝΙΚΕΣ ΔΟΚΙΜΕΣ (ClinicalTrials.gov) ===\n"
        for t in trials:
            content_text += f"- [ClinicalTrials.gov | {t['condition']} | Φάση: {t['phase']} | NCT: {t['nct_id']}]\n"
            content_text += f"  Τίτλος: {t['title_el']}\n"
            content_text += f"  Παρεμβάσεις/Φάρμακα: {t['interventions']}\n"
            content_text += f"  Στόχος Δοκιμής: {t['summary_el']}\n\n"

    prompt = f"""
Είσαι ένας κορυφαίος επιστημονικός δημοσιογράφος και αναλυτής νευρολογίας, ειδικευμένος στον άτυπο παρκινσονισμό (MSA, PSP, CBS/CBD, DLB).

Αποστολή σου είναι να συντάξεις μια ΠΛΟΥΣΙΑ, ΑΝΑΛΥΤΙΚΗ και ΠΕΡΙΕΚΤΙΚΗ σύνθεση με ΟΛΑ τα νέα δεδομένα από PubMed, Europe PMC (preprints) και ClinicalTrials.gov σε μια ενιαία, κατανοητή εικόνα για τον ασθενή και τη φροντίδα του.

⚠️ ΑΥΣΤΗΡΕΣ ΟΔΗΓΙΕΣ ΠΕΡΙΕΧΟΜΕΝΟΥ:
1. ΑΝΑΦΕΡΟΥ ΣΕ ΣΥΓΚΕΚΡΙΜΕΝΑ ΟΝΟΜΑΤΑ: Αν υπάρχουν συγκεκριμένες ουσίες, μόρια, φάρμακα (π.χ. TPN-101, DYR533), βιοδείκτες (α-συνουκλεΐνη, tau, RT-QuIC, AQP4) ή τεχνικές (QSM, FDG-PET, wearable gait analysis), ΠΡΕΠΕΙ να αναφερθούν ονομαστικά.
2. ΚΑΛΥΨΕ ΟΛΕΣ ΤΙΣ ΠΗΓΕΣ: Συνδύασε ευρήματα τόσο από δημοσιεύσεις όσο και από κλινικές δοκιμές/preprints χωρίς να παραλείψεις σημαντικές ανακαλύψεις.
3. ΔΙΑΧΩΡΙΣΕ ΣΤΑΔΙΑ: Διαχώρισε σαφώς τα ευρήματα σε:
   - Θεραπευτικές δοκιμές & Φάρμακα σε εξέλιξη (Clinical trials / interventional).
   - Νέους Βιοδείκτες, Διάγνωση & Απεικόνιση (MRI, PET, βιοϋγρά, αισθητήρες).
   - Βασική Έρευνα, Μηχανισμούς & Αποκατάσταση (παθολογία, φυσικοθεραπεία).

⚠️ ΣΗΜΑΝΤΙΚΗ ΟΔΗΓΙΑ ΜΟΡΦΟΠΟΙΗΣΗΣ:
Επίστρεψε το κείμενο ΑΠΟΚΛΕΙΣΤΙΚΑ σε μορφή HTML code (χωρίς ```html codeblocks).

Ακολούθησε αυστηρά την παρακάτω δομή HTML:

<p>
    <ul>
        <li>MSA = Πολλαπλή συστηματική ατροφία</li>
        <li>PSP = Προϊούσα υπερπυρηνική παράλυση</li>
        <li>CBS = Φλοιοβασικό σύνδρομο</li>
        <li>CBD = Φλοιοβασική εκφύλιση</li>
        <li>DLB = Άνοια με σωμάτια Lewy</li>
    </ul>
</p>

<h2>🎯 Κύριο Συμπέρασμα της Ημέρας</h2>
<p>[Πλούσια παράγραφος που δίνει το κεντρικό στίγμα όλων των σημερινών ευρημάτων μαζί.]</p>

<h2>💊 Νέες Θεραπείες & Κλινικές Δοκιμές</h2>
<ul>
  <li>
    <strong>[Όνομα Φαρμάκου / Παρέμβασης & Φάση]:</strong> [Αναλυτική περιγραφή της δράσης και των αποτελεσμάτων].
    <br><em>👉 Τι σημαίνει για τον ασθενή:</em> [Πρακτική ερμηνεία και προοπτική].
  </li>
</ul>

<h2>🧬 Διαγνωστικοί Βιοδείκτες & Απεικόνιση</h2>
<ul>
  <li>
    <strong>[Εύρημα / Τεχνική / Βιοδείκτης]:</strong> [Τι ανακαλύφθηκε και πώς βοηθά στην έγκαιρη διάγνωση ή διαφοροποίηση των νόσων].
  </li>
</ul>

<h2>🧠 Μηχανισμοί Νόσου & Αποκατάσταση</h2>
<ul>
  <li>
    <strong>[Θέμα Έρευνας / Αποκατάσταση]:</strong> [Ευρήματα για φυσικοθεραπεία, μοριακούς μηχανισμούς ή συμπτώματα].
  </li>
</ul>

<h2>💡 Τι Κρατάμε (Πρακτικά Συμπεράσματα)</h2>
<ul>
  <li>[Πρακτικό συμπέρασμα με βάση τα νέα δεδομένα]</li>
  <!-- Μπορείς να προσθέσεις περισσότερα bullet points αν χρειάζεται -->
</ul>

Οδηγίες Στυλ:
- Χρησιμοποίησε καθαρά ελληνικά με ακριβή ιατρική ορολογία όπου χρειάζεται, επεξηγώντας την.
- Απέφευγε γενικόλογες φράσεις όπως "οι μελέτες δείχνουν υποσχόμενα αποτελέσματα". Γράψε ΣΥΓΚΕΚΡΙΜΕΝΑ τι βρέθηκε.

Δεδομένα προς ανάλυση:
{content_text}
"""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"[ERROR] Αποτυχία δημιουργίας εκλαϊκευμένης σύνοψης: {e}")
        return "Ακολουθεί η αναλυτική ενημέρωση για τις νέες δημοσιεύσεις και κλινικές δοκιμές."

def build_email_body():
    connection = get_connection()
    cursor = connection.cursor()

    # 1. Ανάκτηση Δημοσιεύσεων (PubMed & Europe PMC)
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

    # Υπολογισμός συνολικού αριθμού άρθρων/δοκιμών
    total_articles = len(papers) + len(trials)

    # Δημιουργία της εκλαϊκευμένης σύνοψης μέσω OpenAI
    print("[AI] Δημιουργία σύνοψης...")
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
            <div class="summary-title">💡 Σύνοψη της Ημέρας (Πηγές: PubMed, ClinicalTrials.gov και Europe PMC) (Αριθμός δημοσιεύσεων: {total_articles})</div>
            <p>{layman_summary}</p>
        </div>
    """

    # Ενότητα Δημοσιεύσεων (PubMed & Europe PMC)
    if papers:
        html += f"<h3>📚 Νέες Δημοσιεύσεις PubMed & Europe PMC ({len(papers)})</h3>"
        for p in papers:
            pmid_str = str(p['pmid'])
            if pmid_str.startswith("EPMC_"):
                raw_id = pmid_str.replace("EPMC_", "")
                article_url = f"[https://europepmc.org/article/MED/](https://europepmc.org/article/MED/){raw_id}"
                source_label = "Europe PMC"
            else:
                article_url = f"[https://pubmed.ncbi.nlm.nih.gov/](https://pubmed.ncbi.nlm.nih.gov/){pmid_str}/"
                source_label = "PubMed"

            html += f"""
            <div class="card">
                <div class="meta">
                    <span class="badge">{p['condition']}</span> | Πηγή: {source_label} | Σημαντικότητα: {p['importance']}/5 | ID: <a href="{article_url}" target="_blank">{p['pmid']}</a>
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

    receiver_emails = [email.strip() for email in receiver_email_raw.split(",") if email.strip()]

    msg = MIMEMultipart("alternative")
    msg["Subject"] = "🧠 Ενημέρωση Έρευνας: Νέες Δημοσιεύσεις & Κλινικές Δοκιμές"
    msg["From"] = sender_email
    msg["To"] = ", ".join(receiver_emails)
    msg.attach(MIMEText(html_body, "html"))

    try:
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(sender_email, sender_password)
        server.sendmail(sender_email, receiver_emails, msg.as_string())
        server.quit()
        print("Το email στάλθηκε επιτυχώς!")
    except Exception as e:
        print(f"[ERROR] Αποτυχία αποστολής email: {e}")
    
if __name__ == "__main__":
    send_email()
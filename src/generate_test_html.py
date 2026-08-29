import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
SRC_DIR = BASE_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

# Import build_email_body directly from send_report without triggering send_email()
from send_report import build_email_body

def generate_test_html():
    print("[TEST] Generating HTML email report from database...")
    
    result = build_email_body()
    
    if not result:
        print("[INFO] No unsent papers or clinical trials found in the database.")
        print("[INFO] Creating placeholder HTML file for layout inspection.")
        html_content = """<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Email Report Test</title>
</head>
<body>
    <h2>🧠 Ημερήσια Ενημέρωση Άτυπου Παρκινσονισμού</h2>
    <p>Δεν υπάρχουν νέα δεδομένα προς αποστολή στη βάση δεδομένων.</p>
</body>
</html>"""
    else:
        html_body, pmids = result
        html_content = html_body
        print(f"[SUCCESS] Generated HTML for {len(pmids)} PubMed paper(s) & associated clinical trials.")

    # Save to HTML file in the root directory
    output_file = BASE_DIR / "email_report_test.html"
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(html_content)

    print(f"[DONE] File saved to: {output_file}")
    print("[SAFE] No records were marked as sent in the database.")

if __name__ == "__main__":
    generate_test_html()
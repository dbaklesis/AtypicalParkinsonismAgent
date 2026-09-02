# src/telegram_daemon.py
import os
import time
import requests
from dotenv import load_dotenv
from database import get_unsent_telegram_papers, mark_telegram_sent
from executive_summary import generate_executive_summary

load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")


def send_telegram_alert(paper: dict) -> bool:
    if not BOT_TOKEN or not CHAT_ID:
        print("[TELEGRAM] Error: TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID missing in .env")
        return False

    title = paper.get("title_el") or paper.get("title", "Χωρίς τίτλο")
    condition = paper.get("condition", "N/A")
    importance = paper.get("importance", 0)
    pmid = paper.get("pmid", "")

    message = (
        f"<b>🚨 Νέα Σημαντική Δημοσίευση ({importance}/5)</b>\n\n"
        f"<b>Πάθηση:</b> {condition}\n"
        f"<b>PMID:</b> {pmid}\n"
        f"<b>Τίτλος:</b> {title}\n\n"
        f"<b>📌 Βασικό Ευρημα:</b>\n{paper.get('key_finding_el', 'N/A')}\n\n"
        f"<b>💡 Γιατί έχει σημασία:</b>\n{paper.get('why_it_matters_el', 'N/A')}\n\n"
        f"<b>🔍 Περίληψη:</b>\n{paper.get('summary_el', 'N/A')}\n\n"
        f"<b>⚠️ Περιορισμοί:</b>\n{paper.get('limitations_el', 'N/A')}"
    )

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }

    try:
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        return True
    except Exception as err:
        print(f"[TELEGRAM ERROR] Failed to push PMID {pmid}: {err}")
        return False

def send_telegram_summary(summary: str) -> bool:
    if not BOT_TOKEN or not CHAT_ID:
        print("[TELEGRAM] Error: TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID missing in .env")
        return False

    message = f"<b>📊 Εβδομαδιαία Εκτελεστική Σύνοψη</b>\n\n{summary}"

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }

    try:
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
    except Exception as err:
        print(f"[TELEGRAM ERROR] Failed to send executive summary: {err}")

def run_daemon(poll_interval, days_back):
    print("=" * 60)
    print("Telegram Notification Daemon Started")
    print(f"Monitoring DB for papers with importance >= 4 every {poll_interval} seconds...")
    print("=" * 60)

    while True:
        try:
            pending_papers = get_unsent_telegram_papers()

            for paper in pending_papers:
                pmid = paper["pmid"]
                print(f"[TELEGRAM] New target found: PMID {pmid} (Importance: {paper['importance']})")

                if send_telegram_alert(paper):
                    mark_telegram_sent(pmid)
                    print(f"[TELEGRAM] Sent & marked telegram_sent = 1 for {pmid}")

            summary = generate_executive_summary(days_back=1)
            if summary:
                send_telegram_summary(summary)

        except Exception as e:
            print(f"[TELEGRAM DAEMON EXCEPTION] {e}")

       

        time.sleep(poll_interval)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Telegram Notification Daemon")
    parser.add_argument("--poll-interval", type=int, default=3600, help="Χρόνος αναζήτησης για νέες δημοσιεύσεις σε δευτερόλεπτα (προεπιλογή: 3600s / 1 hour)")
    parser.add_argument("--summary-days-back", type=int, default=7, help="Χρόνος αναζήτησες δυμοσιεύσεων σε ημέρες για την περίληψη")

    args = parser.parse_args()
    
    run_daemon(poll_interval=args.poll_interval, days_back=args.summary_days_back)
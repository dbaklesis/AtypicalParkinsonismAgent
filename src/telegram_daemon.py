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

import html
import re

def clean_html(text: str) -> str:
    """
    Removes unsupported HTML tags (like <sup>, <sub>, <div>, etc.) 
    and safely escapes standard characters for Telegram HTML mode.
    """
    if not text:
        return "N/A"
    
    # Remove unsupported HTML tags while preserving their inner text content
    text = re.sub(r'</?(?:sup|sub|span|div|p|br|font)[^>]*>', '', text, flags=re.IGNORECASE)
    
    # Escape special HTML characters (<, >, &) for Telegram
    return html.escape(text)


def send_telegram_alert(paper: dict) -> bool:
    # Clean and escape all incoming text fields
    title = clean_html(paper.get("title_el") or paper.get("title", "Χωρίς τίτλο"))
    condition = clean_html(paper.get("condition", "N/A"))
    pmid = clean_html(paper.get("pmid", ""))
    key_finding = clean_html(paper.get("key_finding_el", "N/A"))
    why_it_matters = clean_html(paper.get("why_it_matters_el", "N/A"))
    summary = clean_html(paper.get("summary_el", "N/A"))
    limitations = clean_html(paper.get("limitations_el", "N/A"))
    importance = paper.get("importance", 0)

    # Construct message using ONLY Telegram-supported tags (<b>, <i>, etc.)
    message = (
        f"<b>🚨 Νέα Σημαντική Δημοσίευση ({importance}/5)</b>\n\n"
        f"<b>Πάθηση:</b> {condition}\n"
        f"<b>PMID:</b> {pmid}\n"
        f"<b>Τίτλος:</b> {title}\n\n"
        f"<b>📌 Βασικό Ευρημα:</b>\n{key_finding}\n\n"
        f"<b>💡 Γιατί έχει σημασία:</b>\n{why_it_matters}\n\n"
        f"<b>🔍 Περίληψη:</b>\n{summary}\n\n"
        f"<b>⚠️ Περιορισμοί:</b>\n{limitations}"
    )

    # Ensure message stays within Telegram's 4,096 character limit
    if len(message) > 4000:
        message = message[:3997] + "..."

    # ... execute API POST request ...

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
    except requests.exceptions.HTTPError as err:
        print(f"[TELEGRAM ERROR] Failed to push PMID {pmid}: {err}")
        if err.response is not None:
            print(f"[TELEGRAM API RESPONSE] {err.response.text}")
        return False

def send_telegram_summary(summary: str) -> bool:
    if not BOT_TOKEN or not CHAT_ID:
        print("[TELEGRAM] Error: TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID missing in .env")
        return False

    message = f"<b>📊 Εβδομαδιαία Εκτελεστική Σύνοψη</b>\n\n{summary}"

     # Ensure message stays within Telegram's 4,096 character limit
    if len(message) > 4000:
        message = message[:3997] + "..."

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
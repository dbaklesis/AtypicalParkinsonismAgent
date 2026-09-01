# src/telegram_daemon.py
import os
import time
import requests
from dotenv import load_dotenv
from database import get_unsent_telegram_papers, mark_telegram_sent

load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
POLL_INTERVAL_SECONDS = 3600  # Check database every 30 min


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


def run_daemon():
    print("=" * 60)
    print("Telegram Notification Daemon Started")
    print(f"Monitoring DB for papers with importance >= 4 every {POLL_INTERVAL_SECONDS}s...")
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

        except Exception as e:
            print(f"[TELEGRAM DAEMON EXCEPTION] {e}")

        time.sleep(POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    run_daemon()
import os
import requests
from dotenv import load_dotenv

load_dotenv()

token = os.getenv("TELEGRAM_BOT_TOKEN")
chat_id = os.getenv("TELEGRAM_CHAT_ID")

url = f"https://api.telegram.org/bot{token}/sendMessage"
payload = {
    "chat_id": chat_id,
    "text": "🧪 ** Test Message **\nYour Telegram Research Bot is successfully connected!",
    "parse_mode": "Markdown",
}

response = requests.post(url, json=payload)

if response.status_code == 200:
    print("Success! Check your phone for the notification.")
else:
    print("Failed to send message:", response.json())
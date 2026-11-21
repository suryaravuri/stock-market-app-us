"""Print your Telegram chat id.

1. Put TELEGRAM_BOT_TOKEN=<token from @BotFather> in .env
2. In Telegram, send any message (e.g. "hi") to your bot
3. Run:  python -m app.scripts.telegram_chat_id
4. Put the printed TELEGRAM_CHAT_ID=... line in .env and restart the backend
"""
import sys

import requests

from app.core.config import settings


def main() -> None:
    token = settings.telegram_bot_token
    if not token:
        sys.exit("TELEGRAM_BOT_TOKEN is not set in .env")
    response = requests.get(f"https://api.telegram.org/bot{token}/getUpdates", timeout=15)
    if response.status_code != 200:
        sys.exit(f"Telegram refused the token (HTTP {response.status_code}). Check TELEGRAM_BOT_TOKEN.")
    chats = {}
    for update in response.json().get("result", []):
        message = update.get("message") or update.get("edited_message") or {}
        chat = message.get("chat") or {}
        if chat.get("id"):
            chats[chat["id"]] = chat.get("first_name") or chat.get("title") or ""
    if not chats:
        sys.exit("No messages found. Send 'hi' to your bot in Telegram, then run this again.")
    for chat_id, name in chats.items():
        print(f"TELEGRAM_CHAT_ID={chat_id}    ({name})")


if __name__ == "__main__":
    main()

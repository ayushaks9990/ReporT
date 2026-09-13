from __future__ import annotations

import html
import os
import smtplib
from email.message import EmailMessage

import requests


def send_email(destination: str, title: str, content: str) -> None:
    user = os.getenv("GMAIL_USER", "").strip()
    password = os.getenv("GMAIL_APP_PASSWORD", "").strip()
    if not user or not password:
        raise RuntimeError("Email delivery is not configured")

    message = EmailMessage()
    message["Subject"] = f"AI Analytic Platform · {title}"
    message["From"] = user
    message["To"] = destination
    message.set_content(content)
    message.add_alternative(
        "<div style='font-family:Arial,sans-serif;max-width:760px;margin:auto'>"
        f"<h1>{html.escape(title)}</h1>"
        f"<pre style='white-space:pre-wrap;font:15px/1.7 Arial'>{html.escape(content)}</pre>"
        "</div>",
        subtype="html",
    )
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=20) as smtp:
        smtp.login(user, password)
        smtp.send_message(message)


def send_telegram(chat_id: str, title: str, content: str) -> None:
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        raise RuntimeError("Telegram delivery is not configured")
    text = f"*{title}*\n\n{content}"
    chunks = [text[index:index + 3900] for index in range(0, len(text), 3900)]
    for chunk in chunks:
        response = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": chunk},
            timeout=20,
        )
        response.raise_for_status()

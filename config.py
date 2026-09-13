"""Configuration for the report generation system."""
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
try:
    from dotenv import load_dotenv

    load_dotenv(PROJECT_ROOT / ".env")
except ImportError:
    # Environment variables still work when python-dotenv is not installed.
    pass

# OpenAI Configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()

# ChromaDB Configuration
CHROMA_DB_PATH = os.getenv("CHROMA_DB_PATH", str(PROJECT_ROOT / "chroma_db"))
COLLECTION_NAME = os.getenv("COLLECTION_NAME", "sales_marketing_data")
DATA_DIR = os.getenv("DATA_DIR", str(PROJECT_ROOT / "data"))

# AutoGen Configuration
AUTOGEN_CONFIG = {
    "config_list": [
        {
            "model": "gpt-4o-mini",
            "api_key": OPENAI_API_KEY,
        }
    ],
    "temperature": 0.7,
}

# Email Configuration
GMAIL_USER = os.getenv("GMAIL_USER", "")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "")
RECIPIENT_EMAIL = os.getenv("RECIPIENT_EMAIL", "")

# Scheduler Configuration
SCHEDULE_TIME = os.getenv("SCHEDULE_TIME", "09:00")
TIMEZONE = os.getenv("TIMEZONE", "Asia/Kolkata")

# Telegram Configuration
TELEGRAM_API_ID = int(os.getenv("TELEGRAM_API_ID", "0") or "0")
TELEGRAM_API_HASH = os.getenv("TELEGRAM_API_HASH", "")
TELEGRAM_PHONE = os.getenv("TELEGRAM_PHONE", "")

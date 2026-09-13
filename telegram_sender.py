from __future__ import annotations
import asyncio
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

from telethon import TelegramClient # Telegram client that connects your Python program to Telegram.
from telethon.tl.functions.contacts import ImportContactsRequest # Adds a phone number to your Telegram contacts.
from telethon.tl.types import InputPhoneContact

# ============================================================
# CONFIG
# ============================================================

try:
    from config import (
        TELEGRAM_API_ID,
        TELEGRAM_API_HASH,
        TELEGRAM_PHONE,
    )
except Exception as e:
    raise RuntimeError(
        "Missing Telegram configuration in config.py. "
        "Please define TELEGRAM_API_ID, TELEGRAM_API_HASH, and TELEGRAM_PHONE."
    ) from e

SESSION_NAME = os.getenv("TELEGRAM_SESSION_NAME", "report_generator_session_v2")

REPORT_EXTENSIONS = {
    ".txt", ".pdf", ".csv", ".xlsx", ".xls", ".docx", ".doc"
}
CHART_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"
}
MAX_RETRIES = int(os.getenv("TELEGRAM_MAX_RETRIES", "3"))

# ============================================================
# LOGGING
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("telegram_sender")


# ============================================================
# CLIENT FACTORY
# ============================================================

def get_client() -> TelegramClient:
    """
    Create a fresh Telethon client instance.

    A new client per run helps reduce SQLite session locking in:
    - Streamlit reruns
    - scheduler.py runs
    - overlapping local tests
    """
    if not TELEGRAM_API_ID or not TELEGRAM_API_HASH:
        raise RuntimeError("TELEGRAM_API_ID and TELEGRAM_API_HASH are required.")
    return TelegramClient(
        SESSION_NAME,
        TELEGRAM_API_ID,
        TELEGRAM_API_HASH,
    )


# ============================================================
# FILE HELPERS
# ============================================================

def validate_file(filepath: str) -> bool:
    return bool(filepath) and os.path.isfile(filepath)


def list_files(directory: str) -> List[str]:
    if not os.path.isdir(directory):
        return []
    return [
        os.path.join(directory, f)
        for f in sorted(os.listdir(directory))
        if os.path.isfile(os.path.join(directory, f))
    ]


def find_files_auto() -> Tuple[List[str], List[str]]:
    """
    Search reports and charts folders automatically.

    Priority:
      1) ./reports and ./charts
      2) current directory by file extension
    """
    reports = list_files("reports")
    charts = list_files("charts")

    if reports or charts:
        return reports, charts

    cwd_reports: List[str] = []
    cwd_charts: List[str] = []

    for name in sorted(os.listdir(".")):
        if not os.path.isfile(name):
            continue

        ext = Path(name).suffix.lower()
        abs_path = os.path.abspath(name)

        if ext in REPORT_EXTENSIONS:
            cwd_reports.append(abs_path)
        elif ext in CHART_EXTENSIONS:
            cwd_charts.append(abs_path)

    return cwd_reports, cwd_charts


def find_latest_report() -> Optional[str]:
    reports = list_files("reports")
    if not reports:
        return None
    return max(reports, key=os.path.getmtime)


# ============================================================
# TELEGRAM HELPERS
# ============================================================

async def ensure_client_started(client: TelegramClient, phone: Optional[str] = None) -> None:
    """
    Connect and authenticate the client if needed.
    """
    if not client.is_connected():
        await client.connect()

    if not await client.is_user_authorized():
        logger.info("Telegram login required...")
        await client.start(phone=phone or TELEGRAM_PHONE)


async def resolve_recipient(client: TelegramClient, phone: str):
    """
    Resolve a phone number to a Telegram entity.
    If it doesn't exist in contacts, import it and try again.
    """
    try:
        return await client.get_input_entity(phone)
    except Exception:
        logger.info("Importing recipient contact: %s", phone)
        contact = InputPhoneContact(
            client_id=0,
            phone=phone,
            first_name="Report",
            last_name="Recipient",
        )
        await client(ImportContactsRequest([contact]))
        return await client.get_input_entity(phone)


def _file_caption(filepath: str, prefix: str) -> str:
    name = Path(filepath).stem.replace("_", " ").title()
    return f"{prefix} {name}"


def build_header() -> str:
    now = datetime.now().strftime("%d %B %Y • %I:%M %p")
    return (
        "📊 <b>AI Sales & Marketing Report</b>\n\n"
        f"🕒 Generated: {now}\n"
        "━━━━━━━━━━━━━━━━━━━━━━"
    )


def build_footer() -> str:
    return (
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "✅ Delivery Completed\n\n"
        "🤖 AutoGen Multi-Agent System\n"
        "🧠 GROQ LLM\n"
        "📚 RAG Powered Analytics\n"
        "📈 Automated Reporting"
    )


# ============================================================
# SEND FUNCTIONS
# ============================================================

async def send_message(client: TelegramClient, peer, message: str) -> bool:
    """
    Safe message send with retries.
    """
    last_exc = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            await client.send_message(peer, message, parse_mode="html")
            return True
        except Exception as e:
            last_exc = e
            logger.warning("Message send failed (%s/%s): %s", attempt, MAX_RETRIES, e)
            if attempt < MAX_RETRIES:
                await asyncio.sleep(2)
    if last_exc:
        raise last_exc
    return False


async def send_document(client: TelegramClient, peer, filepath: str, caption: str) -> bool:
    """
    Send a single file with retries.
    """
    if not validate_file(filepath):
        logger.warning("Missing file: %s", filepath)
        return False

    last_exc = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            await client.send_file(peer, filepath, caption=caption)
            logger.info("Sent file: %s", os.path.basename(filepath))
            return True
        except Exception as e:
            last_exc = e
            logger.warning("Upload failed (%s/%s): %s", attempt, MAX_RETRIES, e)
            if attempt < MAX_RETRIES:
                await asyncio.sleep(2)

    if last_exc:
        raise last_exc
    return False


async def send_reports_and_charts(
    client: TelegramClient,
    peer,
    reports: Sequence[str],
    charts: Sequence[str],
) -> None:
    """
    Send header, charts, reports, footer.
    """
    await send_message(client, peer, build_header())

    if charts:
        await send_message(client, peer, "📈 <b>Charts & Visualizations</b>")
        for chart in charts:
            if not chart:
                continue
            await send_document(
                client,
                peer,
                chart,
                _file_caption(chart, "📊"),
            )

    if reports:
        await send_message(client, peer, "📄 <b>Generated Reports</b>")
        for report in reports:
            if not report:
                continue
            await send_document(
                client,
                peer,
                report,
                _file_caption(report, "📄"),
            )

    await send_message(client, peer, build_footer())


# ============================================================
# PUBLIC API FOR APP / SCHEDULER
# ============================================================

async def send_telegram_reports(
    reports: Optional[Sequence[str]],
    charts: Optional[Sequence[str]],
    phone: Optional[str] = None,
) -> bool:
    """
    Send reports and charts to a recipient.

    This is the function app.py and scheduler.py should call.
    """
    target = phone or TELEGRAM_PHONE
    if not target:
        logger.error("Telegram recipient phone is not configured.")
        return False
    client = get_client()

    try:
        async with client:
            await ensure_client_started(client, phone=target)
            peer = await resolve_recipient(client, target)
            await send_reports_and_charts(
                client,
                peer,
                reports or [],
                charts or [],
            )
        logger.info("Telegram delivery completed successfully.")
        return True
    except Exception as e:
        logger.exception("Telegram delivery failed: %s", e)
        return False


async def test_telegram(phone: Optional[str] = None) -> bool:
    """
    Send a small test message to verify Telegram integration.
    """
    target = phone or TELEGRAM_PHONE
    if not target:
        logger.error("Telegram recipient phone is not configured.")
        return False
    client = get_client()

    try:
        async with client:
            await ensure_client_started(client, phone=target)
            peer = await resolve_recipient(client, target)
            await send_message(
                client,
                peer,
                """
🚀 <b>Telegram Integration Test</b>

Your AI reporting system is connected successfully.

✅ Telethon Working
✅ Authentication Working
✅ Message Delivery Working
                """.strip(),
            )
        logger.info("Telegram test successful.")
        return True
    except Exception as e:
        logger.exception("Telegram test failed: %s", e)
        return False


# ============================================================
# ASYNC RUNNER
# ============================================================

def run_async(coro):
    """
    Streamlit-safe async runner.

    - If no loop is running, executes immediately.
    - If a loop is already running, returns a Task.
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    else:
        return loop.create_task(coro)


# ============================================================
# CLI
# ============================================================
# Then The Parse_args() reads any command-line options (like --phone or --test) so they can override the default settings in config.py.
def parse_args():
    import argparse

    parser = argparse.ArgumentParser(description="Send reports and charts to Telegram")
    parser.add_argument("--test", action="store_true", help="Send a test message")
    parser.add_argument("--phone", help="Override recipient phone number")
    parser.add_argument("--reports", nargs="*", help="Explicit report files to send")
    parser.add_argument("--charts", nargs="*", help="Explicit chart files to send")
    parser.add_argument("--send", action="store_true", help="Force send files from reports/charts folders")
    return parser.parse_args()


def _cli_main() -> int:
    args = parse_args()

    if args.test:
        logger.info("Sending Telegram test message...")
        ok = run_async(test_telegram(args.phone))
        return 0 if ok else 1

    if args.reports is not None or args.charts is not None:
        reports = [os.path.abspath(p) for p in (args.reports or [])]
        charts = [os.path.abspath(p) for p in (args.charts or [])]
    elif args.send:
        reports, charts = find_files_auto()
    else:
        reports, charts = find_files_auto()
        if not reports and not charts:
            logger.info("No files found; sending a test message instead.")
            ok = run_async(test_telegram(args.phone))
            return 0 if ok else 1

    logger.info("Reports: %s | Charts: %s", len(reports), len(charts))
    ok = run_async(send_telegram_reports(reports, charts, args.phone))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(_cli_main())

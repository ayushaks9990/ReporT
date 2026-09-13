"""
scheduler.py
"""
import os
import sys
import time
import json
import logging
import asyncio
from pathlib import Path
from datetime import datetime, timedelta

import pytz # Then The for time zones
import schedule

from config import (
    PROJECT_ROOT,
    SCHEDULE_TIME,
    TIMEZONE,
    RECIPIENT_EMAIL
)

from report_generator import (
    generate_sales_performance_report,
    generate_marketing_campaign_report,
    generate_quarterly_summary_report,
    save_report_to_file
)

from visualizations import generate_all_charts
from email_sender_html import send_html_email_with_charts

try:
    from telegram_sender import send_telegram_reports
except Exception:
    send_telegram_reports = None


# ==========================================================
# CONFIG
# ==========================================================

REPORT_DIR = Path(PROJECT_ROOT) / "reports"
CHART_DIR = Path(PROJECT_ROOT) / "charts"
LOG_DIR = Path(PROJECT_ROOT) / "logs"

REPORT_DIR.mkdir(exist_ok=True)
CHART_DIR.mkdir(exist_ok=True)
LOG_DIR.mkdir(exist_ok=True)

# ==========================================================
# LOGGING
# ==========================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "scheduler.log"),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


# ==========================================================
# HELPERS
# ==========================================================

def get_current_quarter():
    month = datetime.now(pytz.timezone(TIMEZONE)).month

    if month <= 3:
        return "Q1"
    elif month <= 6:
        return "Q2"
    elif month <= 9:
        return "Q3"

    return "Q4"


def save_run_metadata(metadata):
    history_file = LOG_DIR / "run_history.json"

    history = []

    if history_file.exists():
        try:
            history = json.loads(history_file.read_text(encoding="utf-8"))
        except Exception:
            history = []

    history.append(metadata)

    history_file.write_text(
        json.dumps(history, indent=2),
        encoding="utf-8",
    )


def cleanup_old_files(days=30):
    cutoff = datetime.now() - timedelta(days=days)

    for folder in [REPORT_DIR, CHART_DIR]:

        for file in folder.glob("*"):

            modified = datetime.fromtimestamp(
                file.stat().st_mtime
            )

            if modified < cutoff:
                try:
                    file.unlink()
                    logger.info(f"Deleted old file: {file}")
                except Exception as e:
                    logger.warning(f"Cleanup failed: {e}")


# ==========================================================
# REPORT GENERATION
# ==========================================================

def generate_reports():

    now = datetime.now(pytz.timezone(TIMEZONE))
    quarter = f"{get_current_quarter()} {now.year}"

    timestamp = now.strftime("%Y%m%d_%H%M%S")

    report_files = []

    logger.info("Generating sales report...")

    sales = generate_sales_performance_report()

    sales_file = REPORT_DIR / f"sales_{timestamp}.txt"

    save_report_to_file(sales, str(sales_file))

    report_files.append(str(sales_file))

    logger.info("Generating marketing report...")

    marketing = generate_marketing_campaign_report()

    marketing_file = REPORT_DIR / f"marketing_{timestamp}.txt"

    save_report_to_file(marketing, str(marketing_file))

    report_files.append(str(marketing_file))

    logger.info("Generating executive summary...")

    summary = generate_quarterly_summary_report(
        quarter
    )

    summary_file = REPORT_DIR / f"executive_summary_{timestamp}.txt"

    save_report_to_file(summary, str(summary_file))

    report_files.append(str(summary_file))

    return report_files


# ==========================================================
# TELEGRAM
# ==========================================================

def send_to_telegram(report_files, chart_files):

    if not send_telegram_reports:
        logger.warning("Telegram sender unavailable")
        return False

    try:

        asyncio.run(
            send_telegram_reports(
                report_files,
                chart_files
            )
        )

        logger.info("Telegram delivery successful")

        return True

    except Exception as e:

        logger.error(f"Telegram error: {e}")

        return False


# ==========================================================
# MAIN JOB
# ==========================================================

def daily_job():

    logger.info("=" * 80)
    logger.info("STARTING DAILY REPORT JOB")
    logger.info("=" * 80)

    started = datetime.now(pytz.timezone(TIMEZONE))

    metadata = {
        "timestamp": started.isoformat(),
        "email_sent": False,
        "telegram_sent": False,
        "reports": [],
        "charts": []
    }

    try:

        # --------------------------------------------------
        # REPORTS
        # --------------------------------------------------

        reports = generate_reports()

        metadata["reports"] = reports

        logger.info("Reports generated")

        # --------------------------------------------------
        # CHARTS
        # --------------------------------------------------

        charts = generate_all_charts()

        charts = [
            os.path.abspath(c)
            for c in charts
            if os.path.exists(c)
        ]

        metadata["charts"] = charts

        logger.info(
            f"{len(charts)} charts generated"
        )

        # --------------------------------------------------
        # EMAIL
        # --------------------------------------------------

        try:

            email_ok = send_html_email_with_charts(
                reports,
                charts
            )

            metadata["email_sent"] = bool(email_ok)

        except Exception as e:

            logger.exception(
                f"Email delivery failed: {e}"
            )

        # --------------------------------------------------
        # TELEGRAM
        # --------------------------------------------------

        try:

            metadata["telegram_sent"] = send_to_telegram(
                reports,
                charts
            )

        except Exception as e:

            logger.exception(
                f"Telegram delivery failed: {e}"
            )

        # --------------------------------------------------
        # HOUSEKEEPING
        # --------------------------------------------------

        cleanup_old_files(30)

        metadata["status"] = "success"

        logger.info("Daily job completed")

    except Exception as e:

        metadata["status"] = "failed"

        metadata["error"] = str(e)

        logger.exception("Daily job failed")

    finally:

        save_run_metadata(metadata)

    return metadata


# ==========================================================
# TEST MODE
# ==========================================================

def run_now():

    logger.info(
        "Running immediate test execution..."
    )

    result = daily_job()

    print("\nRESULT:\n")

    print(
        json.dumps(
            result,
            indent=2
        )
    )


# ==========================================================
# SCHEDULER
# ==========================================================

def start_scheduler():

    logger.info("=" * 80)

    logger.info(
        f"Scheduler started "
        f"({TIMEZONE})"
    )

    logger.info(
        f"Schedule Time: {SCHEDULE_TIME}"
    )

    logger.info(
        f"Recipient: {RECIPIENT_EMAIL}"
    )

    logger.info("=" * 80)

    schedule.every().day.at(
        SCHEDULE_TIME,
        TIMEZONE,
    ).do(
        daily_job
    )

    while True:

        schedule.run_pending()

        time.sleep(30)


# ==========================================================
# ENTRYPOINT
# ==========================================================

if __name__ == "__main__":

    if len(sys.argv) > 1:

        cmd = sys.argv[1].lower()

        if cmd == "now":

            run_now()

        else:

            print(
                "Usage:\n"
                "python scheduler.py\n"
                "python scheduler.py now"
            )

    else:

        start_scheduler()

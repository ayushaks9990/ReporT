import os
import re
import time
import mimetypes
import logging
import traceback
import smtplib # Connects to an SMTP server (e.g., Gmail) and sends emails.

from datetime import datetime

from email.mime.text import MIMEText # Creates plain text or HTML email content.
from email.mime.multipart import MIMEMultipart # Creates an email with multiple parts (text, HTML, attachments, images).
from email.mime.application import MIMEApplication # Attaches general files like PDFs, TXT, DOCX, HTML, ZIP, etc.
from email.mime.image import MIMEImage # Embeds or attaches image files (PNG, JPEG, GIF, etc.).
from config import GMAIL_USER, GMAIL_APP_PASSWORD, RECIPIENT_EMAIL
from html_email_template import create_html_email

logger = logging.getLogger(__name__)

if not logger.handlers:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s"
    )


def _safe_file_exists(path):
    return bool(path) and os.path.isfile(path)


def _guess_attachment_type(filepath):
    mime_type, _ = mimetypes.guess_type(filepath)
    if mime_type:
        main, sub = mime_type.split("/", 1)
        return main, sub
    return "application", "octet-stream"


def _extract_report_preview(report_files, max_chars=1800):
    try:
        if not report_files:
            return ""

        for report in report_files:
            if _safe_file_exists(report):
                with open(report, "r", encoding="utf-8", errors="ignore") as f:
                    text = f.read(max_chars)
                return text.strip()

        return ""
    except Exception:
        return ""


def _build_email_statistics(report_files, chart_files):
    return {
        "report_count": len(report_files or []),
        "chart_count": len(chart_files or []),
        "generated_at": datetime.now().strftime("%B %d, %Y %I:%M %p")
    }


def _make_cid_from_filename(path):
    base = os.path.splitext(os.path.basename(path))[0]
    base = re.sub(r"[^a-zA-Z0-9_\-]", "_", base)
    return base


def _attach_inline_chart(msg, chart_path, cid):
    main_type, sub_type = _guess_attachment_type(chart_path)

    with open(chart_path, "rb") as img_file:
        data = img_file.read()

    if main_type == "image" and sub_type.lower() in {"png", "jpeg", "jpg", "gif", "webp"}:
        img = MIMEImage(data, _subtype="jpeg" if sub_type.lower() == "jpg" else sub_type)
    else:
        img = MIMEApplication(data, _subtype=sub_type)

    img.add_header("Content-ID", f"<{cid}>")
    img.add_header("Content-Disposition", "inline", filename=os.path.basename(chart_path))
    msg.attach(img)


def _attach_file(msg, filepath):
    main_type, sub_type = _guess_attachment_type(filepath)

    with open(filepath, "rb") as f:
        data = f.read()

    if main_type == "text":
        try:
            text = data.decode("utf-8", errors="ignore")
            attachment = MIMEText(text, _subtype=sub_type, _charset="utf-8")
        except Exception:
            attachment = MIMEApplication(data, _subtype=sub_type)
    else:
        attachment = MIMEApplication(data, _subtype=sub_type)

    attachment.add_header(
        "Content-Disposition",
        "attachment",
        filename=os.path.basename(filepath)
    )
    msg.attach(attachment)


def _send_via_gmail(msg, retries=3, delay_seconds=3):
    last_error = None

    for attempt in range(1, retries + 1):
        try:
            with smtplib.SMTP("smtp.gmail.com", 587, timeout=60) as smtp:
                smtp.starttls()
                smtp.login(GMAIL_USER, GMAIL_APP_PASSWORD.replace(" ", ""))
                smtp.send_message(msg)
            return True
        except Exception as e:
            last_error = e
            logger.error(f"SMTP attempt {attempt} failed: {e}")
            if attempt < retries:
                time.sleep(delay_seconds)

    if last_error:
        raise last_error

    return False


def send_html_email_with_charts(
    report_files,
    chart_files,
    recipient_email=None,
    subject=None,
    html_report_path=None,
    company_name="AI Sales Intelligence Platform"
):
    recipient = recipient_email or RECIPIENT_EMAIL

    if not GMAIL_USER:
        logger.error("Missing GMAIL_USER")
        return False

    if not GMAIL_APP_PASSWORD:
        logger.error("Missing GMAIL_APP_PASSWORD")
        return False

    if not recipient:
        logger.error("Missing recipient email")
        return False

    try:
        stats = _build_email_statistics(report_files, chart_files)
        report_preview = _extract_report_preview(report_files)
        today = datetime.now().strftime("%B %d, %Y")

        email_subject = subject or f"📊 AI Sales & Marketing Report - {today}"

        chart_cids = []
        msg = MIMEMultipart("related")
        msg["From"] = GMAIL_USER
        msg["To"] = recipient
        msg["Subject"] = email_subject

        alternative = MIMEMultipart("alternative")
        msg.attach(alternative)

        report_names = [os.path.basename(x) for x in (report_files or []) if x]

        for chart in chart_files or []:
            if _safe_file_exists(chart):
                chart_cids.append(_make_cid_from_filename(chart))

        plain_text = f"""
AI Sales & Marketing Report

Generated:
{stats['generated_at']}

Reports Attached:
{stats['report_count']}

Charts Attached:
{stats['chart_count']}

Preview:

{report_preview[:1000]}

Generated Automatically
AI Reporting Platform
""".strip()

        alternative.attach(MIMEText(plain_text, "plain", "utf-8"))

        html_content = create_html_email(
            summary=report_preview,
            metrics={
                "generated_at": stats["generated_at"],
                "report_count": stats["report_count"],
                "chart_count": stats["chart_count"],
                "today": today
            },
            reports=report_names,
            available_charts=chart_cids,
            company_name=company_name
        )

        alternative.attach(MIMEText(html_content, "html", "utf-8"))

        logger.info("Embedding charts")

        for chart in chart_files or []:
            if not _safe_file_exists(chart):
                logger.warning(f"Chart missing: {chart}")
                continue

            cid = _make_cid_from_filename(chart)
            _attach_inline_chart(msg, chart, cid)
            logger.info(f"Embedded chart: {os.path.basename(chart)}")

        logger.info("Attaching reports")

        for filepath in report_files or []:
            if not _safe_file_exists(filepath):
                logger.warning(f"Report missing: {filepath}")
                continue

            _attach_file(msg, filepath)
            logger.info(f"Attached report: {os.path.basename(filepath)}")

        if html_report_path and _safe_file_exists(html_report_path):
            _attach_file(msg, html_report_path)
            logger.info(f"Attached HTML report: {os.path.basename(html_report_path)}")

        logger.info(f"Connecting SMTP -> {recipient}")
        _send_via_gmail(msg, retries=3, delay_seconds=3)
        logger.info(f"Email sent successfully -> {recipient}")

        return True

    except Exception as e:
        logger.error(f"Email sending failed: {e}")
        traceback.print_exc()
        return False


if __name__ == "__main__":
    sample_reports = [
        "reports/sample_report.txt"
    ]

    sample_charts = [
        "charts/sales_by_region.png"
    ]

    success = send_html_email_with_charts(
        sample_reports,
        sample_charts,
        html_report_path="reports/executive_dashboard.html"
    )

    print("SUCCESS" if success else "FAILED")

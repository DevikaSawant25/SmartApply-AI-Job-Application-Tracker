import imaplib
import email
from email.header import decode_header
import html
import re
import os
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv

from backend.ai import parse_job_email
from backend.database import (
    is_email_processed,
    log_email_action,
    find_or_create_job_from_email,
)

load_dotenv()


def _decode_mime_words(raw_header: Optional[str]) -> str:
    """Decodes MIME encoded email headers into clean unicode strings."""
    if not raw_header:
        return ""
    decoded_fragments = []
    for fragment, encoding in decode_header(raw_header):
        if isinstance(fragment, bytes):
            try:
                decoded_fragments.append(fragment.decode(encoding or "utf-8", errors="replace"))
            except Exception:
                decoded_fragments.append(fragment.decode("latin1", errors="replace"))
        else:
            decoded_fragments.append(str(fragment))
    return " ".join(decoded_fragments)


def _clean_body_text(raw_text: str) -> str:
    """Removes HTML tags, URLs, and excess whitespace to feed clean text to Claude."""
    # Strip HTML tags
    text = re.sub(r"<style.*?</style>", "", raw_text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<script.*?</script>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    # Condense whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _extract_body(msg: email.message.Message) -> str:
    """Extracts plain text (or fallback HTML) body from an email Message object."""
    body_parts = []
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            content_disposition = str(part.get("Content-Disposition"))
            if "attachment" not in content_disposition:
                if content_type in ["text/plain", "text/html"]:
                    payload = part.get_payload(decode=True)
                    if payload:
                        charset = part.get_content_charset() or "utf-8"
                        try:
                            decoded = payload.decode(charset, errors="replace")
                            body_parts.append(decoded)
                        except Exception:
                            body_parts.append(payload.decode("latin1", errors="replace"))
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            charset = msg.get_content_charset() or "utf-8"
            try:
                body_parts.append(payload.decode(charset, errors="replace"))
            except Exception:
                body_parts.append(payload.decode("latin1", errors="replace"))

    full_raw = " ".join(body_parts)
    return _clean_body_text(full_raw)


async def process_email_content(
    subject: str,
    sender: str,
    body: str,
    email_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Processes an email through Claude, extracts job data, and updates or creates a job record.
    """
    if email_id and await is_email_processed(email_id):
        return {
            "status": "skipped",
            "reason": "Email already processed previously.",
            "email_id": email_id,
        }

    # Use Claude to parse the email
    parsed = parse_job_email(subject=subject, sender=sender, body=body)

    is_job = parsed.get("is_job_email", False)
    company = parsed.get("company")
    role = parsed.get("role") or "Applicant"
    stage = parsed.get("status") or "applied"
    summary = parsed.get("summary") or "Application confirmation received"

    if is_job and company:
        # Match or create job in database
        result = await find_or_create_job_from_email(
            company=company,
            role=role,
            status=stage,
            summary=summary,
            sender=sender,
        )
        action_taken = result.get("action", "processed")

        # Log event
        await log_email_action(
            email_id=email_id,
            sender=sender,
            subject=subject,
            company=company,
            role=role,
            detected_status=stage,
            summary=summary,
            action_taken=action_taken,
        )

        return {
            "status": "success",
            "action": action_taken,
            "company": company,
            "role": role,
            "stage": stage,
            "summary": summary,
            "job": result.get("job"),
        }
    else:
        # Log non-job email or skipped email
        await log_email_action(
            email_id=email_id,
            sender=sender,
            subject=subject,
            company=None,
            role=None,
            detected_status=None,
            summary=summary,
            action_taken="ignored_non_job",
        )
        return {
            "status": "ignored",
            "reason": "Email not recognized as a job application notification.",
            "summary": summary,
        }


def fetch_and_sync_imap_emails(limit: int = 15) -> List[Dict[str, Any]]:
    """
    Synchronously connects to IMAP server, queries recent messages, and extracts email bodies.
    """
    imap_server = os.getenv("EMAIL_IMAP_SERVER", "imap.gmail.com")
    imap_port = int(os.getenv("EMAIL_IMAP_PORT", "993"))
    email_address = os.getenv("EMAIL_ADDRESS")
    app_password = os.getenv("EMAIL_APP_PASSWORD")

    if not email_address or not app_password:
        raise ValueError("EMAIL_ADDRESS and EMAIL_APP_PASSWORD must be configured in .env to sync with your inbox.")

    results = []
    mail = imaplib.IMAP4_SSL(imap_server, imap_port)
    try:
        mail.login(email_address, app_password)
        mail.select("INBOX", readonly=True)

        # Search for recent emails matching application keywords
        # First try to search for unseen emails or recent emails
        status, messages = mail.search(None, "ALL")
        if status != "OK" or not messages[0]:
            return []

        email_ids = messages[0].split()
        # Take the most recent 'limit' emails
        recent_ids = email_ids[-limit:]
        recent_ids.reverse()

        for eid in recent_ids:
            uid_str = eid.decode("utf-8")
            res, msg_data = mail.fetch(eid, "(RFC822)")
            if res != "OK":
                continue

            for response_part in msg_data:
                if isinstance(response_part, tuple):
                    msg = email.message_from_bytes(response_part[1])
                    subject = _decode_mime_words(msg.get("Subject"))
                    sender = _decode_mime_words(msg.get("From"))
                    body = _extract_body(msg)

                    results.append(
                        {
                            "email_id": uid_str,
                            "subject": subject,
                            "sender": sender,
                            "body": body,
                        }
                    )
    finally:
        try:
            mail.close()
            mail.logout()
        except Exception:
            pass

    return results

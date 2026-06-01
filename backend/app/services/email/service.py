import imaplib
import smtplib
import email
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import decode_header
import logging
from typing import Optional

from app.services.email import graph

logger = logging.getLogger(__name__)

PROVIDER_CONFIG = {
    "gmail": {
        "imap_host": "imap.gmail.com",
        "imap_port": 993,
        "smtp_host": "smtp.gmail.com",
        "smtp_port": 587
    },
    "outlook": {
        "imap_host": "outlook.office365.com",
        "imap_port": 993,
        "smtp_host": "smtp-mail.outlook.com",
        "smtp_port": 587
    },
    "yahoo": {
        "imap_host": "imap.mail.yahoo.com",
        "imap_port": 993,
        "smtp_host": "smtp.mail.yahoo.com",
        "smtp_port": 587
    }
}


def _is_oauth(config) -> bool:
    return getattr(config, "auth_type", "basic") == "oauth"


def decode_str(s):
    if s is None:
        return ""
    decoded = decode_header(s)
    result = ""
    for part, encoding in decoded:
        if isinstance(part, bytes):
            result += part.decode(encoding or "utf-8", errors="replace")
        else:
            result += str(part)
    return result


def get_email_body(msg) -> str:
    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            disposition = str(part.get("Content-Disposition"))
            if content_type == "text/plain" and "attachment" not in disposition:
                try:
                    body = part.get_payload(decode=True).decode("utf-8", errors="replace")
                    break
                except Exception:
                    pass
    else:
        try:
            body = msg.get_payload(decode=True).decode("utf-8", errors="replace")
        except Exception:
            pass
    return body[:3000]  # Limitar a 3000 chars


def connect_imap(config) -> imaplib.IMAP4_SSL:
    imap = imaplib.IMAP4_SSL(config.imap_host or PROVIDER_CONFIG.get(config.provider, {}).get("imap_host"),
                              config.imap_port or 993)
    imap.login(config.email_address, config.app_password)
    return imap


async def fetch_inbox(config, limit: int = 10) -> list:
    # --- Outlook / Graph ---
    if _is_oauth(config):
        token = await graph.get_access_token(config.oauth_refresh_token)
        return await graph.fetch_inbox_graph(token, limit)

    # --- IMAP (Gmail, etc.) ---
    try:
        imap = connect_imap(config)
        imap.select("INBOX")

        _, messages = imap.search(None, "ALL")
        email_ids = messages[0].split()
        email_ids = email_ids[-limit:]  # Últimos N emails

        emails = []
        for eid in reversed(email_ids):
            _, msg_data = imap.fetch(eid, "(RFC822)")
            msg = email.message_from_bytes(msg_data[0][1])

            emails.append({
                "id": eid.decode(),
                "subject": decode_str(msg.get("Subject", "")),
                "from": decode_str(msg.get("From", "")),
                "date": msg.get("Date", ""),
                "body": get_email_body(msg),
                "read": False
            })

        imap.logout()
        return emails

    except Exception as e:
        logger.error(f"Error fetching inbox: {e}")
        raise Exception(f"Error al conectar con el email: {str(e)}")


async def fetch_unread(config, limit: int = 10) -> list:
    # --- Outlook / Graph ---
    if _is_oauth(config):
        token = await graph.get_access_token(config.oauth_refresh_token)
        return await graph.fetch_unread_graph(token, limit)

    # --- IMAP (Gmail, etc.) ---
    try:
        imap = connect_imap(config)
        imap.select("INBOX")

        _, messages = imap.search(None, "UNSEEN")
        email_ids = messages[0].split()
        email_ids = email_ids[-limit:]

        emails = []
        for eid in reversed(email_ids):
            _, msg_data = imap.fetch(eid, "(RFC822)")
            msg = email.message_from_bytes(msg_data[0][1])

            emails.append({
                "id": eid.decode(),
                "subject": decode_str(msg.get("Subject", "")),
                "from": decode_str(msg.get("From", "")),
                "date": msg.get("Date", ""),
                "body": get_email_body(msg),
                "read": False
            })

        imap.logout()
        return emails

    except Exception as e:
        logger.error(f"Error fetching unread: {e}")
        raise Exception(f"Error al obtener emails no leídos: {str(e)}")


async def send_email(config, to: str, subject: str, body: str) -> bool:
    # --- Outlook / Graph ---
    if _is_oauth(config):
        token = await graph.get_access_token(config.oauth_refresh_token)
        return await graph.send_mail_graph(token, to, subject, body)

    # --- SMTP (Gmail, etc.) ---
    try:
        smtp_host = config.smtp_host or PROVIDER_CONFIG.get(config.provider, {}).get("smtp_host")
        smtp_port = config.smtp_port or 587

        msg = MIMEMultipart()
        msg["From"] = config.email_address
        msg["To"] = to
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain", "utf-8"))

        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.ehlo()
            server.starttls()
            server.login(config.email_address, config.app_password)
            server.sendmail(config.email_address, to, msg.as_string())

        return True

    except Exception as e:
        logger.error(f"Error sending email: {e}")
        raise Exception(f"Error al enviar email: {str(e)}")

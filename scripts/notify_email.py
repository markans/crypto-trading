#!/usr/bin/env python3
"""
Email notifications for trading signals.

Configuration is read from environment variables (or .env via load_dotenv):

    SMTP_HOST       SMTP server hostname (e.g. smtp.gmail.com)
    SMTP_PORT       SMTP port (default 587 for STARTTLS, 465 for SSL)
    SMTP_USERNAME   SMTP login username
    SMTP_PASSWORD   SMTP login password / app password
    SMTP_USE_TLS    "true"/"false" (default true). Ignored on port 465 (SSL).
    EMAIL_FROM      Sender address (defaults to SMTP_USERNAME)
    EMAIL_TO        Recipient address(es), comma-separated

Email is best-effort: if SMTP is not configured the helper prints a notice and
returns False instead of raising, so signal runs never fail just because email
delivery is unavailable.
"""

from __future__ import annotations

import os
import smtplib
import ssl
from email.message import EmailMessage


def _split_recipients(raw: str) -> list[str]:
    return [part.strip() for part in raw.replace(";", ",").split(",") if part.strip()]


def email_config() -> dict[str, object] | None:
    """Return the email configuration, or None if not fully configured."""
    host = os.getenv("SMTP_HOST", "").strip()
    username = os.getenv("SMTP_USERNAME", "").strip()
    password = os.getenv("SMTP_PASSWORD", "").strip()
    recipients = _split_recipients(os.getenv("EMAIL_TO", ""))

    if not host or not recipients:
        return None

    # Env vars injected from unset GitHub secrets arrive as empty strings, which
    # would otherwise override these defaults. Fall back when blank.
    port = int((os.getenv("SMTP_PORT", "").strip() or "587"))
    use_tls = (os.getenv("SMTP_USE_TLS", "").strip().lower() or "true") in {"1", "true", "yes", "on"}
    sender = os.getenv("EMAIL_FROM", "").strip() or username

    if not sender:
        return None

    return {
        "host": host,
        "port": port,
        "username": username,
        "password": password,
        "use_tls": use_tls,
        "sender": sender,
        "recipients": recipients,
    }


def send_email(subject: str, body: str) -> bool:
    """Send a plain-text email. Returns True on success, False if skipped/failed."""
    config = email_config()
    if config is None:
        print("email: skipped (SMTP_HOST / EMAIL_TO not configured)")
        return False

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = config["sender"]
    message["To"] = ", ".join(config["recipients"])
    message.set_content(body)

    try:
        if config["port"] == 465:
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL(config["host"], config["port"], context=context, timeout=30) as server:
                if config["username"]:
                    server.login(config["username"], config["password"])
                server.send_message(message)
        else:
            with smtplib.SMTP(config["host"], config["port"], timeout=30) as server:
                if config["use_tls"]:
                    server.starttls(context=ssl.create_default_context())
                if config["username"]:
                    server.login(config["username"], config["password"])
                server.send_message(message)
    except Exception as exc:  # noqa: BLE001 - email must never break a signal run
        print(f"email: failed to send ({exc})")
        return False

    print(f"email: sent to {', '.join(config['recipients'])}")
    return True

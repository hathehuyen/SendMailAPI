"""SMTP delivery of plain-text notifications."""
import logging
import re
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import getaddresses

from flask import current_app

logger = logging.getLogger(__name__)

#: Collapses "a,, b" / "a , , b" / trailing separators into a single ", ".
_SEPARATORS = re.compile(r"(?:\s*,\s*)+")


class MailError(Exception):
    """Raised when a message cannot be built or handed over to the SMTP server."""


def parse_recipients(raw):
    """Turn a comma separated address list into clean, validated addresses.

    Display names are accepted (``Ops <ops@example.com>``) but only the bare
    address is kept, because the envelope recipient must not contain one.
    Empty entries and a trailing separator are tolerated so a hand-written
    configuration does not break delivery.
    """
    raw = (raw or "").strip()
    if not raw:
        raise MailError("No recipient is configured (RCPT_TO is empty).")

    normalized = _SEPARATORS.sub(", ", raw).strip(", ")
    addresses = [address for _, address in getaddresses([normalized]) if address]

    if not addresses:
        raise MailError("No recipient is configured (RCPT_TO is empty).")

    invalid = [address for address in addresses if "@" not in address]
    if invalid:
        raise MailError("Invalid recipient address: " + ", ".join(invalid))

    return addresses



def build_message(msgtext, subject, sender, recipients):
    """Build a UTF-8, plain-text MIME message."""
    message = MIMEMultipart("alternative")
    message["Subject"] = subject
    message["From"] = sender
    message["To"] = ", ".join(recipients)
    message.attach(MIMEText(msgtext, "plain", "utf-8"))
    return message


def _open_connection(settings):
    """Open an SMTP connection honouring the transport settings."""
    if settings["SMTP_USE_SSL"]:
        return smtplib.SMTP_SSL(
            settings["SMTP_HOST"],
            settings["SMTP_PORT"],
            timeout=settings["SMTP_TIMEOUT"],
        )
    return smtplib.SMTP(
        settings["SMTP_HOST"],
        settings["SMTP_PORT"],
        timeout=settings["SMTP_TIMEOUT"],
    )


def _close_connection(client):
    """Say goodbye politely, falling back to an abrupt close."""
    try:
        client.quit()
    except smtplib.SMTPException:
        client.close()


def send_mail(msgtext):
    """Deliver ``msgtext`` to the configured recipients.

    Returns the list of envelope recipients on success and raises
    :class:`MailError` when the SMTP server rejects the message.
    """
    settings = current_app.config
    sender = settings["FROM"]
    recipients = parse_recipients(settings["RCPT_TO"])
    message = build_message(msgtext, settings["SUBJECT"], sender, recipients)

    try:
        client = _open_connection(settings)
        try:
            if settings["SMTP_USE_STARTTLS"] and not settings["SMTP_USE_SSL"]:
                client.starttls()
            if settings["SMTP_USERNAME"]:
                client.login(settings["SMTP_USERNAME"], settings["SMTP_PASSWORD"])
            client.sendmail(sender, recipients, message.as_string())
        finally:
            _close_connection(client)
    except (smtplib.SMTPException, OSError) as exc:
        raise MailError(str(exc)) from exc

    logger.info("Message delivered to %d recipient(s)", len(recipients))
    return recipients

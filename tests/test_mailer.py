"""Unit tests for the SMTP service."""
import smtplib
from unittest.mock import MagicMock, patch

import pytest

from sendmail_api.services.mailer import (
    MailError,
    build_message,
    parse_recipients,
    send_mail,
)

SMTP = "sendmail_api.services.mailer.smtplib.SMTP"
SMTP_SSL = "sendmail_api.services.mailer.smtplib.SMTP_SSL"


# --- recipient parsing ------------------------------------------------------

def test_splits_and_strips_a_comma_separated_list():
    assert parse_recipients("a@example.com, b@example.com") == [
        "a@example.com",
        "b@example.com",
    ]


def test_keeps_only_the_address_of_a_display_name():
    assert parse_recipients("Ops Team <ops@example.com>") == ["ops@example.com"]


def test_drops_empty_entries():
    assert parse_recipients("a@example.com, , b@example.com,") == [
        "a@example.com",
        "b@example.com",
    ]


def test_tolerates_spaces_around_separators():
    assert parse_recipients("  a@example.com ,b@example.com  ") == [
        "a@example.com",
        "b@example.com",
    ]


def test_keeps_a_quoted_display_name_with_a_comma():
    assert parse_recipients('"Doe, John" <john@example.com>') == ["john@example.com"]


@pytest.mark.parametrize("raw", ["", "   ", None], ids=["empty", "blank", "none"])
def test_requires_at_least_one_recipient(raw):
    with pytest.raises(MailError):
        parse_recipients(raw)


def test_rejects_an_address_without_a_domain():
    with pytest.raises(MailError) as error:
        parse_recipients("not-an-address")

    assert "not-an-address" in str(error.value)


# --- message building -------------------------------------------------------

def test_builds_a_utf8_plain_text_message():
    message = build_message(
        "Nhiệt độ cao", "System Email", "noreply@example.com", ["ops@example.com"]
    )

    assert message["Subject"] == "System Email"
    assert message["From"] == "noreply@example.com"
    assert message["To"] == "ops@example.com"

    part = message.get_payload(0)
    assert part.get_content_type() == "text/plain"
    assert part.get_content_charset() == "utf-8"
    assert part.get_payload(decode=True).decode("utf-8") == "Nhiệt độ cao"


# --- delivery ---------------------------------------------------------------

def test_uses_the_configured_smtp_server(app):
    server = MagicMock()

    with app.app_context(), patch(SMTP, return_value=server) as smtp:
        recipients = send_mail("hello")

    smtp.assert_called_once_with("localhost", 25, timeout=10)
    server.sendmail.assert_called_once()
    server.quit.assert_called_once_with()
    assert recipients == ["ops@example.com", "oncall@example.com"]


def test_passes_envelope_sender_and_recipients(app):
    server = MagicMock()

    with app.app_context(), patch(SMTP, return_value=server):
        send_mail("hello")

    sender, recipients, _ = server.sendmail.call_args[0]
    assert sender == "noreply@example.com"
    assert recipients == ["ops@example.com", "oncall@example.com"]


def test_starts_tls_and_authenticates_when_configured(app):
    app.config.update(SMTP_USE_STARTTLS=True, SMTP_USERNAME="user", SMTP_PASSWORD="secret")
    server = MagicMock()

    with app.app_context(), patch(SMTP, return_value=server):
        send_mail("hello")

    server.starttls.assert_called_once_with()
    server.login.assert_called_once_with("user", "secret")


def test_uses_smtp_ssl_when_configured(app):
    app.config.update(SMTP_USE_SSL=True, SMTP_PORT=465)
    server = MagicMock()

    with app.app_context(), patch(SMTP_SSL, return_value=server) as smtp_ssl:
        send_mail("hello")

    smtp_ssl.assert_called_once_with("localhost", 465, timeout=10)
    server.starttls.assert_not_called()


def test_wraps_smtp_errors_in_a_domain_error(app):
    server = MagicMock()
    server.sendmail.side_effect = smtplib.SMTPServerDisconnected("boom")

    with app.app_context(), patch(SMTP, return_value=server):
        with pytest.raises(MailError):
            send_mail("hello")


def test_wraps_connection_errors_in_a_domain_error(app):
    with app.app_context(), patch(SMTP, side_effect=OSError("connection refused")):
        with pytest.raises(MailError):
            send_mail("hello")


def test_closes_the_connection_when_quit_fails(app):
    server = MagicMock()
    server.quit.side_effect = smtplib.SMTPServerDisconnected("already gone")

    with app.app_context(), patch(SMTP, return_value=server):
        send_mail("hello")

    server.close.assert_called_once_with()

"""Behaviour of the ``POST /send`` endpoint.

Delivery and persistence are patched out, so these tests cover the HTTP
contract: authentication, validation and the mapping from service failures to
status codes.
"""
from unittest.mock import patch

import pytest

from sendmail_api.services.mail_log import MailLogError
from sendmail_api.services.mailer import MailError

SEND_MAIL = "sendmail_api.api.send.sendapi.send_mail"
SAVE_LOG = "sendmail_api.api.send.sendapi.save_log"

RECIPIENTS = ["ops@example.com", "oncall@example.com"]


# --- authentication ---------------------------------------------------------

def test_rejects_request_without_api_key(client):
    response = client.post("/send", json={"msg": "hello"})

    assert response.status_code == 401
    assert response.get_json()["error"] == "unauthorized"
    assert response.headers["WWW-Authenticate"] == 'Bearer realm="sendmail_api"'


def test_rejects_request_with_wrong_api_key(client):
    response = client.post("/send", json={"msg": "hello"}, headers={"X-API-Key": "nope"})

    assert response.status_code == 401


def test_accepts_bearer_token(client):
    with patch(SEND_MAIL, return_value=RECIPIENTS), patch(SAVE_LOG):
        response = client.post(
            "/send",
            json={"msg": "hello"},
            headers={"Authorization": "Bearer test-api-key"},
        )

    assert response.status_code == 200


# --- successful delivery ----------------------------------------------------

def test_delivers_message_and_records_the_success(client, headers):
    with patch(SEND_MAIL, return_value=RECIPIENTS) as send, patch(SAVE_LOG) as log:
        response = client.post("/send", json={"msg": "  disk almost full  "}, headers=headers)

    assert response.status_code == 200
    assert response.get_json() == {"result": True, "recipients": 2, "logged": True}
    send.assert_called_once_with("  disk almost full  ")
    log.assert_called_once_with("  disk almost full  ", True)


def test_accepts_form_encoded_message(client, headers):
    with patch(SEND_MAIL, return_value=RECIPIENTS) as send, patch(SAVE_LOG):
        response = client.post("/send", data={"msg": "from a form"}, headers=headers)

    assert response.status_code == 200
    send.assert_called_once_with("from a form")


def test_accepts_message_from_query_string(client, headers):
    with patch(SEND_MAIL, return_value=RECIPIENTS) as send, patch(SAVE_LOG):
        response = client.post("/send?msg=from+a+query", headers=headers)

    assert response.status_code == 200
    send.assert_called_once_with("from a query")


def test_preserves_non_ascii_content(client, headers):
    with patch(SEND_MAIL, return_value=RECIPIENTS) as send, patch(SAVE_LOG):
        response = client.post("/send", json={"msg": "Nhiệt độ cao"}, headers=headers)

    assert response.status_code == 200
    assert response.get_json()["result"] is True
    send.assert_called_once_with("Nhiệt độ cao")


# --- validation -------------------------------------------------------------

@pytest.mark.parametrize(
    "payload",
    [
        pytest.param({}, id="missing"),
        pytest.param({"msg": ""}, id="empty"),
        pytest.param({"msg": "   "}, id="whitespace"),
        pytest.param({"msg": 42}, id="not-a-string"),
        pytest.param({"msg": None}, id="null"),
    ],
)
def test_rejects_invalid_message(client, headers, payload):
    response = client.post("/send", json=payload, headers=headers)

    assert response.status_code == 400
    body = response.get_json()
    assert body["result"] is False
    assert body["error"] == "invalid_request"


def test_rejects_message_longer_than_the_limit(client, headers):
    response = client.post("/send", json={"msg": "x" * 51}, headers=headers)

    assert response.status_code == 400
    assert "50" in response.get_json()["message"]


def test_rejects_body_larger_than_content_length(client, headers):
    response = client.post("/send", json={"msg": "x" * 5000}, headers=headers)

    assert response.status_code == 413
    assert response.get_json()["error"] == "payload_too_large"


def test_invalid_message_never_reaches_the_mailer(client, headers):
    with patch(SEND_MAIL) as send:
        client.post("/send", json={}, headers=headers)

    send.assert_not_called()


# --- failure handling -------------------------------------------------------

def test_reports_delivery_failure_and_audits_unsent_message(client, headers):
    with patch(SEND_MAIL, side_effect=MailError("connection refused")), patch(SAVE_LOG) as log:
        response = client.post("/send", json={"msg": "hello"}, headers=headers)

    assert response.status_code == 502
    body = response.get_json()
    assert body["result"] is False
    assert body["error"] == "smtp_error"
    assert body["logged"] is True
    # The implementation detail must not leak to the caller.
    assert "connection refused" not in body["message"]
    log.assert_called_once_with("hello", False)


def test_delivery_succeeds_even_when_the_audit_insert_fails(client, headers):
    with patch(SEND_MAIL, return_value=RECIPIENTS), patch(
        SAVE_LOG, side_effect=MailLogError("db down")
    ):
        response = client.post("/send", json={"msg": "hello"}, headers=headers)

    assert response.status_code == 200
    assert response.get_json() == {"result": True, "recipients": 2, "logged": False}


def test_reports_failed_audit_when_delivery_fails_too(client, headers):
    with patch(SEND_MAIL, side_effect=MailError("nope")), patch(
        SAVE_LOG, side_effect=MailLogError("db down")
    ):
        response = client.post("/send", json={"msg": "hello"}, headers=headers)

    assert response.status_code == 502
    assert response.get_json()["logged"] is False

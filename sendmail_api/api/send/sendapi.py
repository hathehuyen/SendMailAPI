"""``POST /send`` -- forward a text message to the configured recipients."""
import logging

from flask import Blueprint, current_app, jsonify, request

from sendmail_api.auth import require_api_key
from sendmail_api.services.mail_log import MailLogError, save_log
from sendmail_api.services.mailer import MailError, send_mail

logger = logging.getLogger(__name__)

send_blueprint = Blueprint("send", __name__)

#: Name of the payload field that carries the message body.
MESSAGE_FIELD = "msg"


def _error(code, message, status, logged=None):
    """Build a consistent JSON error response."""
    payload = {"result": False, "error": code, "message": message}
    if logged is not None:
        payload["logged"] = logged
    return jsonify(payload), status


def _extract_message():
    """Read ``msg`` from a JSON body, a form field or the query string.

    JSON wins when present so a caller can send a body without worrying about
    content type negotiation.
    """
    payload = request.get_json(silent=True)
    if isinstance(payload, dict) and MESSAGE_FIELD in payload:
        return payload[MESSAGE_FIELD]
    return request.values.get(MESSAGE_FIELD)


def _validate(msgtext, max_length):
    """Return a human readable problem description, or ``None`` when valid."""
    if msgtext is None:
        return "Field '{0}' is required.".format(MESSAGE_FIELD)
    if not isinstance(msgtext, str):
        return "Field '{0}' must be a string.".format(MESSAGE_FIELD)
    if not msgtext.strip():
        return "Field '{0}' must not be empty.".format(MESSAGE_FIELD)
    if len(msgtext) > max_length:
        return "Field '{0}' must not exceed {1} characters.".format(
            MESSAGE_FIELD, max_length
        )
    return None


def _store(content, sent):
    """Persist the audit row, reporting failure instead of raising."""
    try:
        save_log(content, sent)
    except MailLogError as exc:
        logger.error("Could not persist the mail log entry: %s", exc)
        return False
    return True


@send_blueprint.route("/send", methods=["POST"])
@require_api_key
def sendmail():
    """Deliver a message and record the outcome.

    A failed audit insert never fails an otherwise successful delivery: the
    response reports ``logged: false`` so the caller knows to reconcile.
    """
    msgtext = _extract_message()
    problem = _validate(msgtext, current_app.config["MAX_MESSAGE_LENGTH"])
    if problem is not None:
        return _error("invalid_request", problem, 400)

    try:
        recipients = send_mail(msgtext)
    except MailError as exc:
        logger.error("Delivery failed: %s", exc)
        return _error(
            "smtp_error",
            "The message could not be delivered.",
            502,
            logged=_store(msgtext, sent=False),
        )

    return (
        jsonify(result=True, recipients=len(recipients), logged=_store(msgtext, sent=True)),
        200,
    )


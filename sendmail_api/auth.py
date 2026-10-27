"""API-key authentication for the write endpoints."""
import hmac
import logging
from functools import wraps

from flask import current_app, jsonify, request

logger = logging.getLogger(__name__)


def _provided_key():
    """Read the caller's key from ``X-API-Key`` or ``Authorization: Bearer``."""
    header_key = request.headers.get("X-API-Key", "").strip()
    if header_key:
        return header_key

    scheme, _, credentials = request.headers.get("Authorization", "").partition(" ")
    if scheme.lower() == "bearer":
        return credentials.strip()
    return ""


def require_api_key(view):
    """Reject requests that do not carry the configured API key.

    The comparison is constant time so that response timing does not leak the
    expected value.
    """

    @wraps(view)
    def wrapper(*args, **kwargs):
        expected = current_app.config.get("SEND_API_KEY") or ""
        provided = _provided_key()

        if not expected or not hmac.compare_digest(
            provided.encode("utf-8"), expected.encode("utf-8")
        ):
            logger.warning(
                "Rejected %s %s from %s: invalid API key",
                request.method,
                request.path,
                request.remote_addr,
            )
            response = jsonify(
                result=False,
                error="unauthorized",
                message="A valid API key is required.",
            )
            response.status_code = 401
            response.headers["WWW-Authenticate"] = 'Bearer realm="sendmail_api"'
            return response

        return view(*args, **kwargs)

    return wrapper

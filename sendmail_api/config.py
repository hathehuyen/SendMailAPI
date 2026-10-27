"""Application configuration.

Every setting can be overridden with an environment variable of the same name so the
same package can be deployed to different environments without touching the source
tree. Values are resolved when this module is imported; tests override them through
``create_app(test_config=...)`` instead of mutating the environment.
"""
import os

_TRUTHY = ("1", "true", "yes", "on")


def _env(name, default=None):
    """Return a stripped environment value, falling back to ``default`` when unset."""
    raw = os.environ.get(name)
    if raw is None:
        return default
    raw = raw.strip()
    return raw if raw else default


def _env_bool(name, default=False):
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in _TRUTHY


def _env_int(name, default):
    raw = _env(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        raise RuntimeError(
            "Environment variable {0} must be an integer, got {1!r}".format(name, raw)
        )


class DefaultConfig(object):
    """Default settings, read from the environment."""

    # --- HTTP layer ---------------------------------------------------------
    # Hard cap on the raw request body; larger payloads are rejected with 413.
    MAX_CONTENT_LENGTH = _env_int("MAX_CONTENT_LENGTH", 1024 * 1024)
    # Business limit on the message body; longer messages are rejected with 400.
    MAX_MESSAGE_LENGTH = _env_int("MAX_MESSAGE_LENGTH", 10000)

    # --- Authentication -----------------------------------------------------
    # Shared secret required on every write endpoint. Mandatory.
    SEND_API_KEY = _env("SEND_API_KEY", "")

    # --- Message headers ----------------------------------------------------
    SUBJECT = _env("SUBJECT", "System Email")
    FROM = _env("FROM", "")
    # Comma separated list, e.g. "ops@example.com, oncall@example.com".
    RCPT_TO = _env("RCPT_TO", "")

    # --- SMTP transport -----------------------------------------------------
    SMTP_HOST = _env("SMTP_HOST", "localhost")
    SMTP_PORT = _env_int("SMTP_PORT", 25)
    SMTP_TIMEOUT = _env_int("SMTP_TIMEOUT", 10)
    SMTP_USERNAME = _env("SMTP_USERNAME", "")
    SMTP_PASSWORD = _env("SMTP_PASSWORD", "")
    SMTP_USE_STARTTLS = _env_bool("SMTP_USE_STARTTLS", False)
    SMTP_USE_SSL = _env_bool("SMTP_USE_SSL", False)

    # --- Audit database -----------------------------------------------------
    DB_HOST = _env("DB_HOST", "localhost")
    DB_PORT = _env_int("DB_PORT", 3306)
    DB_USER = _env("DB_USER", "")
    DB_PASSWORD = _env("DB_PASSWORD", "")
    DB_NAME = _env("DB_NAME", "maillog")
    DB_TIMEOUT = _env_int("DB_TIMEOUT", 10)

    # --- Observability ------------------------------------------------------
    LOG_LEVEL = _env("LOG_LEVEL", "INFO")

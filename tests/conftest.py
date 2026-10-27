"""Shared pytest fixtures.

Tests never touch the network: the SMTP client and the database driver are
patched per test, so the fixture only has to supply a deterministic config.
"""
import pytest

from sendmail_api import create_app

API_KEY = "test-api-key"


@pytest.fixture
def app():
    """Application instance configured for tests."""
    return create_app(
        {
            "TESTING": True,
            "SEND_API_KEY": API_KEY,
            "FROM": "noreply@example.com",
            "SUBJECT": "System Email",
            "RCPT_TO": "ops@example.com, oncall@example.com",
            "MAX_MESSAGE_LENGTH": 50,
            "MAX_CONTENT_LENGTH": 2048,
            "LOG_LEVEL": "CRITICAL",
        }
    )


@pytest.fixture
def client(app):
    """Flask test client bound to the test application."""
    return app.test_client()


@pytest.fixture
def headers():
    """Headers carrying a valid API key."""
    return {"X-API-Key": API_KEY}

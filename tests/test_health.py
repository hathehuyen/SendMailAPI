"""Tests for the liveness endpoint."""
from sendmail_api import __version__


def test_health_check_reports_service_metadata(client):
    response = client.get("/")

    assert response.status_code == 200
    assert response.get_json() == {
        "status": "ok",
        "service": "sendmail_api",
        "version": __version__,
    }


def test_unknown_route_is_not_found(client):
    assert client.get("/does-not-exist").status_code == 404


def test_send_rejects_other_methods(client):
    assert client.get("/send").status_code == 405

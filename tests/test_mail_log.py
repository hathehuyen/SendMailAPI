"""Unit tests for the audit-trail repository."""
from unittest.mock import MagicMock, patch

import mysql.connector
import pytest

from sendmail_api.services.mail_log import MailLogError, save_log

CONNECT = "sendmail_api.services.mail_log.mysql.connector.connect"


def _connection():
    connection = MagicMock()
    connection.cursor.return_value = MagicMock()
    return connection


def test_inserts_one_row_and_commits(app):
    connection = _connection()

    with app.app_context(), patch(CONNECT, return_value=connection):
        save_log("disk almost full", True)

    sql, params = connection.cursor.return_value.execute.call_args[0]
    assert "INSERT INTO maillog" in sql
    content, sent = params[1], params[2]
    assert content == "disk almost full"
    assert sent is True
    connection.commit.assert_called_once_with()
    connection.close.assert_called_once_with()


def test_records_failed_deliveries_as_unsent(app):
    connection = _connection()

    with app.app_context(), patch(CONNECT, return_value=connection):
        save_log("hello", False)

    assert connection.cursor.return_value.execute.call_args[0][1][2] is False


def test_uses_the_configured_database(app):
    app.config.update(
        DB_HOST="db.internal",
        DB_PORT=3307,
        DB_USER="logger",
        DB_PASSWORD="secret",
        DB_NAME="maillog",
        DB_TIMEOUT=5,
    )

    with app.app_context(), patch(CONNECT, return_value=_connection()) as connect:
        save_log("hello", True)

    connect.assert_called_once_with(
        host="db.internal",
        port=3307,
        user="logger",
        password="secret",
        database="maillog",
        connection_timeout=5,
    )


def test_wraps_connection_errors(app):
    with app.app_context(), patch(CONNECT, side_effect=mysql.connector.Error("refused")):
        with pytest.raises(MailLogError):
            save_log("hello", True)


def test_rolls_back_when_the_insert_fails(app):
    connection = _connection()
    connection.cursor.return_value.execute.side_effect = mysql.connector.Error("no table")

    with app.app_context(), patch(CONNECT, return_value=connection):
        with pytest.raises(MailLogError):
            save_log("hello", True)

    connection.rollback.assert_called_once_with()
    connection.close.assert_called_once_with()

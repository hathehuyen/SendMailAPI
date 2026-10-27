"""Persistence of the delivery audit trail in MariaDB/MySQL."""
import logging
from datetime import datetime

import mysql.connector
from flask import current_app

logger = logging.getLogger(__name__)

INSERT_SQL = "INSERT INTO maillog (time, content, sent) VALUES (%s, %s, %s)"


class MailLogError(Exception):
    """Raised when an audit row cannot be written."""


def _connect():
    settings = current_app.config
    return mysql.connector.connect(
        host=settings["DB_HOST"],
        port=settings["DB_PORT"],
        user=settings["DB_USER"],
        password=settings["DB_PASSWORD"],
        database=settings["DB_NAME"],
        connection_timeout=settings["DB_TIMEOUT"],
    )


def save_log(content, sent):
    """Append one row to ``maillog``.

    ``sent`` is stored as a boolean so a failed delivery is auditable too.
    Raises :class:`MailLogError` when the row cannot be persisted.
    """
    try:
        connection = _connect()
    except mysql.connector.Error as exc:
        raise MailLogError("Cannot connect to the log database: {0}".format(exc)) from exc

    try:
        cursor = connection.cursor()
        try:
            cursor.execute(INSERT_SQL, (datetime.now().replace(microsecond=0), content, bool(sent)))
            connection.commit()
        finally:
            cursor.close()
    except mysql.connector.Error as exc:
        connection.rollback()
        raise MailLogError("Cannot write to maillog: {0}".format(exc)) from exc
    finally:
        connection.close()

    logger.debug("Audit row written (sent=%s)", bool(sent))

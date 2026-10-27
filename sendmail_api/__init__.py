"""SendMailAPI -- an HTTP to SMTP relay with an auditable delivery log.

The application is built by :func:`create_app` so that tests and deployments can
supply their own configuration without mutating module level state. Flask also
detects this factory automatically, so ``flask --app sendmail_api run`` works.
"""
import logging

from flask import Flask, jsonify

from sendmail_api import config

__version__ = "2.0.0"

#: Settings without which the service must not start.
REQUIRED_SETTINGS = ("SEND_API_KEY", "FROM", "RCPT_TO")


def create_app(test_config=None):
    """Create and configure the Flask application."""
    app = Flask(__name__)
    app.config.from_object(config.DefaultConfig)
    if test_config:
        app.config.update(test_config)

    _configure_logging(app)
    _validate_settings(app)

    from sendmail_api.api import api_blueprint

    app.register_blueprint(api_blueprint)

    @app.get("/")
    def index():
        """Liveness probe: confirms the service booted and its configuration loaded."""
        return jsonify(status="ok", service="sendmail_api", version=__version__)

    @app.errorhandler(413)
    def request_entity_too_large(error):
        return (
            jsonify(
                result=False,
                error="payload_too_large",
                message="Request body must not exceed {0} bytes.".format(
                    app.config["MAX_CONTENT_LENGTH"]
                ),
            ),
            413,
        )

    return app


def _configure_logging(app):
    """Send application logs to stderr at the configured level."""
    level = getattr(logging, str(app.config.get("LOG_LEVEL", "INFO")).upper(), logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
    app.logger.setLevel(level)


def _validate_settings(app):
    """Fail fast instead of serving requests with an incomplete configuration."""
    missing = [name for name in REQUIRED_SETTINGS if not app.config.get(name)]
    if missing:
        raise RuntimeError(
            "Missing required configuration: {0}. Set the matching environment "
            "variables before starting the API.".format(", ".join(missing))
        )

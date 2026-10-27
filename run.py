"""Development entry point.

Production deployments should serve the factory with a WSGI server instead, e.g.
``gunicorn "sendmail_api:create_app()"``.
"""
import os

from sendmail_api import create_app

app = create_app()


if __name__ == "__main__":
    app.run(
        host=os.environ.get("HOST", "0.0.0.0"),
        port=int(os.environ.get("PORT", "5000")),
        debug=os.environ.get("DEBUG", "").lower() in ("1", "true", "yes"),
    )

"""HTTP endpoints, grouped by feature and exposed as a single blueprint."""
from flask import Blueprint

from sendmail_api.api.send import send_blueprint

api_blueprint = Blueprint("api", __name__)
api_blueprint.register_blueprint(send_blueprint)

__all__ = ["api_blueprint"]

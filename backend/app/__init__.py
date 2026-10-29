"""PaperTrail backend - Flask app factory."""
import os

from flask import Flask


def create_app(config=None):
    app = Flask(__name__)

    # Where uploaded PDFs are saved (backend/data/uploads by default)
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    app.config["UPLOAD_FOLDER"] = os.path.join(base_dir, "data", "uploads")
    app.config["MAX_CONTENT_LENGTH"] = 20 * 1024 * 1024  # 20 MB limit per upload

    if config:
        app.config.update(config)

    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    # CORS: let the frontend (opened from another origin) call this API.
    # For the prototype we allow any origin; restrict this before deploying.
    @app.after_request
    def add_cors_headers(response):
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
        return response

    from .auth import auth_bp
    from .routes import bp
    app.register_blueprint(auth_bp)
    app.register_blueprint(bp)

    return app

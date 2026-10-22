"""Local Flask app for furniture marketplace accounts and AI listing drafts."""

import hmac
import os
import re
import secrets
from pathlib import Path
from datetime import datetime, timezone

import click
from flask import Flask, abort, flash, g, jsonify, redirect, render_template, request, session, url_for

from ai.ollama_client import LocalAIError, get_model_status
from ai.prompts import (
    build_product_fallback,
    build_product_prompt,
    verified_product_result,
)
from ai.ollama_client import generate_text
from marketplace.admin import admin_bp, register_admin_commands
from marketplace.auth import auth_bp
from marketplace.database import close_db, get_db, init_db
from marketplace.profiles import profiles_bp
from marketplace.rate_limit import LocalRateLimiter
from marketplace.security import current_user, public_user
from marketplace.support import support_bp
from marketplace.storefront import storefront_bp

PRODUCT_REQUIRED_FIELDS = {"item_name": "Item name", "category": "Furniture category"}
PRODUCT_FIELDS = (
    "item_name", "category", "material", "condition", "dimensions",
    "price", "currency", "colour", "additional_details",
)


class PrivacyAwareFlask(Flask):
    """Avoid writing exception text or request data to default Flask logs."""

    def log_exception(self, exc_info):
        self.logger.error("Unhandled request exception; details suppressed")


def _load_or_create_secret(instance_path: str) -> str:
    key_path = Path(instance_path) / "secret_key"
    key_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        return key_path.read_text(encoding="ascii").strip()
    except FileNotFoundError:
        new_key = secrets.token_hex(32)
        try:
            with key_path.open("x", encoding="ascii") as key_file:
                key_file.write(new_key)
        except FileExistsError:
            return key_path.read_text(encoding="ascii").strip()
        return new_key


def create_app(test_config: dict | None = None) -> Flask:
    app = PrivacyAwareFlask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        DATABASE=os.path.join(app.instance_path, "marketplace.sqlite3"),
        MAX_CONTENT_LENGTH=32 * 1024 * 1024,
        SECRET_KEY=os.environ.get("MARKETPLACE_SECRET_KEY"),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=os.environ.get("MARKETPLACE_COOKIE_SECURE", "0") == "1",
        TEMPLATES_AUTO_RELOAD=True,
        APP_NAME=os.environ.get("MARKETPLACE_APP_NAME", "Furniture Marketplace"),
        APP_OWNER=os.environ.get("MARKETPLACE_APP_OWNER", ""),
        RATE_LIMITS={
            "auth.login": (10, 300),
            "auth.register": (5, 3600),
            "app.generate": (15, 3600),
            "support.create_ticket": (5, 3600),
            "support.ticket_detail": (20, 3600),
            "support.report_listing": (10, 3600),
            "support.report_user": (10, 3600),
            "support.privacy_requests": (5, 3600),
            "storefront.start_inquiry": (10, 3600),
            "storefront.conversation_detail": (40, 3600),
            "storefront.generate_reply_draft": (10, 3600),
        },
    )
    if test_config:
        app.config.update(test_config)
    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    if not app.config.get("SECRET_KEY"):
        app.config["SECRET_KEY"] = _load_or_create_secret(app.instance_path)

    def new_csrf_token() -> str:
        return secrets.token_urlsafe(32)

    app.extensions["new_csrf_token"] = new_csrf_token
    app.extensions["rate_limiter"] = LocalRateLimiter()

    @app.before_request
    def load_user_and_check_csrf():
        if request.path.startswith("/api/") and request.content_length and request.content_length > 64 * 1024:
            abort(413)
        if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            expected = session.get("csrf_token", "")
            supplied = request.form.get("csrf_token", "") or request.headers.get("X-CSRFToken", "")
            if not expected or not supplied or not hmac.compare_digest(expected, supplied):
                abort(400, description="The form expired or its security token was missing. Reload and try again.")
        elif "csrf_token" not in session:
            session["csrf_token"] = new_csrf_token()

        g.user = None
        user_id = session.get("user_id")
        if user_id is not None:
            user = get_db().execute(
                "SELECT * FROM users WHERE id = ?", (user_id,)
            ).fetchone()
            if user is None or user["account_status"] != "active":
                session.clear()
                session["csrf_token"] = new_csrf_token()
                flash("Your session ended because the account is unavailable.", "error")
            else:
                g.user = user

        rate_limits = app.config.get("RATE_LIMITS", {})
        rule = rate_limits.get(request.endpoint)
        if rule and request.method == "POST":
            limit, window_seconds = rule
            identity = request.remote_addr or "unknown"
            key = f"{request.endpoint}:{identity}"
            if not app.extensions["rate_limiter"].allow(key, limit, window_seconds):
                abort(429)

    @app.context_processor
    def inject_request_context():
        return {
            "current_user": public_user(current_user()),
            "csrf_token": session.get("csrf_token", ""),
            "app_name": app.config["APP_NAME"],
            "app_owner": app.config["APP_OWNER"],
            "current_year": datetime.now(timezone.utc).year,
        }

    @app.after_request
    def add_safe_content_headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'; object-src 'none'; img-src 'self'; script-src 'self'; style-src 'self'",
        )
        response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        if current_user() is not None or request.path.startswith(("/account", "/support", "/admin", "/privacy", "/reports")):
            response.headers["Cache-Control"] = "private, no-store"
        return response

    app.teardown_appcontext(close_db)
    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(profiles_bp)
    app.register_blueprint(support_bp)
    app.register_blueprint(storefront_bp)
    register_admin_commands(app)

    @app.cli.command("init-db")
    def init_db_command():
        init_db()
        click.echo("Marketplace database initialized.")

    @app.get("/")
    def index():
        return redirect(url_for("storefront.browse"))

    @app.get("/tools/product-description")
    def product_description_tool():
        return render_template("index.html")

    @app.get("/api/status")
    def local_ai_status():
        return jsonify(get_model_status())

    @app.post("/api/generate")
    def generate():
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict) or payload.get("task") != "product":
            return jsonify(error="Choose a supported task and try again."), 400

        fields = payload.get("fields")
        if not isinstance(fields, dict):
            return jsonify(error="Please enter the furniture details and try again."), 400

        normalized = {key: str(fields.get(key, "")).strip() for key in PRODUCT_FIELDS}
        missing = [label for key, label in PRODUCT_REQUIRED_FIELDS.items() if not normalized[key]]
        if missing:
            return jsonify(error="Please fill in: " + ", ".join(missing) + "."), 400
        if normalized["currency"] and not re.fullmatch(r"[A-Za-z]{3}", normalized["currency"]):
            return jsonify(error="Currency must be a three-letter code when provided."), 400
        normalized["currency"] = normalized["currency"].upper()

        try:
            result = generate_text(build_product_prompt(normalized))
        except LocalAIError:
            return product_fallback_response(normalized, "Local Ollama could not provide a description.")
        except Exception:
            app.logger.error("Local product draft failed; exception details suppressed")
            return product_fallback_response(normalized, "Local AI could not provide a description.")

        safe_result = verified_product_result(result, normalized)
        if safe_result is None:
            return product_fallback_response(
                normalized,
                "The local model added wording outside the supplied facts, so its draft was withheld.",
            )
        return jsonify(
            result=safe_result,
            source="local_ai",
            notice="The local model's output passed the facts check and was formatted for display. Review it before use.",
        )

    @app.errorhandler(400)
    def bad_request(error):
        if request.path.startswith("/api/"):
            return jsonify(error=error.description or "Please reload and try again."), 400
        return render_template("error.html", code=400, message=error.description or "Please reload and try again."), 400

    @app.errorhandler(403)
    def forbidden(_error):
        return render_template("error.html", code=403, message="You do not have permission to open this page."), 403

    @app.errorhandler(413)
    def request_too_large(_error):
        return render_template(
            "error.html", code=413,
            message="That upload is too large. Choose smaller image files and try again.",
        ), 413

    @app.errorhandler(404)
    def not_found(_error):
        return render_template("error.html", code=404, message="That page could not be found."), 404

    @app.errorhandler(429)
    def too_many_requests(_error):
        response = render_template("error.html", code=429, message="Too many requests. Please wait a little while and try again."), 429
        return response

    @app.errorhandler(500)
    def internal_error(_error):
        request_id = secrets.token_hex(8)
        app.logger.error("Request failed safely; request_id=%s", request_id)
        return render_template(
            "error.html", code=500,
            message=f"Something went wrong. Please try again later. Reference: {request_id}",
        ), 500

    with app.app_context():
        init_db()
    return app


def product_fallback_response(fields: dict[str, str], reason: str):
    """Return a facts-only deterministic draft and identify it as non-AI text."""
    return jsonify(
        result=build_product_fallback(fields),
        source="seller_facts_fallback",
        notice=f"Safe fallback (not AI-generated). {reason} The text below uses only the details you supplied.",
    )


if __name__ == "__main__":
    app = create_app()
    app.run(host="127.0.0.1", port=5000, debug=False)

import os
import secrets
from datetime import datetime
from flask import Flask, g, session, request, abort

from .db import init_app as init_db_app


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        SECRET_KEY=os.environ.get("SECRET_KEY", "dev-change-this-secret"),
        DATABASE=os.path.join(app.instance_path, "vluchtwinkel.sqlite"),
        ADMIN_PASSWORD=os.environ.get("ADMIN_PASSWORD", "admin123"),
    )

    if test_config:
        app.config.update(test_config)

    os.makedirs(app.instance_path, exist_ok=True)
    init_db_app(app)

    from .routes import bp
    app.register_blueprint(bp)

    @app.before_request
    def protect_post_requests():
        if request.method == "POST" and not app.config.get("TESTING"):
            submitted = request.form.get("csrf_token", "")
            expected = session.get("csrf_token", "")
            if not submitted or not expected or not secrets.compare_digest(submitted, expected):
                abort(400, description="Ongeldige of verlopen formulierbeveiliging. Vernieuw de pagina en probeer opnieuw.")

    @app.context_processor
    def inject_helpers():
        def csrf_token():
            if "csrf_token" not in session:
                session["csrf_token"] = secrets.token_urlsafe(32)
            return session["csrf_token"]

        return {"csrf_token": csrf_token, "now": datetime.now()}

    @app.template_filter("money")
    def money_filter(cents):
        amount = (cents or 0) / 100
        return f"€ {amount:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    @app.template_filter("nl_datetime")
    def datetime_filter(value):
        if not value:
            return "—"
        try:
            dt = datetime.fromisoformat(value)
            return dt.strftime("%d-%m-%Y %H:%M")
        except (TypeError, ValueError):
            return value

    return app

"""SpeedSpot Mapper — Flask application factory.

`create_app()` builds a fresh, fully configured Flask app. Tests call it with
"testing" to get an isolated app backed by an in-memory database.
"""
from pathlib import Path

from flask import Flask
from werkzeug.middleware.proxy_fix import ProxyFix

from . import cli, errors, security
from .config import get_config
from .extensions import db, limiter, migrate
from .routes.api import api_v1
from .routes.pages import pages

PROJECT_ROOT = Path(__file__).resolve().parent.parent
FRONTEND_DIR = PROJECT_ROOT / "frontend"
MIGRATIONS_DIR = PROJECT_ROOT / "migrations"


def create_app(config_name: str | None = None, overrides: dict | None = None) -> Flask:
    app = Flask(
        __name__,
        instance_path=str(PROJECT_ROOT / "instance"),
        template_folder=str(FRONTEND_DIR / "templates"),
        static_folder=str(FRONTEND_DIR / "static"),
    )
    config_class = get_config(config_name)
    app.config.from_object(config_class)
    if overrides:
        app.config.update(overrides)
    config_class.validate(app.config)

    if not app.config.get("SQLALCHEMY_DATABASE_URI"):
        Path(app.instance_path).mkdir(parents=True, exist_ok=True)
        db_path = Path(app.instance_path) / "speedspot.db"
        app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{db_path}"

    app.json.sort_keys = False  # keep keys in the order we write them
    db.init_app(app)
    # render_as_batch lets Alembic alter tables on SQLite (which can't ALTER most columns).
    migrate.init_app(app, db, directory=str(MIGRATIONS_DIR), render_as_batch=True)
    limiter.init_app(app)

    if app.config["USE_WHITENOISE"]:
        # Serves /static/ efficiently (pre-compressed .gz/.br files, cache headers) in production.
        from whitenoise import WhiteNoise
        app.wsgi_app = WhiteNoise(app.wsgi_app, root=str(FRONTEND_DIR / "static"), prefix="static/",
                                  max_age=app.config["STATIC_MAX_AGE"],
                                  add_headers_function=security.static_headers)

    if app.config["TRUSTED_PROXY_COUNT"]:
        # Only when deployed behind known reverse proxies: read the visitor's IP from X-Forwarded-For.
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=app.config["TRUSTED_PROXY_COUNT"],
                                x_proto=app.config["TRUSTED_PROXY_COUNT"])

    app.register_blueprint(pages)
    app.register_blueprint(api_v1)
    app.register_blueprint(api_v1, url_prefix="/api", name="api")  # /api = current version
    errors.register(app)
    security.register(app)
    cli.register(app)

    return app

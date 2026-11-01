"""Configuration classes, selected with the SPEEDSPOT_ENV environment variable.

Secrets are read from the environment (or a local, git-ignored `.env` file),
never written in source code.
"""
import os
import secrets
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _env_flag(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def database_url() -> str | None:
    """DATABASE_URL from the environment, adapted for SQLAlchemy + psycopg 3.

    Hosts such as Render give "postgres://…" or "postgresql://…"; SQLAlchemy needs
    "postgresql+psycopg://…" to use the psycopg 3 driver.
    """
    url = os.environ.get("DATABASE_URL")
    if not url:
        return None
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix):]
    return url


class BaseConfig:
    ENV_NAME = "base"
    DEBUG = False
    TESTING = False

    SECRET_KEY = os.environ.get("SECRET_KEY")
    # None means "use instance/speedspot.db" (resolved in create_app).
    SQLALCHEMY_DATABASE_URI = database_url()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}  # survive dropped database connections
    MAX_CONTENT_LENGTH = 64 * 1024  # requests larger than 64 KB are refused (413)

    # Geography: national scope, with VIT Chennai as the first pilot location.
    # Bounds are a generous rectangle around India incl. island territories.
    INDIA_BOUNDS = {"south": 6.5, "west": 68.0, "north": 37.5, "east": 97.5}
    DEV_LOCATION = {"name": "VIT Chennai", "lat": 12.8406, "lng": 80.1534}

    # Only tests from the last N days count towards scores ("data freshness").
    FRESHNESS_WINDOW_DAYS = 180

    # Aggregated statistics cache (area_statistics table): entries expire after this long.
    STATS_CACHE_TTL_MINUTES = 30

    # IP → ASN database (DB-IP ASN Lite, CC-BY 4.0). Download: python scripts/download_asn_db.py
    ASN_DATABASE_PATH = os.environ.get(
        "ASN_DATABASE_PATH", str(PROJECT_ROOT / "data" / "asn" / "dbip-asn-lite.mmdb"))
    # Number of reverse proxies in front of the app (0 = trust nothing in X-Forwarded-For).
    TRUSTED_PROXY_COUNT = int(os.environ.get("TRUSTED_PROXY_COUNT", "0"))
    # Development only: pretend requests come from this IP, to test provider detection locally.
    DEV_CLIENT_IP = None

    # Rate limiting (Flask-Limiter). Counters are in memory only.
    RATELIMIT_ENABLED = True
    RATELIMIT_STORAGE_URI = os.environ.get("RATELIMIT_STORAGE_URI", "memory://")
    RATELIMIT_HEADERS_ENABLED = True
    MEASUREMENT_RATE_LIMIT = "30 per hour"

    # Static files: served by WhiteNoise (compressed, cached) when enabled.
    USE_WHITENOISE = False
    STATIC_MAX_AGE = 0
    FORCE_HTTPS = False

    HSTS_ENABLED = False

    @classmethod
    def validate(cls, config) -> None:
        """Hook for configs that must refuse to start when misconfigured."""


class DevelopmentConfig(BaseConfig):
    ENV_NAME = "development"
    DEBUG = True
    # A random per-process key is fine locally; sessions reset on restart.
    SECRET_KEY = os.environ.get("SECRET_KEY") or secrets.token_hex(32)
    DEV_CLIENT_IP = os.environ.get("SPEEDSPOT_DEV_CLIENT_IP") or None


class TestingConfig(BaseConfig):
    ENV_NAME = "testing"
    TESTING = True
    # Placeholder for automated tests only; never deployed (reviewed security-scan finding).
    SECRET_KEY = "testing-only-not-secret"  # nosec B105
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    RATELIMIT_ENABLED = False  # tests that check limits switch it on explicitly
    ASN_DATABASE_PATH = "/nonexistent/tests-inject-a-fake-lookup.mmdb"


class ProductionConfig(BaseConfig):
    ENV_NAME = "production"
    HSTS_ENABLED = True
    FORCE_HTTPS = _env_flag("FORCE_HTTPS", True)
    USE_WHITENOISE = True
    STATIC_MAX_AGE = 3600
    # A local SQLite file is wiped on every redeploy on hosts like Render, so production
    # refuses to start with one unless this is set explicitly (e.g. a paid persistent disk).
    ALLOW_SQLITE_IN_PRODUCTION = _env_flag("ALLOW_SQLITE_IN_PRODUCTION")

    @classmethod
    def validate(cls, config) -> None:
        if not config.get("SECRET_KEY"):
            raise RuntimeError("SECRET_KEY must be set in production.")
        uri = config.get("SQLALCHEMY_DATABASE_URI") or "sqlite:"
        if uri.startswith("sqlite") and not config.get("ALLOW_SQLITE_IN_PRODUCTION"):
            raise RuntimeError("Production needs a persistent database: set DATABASE_URL to PostgreSQL "
                               "(or ALLOW_SQLITE_IN_PRODUCTION=true with a persistent disk).")


CONFIGS = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
}


def get_config(name: str | None = None) -> type[BaseConfig]:
    name = name or os.environ.get("SPEEDSPOT_ENV", "development")
    try:
        return CONFIGS[name]
    except KeyError:
        raise ValueError(f"Unknown config '{name}'. Use one of: {', '.join(CONFIGS)}") from None

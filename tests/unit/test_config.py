import pytest

from backend import create_app
from backend.config import ProductionConfig, get_config
from tests.conftest import PROD_OVERRIDES


def test_testing_config_uses_in_memory_database(app):
    assert app.config["TESTING"] is True
    assert app.config["SQLALCHEMY_DATABASE_URI"] == "sqlite:///:memory:"


def test_unknown_config_name_is_rejected():
    with pytest.raises(ValueError):
        get_config("staging")


def test_production_refuses_to_start_without_secret_key():
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        create_app("production", {"SECRET_KEY": None, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:"})


def test_production_is_safe_by_default():
    app = create_app("production", PROD_OVERRIDES)
    assert app.config["DEBUG"] is False
    assert app.config["HSTS_ENABLED"] is True
    assert app.config["FORCE_HTTPS"] is True
    assert app.config["MAX_CONTENT_LENGTH"] == 64 * 1024


def test_production_refuses_an_ephemeral_sqlite_database():
    with pytest.raises(RuntimeError, match="persistent database"):
        create_app("production", {"SECRET_KEY": "x" * 64, "SQLALCHEMY_DATABASE_URI": "sqlite:////tmp/x.db"})


@pytest.mark.parametrize("given,expected", [
    ("postgres://u:p@h:5432/db", "postgresql+psycopg://u:p@h:5432/db"),
    ("postgresql://u:p@h/db", "postgresql+psycopg://u:p@h/db"),
    ("sqlite:////tmp/a.db", "sqlite:////tmp/a.db"),
])
def test_database_url_is_adapted_for_psycopg(monkeypatch, given, expected):
    from backend.config import database_url
    monkeypatch.setenv("DATABASE_URL", given)
    assert database_url() == expected


@pytest.mark.parametrize("config_name", ["development", "testing", "production"])
def test_no_config_can_enable_demo_data(monkeypatch, config_name):
    monkeypatch.setenv("SPEEDSPOT_ALLOW_DEMO_DATA", "true")  # the old switch must have no effect anywhere
    config = get_config(config_name)
    assert not hasattr(config, "ALLOW_DEMO_DATA")


def test_dev_location_is_inside_india_bounds(app):
    bounds, loc = app.config["INDIA_BOUNDS"], app.config["DEV_LOCATION"]
    assert bounds["south"] <= loc["lat"] <= bounds["north"]
    assert bounds["west"] <= loc["lng"] <= bounds["east"]

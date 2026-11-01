from backend import create_app
from backend.extensions import db


def test_init_db_runs_migrations_and_is_repeatable(tmp_path):
    """`flask init-db` applies the real Alembic migrations to an empty database, then seeds it."""
    app = create_app("testing", {"SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path / 'fresh.db'}"})
    runner = app.test_cli_runner()
    first = runner.invoke(args=["init-db"])
    assert first.exit_code == 0, first.output
    assert "newly added" in first.output and "Providers: 18" in first.output

    second = runner.invoke(args=["init-db"])
    assert second.exit_code == 0
    assert "(0 newly added)" in second.output
    with app.app_context():
        tables = set(db.inspect(db.engine).get_table_names())
    assert {"alembic_version", "measurements", "grid_cells", "regions", "providers", "provider_asns",
            "area_statistics"} <= tables


def test_migrations_match_the_models(tmp_path):
    """The migration history produces exactly the schema the models describe (no drift)."""
    from alembic.autogenerate import compare_metadata
    from alembic.migration import MigrationContext
    from flask_migrate import upgrade

    app = create_app("testing", {"SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path / 'drift.db'}"})
    with app.app_context():
        upgrade()
        with db.engine.connect() as connection:
            diff = compare_metadata(MigrationContext.configure(connection), db.metadata)
    assert diff == []


def test_there_is_no_demo_data_command(seeded):
    result = seeded.test_cli_runner().invoke(args=["demo-data", "seed"])
    assert result.exit_code != 0 and "No such command" in result.output

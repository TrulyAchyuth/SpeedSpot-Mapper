"""Custom `flask` commands.

  flask init-db           apply database migrations, then load reference data (safe to repeat)
  flask seed              load/refresh reference data only (regions, providers)
  flask stats clear-cache drop cached area statistics (they rebuild on demand)
"""
import click

from .services import stats_cache
from .services.regions import seed_providers, seed_reference_regions


def _seed() -> str:
    result = seed_reference_regions()
    providers = seed_providers()
    return (f"Regions: {result['total']} ({result['created']} newly added). Providers: {providers}.")


def register(app) -> None:
    @app.cli.command("init-db")
    def init_db() -> None:
        """Apply migrations (Alembic) and load reference regions and providers."""
        from flask_migrate import upgrade

        upgrade()
        click.echo(f"Database ready. {_seed()}")

    @app.cli.command("seed")
    def seed_command() -> None:
        """Load or refresh reference data (idempotent)."""
        click.echo(f"Reference data loaded. {_seed()}")

    @app.cli.group("stats")
    def stats_group() -> None:
        """Aggregated statistics cache."""

    @stats_group.command("clear-cache")
    def clear_cache() -> None:
        stats_cache.invalidate_all()
        click.echo("Cached area statistics cleared.")

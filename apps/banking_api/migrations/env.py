import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

# Add the application source directory to Python's import path.
PROJECT_ROOT = Path(__file__).resolve().parents[3]
APP_SOURCE = PROJECT_ROOT / "apps" / "banking_api" / "src"

if str(APP_SOURCE) not in sys.path:
    sys.path.insert(0, str(APP_SOURCE))

# Import application settings and register models for Alembic autogeneration.
import rubies_banking_api.models  # noqa: E402, F401
from rubies_banking_api.config import get_settings  # noqa: E402
from rubies_banking_api.db.base import Base  # noqa: E402

# Alembic Config object provides access to values in the .ini file.
config = context.config

settings = get_settings()

config.set_main_option(
    "sqlalchemy.url",
    settings.database_url.replace("%", "%%"),
)

# Configure Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Metadata used by Alembic for migration autogeneration.
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations without creating a database engine."""
    url = config.get_main_option("sqlalchemy.url")

    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations using a live database connection."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()


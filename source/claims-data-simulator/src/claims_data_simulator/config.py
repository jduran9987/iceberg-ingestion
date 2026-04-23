"""Application configuration loaded from environment variables.

Uses pydantic-settings to parse and validate environment variables into
a typed settings object. The primary setting is the Postgres connection
URL used by the database layer.
"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings sourced from environment variables.

    Attributes:
        database_url: Postgres connection string
            (e.g. ``postgresql+psycopg://user:pass@host:5432/db``).
    """

    database_url: str

    model_config = {"env_file": ".env"}


def get_settings() -> Settings:
    """Build and return a ``Settings`` instance from the environment."""
    return Settings()  # type: ignore[call-arg]

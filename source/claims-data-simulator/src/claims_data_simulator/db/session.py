"""Database engine and session management.

Creates the SQLAlchemy engine from the application's ``DATABASE_URL``
setting and provides a FastAPI-compatible dependency that yields
short-lived sessions.
"""

from collections.abc import Generator

from sqlalchemy import Engine
from sqlmodel import Session, create_engine

from claims_data_simulator.config import get_settings

_engine: Engine | None = None


def get_engine() -> Engine:
    """Return the singleton SQLAlchemy engine.

    The engine is created lazily on first call using the ``DATABASE_URL``
    from application settings.

    Returns:
        The shared ``Engine`` instance.
    """
    global _engine  # noqa: PLW0603
    if _engine is None:
        settings = get_settings()
        _engine = create_engine(settings.database_url, echo=False)
    return _engine


def get_session() -> Generator[Session, None, None]:
    """Yield a database session for use as a FastAPI dependency.

    The session is automatically closed when the request completes.

    Yields:
        A ``Session`` bound to the application engine.
    """
    with Session(get_engine()) as session:
        yield session

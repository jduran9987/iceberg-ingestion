"""Shared test fixtures for the claims data simulator.

Spins up a throwaway Postgres container via testcontainers and overrides
the FastAPI session dependency so that every test runs against an
isolated, ephemeral database.
"""

from collections.abc import AsyncIterator, Iterator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import Engine
from sqlmodel import Session, SQLModel, create_engine
from testcontainers.postgres import PostgresContainer

from claims_data_simulator.db.session import get_session
from claims_data_simulator.main import app


@pytest.fixture(scope="session")
def postgres_container() -> Iterator[PostgresContainer]:
    """Start a throwaway Postgres container for the test session.

    Yields:
        A running ``PostgresContainer`` instance.
    """
    with PostgresContainer("postgres:16-alpine") as container:
        yield container


@pytest.fixture(scope="session")
def engine(postgres_container: PostgresContainer) -> Engine:
    """Create a SQLAlchemy engine connected to the test Postgres.

    Args:
        postgres_container: The running Postgres container.

    Returns:
        An ``Engine`` bound to the test database.
    """
    url = postgres_container.get_connection_url().replace("psycopg2", "psycopg")
    return create_engine(url, echo=False)


@pytest.fixture(autouse=True)
def setup_tables(engine: Engine) -> Iterator[None]:
    """Create all tables before each test and drop them afterward.

    Args:
        engine: The test database engine.

    Yields:
        Control to the test after tables are created.
    """
    SQLModel.metadata.create_all(engine)
    yield
    SQLModel.metadata.drop_all(engine)


@pytest.fixture
def session(engine: Engine) -> Iterator[Session]:
    """Provide a test database session.

    Args:
        engine: The test database engine.

    Yields:
        A ``Session`` that is closed after the test.
    """
    with Session(engine) as session:
        yield session


@pytest.fixture(autouse=True)
def override_get_session(engine: Engine) -> Iterator[None]:
    """Override the FastAPI ``get_session`` dependency with the test engine.

    Args:
        engine: The test database engine.

    Yields:
        Control to the test with the dependency override active.
    """

    def _test_session() -> Iterator[Session]:
        """Yield a session from the test engine."""
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = _test_session
    yield
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def client() -> AsyncIterator[AsyncClient]:
    """Provide an async HTTP client wired to the FastAPI app.

    Yields:
        An ``AsyncClient`` that sends requests through the ASGI app.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

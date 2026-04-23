"""FastAPI app construction, lifespan, and route registration."""

from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI
from sqlmodel import SQLModel

from claims_data_simulator.api.routes import router
from claims_data_simulator.db.session import get_engine


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    """Create database tables on startup.

    Args:
        application: The FastAPI application instance.

    Yields:
        Control to the application after startup completes.
    """
    _ = application
    SQLModel.metadata.create_all(get_engine())
    yield


app = FastAPI(title="Claims Data Simulator", lifespan=lifespan)
app.include_router(router)

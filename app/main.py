"""Application entrypoint."""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.middleware import RequestIdAndTimingMiddleware
from app.api.routes import router
from app.infra.logging import setup_logging
from app.infra.persistence.db import Base, get_engine, init_engine
from app.settings import Settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan: setup logging and database."""
    setup_logging()

    # Initialise DB engine and create tables.
    settings = Settings()
    init_engine(settings.database_url)
    engine = get_engine()
    Base.metadata.create_all(bind=engine)

    yield
    # teardown if any


def create_app() -> FastAPI:
    """Create and configure FastAPI app."""
    app = FastAPI(title="Low-Latency Chat", lifespan=lifespan)
    app.add_middleware(RequestIdAndTimingMiddleware)
    app.include_router(router, tags=["api"])
    return app


app = create_app()

"""Application entrypoint."""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.middleware import RequestIdAndTimingMiddleware
from app.api.routes import router
from app.infra.logging import setup_logging


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan: setup logging. DB and tables come in later."""
    setup_logging()
    yield
    # teardown if any


def create_app() -> FastAPI:
    """Create and configure FastAPI app."""
    app = FastAPI(title="Low-Latency Chat", lifespan=lifespan)
    app.add_middleware(RequestIdAndTimingMiddleware)
    app.include_router(router, tags=["api"])
    return app


app = create_app()

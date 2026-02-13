"""Application entrypoint."""

import logging
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api.middleware import RequestIdAndTimingMiddleware
from app.api.routes import router
from app.infra.logging import setup_logging
from app.infra.persistence.db import Base, get_engine, init_engine
from app.settings import Settings

logger = logging.getLogger(__name__)


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Log unhandled exception with request_id and return 500 envelope."""
    request_id = getattr(request.state, "request_id", None)
    logger.exception(
        "unhandled exception",
        extra={"request_id": request_id, "path": request.url.path},
    )
    body: dict[str, Any] = {"detail": "Internal server error"}
    if request_id:
        body["request_id"] = request_id
    return JSONResponse(status_code=500, content=body)


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
    app.add_exception_handler(Exception, unhandled_exception_handler)
    app.add_middleware(RequestIdAndTimingMiddleware)
    app.include_router(router, tags=["api"])
    return app


app = create_app()

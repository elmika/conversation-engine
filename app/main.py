"""Application entrypoint. Infra is created here and injected via app.state."""

import logging
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from pathlib import Path

from app.api.middleware import RequestIdAndTimingMiddleware
from app.api.routes import router
from app.infra.llm_openai import OpenAILLMAdapter
from app.infra.logging import setup_logging
import app.infra.persistence.db as _db
from app.infra.persistence.db import Base, get_engine, init_engine
from app.infra.prompt_seeder import seed_prompts_from_directory
from app.settings import Settings

logger = logging.getLogger(__name__)


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Log unhandled exception with request_id and return an error envelope.

    We preserve HTTPException status codes/details, and fall back to 500 for unknown errors.
    """
    request_id = getattr(request.state, "request_id", None)
    logger.exception(
        "unhandled exception",
        extra={"request_id": request_id, "path": request.url.path},
    )

    if isinstance(exc, HTTPException):
        body: dict[str, Any] = {"detail": exc.detail}
        if request_id:
            body["request_id"] = request_id
        return JSONResponse(status_code=exc.status_code, content=body)

    body: dict[str, Any] = {"detail": "Internal server error"}
    if request_id:
        body["request_id"] = request_id
    return JSONResponse(status_code=500, content=body)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan: setup logging, database, and inject infra into app.state."""
    setup_logging()

    settings = Settings()
    init_engine(settings.database_url)
    engine = get_engine()
    Base.metadata.create_all(bind=engine)

    with _db.SessionLocal() as session:
        seed_prompts_from_directory(Path(settings.prompts_dir), session)

    # Inject infra so routes depend on app.state instead of constructing adapters.
    app.state.settings = settings
    app.state.llm = OpenAILLMAdapter(settings)

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

from collections.abc import AsyncIterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.formparsers import MultiPartParser

from app.analyzers.registry import build_analyzers
from app.api.v1.router import api_router
from app.core.config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()

    # Keep uploads in RAM: Starlette otherwise rolls files over 1 MB to a temp file on disk.
    MultiPartParser.spool_max_size = settings.max_file_bytes

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        executor = ThreadPoolExecutor(max_workers=settings.max_workers, thread_name_prefix="photosort-cv")
        app.state.executor = executor
        app.state.analyzers = build_analyzers()
        try:
            yield
        finally:
            executor.shutdown(wait=True)

    app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(api_router)

    @app.get("/health", tags=["meta"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()

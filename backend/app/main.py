"""FastAPI application: groundwater-potential analysis API for the Borewell Water Finder web app."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from . import __version__
from .ratelimit import RateLimiter
from .routers import ai, analysis, contact, layers, meta, report
from .services import Container, build_container
from .settings import Settings, load_settings

log = logging.getLogger("bwf")

DESCRIPTION = (
    "Groundwater POTENTIAL analysis for Indian locations, built from public datasets and a documented method. "
    "Results are estimates with a stated confidence - never a guarantee that water exists or that drilling will succeed. "
    "Every response says whether it is computed from demonstration or production data."
)


def create_app(settings: Optional[Settings] = None, container: Optional[Container] = None) -> FastAPI:
    settings = settings or (container.settings if container else load_settings())

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.container = container or build_container(settings)
        app.state.limiter = RateLimiter(settings.rate_limit_per_min)
        app.state.ai_limiter = RateLimiter(8, 3600.0)
        app.state.settings = settings
        app.state.contact_limiter = RateLimiter(5, 3600.0)
        log.info("started: mode=%s backend=%s state=%s", settings.data_mode, settings.backend, settings.state)
        try:
            yield
        finally:
            close = getattr(app.state.container.repo, "close", None)
            if callable(close):
                close()

    app = FastAPI(title="Borewell Water Finder API", version=__version__, description=DESCRIPTION,
                  lifespan=lifespan, docs_url="/api/docs", openapi_url="/api/openapi.json", redoc_url=None)
    app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_methods=["GET", "POST"],
                       allow_headers=["Content-Type"], allow_credentials=False, max_age=600)

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        resp = await call_next(request)
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("Referrer-Policy", "no-referrer")
        return resp

    @app.exception_handler(Exception)
    async def unhandled(request: Request, exc: Exception):
        # Never echo internals or the query string (it contains the user's coordinates).
        log.exception("unhandled error on %s", request.url.path)
        return JSONResponse({"detail": "Internal server error"}, status_code=500)

    for r in (meta.router, analysis.router, layers.router, report.router, contact.router, ai.router):
        app.include_router(r, prefix="/api")
    return app


app = create_app()

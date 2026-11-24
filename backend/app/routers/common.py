"""Shared FastAPI dependencies."""
from __future__ import annotations

from fastapi import HTTPException, Request

from ..ratelimit import RateLimiter
from ..services import Container
from ..settings import Settings


def get_container(request: Request) -> Container:
    return request.app.state.container


def client_key(request: Request) -> str:
    return request.headers.get("x-real-ip") or (request.client.host if request.client else "anon")


def limit_requests(request: Request) -> None:
    limiter: RateLimiter = request.app.state.limiter
    if not limiter.allow(client_key(request)):
        raise HTTPException(status_code=429, detail="Too many requests - please slow down.",
                            headers={"Retry-After": "30"})


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def limit_ai_requests(request: Request) -> None:
    limiter: RateLimiter = request.app.state.ai_limiter
    if not limiter.allow(client_key(request)):
        raise HTTPException(status_code=429, detail="AI request limit reached - please try again later.",
                            headers={"Retry-After": "60"})

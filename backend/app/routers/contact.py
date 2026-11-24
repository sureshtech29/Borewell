from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

from ..ratelimit import RateLimiter
from ..schemas import ContactIn, ContactOut
from ..services import Container
from .common import client_key, get_container

router = APIRouter(tags=["contact"])


@router.post("/contact", response_model=ContactOut)
def contact(body: ContactIn, request: Request, c: Container = Depends(get_container)):
    """Store a contact-form message. Limited to 5 messages per hour per client."""
    limiter: RateLimiter = request.app.state.contact_limiter
    if not limiter.allow(client_key(request)):
        raise HTTPException(status_code=429, detail="Too many messages - please try again later.")
    if not body.email and not body.phone:
        raise HTTPException(status_code=422, detail="Please provide an email address or a phone number.")
    mid = c.repo.save_contact(body.name.strip(), body.email, body.phone, body.message.strip(), body.lang)
    return {"ok": True, "id": mid}

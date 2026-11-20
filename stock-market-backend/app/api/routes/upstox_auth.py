"""
Daily Upstox login flow.

1. Morning Telegram/email alert links the user to /brokers/upstox/login
2. They approve on Upstox, which redirects to /brokers/upstox/callback
3. We exchange the code for today's token and store it encrypted

Adapt the imports to your project (auth dependency, DB session, repo functions).
"""

import secrets

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse

from app.api.deps import get_current_user, get_db
from app.brokers.upstox.upstox_broker import (
    UpstoxCredentials,
    UpstoxError,
    build_login_url,
    exchange_code_for_token,
)
from app.core.config import settings
from app.core.crypto import decrypt_secret, encrypt_secret
from app.repositories import broker_accounts, oauth_states

router = APIRouter(prefix="/brokers/upstox", tags=["upstox"])


def _load_creds(db, user_id: int) -> UpstoxCredentials:
    acct = broker_accounts.get(db, user_id=user_id, broker="upstox")
    if acct is None:
        raise HTTPException(404, "No Upstox account connected")
    return UpstoxCredentials(
        api_key=decrypt_secret(acct.api_key_enc),
        api_secret=decrypt_secret(acct.api_secret_enc),
        redirect_uri=settings.upstox_redirect_uri,
    )


@router.get("/login")
def upstox_login(user=Depends(get_current_user), db=Depends(get_db)):
    creds = _load_creds(db, user.id)
    state = secrets.token_urlsafe(24)
    oauth_states.save(db, state=state, user_id=user.id, broker="upstox", ttl_minutes=10)
    return RedirectResponse(build_login_url(creds.api_key, creds.redirect_uri, state))


@router.get("/callback")
def upstox_callback(code: str, state: str, db=Depends(get_db)):
    # The state check stops someone from attaching their token to another user.
    record = oauth_states.pop(db, state=state, broker="upstox")
    if record is None:
        raise HTTPException(400, "Login link expired or invalid; start again")

    creds = _load_creds(db, record.user_id)
    try:
        creds = exchange_code_for_token(creds, code)
    except UpstoxError:
        raise HTTPException(502, "Upstox login failed; please try again")

    broker_accounts.save_token(
        db,
        user_id=record.user_id,
        broker="upstox",
        access_token_enc=encrypt_secret(creds.access_token),
        token_expires_at=creds.token_expires_at,
    )
    return RedirectResponse("/dashboard?upstox=connected")

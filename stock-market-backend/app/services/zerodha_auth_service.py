"""Links an app user to their Zerodha account via the daily Kite login.

Flow:
  1. Logged-in app user calls GET /zerodha/login-url.
  2. Browser goes to Zerodha, user logs in with their own Zerodha credentials.
  3. Zerodha redirects to GET /zerodha/callback?request_token=...&state=...
  4. Backend exchanges request_token for an access_token and stores it
     encrypted until it expires at 06:00 IST the next morning.

The callback is a plain browser redirect without our Bearer token, so the
user is identified by a short-lived signed `state` value instead.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.brokers.zerodha.kite_client import (
    ZerodhaClient,
    build_login_url,
    exchange_request_token,
)
from app.core.config import settings
from app.core.token_crypto import decrypt_token, encrypt_token
from app.models.user import AppUser
from app.models.zerodha import ZerodhaSession
from app.trading.zerodha_order_rules import IST, kite_token_expiry

STATE_PURPOSE = "zerodha_link"
STATE_TTL = timedelta(minutes=10)


class ZerodhaAuthService:

    @staticmethod
    def login_url(user: AppUser) -> str:
        now = datetime.now(timezone.utc)
        state = jwt.encode(
            {
                "sub": str(user.id),
                "purpose": STATE_PURPOSE,
                "iat": now,
                "exp": now + STATE_TTL,
            },
            settings.jwt_secret_key,
            algorithm=settings.jwt_algorithm,
        )
        return build_login_url(state)

    @staticmethod
    def _user_id_from_state(state: str) -> int:
        try:
            payload = jwt.decode(
                state,
                settings.jwt_secret_key,
                algorithms=[settings.jwt_algorithm],
            )
        except JWTError as exc:
            raise ValueError("Zerodha login link is invalid or expired; start again") from exc
        if payload.get("purpose") != STATE_PURPOSE:
            raise ValueError("Zerodha login link is invalid")
        return int(payload["sub"])

    @staticmethod
    def complete_login(db: Session, request_token: str, state: str) -> ZerodhaSession:
        user_id = ZerodhaAuthService._user_id_from_state(state)
        user = db.get(AppUser, user_id)
        if user is None or not user.is_active:
            raise ValueError("App user is not active")

        data = exchange_request_token(request_token)

        login_time = data.get("login_time")
        if isinstance(login_time, datetime):
            # pykiteconnect returns a naive IST datetime.
            if login_time.tzinfo is None:
                login_time = login_time.replace(tzinfo=IST)
        else:
            login_time = datetime.now(timezone.utc)

        row = db.scalar(select(ZerodhaSession).where(ZerodhaSession.user_id == user.id))
        if row is None:
            row = ZerodhaSession(user_id=user.id)
            db.add(row)

        row.kite_user_id = data["user_id"]
        row.kite_user_name = data.get("user_name")
        row.access_token_encrypted = encrypt_token(data["access_token"])
        row.login_time = login_time
        # Kite's login_time can be an earlier Kite login from before the 06:00 IST
        # reset; the token we just received is valid until the NEXT reset.
        row.expires_at = kite_token_expiry(datetime.now(timezone.utc))
        db.commit()
        db.refresh(row)
        return row

    @staticmethod
    def get_active_session(db: Session, user: AppUser) -> ZerodhaSession | None:
        row = db.scalar(select(ZerodhaSession).where(ZerodhaSession.user_id == user.id))
        if row is None or row.expires_at <= datetime.now(timezone.utc):
            return None
        return row

    @staticmethod
    def client_for(db: Session, user: AppUser) -> tuple[ZerodhaClient, ZerodhaSession]:
        row = ZerodhaAuthService.get_active_session(db, user)
        if row is None:
            raise ValueError("Zerodha is not connected or the daily login has expired")
        return ZerodhaClient(decrypt_token(row.access_token_encrypted)), row

    @staticmethod
    def status(db: Session, user: AppUser) -> dict:
        row = ZerodhaAuthService.get_active_session(db, user)
        return {
            "connected": row is not None,
            "kite_user_id": row.kite_user_id if row else None,
            "kite_user_name": row.kite_user_name if row else None,
            "expires_at": row.expires_at if row else None,
            "trading_enabled": settings.zerodha_trading_enabled,
            "dry_run": settings.zerodha_dry_run,
        }

    @staticmethod
    def disconnect(db: Session, user: AppUser) -> None:
        row = db.scalar(select(ZerodhaSession).where(ZerodhaSession.user_id == user.id))
        if row is None:
            return
        try:
            ZerodhaClient(decrypt_token(row.access_token_encrypted)).invalidate()
        except Exception:
            # The token may already be expired; deleting locally is what matters.
            pass
        db.delete(row)
        db.commit()

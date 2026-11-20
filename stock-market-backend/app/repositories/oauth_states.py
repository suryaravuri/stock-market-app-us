from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.broker import OAuthState


def save(db: Session, *, state: str, user_id: int, broker: str, ttl_minutes: int = 10) -> None:
    now = datetime.now(timezone.utc)
    # Clean up old, unused states while we're here
    db.execute(delete(OAuthState).where(OAuthState.expires_at < now))
    db.add(OAuthState(
        state=state, user_id=user_id, broker=broker,
        expires_at=now + timedelta(minutes=ttl_minutes),
    ))
    db.commit()


def pop(db: Session, *, state: str, broker: str) -> OAuthState | None:
    """Returns the state record once and deletes it, so a link can't be reused."""
    record = db.scalar(
        select(OAuthState).where(OAuthState.state == state, OAuthState.broker == broker)
    )
    if record is None:
        return None
    db.delete(record)
    db.commit()
    if record.expires_at < datetime.now(timezone.utc):
        return None
    return record

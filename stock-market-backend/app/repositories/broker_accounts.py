from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.crypto import encrypt_secret
from app.models.broker import BrokerAccount


def get(db: Session, *, user_id: int, broker: str) -> BrokerAccount | None:
    return db.scalar(
        select(BrokerAccount).where(
            BrokerAccount.user_id == user_id, BrokerAccount.broker == broker
        )
    )


def upsert_keys(db: Session, *, user_id: int, broker: str, api_key: str, api_secret: str) -> BrokerAccount:
    """Called when a user connects a broker by entering their API key and secret."""
    acct = get(db, user_id=user_id, broker=broker)
    if acct is None:
        acct = BrokerAccount(user_id=user_id, broker=broker)
        db.add(acct)
    acct.api_key_enc = encrypt_secret(api_key)
    acct.api_secret_enc = encrypt_secret(api_secret)
    acct.access_token_enc = None
    acct.token_expires_at = None
    db.commit()
    db.refresh(acct)
    return acct


def save_token(
    db: Session, *, user_id: int, broker: str, access_token_enc: str, token_expires_at: datetime
) -> None:
    acct = get(db, user_id=user_id, broker=broker)
    if acct is None:
        raise ValueError(f"No {broker} account for user {user_id}")
    acct.access_token_enc = access_token_enc
    acct.token_expires_at = token_expires_at
    db.commit()

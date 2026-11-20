"""Engine/session for the separate backtest database."""
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

backtest_engine = create_engine(
    settings.backtest_database_url,
    pool_pre_ping=True,
    pool_size=2,
    max_overflow=2,
)

BacktestSessionLocal = sessionmaker(
    bind=backtest_engine,
    class_=Session,
    autoflush=False,
    expire_on_commit=False,
)

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api.v1.admin_users import router as admin_users_router
from app.api.v1.analysis import router as analysis_router
from app.api.v1.auth import router as auth_router
from app.api.v1.indicators import router as indicators_router
from app.api.v1.derivatives import router as derivatives_router
from app.api.v1.diagnostics import router as diagnostics_router
from app.api.v1.jobs import router as jobs_router
from app.api.v1.market_sessions import router as market_sessions_router
from app.api.v1.backtests import router as backtests_router
from app.api.v1.market import router as market_router
from app.api.v1.statistics import router as statistics_router
from app.api.v1.stocks import router as stocks_router
from app.api.v1.trading import router as trading_router
from app.api.v1.validation_runs import router as validation_runs_router
from app.api.v1.watchlist_market_sync import (
    router as watchlist_market_sync_router,
)
from app.api.v1.watchlist_monitor import (
    router as watchlist_monitor_router,
)
from app.api.v1.watchlist_scanner import (
    router as watchlist_scanner_router,
)
from app.api.v1.watchlist_stocks import (
    router as watchlist_stocks_router,
)
from app.api.v1.watchlists import router as watchlists_router
from app.api.v1.zerodha import router as zerodha_router

from app.core import local_scheduler
from app.core.config import settings
from app.core.database import engine


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Optional in-process trading-cycle scheduler (LOCAL_SCHEDULER_ENABLED=true).
    local_scheduler.start()
    try:
        yield
    finally:
        local_scheduler.stop()


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    debug=settings.debug,
    lifespan=lifespan,
)


# ---------------------------------------------------------
# CORS
# ---------------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------
# Authentication / Administration
# ---------------------------------------------------------

app.include_router(
    auth_router,
    prefix="/api/v1",
)

app.include_router(
    admin_users_router,
    prefix="/api/v1",
)


# ---------------------------------------------------------
# Application APIs
# ---------------------------------------------------------

app.include_router(
    stocks_router,
    prefix="/api/v1",
)

app.include_router(
    watchlists_router,
    prefix="/api/v1",
)

app.include_router(
    watchlist_stocks_router,
    prefix="/api/v1",
)

app.include_router(
    market_router,
    prefix="/api/v1",
)

app.include_router(
    indicators_router,
    prefix="/api/v1",
)

app.include_router(
    analysis_router,
    prefix="/api/v1",
)

app.include_router(
    trading_router,
    prefix="/api/v1",
)

app.include_router(
    watchlist_scanner_router,
    prefix="/api/v1",
)

app.include_router(
    watchlist_market_sync_router,
    prefix="/api/v1",
)

app.include_router(
    validation_runs_router,
    prefix="/api/v1",
)

app.include_router(
    watchlist_monitor_router,
    prefix="/api/v1",
)

app.include_router(
    statistics_router,
    prefix="/api/v1",
)

app.include_router(
    zerodha_router,
    prefix="/api/v1",
)

app.include_router(
    jobs_router,
    prefix="/api/v1",
)

app.include_router(
    derivatives_router,
    prefix="/api/v1",
)

app.include_router(
    diagnostics_router,
    prefix="/api/v1",
)

app.include_router(
    market_sessions_router,
    prefix="/api/v1",
)

app.include_router(
    backtests_router,
    prefix="/api/v1",
)


# ---------------------------------------------------------
# Health
# ---------------------------------------------------------

@app.get("/health")
def health():
    return {
        "status": "UP",
        "application": settings.app_name,
        "version": settings.app_version,
    }


@app.get("/health/database")
def database_health():
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))

        return {
            "status": "UP",
            "database": "PostgreSQL",
        }

    except Exception as exc:
        print(
            "DATABASE CONNECTION ERROR:",
            repr(exc),
        )

        return {
            "status": "DOWN",
            "database": "PostgreSQL",
        }
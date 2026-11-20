"""Create and inspect backtest runs.

Backtests run outside the web request (they take minutes to hours):
- With BACKTEST_JOB_NAME set, POST starts the Cloud Run Job.
- Otherwise the run stays QUEUED and you start it locally with
  `python -m app.backtest.runner --run-id <id>`.
"""
from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth_dependencies import get_current_user, require_admin
from app.core.config import settings
from app.core.database import get_db
from app.backtest import upload_service
from app.backtest.database import BacktestSessionLocal
from app.models.backtest import BacktestDataset, BacktestRun, BacktestTrade

router = APIRouter(
    prefix="/backtests",
    tags=["Backtesting"],
    dependencies=[Depends(get_current_user)],
)

MAX_SYMBOLS = 10
MAX_YEARS = 6


class BacktestCreate(BaseModel):
    symbols: list[str] = Field(min_length=1, max_length=MAX_SYMBOLS)
    start_date: date
    end_date: date
    starting_cash: float = Field(default=10_000.0, gt=0)
    risk_percent: float = Field(default=settings.risk_percent, gt=0, le=5)
    slippage_bps: float = Field(default=5.0, ge=0, le=100)
    trailing_enabled: bool = settings.trailing_stop_enabled
    trail_percent: float = Field(default=settings.trailing_stop_percent, gt=0, lt=50)
    # Pre-breakout risk/reward model to test: compare LEGACY vs ATR_FLOOR.
    risk_model: Literal["LEGACY", "ATR_FLOOR"] = "ATR_FLOOR"
    # Entry rules to test: compare BREAKOUT vs SUPPORT_BOUNCE vs BOTH.
    entry_mode: Literal["BREAKOUT", "SUPPORT_BOUNCE", "BOTH"] = "BREAKOUT"
    bounce_holding_style: Literal["INTRADAY", "WEEKLY", "MONTHLY", "SWING"] = "WEEKLY"
    bounce_min_rr: float = Field(default=1.5, gt=0, le=10)
    bounce_level_zone_atr: float = Field(default=0.0, ge=0, le=2)
    bounce_confirm_bars: int = Field(default=1, ge=1, le=3)
    # ALPACA = download history; UPLOAD = use the symbols' uploaded CSV data
    data_source: Literal["ALPACA", "UPLOAD"] = "ALPACA"
    # Uploaded data is deleted after the run unless this is set to false.
    purge_candles_after_run: bool | None = None

    @field_validator("symbols")
    @classmethod
    def clean_symbols(cls, value: list[str]) -> list[str]:
        return [s.strip().upper() for s in value if s.strip()]


def _serialize(run: BacktestRun, include_results: bool = False) -> dict:
    data = {
        "backtest_run_id": run.backtest_run_id,
        "status": run.status,
        "symbols": run.symbols.split(","),
        "start_date": run.start_date,
        "end_date": run.end_date,
        "parameters": run.parameters,
        "progress_percent": run.progress_percent,
        "message": run.message,
        "created_at": run.created_at,
        "started_at": run.started_at,
        "finished_at": run.finished_at,
    }
    if include_results:
        data["results"] = run.results
    elif run.results:
        data["summary"] = (run.results.get("overall") or {}).get("summary")
    return data


def _start_cloud_run_job(run_id: int) -> str:
    from google.cloud import run_v2  # pip install google-cloud-run

    client = run_v2.JobsClient()
    name = f"projects/{settings.gcp_project_id}/locations/{settings.gcp_region}/jobs/{settings.backtest_job_name}"
    request = run_v2.RunJobRequest(
        name=name,
        overrides=run_v2.RunJobRequest.Overrides(
            container_overrides=[
                run_v2.RunJobRequest.Overrides.ContainerOverride(args=["--run-id", str(run_id)])
            ]
        ),
    )
    client.run_job(request=request)  # returns a long-running operation; don't wait
    return "Started on Cloud Run"


@router.post("", status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_admin)])
def create_backtest(
    req: BacktestCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    if req.end_date <= req.start_date:
        raise HTTPException(400, "end_date must be after start_date")
    if (req.end_date - req.start_date).days > MAX_YEARS * 366:
        raise HTTPException(400, f"At most {MAX_YEARS} years per backtest")
    if db.scalar(select(BacktestRun).where(BacktestRun.status == "RUNNING")):
        raise HTTPException(409, "Another backtest is running; try again when it finishes")

    if req.data_source == "ALPACA":
        indian = [s for s in req.symbols if s.endswith((".NS", ".BO"))]
        if indian:
            raise HTTPException(400, f"Upload a CSV for Indian stocks: {', '.join(indian)}")
    else:
        for symbol in req.symbols:
            ds = _ready_dataset(db, symbol)
            if ds is None:
                raise HTTPException(400, f"No uploaded data ready for {symbol}")
            if req.start_date < ds.first_bar.date() or req.end_date > ds.last_bar.date():
                raise HTTPException(
                    400,
                    f"{symbol} upload covers {ds.first_bar.date()} to {ds.last_bar.date()}; "
                    "pick dates inside that range (allow ~3 months at the start for indicator warm-up)",
                )
    if req.purge_candles_after_run is None:
        req.purge_candles_after_run = req.data_source == "UPLOAD"

    run = BacktestRun(
        created_by_user_id=current_user.id,
        symbols=",".join(req.symbols),
        start_date=req.start_date,
        end_date=req.end_date,
        parameters=req.model_dump(exclude={"symbols", "start_date", "end_date"}),
        status="QUEUED",
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    if settings.backtest_job_name and settings.gcp_project_id:
        try:
            run.message = _start_cloud_run_job(run.backtest_run_id)
        except Exception as exc:  # noqa: BLE001
            run.status = "FAILED"
            run.message = f"Could not start Cloud Run Job: {exc}"[:2000]
    else:
        run.message = (
            "Queued. Start it with: python -m app.backtest.runner "
            f"--run-id {run.backtest_run_id}"
        )
    db.commit()
    return _serialize(run)


@router.get("")
def list_backtests(db: Session = Depends(get_db)):
    runs = db.scalars(
        select(BacktestRun).order_by(BacktestRun.backtest_run_id.desc()).limit(50)
    ).all()
    return [_serialize(r) for r in runs]


@router.get("/{run_id:int}")
def get_backtest(run_id: int, db: Session = Depends(get_db)):
    run = db.get(BacktestRun, run_id)
    if run is None:
        raise HTTPException(404, "Backtest not found")
    return _serialize(run, include_results=True)


@router.get("/{run_id:int}/trades")
def get_backtest_trades(run_id: int, db: Session = Depends(get_db)):
    trades = db.scalars(
        select(BacktestTrade)
        .where(BacktestTrade.backtest_run_id == run_id)
        .order_by(BacktestTrade.entry_time)
    ).all()
    return [
        {c.name: getattr(t, c.name) for c in BacktestTrade.__table__.columns}
        for t in trades
    ]


# ---------------------------------------------------------------------------
# CSV uploads: the browser parses the file and sends rows in chunks.
# The file itself never reaches Google Cloud.
# ---------------------------------------------------------------------------

def _ready_dataset(db: Session, symbol: str) -> BacktestDataset | None:
    return db.scalar(
        select(BacktestDataset)
        .where(BacktestDataset.symbol == symbol, BacktestDataset.status == "READY")
        .order_by(BacktestDataset.backtest_dataset_id.desc())
    )


def _dataset_out(ds: BacktestDataset) -> dict:
    return {c.name: getattr(ds, c.name) for c in BacktestDataset.__table__.columns}


class DatasetCreate(BaseModel):
    symbol: str = Field(min_length=1, max_length=20)
    # Used only for timestamps without an offset, e.g. "2024-03-01 09:30:00"
    source_timezone: str = "America/New_York"


class DatasetChunk(BaseModel):
    chunk_index: int = Field(ge=0)
    rows: list[dict] = Field(max_length=upload_service.MAX_ROWS_PER_CHUNK)


def _upload_call(fn):
    try:
        return fn()
    except LookupError as exc:
        raise HTTPException(404, str(exc))
    except ValueError as exc:
        raise HTTPException(400, str(exc))


@router.post("/datasets", status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_admin)])
def create_dataset(req: DatasetCreate, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    if db.scalar(select(BacktestRun).where(BacktestRun.status == "RUNNING")):
        raise HTTPException(409, "A backtest is running; upload when it finishes")
    with BacktestSessionLocal() as bt_db:
        ds = _upload_call(lambda: upload_service.create(db, bt_db, req.symbol, req.source_timezone, current_user.id))
    return _dataset_out(ds)


@router.post("/datasets/{dataset_id}/chunks", dependencies=[Depends(require_admin)])
def upload_chunk(dataset_id: int, req: DatasetChunk, db: Session = Depends(get_db)):
    with BacktestSessionLocal() as bt_db:
        ds = _upload_call(lambda: upload_service.add_chunk(db, bt_db, dataset_id, req.chunk_index, req.rows))
    return {
        "chunks_received": ds.chunks_received,
        "rows_received": ds.rows_received,
        "rows_rejected": ds.rows_rejected,
    }


@router.post("/datasets/{dataset_id}/complete", dependencies=[Depends(require_admin)])
def complete_dataset(dataset_id: int, db: Session = Depends(get_db)):
    with BacktestSessionLocal() as bt_db:
        ds = _upload_call(lambda: upload_service.complete(db, bt_db, dataset_id))
    return _dataset_out(ds)


@router.get("/datasets")
def list_datasets(db: Session = Depends(get_db)):
    rows = db.scalars(
        select(BacktestDataset).order_by(BacktestDataset.backtest_dataset_id.desc()).limit(50)
    ).all()
    return [_dataset_out(ds) for ds in rows]


@router.delete("/datasets/{dataset_id}", dependencies=[Depends(require_admin)])
def delete_dataset(dataset_id: int, db: Session = Depends(get_db)):
    ds = db.get(BacktestDataset, dataset_id)
    if ds is None:
        raise HTTPException(404, "Dataset not found")
    with BacktestSessionLocal() as bt_db:
        upload_service.purge(db, bt_db, ds)
    return {"deleted": True}

"""CSV upload for backtests, without ever storing the file.

The browser parses the CSV and sends rows in chunks (max 5,000 rows each):

  1. create()     -> a dataset record; clears old backtest candles for the symbol
  2. add_chunk()  -> validates rows, converts time to UTC, stores them as RAW
                     candles in the BACKTEST database (retries are harmless)
  3. complete()   -> pandas builds 15Min / 1Hour / 1Day bars from the raw
                     bars (only regular session), then deletes the RAW rows

The strategy needs bars of 15 minutes or smaller (1, 5 or 15 minute data).
Daily-only files (e.g. Yahoo/Google daily history) are rejected with a clear
message, because they can't drive a 15-minute strategy.
"""
from __future__ import annotations

from datetime import datetime, time, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import pandas as pd
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.backtest.data_loader import UPSERT_BATCH, ensure_stock
from app.market.sessions import MarketSession, session_for_stock
from app.models.backtest import BacktestDataset
from app.models.market_candle import MarketCandle
from app.models.stock import Stock
from app.repositories.market_candle_repository import MarketCandleRepository

RAW_TIMEFRAME = "RAW"
MAX_ROWS_PER_CHUNK = 5_000
MAX_ROWS_PER_DATASET = 700_000  # about 6 years of 1-minute bars
SOURCE = "CSV_UPLOAD"


# ---------------------------------------------------------------------------
# Pure helpers (no database): easy to unit test
# ---------------------------------------------------------------------------

def validate_timezone(name: str) -> str:
    try:
        ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        raise ValueError(f"Unknown timezone '{name}'") from None
    return name


def normalize_rows(rows: list[dict], source_timezone: str) -> tuple[pd.DataFrame, int]:
    """rows: [{"time": "...", "open": .., "high": .., "low": .., "close": .., "volume": ..}]

    Returns (clean frame indexed by UTC time, number of rejected rows).
    Timestamps with an offset/zone keep it; naive ones use source_timezone.
    """
    if not rows:
        return pd.DataFrame(columns=["open", "high", "low", "close", "volume"]), 0

    df = pd.DataFrame(rows)
    missing = {"time", "open", "high", "low", "close"} - set(df.columns)
    if missing:
        raise ValueError(f"Missing columns: {', '.join(sorted(missing))}")
    if "volume" not in df.columns:
        df["volume"] = 0

    total = len(df)
    for column in ("open", "high", "low", "close", "volume"):
        df[column] = pd.to_numeric(df[column], errors="coerce")

    parsed = []
    for value in df["time"]:
        try:
            ts = pd.Timestamp(value)
            if ts.tzinfo is None:
                ts = ts.tz_localize(source_timezone, ambiguous="NaT", nonexistent="NaT")
            parsed.append(ts.tz_convert("UTC") if ts is not pd.NaT else pd.NaT)
        except (ValueError, TypeError):
            parsed.append(pd.NaT)
    df["time"] = pd.to_datetime(parsed, utc=True)

    df["volume"] = df["volume"].fillna(0)
    ok = (
        df["time"].notna()
        & df[["open", "high", "low", "close"]].notna().all(axis=1)
        & (df[["open", "high", "low", "close"]] > 0).all(axis=1)
        & (df["high"] >= df[["open", "close", "low"]].max(axis=1))
        & (df["low"] <= df[["open", "close"]].min(axis=1))
        & (df["volume"] >= 0)
    )
    clean = df.loc[ok, ["time", "open", "high", "low", "close", "volume"]]
    clean = clean.drop_duplicates(subset="time", keep="last").set_index("time").sort_index()
    return clean, total - len(clean)


def detect_bar_minutes(index: pd.DatetimeIndex) -> int | None:
    """Most common gap between consecutive bars on the same day, in minutes."""
    if len(index) < 3:
        return None
    s = pd.Series(index)
    same_day = s.dt.date == s.shift().dt.date
    gaps = s.diff()[same_day].dropna()
    if gaps.empty:
        return 1440  # one bar per day
    return int(round(gaps.mode().iloc[0].total_seconds() / 60))


AGG = {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}


def build_timeframes(raw_utc: pd.DataFrame, session: MarketSession) -> dict[str, pd.DataFrame]:
    """Regular-session 15Min / 1Hour / 1Day bars from small raw bars.

    Alignment matches the live data sources so the strategy sees the same
    shapes: 15-minute bars on the quarter hour; hourly bars on clock hours for
    the US (Alpaca) and at :15 for India (Kite); daily bars labelled at local
    midnight.
    """
    local = raw_utc.tz_convert(session.tz)
    local = local[local.index.dayofweek < 5]
    local = local.between_time(session.open, session.close, inclusive="left")
    if local.empty:
        raise ValueError("No bars inside regular trading hours. Check the timezone setting.")

    hour_offset = "15min" if session.code == "IN" else "0min"
    frames = {
        "15Min": local.resample("15min", label="left", closed="left").agg(AGG),
        "1Hour": local.resample("60min", label="left", closed="left", offset=hour_offset).agg(AGG),
        "1Day": local.resample("1D", label="left", closed="left").agg(AGG),
    }
    return {
        tf: frame.dropna(subset=["open"]).tz_convert("UTC")
        for tf, frame in frames.items()
    }


def _candle_rows(stock_id: int, timeframe: str, frame: pd.DataFrame) -> list[dict]:
    return [
        {
            "stock_id": stock_id,
            "timeframe": timeframe,
            "candle_time": ts.to_pydatetime(),
            "open_price": float(r.open),
            "high_price": float(r.high),
            "low_price": float(r.low),
            "close_price": float(r.close),
            "volume": float(r.volume),
            "trade_count": None,
            "vwap": None,
            "source": SOURCE,
        }
        for ts, r in frame.iterrows()
    ]


def _upsert(bt_db: Session, rows: list[dict]) -> None:
    for i in range(0, len(rows), UPSERT_BATCH):
        MarketCandleRepository.upsert_all(bt_db, rows[i : i + UPSERT_BATCH])


# ---------------------------------------------------------------------------
# Database operations
# ---------------------------------------------------------------------------

def _stock(bt_db: Session, symbol: str) -> Stock:
    stock = bt_db.scalar(select(Stock).where(Stock.symbol == symbol))
    if stock is None:
        raise ValueError(f"{symbol} is missing from the backtest database")
    return stock


def create(app_db: Session, bt_db: Session, symbol: str, source_timezone: str, user_id: int | None) -> BacktestDataset:
    symbol = symbol.strip().upper()
    validate_timezone(source_timezone)
    stock = ensure_stock(bt_db, app_db, symbol, allow_indian=True)

    # A new upload replaces whatever history the backtest DB had for this symbol.
    bt_db.execute(delete(MarketCandle).where(MarketCandle.stock_id == stock.stock_id))
    bt_db.commit()

    previous = app_db.scalars(
        select(BacktestDataset).where(
            BacktestDataset.symbol == symbol,
            BacktestDataset.status.in_(("UPLOADING", "READY")),
        )
    ).all()
    for old in previous:
        old.status = "PURGED"
        old.message = "Replaced by a newer upload"

    dataset = BacktestDataset(
        created_by_user_id=user_id,
        symbol=symbol,
        source_timezone=source_timezone,
        status="UPLOADING",
    )
    app_db.add(dataset)
    app_db.commit()
    app_db.refresh(dataset)
    return dataset


def add_chunk(app_db: Session, bt_db: Session, dataset_id: int, chunk_index: int, rows: list[dict]) -> BacktestDataset:
    dataset = app_db.get(BacktestDataset, dataset_id)
    if dataset is None:
        raise LookupError("Dataset not found")
    if dataset.status != "UPLOADING":
        raise ValueError(f"Dataset is {dataset.status}; start a new upload")
    if len(rows) > MAX_ROWS_PER_CHUNK:
        raise ValueError(f"At most {MAX_ROWS_PER_CHUNK} rows per chunk")
    if chunk_index < dataset.chunks_received:
        return dataset  # already received (browser retry); upsert makes it harmless anyway
    if chunk_index > dataset.chunks_received:
        raise ValueError(f"Expected chunk {dataset.chunks_received}, got {chunk_index}")
    if dataset.rows_received + len(rows) > MAX_ROWS_PER_DATASET:
        raise ValueError(f"File too large: at most {MAX_ROWS_PER_DATASET:,} rows per upload")

    clean, rejected = normalize_rows(rows, dataset.source_timezone)
    stock = _stock(bt_db, dataset.symbol)
    _upsert(bt_db, _candle_rows(stock.stock_id, RAW_TIMEFRAME, clean))

    dataset.chunks_received += 1
    dataset.rows_received += len(clean)
    dataset.rows_rejected += rejected
    app_db.commit()
    return dataset


def complete(app_db: Session, bt_db: Session, dataset_id: int) -> BacktestDataset:
    dataset = app_db.get(BacktestDataset, dataset_id)
    if dataset is None:
        raise LookupError("Dataset not found")
    if dataset.status != "UPLOADING":
        raise ValueError(f"Dataset is {dataset.status}")

    stock = _stock(bt_db, dataset.symbol)
    raw_rows = bt_db.execute(
        select(
            MarketCandle.candle_time,
            MarketCandle.open_price,
            MarketCandle.high_price,
            MarketCandle.low_price,
            MarketCandle.close_price,
            MarketCandle.volume,
        )
        .where(MarketCandle.stock_id == stock.stock_id, MarketCandle.timeframe == RAW_TIMEFRAME)
        .order_by(MarketCandle.candle_time)
    ).all()

    try:
        if not raw_rows:
            raise ValueError("No valid rows were received")
        raw = pd.DataFrame(raw_rows, columns=["time", "open", "high", "low", "close", "volume"])
        raw["time"] = pd.to_datetime(raw["time"], utc=True)
        raw = raw.set_index("time").astype(float)

        minutes = detect_bar_minutes(raw.index)
        if minutes is None or minutes > 15 or 15 % minutes != 0:
            size = "daily" if minutes and minutes >= 1440 else f"{minutes}-minute" if minutes else "unknown"
            raise ValueError(
                f"This file has {size} bars. The strategy trades on 15-minute bars, "
                "so the file needs 1, 5 or 15-minute bars."
            )
        dataset.base_timeframe = f"{minutes}Min"

        frames = build_timeframes(raw, session_for_stock(stock))
        counts = {}
        for timeframe, frame in frames.items():
            _upsert(bt_db, _candle_rows(stock.stock_id, timeframe, frame))
            counts[timeframe] = len(frame)

        dataset.bars_by_timeframe = counts
        dataset.first_bar = frames["15Min"].index.min().to_pydatetime()
        dataset.last_bar = frames["15Min"].index.max().to_pydatetime()
        dataset.status = "READY"
        dataset.message = (
            f"{counts['15Min']:,} 15-minute bars, {dataset.rows_rejected:,} rows rejected"
        )
    except ValueError as exc:
        dataset.status = "FAILED"
        dataset.message = str(exc)
    finally:
        bt_db.execute(
            delete(MarketCandle).where(
                MarketCandle.stock_id == stock.stock_id,
                MarketCandle.timeframe == RAW_TIMEFRAME,
            )
        )
        bt_db.commit()
        dataset.completed_at = datetime.now(timezone.utc)
        app_db.commit()
    return dataset


def purge(app_db: Session, bt_db: Session, dataset: BacktestDataset) -> None:
    """Delete the dataset's candles from the backtest DB (keeps the record)."""
    stock = bt_db.scalar(select(Stock).where(Stock.symbol == dataset.symbol))
    if stock is not None:
        bt_db.execute(delete(MarketCandle).where(MarketCandle.stock_id == stock.stock_id))
        bt_db.commit()
    dataset.status = "PURGED"
    app_db.commit()

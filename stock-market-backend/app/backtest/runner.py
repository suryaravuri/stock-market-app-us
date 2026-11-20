"""Execute a backtest run.

Locally:
    python -m app.backtest.runner --symbols AAPL --start 2025-01-01 --end 2025-12-31
    python -m app.backtest.runner --run-id 7          # a run created in the app

On Cloud Run the same module is the command of a Cloud Run Job, started by
POST /api/v1/backtests with the arguments ["--run-id", "<id>"].
"""
from __future__ import annotations

import argparse
import logging
import sys
from datetime import date, datetime, timezone

from sqlalchemy import delete

from app.backtest.data_loader import ensure_stock, load_history
from app.backtest.database import BacktestSessionLocal
from app.backtest.engine import BacktestParams, combine, run_symbol
from app.backtest.metrics import equity_curve_points
from app.core.database import SessionLocal
from app.models.backtest import BacktestDataset, BacktestRun, BacktestTrade
from app.models.market_candle import MarketCandle

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("backtest")


def execute(run_id: int) -> None:
    app_db = SessionLocal()
    bt_db = BacktestSessionLocal()
    run = app_db.get(BacktestRun, run_id)
    if run is None:
        raise SystemExit(f"Backtest run {run_id} not found")
    if run.status not in ("QUEUED", "FAILED"):
        raise SystemExit(f"Backtest run {run_id} is {run.status}")

    params = BacktestParams.from_dict(run.parameters)
    symbols = [s.strip().upper() for s in run.symbols.split(",") if s.strip()]

    def update(progress: float, message: str) -> None:
        run.progress_percent = round(progress * 100, 1)
        run.message = message
        app_db.commit()

    run.status = "RUNNING"
    run.started_at = datetime.now(timezone.utc)
    run.results = None
    app_db.execute(delete(BacktestTrade).where(BacktestTrade.backtest_run_id == run_id))
    update(0, "Starting")

    try:
        results = []
        for position, symbol in enumerate(symbols):
            share = 1 / len(symbols)
            base = position * share

            uploaded = (run.parameters or {}).get("data_source") == "UPLOAD"
            stock = ensure_stock(bt_db, app_db, symbol, allow_indian=uploaded)
            if uploaded:
                update(base, f"{symbol}: using uploaded data")
            else:
                update(base, f"{symbol}: downloading history from Alpaca")
                load_history(bt_db, stock, run.start_date, run.end_date,
                             progress=lambda msg: update(base, msg))

            # Downloading is ~10% of the work; the replay is the rest.
            symbol_result = run_symbol(
                bt_db, stock, run.start_date, run.end_date, params,
                progress=lambda p, msg: update(base + share * (0.1 + 0.9 * p), msg),
            )
            results.append(symbol_result)

            app_db.add_all(
                BacktestTrade(
                    backtest_run_id=run_id,
                    symbol=t.symbol,
                    signal_time=t.signal_time,
                    entry_time=t.entry_time,
                    entry_price=round(t.entry_price, 4),
                    exit_time=t.exit_time,
                    exit_price=round(t.exit_price, 4),
                    shares=t.shares,
                    initial_stop=round(t.initial_stop, 4),
                    final_stop=round(t.final_stop, 4),
                    target=round(t.target, 4),
                    pnl=round(t.pnl, 2),
                    pnl_percent=round(t.pnl_percent, 3),
                    r_multiple=round(t.r_multiple, 3) if t.r_multiple is not None else None,
                    exit_reason=t.exit_reason,
                )
                for t in symbol_result.trades
            )
            app_db.commit()

            if params_purge(run):
                bt_db.execute(delete(MarketCandle).where(MarketCandle.stock_id == stock.stock_id))
                bt_db.commit()
                if uploaded:
                    for ds in app_db.query(BacktestDataset).filter(
                        BacktestDataset.symbol == symbol, BacktestDataset.status == "READY"
                    ):
                        ds.status = "PURGED"
                        ds.message = f"Deleted after backtest run {run_id}"
                    app_db.commit()

        run.results = {
            "overall": combine(results, params),
            "by_symbol": {r.symbol: r.summary for r in results},
            "equity_curve": {r.symbol: equity_curve_points(r.equity) for r in results},
            "parameters": params.to_dict(),
        }
        run.status = "COMPLETED"
        run.progress_percent = 100.0
        run.message = f"Completed: {sum(len(r.trades) for r in results)} trades"
    except Exception as exc:  # noqa: BLE001
        logger.exception("Backtest %s failed", run_id)
        app_db.rollback()
        run.status = "FAILED"
        run.message = f"{type(exc).__name__}: {exc}"[:2000]
    finally:
        run.finished_at = datetime.now(timezone.utc)
        app_db.commit()
        app_db.close()
        bt_db.close()

    logger.info("Backtest %s %s: %s", run_id, run.status, run.message)
    if run.status == "FAILED":
        sys.exit(1)


def params_purge(run: BacktestRun) -> bool:
    return bool((run.parameters or {}).get("purge_candles_after_run", False))


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a strategy backtest")
    parser.add_argument("--run-id", type=int)
    parser.add_argument("--symbols", help="Comma-separated, e.g. AAPL,MSFT")
    parser.add_argument("--start", type=date.fromisoformat)
    parser.add_argument("--end", type=date.fromisoformat)
    parser.add_argument("--cash", type=float, default=10_000.0)
    args = parser.parse_args()

    run_id = args.run_id
    if run_id is None:
        if not (args.symbols and args.start and args.end):
            parser.error("give --run-id, or --symbols with --start and --end")
        with SessionLocal() as db:
            run = BacktestRun(
                symbols=args.symbols.upper(),
                start_date=args.start,
                end_date=args.end,
                parameters={"starting_cash": args.cash},
                status="QUEUED",
            )
            db.add(run)
            db.commit()
            run_id = run.backtest_run_id
        logger.info("Created backtest run %s", run_id)

    execute(run_id)


if __name__ == "__main__":
    main()

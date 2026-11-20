"""Compare the current support-bounce rules with the experimental ones.

Step 1 - create two backtest runs with identical symbols/dates:
    python -m app.backtest.compare_bounce create --symbols COST,WMT,AAPL,MSFT,JPM \
        --start 2026-05-01 --end 2026-11-14

    A = current rules   (zone 0.5 x 15-min ATR, same-candle confirmation)
    B = experimental    (zone also 0.25 x daily ATR, touch up to 2 candles earlier)
    Both: ENTRY_MODE=SUPPORT_BOUNCE, SWING (daily) levels.

Step 2 - run them (one at a time; each can take a while):
    python -m app.backtest.runner --run-id <A>
    python -m app.backtest.runner --run-id <B>

Step 3 - side-by-side report:
    python -m app.backtest.compare_bounce report <A> <B>
"""
from __future__ import annotations

import argparse
from datetime import date

from sqlalchemy import select

from app.api.v1.backtests import BacktestCreate
from app.core.database import SessionLocal
from app.models.backtest import BacktestRun
from app.models.user import AppUser

VARIANTS = {
    "A_current": {"bounce_level_zone_atr": 0.0, "bounce_confirm_bars": 1},
    "B_experimental": {"bounce_level_zone_atr": 0.25, "bounce_confirm_bars": 3},
}


def create(symbols: list[str], start: date, end: date, style: str, min_rr: float) -> None:
    db = SessionLocal()
    try:
        user = db.scalar(select(AppUser).where(AppUser.role.ilike("admin"))) or db.scalar(select(AppUser))
        ids = []
        for name, overrides in VARIANTS.items():
            req = BacktestCreate(
                symbols=symbols, start_date=start, end_date=end,
                entry_mode="SUPPORT_BOUNCE", bounce_holding_style=style,
                bounce_min_rr=min_rr, **overrides,
            )
            params = req.model_dump(exclude={"symbols", "start_date", "end_date"})
            params["variant"] = name
            run = BacktestRun(
                created_by_user_id=user.id if user else None,
                symbols=",".join(req.symbols),
                start_date=req.start_date,
                end_date=req.end_date,
                parameters=params,
                status="QUEUED",
                message=f"compare_bounce {name}",
            )
            db.add(run)
            db.commit()
            db.refresh(run)
            ids.append(run.backtest_run_id)
            print(f"{name}: run {run.backtest_run_id}")
        print("\nNow run:")
        for run_id in ids:
            print(f"  python -m app.backtest.runner --run-id {run_id}")
        print(f"\nThen:  python -m app.backtest.compare_bounce report {ids[0]} {ids[1]}")
    finally:
        db.close()


def report(a_id: int, b_id: int) -> None:
    db = SessionLocal()
    try:
        runs = [db.get(BacktestRun, a_id), db.get(BacktestRun, b_id)]
        for run_id, run in zip((a_id, b_id), runs):
            if run is None or run.status != "COMPLETED" or not run.results:
                print(f"Run {run_id}: status {getattr(run, 'status', 'NOT FOUND')} - finish it first")
                return
        summaries = [(r.results.get("overall") or {}).get("summary") or {} for r in runs]
        keys = sorted(set(summaries[0]) | set(summaries[1]))
        names = [str((r.parameters or {}).get("variant", r.backtest_run_id)) for r in runs]
        width = max([len(k) for k in keys] + [10])
        print(f"{'metric':<{width}}  {names[0]:>16}  {names[1]:>16}")
        print("-" * (width + 36))
        for key in keys:
            va, vb = summaries[0].get(key), summaries[1].get(key)
            fmt = lambda v: f"{v:,.2f}" if isinstance(v, float) else str(v)  # noqa: E731
            print(f"{key:<{width}}  {fmt(va):>16}  {fmt(vb):>16}")
        print("\nLook at: number of trades, win rate, total/average P&L, max drawdown.")
        print("B is only better if it makes MORE money per unit of drawdown, not just more trades.")
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("create")
    c.add_argument("--symbols", required=True, help="comma-separated, max 10")
    c.add_argument("--start", required=True, type=date.fromisoformat)
    c.add_argument("--end", required=True, type=date.fromisoformat)
    c.add_argument("--style", default="SWING", choices=["INTRADAY", "WEEKLY", "MONTHLY", "SWING"])
    c.add_argument("--min-rr", type=float, default=1.5)
    r = sub.add_parser("report")
    r.add_argument("a", type=int)
    r.add_argument("b", type=int)
    args = parser.parse_args()
    if args.cmd == "create":
        create([s.strip().upper() for s in args.symbols.split(",") if s.strip()],
               args.start, args.end, args.style, args.min_rr)
    else:
        report(args.a, args.b)


if __name__ == "__main__":
    main()

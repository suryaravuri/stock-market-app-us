"""Why do Dashboard / Risk screens fail?

Step 2 has the same effect as opening the Dashboard once (the strategy
may advance signal states, exactly like a normal dashboard load).

Run from stock-market-backend/:
    python -m app.scripts.check_strategy

1. Compares every frozen strategy file with the hash recorded when the
   ACTIVE validation run started, and names any file that differs.
2. Runs the same strategy call the Dashboard and Risk screens make
   (SetupService.get_setup) for each watchlist symbol and prints the
   real error, if any.
"""
import json
import traceback

from sqlalchemy import select

from app.core.database import SessionLocal
from app.models.stock import Stock
from app.models.watchlist import WatchlistStock
from app.services.validation_run_service import ValidationRunService


def check_baseline(db) -> None:
    print("1) Frozen strategy baseline")
    print(f"   Files are read from: {ValidationRunService.BASE}")
    run = ValidationRunService.active(db)
    if run is None:
        print("   No ACTIVE validation run -> baseline check is not enforced.")
        return

    status, _ = ValidationRunService.baseline_status(run)
    print(f"   Active run #{run.validation_run_id} ({run.strategy_version}): {status}")
    if status == "MATCH":
        return

    recorded = json.loads(run.baseline_manifest)["files"]
    _, current_raw = ValidationRunService.baseline()
    current = json.loads(current_raw)["files"]
    for rel in ValidationRunService.BASELINE_FILES:
        if recorded.get(rel) != current.get(rel):
            print(f"   DIFFERS: {rel}")
            print(f"      recorded {str(recorded.get(rel))[:16]}...  now {str(current.get(rel))[:16]}...")


def check_setups(db) -> None:
    from app.services.setup_service import SetupService

    print("\n2) Strategy call per symbol (what Dashboard/Risk use)")
    symbols = db.scalars(
        select(Stock.symbol)
        .join(WatchlistStock, WatchlistStock.stock_id == Stock.stock_id)
        .where(Stock.active.is_(True), WatchlistStock.analysis_enabled.is_(True))
        .distinct()
        .order_by(Stock.symbol)
    ).all()

    shown_traceback = False
    for symbol in symbols:
        try:
            setup = SetupService.get_setup(db=db, symbol=symbol)
            print(f"   OK    {symbol:6} price={setup.get('current_price')} action={setup.get('action')}")
        except Exception as exc:  # noqa: BLE001
            db.rollback()
            print(f"   ERROR {symbol:6} {type(exc).__name__}: {exc}")
            if not shown_traceback and not isinstance(exc, ValueError):
                traceback.print_exc()
                shown_traceback = True


def main() -> None:
    with SessionLocal() as db:
        check_baseline(db)
        check_setups(db)


if __name__ == "__main__":
    main()

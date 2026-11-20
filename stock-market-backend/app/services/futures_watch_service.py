"""Futures screen: READ-ONLY watch of index and commodity futures via Zerodha.

For each requested underlying (e.g. NIFTY, BANKNIFTY on NFO; GOLDM,
CRUDEOILM on MCX) it shows the nearest contracts with price, change, open
interest, lot size, basis vs spot (NFO indices/stocks) and the margin
Zerodha would block for ONE lot - i.e. how much leverage is involved.

No futures orders exist anywhere in the app. Needs the user's daily Zerodha
login (Kite Connect plan for quotes).
"""
from __future__ import annotations

import logging
import threading
from datetime import date, datetime, timezone

from sqlalchemy.orm import Session

from app.models.user import AppUser
from app.services.zerodha_auth_service import ZerodhaAuthService
from app.trading.derivatives_math import basis, change_percent, pick_nearest_futures
from app.trading.zerodha_order_rules import IST

logger = logging.getLogger(__name__)

DEFAULT_UNDERLYINGS = ["NIFTY", "BANKNIFTY", "GOLDM", "CRUDEOILM"]
FUTURES_EXCHANGES = ("NFO", "MCX")

# Index futures whose spot quote has a different name on NSE.
INDEX_SPOT_KEYS = {
    "NIFTY": "NSE:NIFTY 50",
    "BANKNIFTY": "NSE:NIFTY BANK",
    "FINNIFTY": "NSE:NIFTY FIN SERVICE",
    "MIDCPNIFTY": "NSE:NIFTY MID SELECT",
}

RISK_NOTE = (
    "Futures are leveraged: you put up only the margin, but gain or lose on "
    "the full contract value, and losses can exceed the margin. Watch-only - "
    "the app places no futures orders."
)

# The instrument dumps are large; download each exchange once per IST day.
_cache: dict[tuple[str, date], list[dict]] = {}
_cache_lock = threading.Lock()


def _instruments(client, exchange: str, today: date) -> list[dict]:
    key = (exchange, today)
    with _cache_lock:
        if key not in _cache:
            for old in [k for k in _cache if k[0] == exchange]:
                del _cache[old]
            _cache[key] = client.instruments(exchange)
        return _cache[key]


class FuturesWatchService:

    @staticmethod
    def watch(
        db: Session,
        user: AppUser,
        underlyings: list[str] | None = None,
        contracts_per_underlying: int = 2,
    ) -> dict:
        names = [u.strip().upper() for u in (underlyings or DEFAULT_UNDERLYINGS) if u.strip()]
        if not names:
            raise ValueError("No underlyings requested")
        if len(names) > 10:
            raise ValueError("At most 10 underlyings at a time")

        client, _ = ZerodhaAuthService.client_for(db, user)  # ValueError if not connected
        today = datetime.now(timezone.utc).astimezone(IST).date()

        # 1. Find the nearest contracts on NFO first, then MCX.
        chosen: list[tuple[str, dict]] = []
        not_found: list[str] = []
        for name in names:
            found = []
            for exchange in FUTURES_EXCHANGES:
                found = pick_nearest_futures(
                    _instruments(client, exchange, today), name, today, contracts_per_underlying
                )
                if found:
                    chosen.extend((exchange, row) for row in found)
                    break
            if not found:
                not_found.append(name)

        # 2. One quote call for all futures plus NFO spots.
        future_keys = [f"{ex}:{row['tradingsymbol']}" for ex, row in chosen]
        spot_keys = {
            row["name"].upper(): INDEX_SPOT_KEYS.get(row["name"].upper(), f"NSE:{row['name'].upper()}")
            for ex, row in chosen if ex == "NFO"
        }
        quotes = client.quote(future_keys + sorted(set(spot_keys.values())))

        contracts = []
        for exchange, row in chosen:
            key = f"{exchange}:{row['tradingsymbol']}"
            q = quotes.get(key) or {}
            last = q.get("last_price")
            prev_close = (q.get("ohlc") or {}).get("close")
            lot_size = int(row.get("lot_size") or 0)

            spot_price = None
            if exchange == "NFO":
                spot_price = (quotes.get(spot_keys[row["name"].upper()]) or {}).get("last_price")
            basis_points, basis_pct = basis(last, spot_price)

            contracts.append({
                "underlying": row["name"].upper(),
                "exchange": exchange,
                "tradingsymbol": row["tradingsymbol"],
                "expiry": row["expiry"],
                "days_to_expiry": (row["expiry"] - today).days,
                "lot_size": lot_size,
                "tick_size": row.get("tick_size"),
                "last_price": last,
                "change_percent": change_percent(last, prev_close),
                "volume": q.get("volume"),
                "open_interest": q.get("oi"),
                "spot_price": spot_price,
                "basis_points": basis_points,
                "basis_percent": basis_pct,
                # NFO: rupees per lot = price x lot size. MCX contract values
                # depend on per-commodity units, so only the margin is shown.
                "notional_per_lot": round(last * lot_size, 2) if exchange == "NFO" and last else None,
                "rupees_per_point_per_lot": lot_size if exchange == "NFO" else None,
                "margin_per_lot": FuturesWatchService._margin(client, exchange, row, lot_size),
            })

        return {
            "as_of": datetime.now(timezone.utc),
            "watch_only": True,
            "orders_enabled": False,
            "contracts": contracts,
            "not_found": not_found,
            "risk_note": RISK_NOTE,
        }

    @staticmethod
    def _margin(client, exchange: str, row: dict, lot_size: int) -> float | None:
        """Margin for a hypothetical 1-lot BUY (NRML). Best effort."""
        if lot_size <= 0:
            return None
        try:
            result = client.order_margins([{
                "exchange": exchange,
                "tradingsymbol": row["tradingsymbol"],
                "transaction_type": "BUY",
                "variety": "regular",
                "product": "NRML",
                "order_type": "MARKET",
                "quantity": lot_size,
                "price": 0,
                "trigger_price": 0,
            }])
            return round(float(result[0]["total"]), 2) if result else None
        except Exception as exc:  # noqa: BLE001
            logger.warning("Margin lookup failed for %s: %s", row.get("tradingsymbol"), exc)
            return None

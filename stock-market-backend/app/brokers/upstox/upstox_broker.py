"""
Upstox adapter for the multi-broker trading bot.

Implements BrokerAdapter from app/brokers/base.py so strategy code never
talks to Upstox directly.

Upstox API notes (verify against https://upstox.com/developer/api-documentation):
- Auth is OAuth2. The access token expires daily, so each user logs in once a day.
- Orders go to the HFT host (api-hft.upstox.com), using Place Order V3.
- The order API is unavailable daily from 12:00 AM to 5:30 AM IST.
- Instruments are identified by instrument_key, e.g. "NSE_EQ|INE002A01018".
"""

from __future__ import annotations

import gzip
import json
import logging
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import httpx

from app.brokers.base import BrokerAdapter, OrderRequest, OrderResult, Side

log = logging.getLogger(__name__)

API_BASE = "https://api.upstox.com"
HFT_BASE = "https://api-hft.upstox.com"
INSTRUMENTS_URL = "https://assets.upstox.com/market-quote/instruments/exchange/NSE.json.gz"

IST = timezone(timedelta(hours=5, minutes=30))

# Upstox order statuses -> our normalized statuses
STATUS_MAP = {
    "complete": "FILLED",
    "rejected": "REJECTED",
    "cancelled": "CANCELLED",
    "open": "PLACED",
    "trigger pending": "PLACED",
    "validation pending": "PLACED",
    "put order req received": "PLACED",
    "open pending": "PLACED",
    "modify pending": "PLACED",
    "cancel pending": "PLACED",
}

ORDER_TYPE_MAP = {"MARKET": "MARKET", "LIMIT": "LIMIT", "SL": "SL", "SL-M": "SL-M"}


class UpstoxError(Exception):
    """Raised for Upstox API errors, carrying the Upstox error code if present."""

    def __init__(self, message: str, code: str | None = None, status: int | None = None):
        super().__init__(message)
        self.code = code
        self.status = status


class UpstoxSessionExpired(UpstoxError):
    """Access token missing, expired or revoked: the user must log in again."""


@dataclass
class UpstoxCredentials:
    api_key: str                 # Upstox "client_id"
    api_secret: str
    redirect_uri: str
    access_token: str | None = None
    token_expires_at: datetime | None = None


# ---------------------------------------------------------------------------
# Symbol mapping: internal "NSE:RELIANCE" <-> Upstox "NSE_EQ|INE002A01018"
# ---------------------------------------------------------------------------

class UpstoxInstruments:
    """
    Caches the NSE instrument master. Refresh once per trading day
    (e.g. a scheduled job at 8:00 AM IST) and share one instance across users.
    """

    def __init__(self) -> None:
        self._by_symbol: dict[str, str] = {}
        self._by_key: dict[str, str] = {}
        self.loaded_on: str | None = None

    def refresh(self, client: httpx.Client | None = None) -> None:
        own_client = client is None
        client = client or httpx.Client(timeout=60)
        try:
            resp = client.get(INSTRUMENTS_URL)
            resp.raise_for_status()
            rows = json.loads(gzip.decompress(resp.content))
        finally:
            if own_client:
                client.close()

        by_symbol, by_key = {}, {}
        for row in rows:
            if row.get("segment") != "NSE_EQ" or row.get("instrument_type") != "EQ":
                continue
            internal = f"NSE:{row['trading_symbol']}"
            by_symbol[internal] = row["instrument_key"]
            by_key[row["instrument_key"]] = internal

        self._by_symbol, self._by_key = by_symbol, by_key
        self.loaded_on = datetime.now(IST).date().isoformat()
        log.info("Loaded %d Upstox NSE equity instruments", len(by_symbol))

    def to_key(self, symbol: str) -> str:
        try:
            return self._by_symbol[symbol]
        except KeyError:
            raise UpstoxError(f"Unknown symbol for Upstox: {symbol}") from None

    def to_symbol(self, instrument_key: str) -> str:
        return self._by_key.get(instrument_key, instrument_key)


# ---------------------------------------------------------------------------
# OAuth helpers (used by the FastAPI login routes)
# ---------------------------------------------------------------------------

def build_login_url(api_key: str, redirect_uri: str, state: str) -> str:
    """URL the user opens each morning to authorize the app."""
    params = {
        "response_type": "code",
        "client_id": api_key,
        "redirect_uri": redirect_uri,
        "state": state,  # random value tied to the user, checked in the callback
    }
    return f"{API_BASE}/v2/login/authorization/dialog?{urlencode(params)}"


def exchange_code_for_token(creds: UpstoxCredentials, code: str) -> UpstoxCredentials:
    """Swap the OAuth code from the callback for today's access token."""
    resp = httpx.post(
        f"{API_BASE}/v2/login/authorization/token",
        data={
            "code": code,
            "client_id": creds.api_key,
            "client_secret": creds.api_secret,
            "redirect_uri": creds.redirect_uri,
            "grant_type": "authorization_code",
        },
        headers={"Accept": "application/json"},
        timeout=15,
    )
    if resp.status_code != 200:
        raise UpstoxError(f"Token exchange failed: {resp.text}", status=resp.status_code)

    creds.access_token = resp.json()["access_token"]
    creds.token_expires_at = _next_token_expiry()
    return creds


def _next_token_expiry() -> datetime:
    """Upstox tokens expire around 3:30 AM IST the next day."""
    now = datetime.now(IST)
    expiry = now.replace(hour=3, minute=30, second=0, microsecond=0)
    if now >= expiry:
        expiry += timedelta(days=1)
    return expiry


# ---------------------------------------------------------------------------
# The adapter
# ---------------------------------------------------------------------------

class UpstoxBroker(BrokerAdapter):
    """
    One instance per user session. Build it through the registry with
    decrypted credentials and the shared UpstoxInstruments cache.
    """

    def __init__(
        self,
        creds: UpstoxCredentials,
        instruments: UpstoxInstruments,
        product: str = "D",        # "D" = delivery (swing trades), "I" = intraday
        dry_run: bool = True,       # log orders instead of sending them
    ) -> None:
        self.creds = creds
        self.instruments = instruments
        self.product = product
        self.dry_run = dry_run
        self._client = httpx.Client(timeout=10)

    # ---- BrokerAdapter interface -----------------------------------------

    def place_order(self, order: OrderRequest) -> OrderResult:
        self._require_session()
        if not self._order_window_open():
            return OrderResult("", "REJECTED", "Upstox order API is closed 12:00-5:30 AM IST")

        order_type = ORDER_TYPE_MAP.get(order.order_type.upper())
        if order_type is None:
            return OrderResult("", "REJECTED", f"Unsupported order type: {order.order_type}")
        if order_type in ("LIMIT", "SL") and not order.price:
            return OrderResult("", "REJECTED", f"{order_type} order needs a price")

        trigger_price = getattr(order, "trigger_price", None) or 0
        if order_type in ("SL", "SL-M") and not trigger_price:
            return OrderResult("", "REJECTED", f"{order_type} order needs a trigger price")

        # The tag lets us find this order again if the response is lost,
        # instead of blindly retrying and risking a duplicate order.
        tag = getattr(order, "tag", None) or uuid.uuid4().hex[:20]

        payload = {
            "instrument_token": self.instruments.to_key(order.symbol),
            "quantity": int(order.qty),
            "product": self.product,
            "validity": "DAY",
            "price": float(order.price or 0),
            "tag": tag,
            "order_type": order_type,
            "transaction_type": "BUY" if order.side == Side.BUY else "SELL",
            "disclosed_quantity": 0,
            "trigger_price": float(trigger_price),
            "is_amo": False,
            "slice": True,
        }

        if self.dry_run:
            log.info("[DRY RUN] Upstox order: %s", payload)
            return OrderResult(f"DRYRUN-{tag}", "PLACED", "Dry run, not sent to Upstox")

        try:
            data = self._request("POST", f"{HFT_BASE}/v3/order/place", json=payload, retry=False)
        except UpstoxSessionExpired:
            raise
        except UpstoxError as exc:
            log.warning("Upstox order rejected (%s): %s", exc.code, exc)
            return OrderResult("", "REJECTED", str(exc))
        except httpx.TransportError as exc:
            # Network failure: the order may or may not have reached Upstox.
            log.error("Upstox order status unknown, tag=%s: %s", tag, exc)
            return OrderResult("", "UNKNOWN", f"Network error; check order book for tag {tag}")

        order_ids = data.get("order_ids") or []
        return OrderResult(",".join(order_ids), "PLACED", f"tag={tag}")

    def get_order_status(self, broker_order_id: str) -> OrderResult:
        """Not in the base interface yet; useful for confirming fills."""
        self._require_session()
        data = self._request(
            "GET", f"{API_BASE}/v2/order/details", params={"order_id": broker_order_id}
        )
        raw = (data.get("status") or "").lower()
        return OrderResult(
            broker_order_id,
            STATUS_MAP.get(raw, "PLACED"),
            data.get("status_message") or raw,
        )

    def get_positions(self) -> list[dict]:
        """Delivery holdings plus today's positions, in a normalized shape."""
        self._require_session()
        out: list[dict] = []

        holdings = self._request("GET", f"{API_BASE}/v2/portfolio/long-term-holdings") or []
        for h in holdings:
            out.append({
                "symbol": self.instruments.to_symbol(h.get("instrument_token", "")),
                "qty": int(h.get("quantity", 0)),
                "avg_price": float(h.get("average_price", 0)),
                "ltp": float(h.get("last_price", 0)),
                "pnl": float(h.get("pnl", 0)),
                "source": "holding",
            })

        positions = self._request("GET", f"{API_BASE}/v2/portfolio/short-term-positions") or []
        for p in positions:
            qty = int(p.get("quantity", 0))
            if qty == 0:
                continue
            out.append({
                "symbol": self.instruments.to_symbol(p.get("instrument_token", "")),
                "qty": qty,
                "avg_price": float(p.get("average_price", 0)),
                "ltp": float(p.get("last_price", 0)),
                "pnl": float(p.get("pnl", 0)),
                "source": "position",
            })
        return out

    def get_ltp(self, symbols: list[str]) -> dict[str, float]:
        self._require_session()
        prices: dict[str, float] = {}

        # Upstox accepts several instrument keys per request; batch to stay safe.
        keys = [self.instruments.to_key(s) for s in symbols]
        for i in range(0, len(keys), 100):
            batch = keys[i:i + 100]
            data = self._request(
                "GET",
                f"{API_BASE}/v3/market-quote/ltp",
                params={"instrument_key": ",".join(batch)},
            ) or {}
            # Response is keyed like "NSE_EQ:RELIANCE"; each entry carries instrument_token.
            for quote in data.values():
                key = quote.get("instrument_token")
                if key and quote.get("last_price") is not None:
                    prices[self.instruments.to_symbol(key)] = float(quote["last_price"])
        return prices

    def is_session_valid(self) -> bool:
        if not self.creds.access_token:
            return False
        if self.creds.token_expires_at and datetime.now(IST) >= self.creds.token_expires_at:
            return False
        try:
            self._request("GET", f"{API_BASE}/v2/user/profile")
            return True
        except UpstoxSessionExpired:
            return False

    def close(self) -> None:
        self._client.close()

    # ---- internals --------------------------------------------------------

    def _require_session(self) -> None:
        if not self.creds.access_token:
            raise UpstoxSessionExpired("No Upstox access token; user must log in today")

    @staticmethod
    def _order_window_open() -> bool:
        now = datetime.now(IST)
        return now.hour > 5 or (now.hour == 5 and now.minute >= 30)

    def _request(self, method: str, url: str, retry: bool = True, **kwargs):
        """
        Sends a request and returns the "data" field.
        Read-only calls retry on 429/5xx; order placement passes retry=False
        so a slow response never turns into a duplicate order.
        """
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {self.creds.access_token}",
        }
        if "json" in kwargs:
            headers["Content-Type"] = "application/json"

        attempts = 3 if retry else 1
        for attempt in range(1, attempts + 1):
            resp = self._client.request(method, url, headers=headers, **kwargs)

            if resp.status_code == 401:
                raise UpstoxSessionExpired("Upstox token expired or invalid", status=401)

            if resp.status_code in (429, 500, 502, 503, 504) and attempt < attempts:
                time.sleep(0.5 * 2 ** (attempt - 1))
                continue

            try:
                body = resp.json()
            except ValueError:
                raise UpstoxError(f"Non-JSON response ({resp.status_code})", status=resp.status_code)

            if resp.status_code >= 400 or body.get("status") == "error":
                err = (body.get("errors") or [{}])[0]
                raise UpstoxError(
                    err.get("message") or resp.text,
                    code=err.get("errorCode") or err.get("error_code"),
                    status=resp.status_code,
                )
            return body.get("data")

        raise UpstoxError("Upstox request failed after retries")

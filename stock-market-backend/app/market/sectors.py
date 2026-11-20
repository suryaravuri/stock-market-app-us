"""Sector of each stock, for the per-sector position limit.

Static map for the stocks this app trades; anything not listed falls back
to stock.sector in the database, then to "UNKNOWN" (no limit applied).
Groups follow how these stocks actually move together (e.g. all chip
makers and chip-equipment makers are one group: they fell together on
2026-11-16).
"""
from __future__ import annotations

SECTOR_MAP: dict[str, str] = {}

_GROUPS = {
    "SEMICONDUCTORS": "NVDA AMD AVGO TSM MU LRCX AMAT KLAC NXPI SNDK INTC QCOM TXN ADI MRVL ON ARM ASML MCHP",
    "SOFTWARE_CLOUD": "MSFT ORCL ADBE INTU CRM NOW ADP PANW CRWD SNOW PLTR CRWV WDAY FTNT IONQ",
    "INTERNET_MEDIA": "GOOGL GOOG META NFLX DIS",
    "TECH_HARDWARE": "AAPL ANET DELL HPQ CSCO",
    "CONSUMER_DISCRETIONARY": "AMZN TSLA SBUX MCD TSCO DPZ HD LOW NKE CMG BKNG",
    "CONSUMER_STAPLES": "COST PG KO PEP WMT CL MDLZ",
    "HEALTHCARE": "JNJ UNH AMGN LLY ABBV MRK PFE TMO",
    "FINANCIALS": "V MA BRK.B JPM BAC GS MS AXP",
    "INDUSTRIALS": "BA CAT GE HON UPS RTX LMT DE SHIP",
    "ENERGY": "OXY XOM CVX COP SLB",
}
for _sector, _symbols in _GROUPS.items():
    for _symbol in _symbols.split():
        SECTOR_MAP[_symbol] = _sector


def sector_for(symbol: str, db_sector: str | None = None) -> str:
    symbol = (symbol or "").strip().upper()
    if symbol in SECTOR_MAP:
        return SECTOR_MAP[symbol]
    if db_sector and db_sector.strip():
        return db_sector.strip().upper().replace(" ", "_")
    return "UNKNOWN"

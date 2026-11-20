"""Service package.

Keep package import side-effect free so stateless strategy/simulation tests do not
initialize database/broker configuration just by importing a service module.
"""

__all__ = ["StockService", "WatchlistService"]


def __getattr__(name: str):
    if name == "StockService":
        from app.services.stock_service import StockService
        return StockService
    if name == "WatchlistService":
        from app.services.watchlist_service import WatchlistService
        return WatchlistService
    raise AttributeError(name)

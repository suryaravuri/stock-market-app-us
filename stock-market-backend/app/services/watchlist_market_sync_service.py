from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AppUser
from app.models.stock import Stock
from app.models.watchlist import (
    Watchlist,
    WatchlistStock,
)
from app.schemas.market import MarketTimeframe
from app.market.sessions import is_indian_exchange
from app.services.market_service import MarketService
from app.services.zerodha_auth_service import ZerodhaAuthService
from app.services.watchlist_service import WatchlistService


class WatchlistMarketSyncService:

    TIMEFRAMES = [
        (
            MarketTimeframe.FIFTEEN_MINUTES,
            15,
        ),
        (
            MarketTimeframe.ONE_HOUR,
            180,
        ),
        (
            MarketTimeframe.ONE_DAY,
            180,
        ),
    ]

    @staticmethod
    def sync(
        db: Session,
        watchlist_id: int,
        current_user: AppUser,
    ) -> dict:

        # ---------------------------------
        # 1. Validate watchlist
        # ---------------------------------

        # ---------------------------------
        # 1. Validate watchlist ownership
        # ---------------------------------

        watchlist = WatchlistService.get_watchlist(
            db=db,
            watchlist_id=watchlist_id,
            current_user=current_user,
        )

        # if watchlist is None:
        #     raise ValueError(
        #         f"Watchlist '{watchlist_id}' not found"
        #     )

        # ---------------------------------
        # 2. Load analysis-enabled stocks
        # ---------------------------------

        stmt = (
            select(
                WatchlistStock,
                Stock,
            )
            .join(
                Stock,
                Stock.stock_id
                == WatchlistStock.stock_id,
            )
            .where(
                WatchlistStock.watchlist_id
                == watchlist_id,
                Stock.active.is_(True),
            )
            .order_by(
                WatchlistStock.priority.desc(),
                Stock.symbol.asc(),
            )
        )

        rows = db.execute(
            stmt
        ).all()

        # ---------------------------------
        # 3. Create MarketService instance
        # ---------------------------------

        # NSE/BSE candles come from Zerodha using this user's daily login.
        zerodha_client = None
        if any(is_indian_exchange(stock.exchange) for _, stock in rows):
            try:
                zerodha_client, _ = ZerodhaAuthService.client_for(db, current_user)
            except ValueError:
                zerodha_client = None  # Indian rows report a clear per-stock error

        market_service = MarketService(zerodha_client=zerodha_client)

        results: list[dict] = []

        # ---------------------------------
        # 4. Process each stock
        # ---------------------------------

        for watchlist_stock, stock in rows:

            symbol = stock.symbol.strip().upper()

            stock_result = {
                "stock_id": stock.stock_id,
                "symbol": symbol,
                "success": True,
                "timeframes": [],
                "errors": [],
            }

            # -----------------------------
            # 5. Sync each timeframe
            # -----------------------------

            for timeframe, days in (
                WatchlistMarketSyncService.TIMEFRAMES
            ):

                try:

                    result = (
                        market_service.sync_bars(
                            db=db,
                            symbol=symbol,
                            timeframe=timeframe,
                            days=days,
                        )
                    )

                    stock_result[
                        "timeframes"
                    ].append(
                        {
                            "timeframe":
                                timeframe.value,

                            "days":
                                days,

                            "fetched":
                                result["fetched"],

                            "persisted":
                                result["persisted"],

                            "position_monitoring":
                                result.get("position_monitoring"),

                            "success":
                                True,
                        }
                    )

                except Exception as exc:

                    # Roll back transaction in case
                    # database operation failed.
                    db.rollback()

                    stock_result[
                        "success"
                    ] = False

                    stock_result[
                        "timeframes"
                    ].append(
                        {
                            "timeframe":
                                timeframe.value,

                            "days":
                                days,

                            "fetched":
                                0,

                            "persisted":
                                0,

                            "success":
                                False,
                        }
                    )

                    stock_result[
                        "errors"
                    ].append(
                        {
                            "timeframe":
                                timeframe.value,

                            "message":
                                str(exc),
                        }
                    )

            results.append(
                stock_result
            )

        # ---------------------------------
        # 6. Summary counts
        # ---------------------------------

        successful_stocks = sum(
            1
            for result in results
            if result["success"]
        )

        failed_stocks = (
            len(results)
            - successful_stocks
        )

        # ---------------------------------
        # 7. Response
        # ---------------------------------

        return {
            "watchlist_id":
                watchlist.watchlist_id,

            "watchlist_name":
                watchlist.name,

            "total_stocks":
                len(results),

            "successful_stocks":
                successful_stocks,

            "failed_stocks":
                failed_stocks,

            "stocks":
                results,
        }
from sqlalchemy.orm import Session

from app.models import AppUser
from app.services.setup_service import SetupService
from app.services.watchlist_service import WatchlistService



class WatchlistScannerService:

    @staticmethod
    def scan(
        db: Session,
        watchlist_id: int,
        current_user: AppUser,
    ) -> dict:

        # ---------------------------------
        # 1. Validate watchlist ownership
        # ---------------------------------

        watchlist = WatchlistService.get_watchlist(
            db=db,
            watchlist_id=watchlist_id,
            current_user=current_user,
        )

        # ---------------------------------
        # 2. Load only owner's watchlist stocks
        # ---------------------------------

        watchlist_stocks = (
            WatchlistService.get_watchlist_stocks(
                db=db,
                watchlist_id=watchlist_id,
                current_user=current_user,
            )
        )

        results: list[dict] = []

        # everything below remains unchanged

        # ---------------------------------
        # 3. Analyze each stock
        # ---------------------------------

        for watchlist_stock in watchlist_stocks:

            stock = watchlist_stock.stock

            if stock is None:
                continue

            symbol = stock.symbol

            try:
                setup = SetupService.get_setup(
                    db=db,
                    symbol=symbol,
                )

                multi = setup["multi_timeframe"]
                risk_reward = setup["risk_reward"]

                results.append(
                    {
                        "stock_id": stock.stock_id,
                        "symbol": symbol,
                        "company_name": stock.company_name,
                        "exchange": stock.exchange,

                        "priority": watchlist_stock.priority,

                        "current_price":
                            setup["current_price"],

                        "overall_score":
                            multi["overall_score"],

                        "overall_classification":
                            multi[
                                "overall_classification"
                            ],

                        "risk_reward_quality":
                            risk_reward["quality"],

                        "rr_1":
                            risk_reward["rr_1"],

                        "rr_2":
                            risk_reward["rr_2"],

                        "entry":
                            risk_reward["entry"],

                        "stop_loss":
                            risk_reward["stop_loss"],

                        "target_1":
                            risk_reward["target_1"],

                        "target_2":
                            risk_reward["target_2"],

                        "action":
                            setup["action"],

                        "decision_reasons":
                            setup["decision_reasons"],

                        "actionable":
                            setup["actionable"],

                        "error": None,
                    }
                )

            except ValueError as exc:

                results.append(
                    {
                        "stock_id": stock.stock_id,
                        "symbol": symbol,
                        "company_name": stock.company_name,
                        "exchange": stock.exchange,

                        "priority":
                            watchlist_stock.priority,

                        "current_price": None,
                        "overall_score": None,
                        "overall_classification":
                            "UNAVAILABLE",

                        "risk_reward_quality":
                            "UNAVAILABLE",

                        "rr_1": None,
                        "rr_2": None,

                        "entry": None,
                        "stop_loss": None,
                        "target_1": None,
                        "target_2": None,

                        "action": "UNAVAILABLE",
                        "decision_reasons": [str(exc)],
                        "actionable": False,

                        "error": str(exc),
                    }
                )

        # ---------------------------------
        # 4. Rank candidates
        # ---------------------------------

        results.sort(
            key=lambda item: (
                not item["actionable"],
                -(
                    item["overall_score"]
                    if item["overall_score"]
                    is not None
                    else -999
                ),
                -item["priority"],
            )
        )

        actionable_count = sum(
            1
            for item in results
            if item["actionable"]
        )

        return {
            "watchlist_id":
                watchlist.watchlist_id,

            "watchlist_name":
                watchlist.name,

            "total_stocks":
                len(results),

            "actionable_count":
                actionable_count,

            "stocks":
                results,
        }
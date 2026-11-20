from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.market import MarketTimeframe
from app.services.support_resistance_service import SupportResistanceService
from app.schemas.analysis import AnalysisSummaryResponse
from app.services.analysis_service import AnalysisService
from app.schemas.opportunity import OpportunityResponse
from app.services.opportunity_service import OpportunityService

from app.schemas.multi_timeframe import (
    MultiTimeframeResponse,
)
from app.services.multi_timeframe_service import (
    MultiTimeframeService,
)

from app.schemas.setup import SetupResponse
from app.services.setup_service import SetupService

from app.schemas.risk import PositionSizeResponse
from app.services.risk_service import RiskService
from app.schemas.breakout import BreakoutConfirmationResponse
from app.services.breakout_service import BreakoutService
from app.schemas.market_data_quality import MarketDataQualityResponse
from app.services.market_data_quality_service import MarketDataQualityService
from app.schemas.signal_lifecycle import SignalLifecycleHistoryResponse, SignalLifecycleResponse
from app.services.signal_lifecycle_service import SignalLifecycleService
from app.schemas.position_lifecycle import (
    PositionLifecycleHistoryResponse,
    PositionLifecycleResponse,
    PositionLifecycleSimulationRequest,
    PositionLifecycleSimulationResponse,
    PersistentPositionTestRequest,
    PersistentPositionTestResponse,
    PersistentPositionTestHistoryResponse,
    PersistentPositionTestDeleteResponse,
    PersistentRealCandleMonitorStartRequest,
    PersistentRealCandleMonitorResponse,
    PositionPnLAnalyticsResponse,
)
from app.services.position_lifecycle_service import PositionLifecycleService
from app.services.position_monitoring_service import PositionMonitoringService
from app.services.position_lifecycle_simulation_service import PositionLifecycleSimulationService
from app.services.position_lifecycle_persistent_test_service import PositionLifecyclePersistentTestService
from app.services.position_lifecycle_real_candle_test_service import PositionLifecycleRealCandleTestService
from app.services.position_pnl_analytics_service import PositionPnLAnalyticsService
from app.schemas.trade_journal import TradeJournalResponse, TradePerformanceResponse
from app.services.trade_journal_service import TradeJournalService
from app.schemas.strategy_quality import (
    StrategyQualityResponse,
    StrategyQualitySimulationRequest,
    StrategyQualitySimulationResponse,
)
from app.services.strategy_quality_service import StrategyQualityService
from app.services.strategy_quality_simulation_service import StrategyQualitySimulationService
from app.schemas.strategy_diagnostics import (
    StrategyDiagnosticsResponse,
    StrategyDiagnosticsSimulationRequest,
    StrategyDiagnosticsSimulationResponse,
)
from app.services.strategy_diagnostics_service import StrategyDiagnosticsService
from app.services.strategy_diagnostics_simulation_service import StrategyDiagnosticsSimulationService
from app.core.auth_dependencies import get_current_user


router = APIRouter(
    prefix="/analysis",
    tags=["Analysis"],
    dependencies=[Depends(get_current_user)],
)


@router.get(
    "/trade-journal",
    response_model=TradeJournalResponse,
    responses={400: {"description": "Invalid journal scope"}},
)
def get_trade_journal(
    scope: str = Query(default="ALL"),
    symbol: str | None = Query(default=None),
    timeframe: MarketTimeframe | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=500),
    db: Session = Depends(get_db),
):
    """#15F read-only journal of completed analytical positions."""
    try:
        return TradeJournalService.journal(
            db,
            scope=scope,
            symbol=symbol,
            timeframe=timeframe.value if timeframe else None,
            limit=limit,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get(
    "/trade-journal/performance",
    response_model=TradePerformanceResponse,
    responses={400: {"description": "Invalid statistics scope"}},
)
def get_trade_performance(
    scope: str = Query(default="ALL"),
    symbol: str | None = Query(default=None),
    timeframe: MarketTimeframe | None = Query(default=None),
    limit: int = Query(default=500, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    """#15F aggregate win rate, R expectancy, profit factor and breakdowns."""
    try:
        return TradeJournalService.performance(
            db,
            scope=scope,
            symbol=symbol,
            timeframe=timeframe.value if timeframe else None,
            limit=limit,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get(
    "/trade-journal/quality",
    response_model=StrategyQualityResponse,
    responses={400: {"description": "Invalid quality scope"}},
)
def get_strategy_quality(
    scope: str = Query(default="ALL"),
    symbol: str | None = Query(default=None),
    timeframe: MarketTimeframe | None = Query(default=None),
    limit: int = Query(default=1000, ge=1, le=5000),
    db: Session = Depends(get_db),
):
    """#15G source-aware strategy quality score. Synthetic tests never improve the score."""
    try:
        return StrategyQualityService.quality(
            db,
            scope=scope,
            symbol=symbol,
            timeframe=timeframe.value if timeframe else None,
            limit=limit,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get(
    "/trade-journal/diagnostics",
    response_model=StrategyDiagnosticsResponse,
    responses={400: {"description": "Invalid diagnostics scope"}},
)
def get_strategy_diagnostics(
    scope: str = Query(default="ALL"),
    symbol: str | None = Query(default=None),
    timeframe: MarketTimeframe | None = Query(default=None),
    limit: int = Query(default=1000, ge=1, le=5000),
    db: Session = Depends(get_db),
):
    """#15H source-aware strategy diagnostics and prioritized weakness analysis."""
    try:
        return StrategyDiagnosticsService.diagnostics(
            db,
            scope=scope,
            symbol=symbol,
            timeframe=timeframe.value if timeframe else None,
            limit=limit,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post(
    "/trade-journal/diagnostics/simulate",
    response_model=StrategyDiagnosticsSimulationResponse,
    responses={400: {"description": "Invalid diagnostics simulation input"}},
)
def simulate_strategy_diagnostics(request: StrategyDiagnosticsSimulationRequest):
    """#15H-5 stateless, DB-free controlled weakness-diagnostics validation."""
    try:
        return StrategyDiagnosticsSimulationService.simulate(request.trades)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post(
    "/trade-journal/quality/simulate",
    response_model=StrategyQualitySimulationResponse,
    responses={400: {"description": "Invalid quality simulation input"}},
)
def simulate_strategy_quality(request: StrategyQualitySimulationRequest):
    """#15G-5 stateless, DB-free validation of the quality-score mathematics."""
    try:
        return StrategyQualitySimulationService.simulate(request.realized_r_values)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get(
    "/{symbol}/support-resistance",
    responses={
        404: {
            "description": "Stock or candle data not found"
        }
    },
)
def get_support_resistance(
    symbol: str,
    timeframe: MarketTimeframe = Query(
        default=MarketTimeframe.FIFTEEN_MINUTES
    ),
    db: Session = Depends(get_db),
):
    try:
        return SupportResistanceService.get_levels(
            db=db,
            symbol=symbol,
            timeframe=timeframe,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.get(
    "/{symbol}/summary",
    response_model=AnalysisSummaryResponse,
    responses={
        404: {
            "description": "Stock or candle data not found"
        }
    },
)
def get_analysis_summary(
    symbol: str,
    timeframe: MarketTimeframe = Query(
        default=MarketTimeframe.FIFTEEN_MINUTES
    ),
    db: Session = Depends(get_db),
):
    try:
        return AnalysisService.get_summary(
            db=db,
            symbol=symbol,
            timeframe=timeframe,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.get(
    "/{symbol}/opportunity",
    response_model=OpportunityResponse,
    responses={
        404: {
            "description": "Stock or candle data not found"
        }
    },
)
def get_opportunity(
    symbol: str,
    timeframe: MarketTimeframe = Query(
        default=MarketTimeframe.FIFTEEN_MINUTES
    ),
    db: Session = Depends(get_db),
):
    try:
        return OpportunityService.get_opportunity(
            db=db,
            symbol=symbol,
            timeframe=timeframe,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc



@router.get(
    "/{symbol}/multi-timeframe",
    response_model=MultiTimeframeResponse,
    responses={
        404: {
            "description": "Stock or candle data not found"
        }
    },
)
def get_multi_timeframe_analysis(
    symbol: str,
    db: Session = Depends(get_db),
):
    try:
        return MultiTimeframeService.get_analysis(
            db=db,
            symbol=symbol,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

@router.get(
    "/{symbol}/setup",
    response_model=SetupResponse,
    responses={
        404: {
            "description": "Stock or candle data not found"
        }
    },
)
def get_setup(
    symbol: str,
    db: Session = Depends(get_db),
):
    try:
        return SetupService.get_setup(
            db=db,
            symbol=symbol,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.get(
    "/{symbol}/breakout-confirmation",
    response_model=BreakoutConfirmationResponse,
    responses={404: {"description": "Stock or candle data not found"}},
)
def get_breakout_confirmation(
    symbol: str,
    timeframe: MarketTimeframe = Query(
        default=MarketTimeframe.FIFTEEN_MINUTES
    ),
    db: Session = Depends(get_db),
):
    try:
        return BreakoutService.get_confirmation(
            db=db,
            symbol=symbol,
            timeframe=timeframe,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.get(
    "/{symbol}/market-data-quality",
    response_model=MarketDataQualityResponse,
    responses={404: {"description": "Stock or candle data not found"}},
)
def get_market_data_quality(
    symbol: str,
    timeframe: MarketTimeframe = Query(
        default=MarketTimeframe.FIFTEEN_MINUTES
    ),
    lookback: int = Query(default=25, ge=21, le=250),
    db: Session = Depends(get_db),
):
    try:
        return MarketDataQualityService.get_quality_report(
            db=db,
            symbol=symbol,
            timeframe=timeframe,
            lookback=lookback,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.get(
    "/{symbol}/position-size",
    response_model=PositionSizeResponse,
    responses={
        404: {
            "description": "Stock or candle data not found"
        }
    },
)
def get_position_size(
    symbol: str,
    account_size: float = Query(
        ...,
        gt=0,
    ),
    risk_percent: float = Query(
        default=1.0,
        gt=0,
        le=5,
    ),
    db: Session = Depends(get_db),
):
    try:
        return RiskService.get_position_size(
            db=db,
            symbol=symbol,
            account_size=account_size,
            risk_percent=risk_percent,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

@router.get(
    "/{symbol}/signal-lifecycle",
    response_model=SignalLifecycleResponse,
    responses={404: {"description": "Signal lifecycle not initialized or stock not found"}},
)
def get_signal_lifecycle(
    symbol: str,
    timeframe: MarketTimeframe = Query(default=MarketTimeframe.FIFTEEN_MINUTES),
    db: Session = Depends(get_db),
):
    try:
        return SignalLifecycleService.get_current(db, symbol, timeframe)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get(
    "/{symbol}/signal-lifecycle/history",
    response_model=SignalLifecycleHistoryResponse,
    responses={404: {"description": "Stock not found"}},
)
def get_signal_lifecycle_history(
    symbol: str,
    timeframe: MarketTimeframe = Query(default=MarketTimeframe.FIFTEEN_MINUTES),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    try:
        return SignalLifecycleService.get_history(db, symbol, timeframe, limit)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get(
    "/{symbol}/position-lifecycle",
    response_model=PositionLifecycleResponse,
    responses={404: {"description": "Stock not found"}},
)
def get_position_lifecycle(
    symbol: str,
    timeframe: MarketTimeframe = Query(default=MarketTimeframe.FIFTEEN_MINUTES),
    db: Session = Depends(get_db),
):
    try:
        return PositionLifecycleService.get_current(db, symbol, timeframe)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post(
    "/{symbol}/position-lifecycle/monitor",
    response_model=PositionLifecycleResponse,
    responses={404: {"description": "Stock not found"}},
)
def monitor_position_lifecycle(
    symbol: str,
    timeframe: MarketTimeframe = Query(default=MarketTimeframe.FIFTEEN_MINUTES),
    db: Session = Depends(get_db),
):
    """Advance an existing real analytical position with newly stored completed candles.

    This endpoint is analysis-only: it never opens a position and never submits a broker order.
    """
    try:
        return PositionMonitoringService.monitor_existing(
            db, symbol, timeframe, trigger="MANUAL"
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get(
    "/{symbol}/position-lifecycle/history",
    response_model=PositionLifecycleHistoryResponse,
    responses={404: {"description": "Stock not found"}},
)
def get_position_lifecycle_history(
    symbol: str,
    timeframe: MarketTimeframe = Query(default=MarketTimeframe.FIFTEEN_MINUTES),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    try:
        return PositionLifecycleService.get_history(db, symbol, timeframe, limit)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get(
    "/{symbol}/position-lifecycle/analytics",
    response_model=PositionPnLAnalyticsResponse,
    responses={404: {"description": "Stock not found"}},
)
def get_position_pnl_analytics(
    symbol: str,
    timeframe: MarketTimeframe = Query(default=MarketTimeframe.FIFTEEN_MINUTES),
    db: Session = Depends(get_db),
):
    """#15E read-only per-share P&L, MFE/MAE, holding-time and exit analytics."""
    try:
        return PositionPnLAnalyticsService.for_persistent_position(db, symbol, timeframe)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get(
    "/{symbol}/position-lifecycle/persistent-test/{test_run_id}/analytics",
    response_model=PositionPnLAnalyticsResponse,
    responses={404: {"description": "Persistent test run not found"}},
)
def get_persistent_test_position_pnl_analytics(
    symbol: str,
    test_run_id: str,
    db: Session = Depends(get_db),
):
    """#15E isolated validation using an existing #15C/#15D test position."""
    try:
        return PositionPnLAnalyticsService.for_test_run(db, symbol, test_run_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post(
    "/{symbol}/position-lifecycle/simulate",
    response_model=PositionLifecycleSimulationResponse,
    responses={400: {"description": "Invalid simulation scenario"}},
)
def simulate_position_lifecycle(
    symbol: str,
    request: PositionLifecycleSimulationRequest,
):
    """Run a stateless post-entry lifecycle scenario.

    This endpoint does not write to the database and never calls a broker.
    """
    try:
        return PositionLifecycleSimulationService.simulate(symbol, request)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post(
    "/{symbol}/position-lifecycle/persistent-test/real-candle-monitor",
    response_model=PersistentRealCandleMonitorResponse,
    responses={400: {"description": "Invalid isolated real-candle monitoring scenario"}, 404: {"description": "Stock not found"}},
)
def start_real_candle_persistent_test(
    symbol: str,
    request: PersistentRealCandleMonitorStartRequest,
    db: Session = Depends(get_db),
):
    """#15D-3: create an isolated test position and consume real stored market candles."""
    try:
        return PositionLifecycleRealCandleTestService.start_and_monitor(db, symbol, request)
    except ValueError as exc:
        code = status.HTTP_404_NOT_FOUND if str(exc).startswith("Stock not found") else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=code, detail=str(exc)) from exc


@router.post(
    "/{symbol}/position-lifecycle/persistent-test/{test_run_id}/real-candle-monitor",
    response_model=PersistentRealCandleMonitorResponse,
    responses={404: {"description": "Persistent test run not found"}},
)
def remonitor_real_candle_persistent_test(
    symbol: str,
    test_run_id: str,
    db: Session = Depends(get_db),
):
    """#15D-4: re-run monitoring to prove eligible candles are never applied twice."""
    try:
        return PositionLifecycleRealCandleTestService.monitor_existing_test_run(
            db, symbol, test_run_id
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post(
    "/{symbol}/position-lifecycle/persistent-test",
    response_model=PersistentPositionTestResponse,
    responses={400: {"description": "Invalid controlled persistent test scenario"}, 404: {"description": "Stock not found"}},
)
def run_persistent_position_test(
    symbol: str,
    request: PersistentPositionTestRequest,
    db: Session = Depends(get_db),
):
    """Persist a controlled lifecycle scenario only in isolated test tables."""
    try:
        return PositionLifecyclePersistentTestService.run(db, symbol, request)
    except ValueError as exc:
        code = status.HTTP_404_NOT_FOUND if str(exc).startswith("Stock not found") else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=code, detail=str(exc)) from exc


@router.get(
    "/{symbol}/position-lifecycle/persistent-test/{test_run_id}",
    response_model=PersistentPositionTestResponse,
    responses={404: {"description": "Persistent test run not found"}},
)
def get_persistent_position_test(
    symbol: str,
    test_run_id: str,
    db: Session = Depends(get_db),
):
    try:
        result = PositionLifecyclePersistentTestService.get(db, test_run_id)
        if result["symbol"] != symbol.strip().upper():
            raise ValueError(f"Persistent test run not found: {test_run_id}")
        return result
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get(
    "/{symbol}/position-lifecycle/persistent-test/{test_run_id}/history",
    response_model=PersistentPositionTestHistoryResponse,
    responses={404: {"description": "Persistent test run not found"}},
)
def get_persistent_position_test_history(
    symbol: str,
    test_run_id: str,
    db: Session = Depends(get_db),
):
    try:
        result = PositionLifecyclePersistentTestService.history(db, test_run_id)
        if result["symbol"] != symbol.strip().upper():
            raise ValueError(f"Persistent test run not found: {test_run_id}")
        return result
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.delete(
    "/{symbol}/position-lifecycle/persistent-test/{test_run_id}",
    response_model=PersistentPositionTestDeleteResponse,
)
def delete_persistent_position_test(
    symbol: str,
    test_run_id: str,
    db: Session = Depends(get_db),
):
    try:
        return PositionLifecyclePersistentTestService.delete(db, symbol, test_run_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

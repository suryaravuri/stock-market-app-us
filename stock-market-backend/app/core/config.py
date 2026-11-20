from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL


class Settings(BaseSettings):

    # Application
    app_name: str = "Stock Market Application"
    app_version: str = "1.0.0"
    debug: bool = False

    # PostgreSQL
    database_host: str = "localhost"
    database_port: int = 5433
    database_name: str = "stockmarket"
    database_user: str = "stockuser"
    database_password: str

    # Google Cloud SQL
    cloud_sql_connection_name: str | None = None

    # Redis
    redis_host: str = "localhost"
    redis_port: int = 6379

    # Alpaca
    alpaca_api_key: str
    alpaca_secret_key: str
    alpaca_data_feed: str = "iex"

    # Authentication / JWT
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    # Trading
    trading_enabled: bool = False
    paper_trading_enabled: bool = False
    live_trading_enabled: bool = False
    auto_trading_enabled: bool = False

    # Shared secret Cloud Scheduler sends in the X-Job-Token header.
    # Leave unset to disable /api/v1/jobs/* entirely.
    job_trigger_token: str | None = None

    # Zerodha (Kite Connect) - REAL MONEY. Everything defaults to OFF/safe.
    kite_api_key: str | None = None
    kite_api_secret: str | None = None
    # Where the backend sends the browser after the Zerodha login callback.
    zerodha_post_login_redirect_url: str = "http://localhost:5173/"
    # Master switch for sending orders to Zerodha at all.
    zerodha_trading_enabled: bool = False
    # When true, orders pass every check and are recorded, but are NOT sent.
    zerodha_dry_run: bool = True
    # Comma-separated app-user emails allowed to place real Zerodha orders.
    zerodha_allowed_user_emails: str = ""
    # Per-order and per-day limits (INR / count), enforced per app user.
    zerodha_max_order_value_inr: float = 10000.0
    zerodha_max_orders_per_day: int = 10
    # Reject LIMIT prices further than this from the last traded price.
    zerodha_max_price_deviation_percent: float = 3.0

    # Risk controls
    account_size: float = 10000.0
    risk_percent: float = 1.0
    max_position_percent: float = 20.0

    # Entry types for automatic paper trades: BREAKOUT, SUPPORT_BOUNCE or BOTH.
    entry_mode: str = "BOTH"
    bounce_zone_atr: float = 0.5        # low must come within this many ATRs of support
    bounce_min_rr: float = 1.5          # reward to resistance / risk to stop
    bounce_min_trend_score: float = 0.0 # skip bounces when the trend score is bearish
    # Experimental (off until backtested): zone sized to the level timeframe's
    # ATR, and 2-candle confirmation (touch, then green close next candle).
    bounce_level_zone_atr: float = 0.0
    bounce_confirm_bars: int = 1

    # Live support-bounce entries from Alpaca 1-minute bars. The 15-minute
    # cycle prepares support/resistance/ATR per stock; the stream then checks
    # every LIVE_BOUNCE_BAR_MINUTES-minute candle built from 1-minute bars, so
    # a bounce is bought within minutes instead of up to 15 minutes later.
    live_bounce_enabled: bool = False
    live_bounce_bar_minutes: int = 5
    # Alpaca's free plan limits the live 1-minute stream; the most important
    # symbols (trading enabled, highest priority) are streamed first.
    live_stream_max_symbols: int = 30
    # Re-check the live price just before any support-bounce order: skip if
    # price is already back at support, otherwise re-price stop and RR.
    live_price_check_enabled: bool = True
    # 1 = never re-enter a stock on the same (exchange-local) day after an
    # automatic entry, e.g. after being stopped out. 0 = no limit.
    max_auto_entries_per_symbol_per_day: int = 1

    # Market-mood filter: no new buys while the broad market is falling.
    # Blocks when any symbol in MARKET_FILTER_SYMBOLS is down more than
    # MAX_DAY_DROP_PCT vs yesterday's close, or more than
    # MAX_FROM_OPEN_DROP_PCT below today's open.
    market_filter_enabled: bool = True
    market_filter_symbols: str = "SPY,QQQ"
    market_filter_max_day_drop_pct: float = 1.0
    market_filter_max_from_open_drop_pct: float = 0.6
    # At most this many open positions (incl. pending buys) per sector. 0 = off.
    max_open_positions_per_sector: int = 2

    # Holdings Guard (holdings_guard_service.py): trailing stop on part of
    # each listed holding, buy back at support. Alpaca paper only.
    holdings_guard_enabled: bool = False
    holdings_guard_symbols: str = ""          # e.g. "WMT,AMD"
    holdings_guard_trade_pct: float = 40.0    # part that may be sold; rest is core
    holdings_guard_trail_pct: float = 0.0     # 0 = auto from daily ATR (4-12%)
    holdings_guard_rebuy_above_pct: float = 1.0
    holdings_guard_rebuy_max_days: int = 10
    # Market trend: WEAK when SPY closes below its 200-day average.
    holdings_guard_regime_symbol: str = "SPY"
    holdings_guard_weak_trail_factor: float = 0.75   # tighter trail in a weak market
    holdings_guard_weak_rebuy_above_pct: float = 3.0 # recovery needed to buy back when WEAK
    # Intraday spike lock: if a holding rises this % above today's open,
    # tighten its trailing stop to SPIKE_TRAIL_PCT for the rest of the day.
    holdings_guard_spike_pct: float = 4.0
    holdings_guard_spike_trail_pct: float = 3.0

    # Pre-breakout risk/reward model: ATR_FLOOR (default) or LEGACY.
    risk_model: str = "ATR_FLOOR"
    risk_min_stop_atr: float = 1.0      # stop at least this many ATRs below entry
    risk_target_1_atr: float = 2.0      # projected targets when no resistance above
    risk_target_2_atr: float = 3.0

    # Paper order exits. These were referenced by paper_trading_service.py and
    # trailing_stop_service.py but never defined, so every paper order raised
    # AttributeError just before it reached Alpaca.
    paper_use_bracket_orders: bool = True
    default_stop_loss_percent: float = 5.0     # used when the setup has no valid stop
    default_take_profit_percent: float = 20.0  # used when the setup has no valid target

    # Profit protection (trailing stop)
    trailing_stop_enabled: bool = True
    trailing_stop_percent: float = 5.0         # trail distance below price
    trailing_activation_percent: float = 5.0   # start trailing after +5%
    trailing_breakeven_percent: float = 10.0   # never below entry after +10%
    trailing_min_step_percent: float = 0.25

    # Holding style (intraday / weekly / monthly) exits
    time_exit_buffer_minutes: int = 15        # close positions this long before the close
    intraday_entry_cutoff_minutes: int = 45   # no new INTRADAY entries this close to the close

    # In-process scheduler for running the trading cycle on a laptop/server
    # without Cloud Scheduler. Only enable in ONE running backend process.
    local_scheduler_enabled: bool = False
    local_scheduler_interval_minutes: int = 15

    # Live early-breakout alerts from Alpaca 1-minute bars (alerts only, no orders)
    early_alerts_enabled: bool = False
    early_alert_min_elapsed_minutes: int = 5

    # TradingView webhook alerts: put this secret in the alert's JSON message.
    # Leave unset to disable the webhook endpoint.
    tradingview_webhook_secret: str | None = None

    # Upstox OAuth callback (must match the Upstox developer console exactly)
    upstox_redirect_uri: str | None = None

    # Backtesting: separate database on the same Postgres server, so replaying
    # history never touches live signal/position tables.
    backtest_database_name: str = "stockmarket_backtest"
    # Alpaca feed for historical bars: "sip" (all exchanges) or "iex".
    backtest_data_feed: str = "sip"
    # Optional: Cloud Run Job that executes backtests ("" = run locally via CLI).
    backtest_job_name: str = ""
    gcp_project_id: str = ""
    gcp_region: str = "us-central1"

    broker_encryption_key: str
    legacy_jwt_key_fallback: bool = True

    @property
    def database_url(self) -> str:
        # Cloud Run + Cloud SQL Unix socket
        if self.cloud_sql_connection_name:
            return URL.create(
                drivername="postgresql+psycopg",
                username=self.database_user,
                password=self.database_password,
                database=self.database_name,
                query={
                    "host": f"/cloudsql/{self.cloud_sql_connection_name}"
                },
            ).render_as_string(hide_password=False)

        # Local development
        return URL.create(
            drivername="postgresql+psycopg",
            username=self.database_user,
            password=self.database_password,
            host=self.database_host,
            port=self.database_port,
            database=self.database_name,
        ).render_as_string(hide_password=False)

    @property
    def backtest_database_url(self) -> str:
        """Same server and credentials as the app database, different database."""
        if self.cloud_sql_connection_name:
            return URL.create(
                drivername="postgresql+psycopg",
                username=self.database_user,
                password=self.database_password,
                database=self.backtest_database_name,
                query={"host": f"/cloudsql/{self.cloud_sql_connection_name}"},
            ).render_as_string(hide_password=False)
        return URL.create(
            drivername="postgresql+psycopg",
            username=self.database_user,
            password=self.database_password,
            host=self.database_host,
            port=self.database_port,
            database=self.backtest_database_name,
        ).render_as_string(hide_password=False)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


def zerodha_allowed_emails(value: str) -> set[str]:
    return {item.strip().lower() for item in value.split(",") if item.strip()}


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
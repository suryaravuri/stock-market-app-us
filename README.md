# Stock Decision Engine — US (Alpaca paper trading)

FastAPI backend + React dashboard + PostgreSQL. Every 15 minutes during US
market hours the bot syncs candles from Alpaca, scans the watchlists
(support-bounce and breakout rules), places **paper** bracket orders, and
manages exits. A 1-minute stream adds faster live bounce entries.

> Paper trading only. `LIVE_TRADING_ENABLED` must stay `false`.
>
> US market only (`APP_MARKET=US`). The India app lives in the separate
> `stock-market-app-india` repository with its own database.

## Layout
| Folder | What |
|---|---|
| `stock-market-backend/` | FastAPI app (`app.main:app`), Alembic migrations, tests |
| `stock-market-ui/` | React + MUI dashboard (Vite) |
| `docker-compose.yml` | PostgreSQL (`stock-postgres`, port 5433) and Redis |

## First-time setup (Windows, PowerShell)
```powershell
docker compose up -d                      # database
cd stock-market-backend
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
copy .env.example .env                    # then fill in keys
.\.venv\Scripts\alembic upgrade head
cd ..\stock-market-ui
npm install
```

## Run
```powershell
# backend (from stock-market-backend)
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
# dashboard (from stock-market-ui)
npm run dev
```
Startup log must show `Logging configured`, `Local scheduler started` and
`1-minute stream started ...`.

## Update to the latest version
```powershell
git pull
cd stock-market-backend; .\.venv\Scripts\alembic upgrade head
# restart the backend (Ctrl+C, start again)
```

## Daily checks
```powershell
cd stock-market-backend
$job = ((Select-String -Path .env -Pattern "^JOB_TRIGGER_TOKEN=").Line -split "=", 2)[1].Trim()
# every gate an order must pass, PASS/WARN/FAIL
Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/v1/diagnostics/trading-readiness" -Headers @{ "X-Job-Token" = $job } | ConvertTo-Json -Depth 5
# did cycles run?
Select-String -Path logs\trading.log -Pattern "Local scheduler cycle" | Select-Object -Last 3
```
- `logs/trading.log` — readable log: one BUY/SKIP line per stock per cycle
- `logs/decisions.jsonl` — the same decisions as JSON (Bot Health page)
- `logs/holdings_guard_state.json` — Holdings Guard state

## Phone alerts (Telegram)
1. In Telegram, message **@BotFather** -> `/newbot` -> copy the token.
2. Send "hi" to your new bot.
3. Put `TELEGRAM_BOT_TOKEN=...` in `.env`, then run
   `.\.venv\Scripts\python.exe -m app.scripts.telegram_chat_id` and add the
   printed `TELEGRAM_CHAT_ID=...` line to `.env`. Restart the backend.
4. Test: `Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/api/v1/diagnostics/test-alert" -Headers @{ "X-Job-Token" = $job }`

You get: BUY / SELL (with P&L) / Holdings Guard messages, a warning if a
cycle crashes or no cycle succeeds for 35 min, "Bot ready" at 9:20 AM ET
(if it doesn't arrive, the bot isn't running) and a 4:25 PM ET summary.

## Tests
```powershell
cd stock-market-backend
.\.venv\Scripts\python.exe -m pytest -q
```

## Safety rules
- Never commit `.env` (it is in `.gitignore`).
- New features ship **off** and are switched on only after a backtest
  (`python -m app.backtest.compare_bounce`) or a paper-trading trial.

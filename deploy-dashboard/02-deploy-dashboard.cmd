@echo off
setlocal
cd /d "%~dp0.."
call gcloud run services update stock-market-backend --project=commanding-pier-324218 --region=us-central1 --image=us-central1-docker.pkg.dev/commanding-pier-324218/stock-app/backend:dashboard-v5-20260927-dbfix --update-env-vars=TRADING_ENABLED=false,PAPER_TRADING_ENABLED=false,LIVE_TRADING_ENABLED=false,AUTO_TRADING_ENABLED=false
if errorlevel 1 exit /b 1
echo DASHBOARD DEPLOYED. Open http://127.0.0.1:8080/ while the existing proxy is running.

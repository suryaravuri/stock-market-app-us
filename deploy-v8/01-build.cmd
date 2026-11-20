@echo off
setlocal
cd /d "%~dp0.."
if not exist stock-market-backend\app\services\zerodha_statistics_service.py (
  echo ERROR: Apply the latest code zip first ^(Zerodha + Trades P^&L missing^).
  exit /b 1
)
call gcloud builds submit . --config=cloudbuild.dashboard.yaml --ignore-file=dashboard.gcloudignore --project=commanding-pier-324218
if errorlevel 1 exit /b 1
echo BUILD SUCCEEDED: us-central1-docker.pkg.dev/commanding-pier-324218/stock-app/backend:dashboard-v8-20261102-kitefix
echo Next: deploy-v8\02-migrate.cmd

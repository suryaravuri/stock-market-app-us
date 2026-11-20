@echo off
setlocal
cd /d "%~dp0.."
if not exist stock-market-backend\app\core\database.py (
  echo ERROR: Extract this overlay into the existing folder containing BOTH stock-market-backend and stock-market-ui.
  exit /b 1
)
if not exist stock-market-ui\src\App.tsx (
  echo ERROR: Complete React source is missing. This package contains deployment changes only.
  exit /b 1
)
call gcloud builds submit . --config=cloudbuild.dashboard.yaml --ignore-file=dashboard.gcloudignore --project=commanding-pier-324218
if errorlevel 1 exit /b 1
echo DASHBOARD BUILD SUCCEEDED. Run deploy-dashboard\02-deploy-dashboard.cmd next.

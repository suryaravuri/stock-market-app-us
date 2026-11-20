@echo off
setlocal
cd /d "%~dp0.."
call gcloud artifacts repositories describe stock-app --location=us-central1 --project=commanding-pier-324218 >nul 2>&1
if errorlevel 1 (
  call gcloud artifacts repositories create stock-app --repository-format=docker --location=us-central1 --project=commanding-pier-324218
  if errorlevel 1 exit /b 1
)
call gcloud builds submit . --tag=us-central1-docker.pkg.dev/commanding-pier-324218/stock-app/backend:cloud-v1 --project=commanding-pier-324218
if errorlevel 1 exit /b 1
echo BUILD SUCCEEDED. Next run deploy\02-migrate.cmd.

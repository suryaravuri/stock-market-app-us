@echo off
setlocal
cd /d "%~dp0.."
call gcloud run services proxy stock-market-backend --project=commanding-pier-324218 --region=us-central1 --port=8080

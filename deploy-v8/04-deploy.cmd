@echo off
setlocal
call gcloud run services update stock-market-backend --region=us-central1 --project=commanding-pier-324218 ^
  --image=us-central1-docker.pkg.dev/commanding-pier-324218/stock-app/backend:dashboard-v8-20261102-kitefix ^
  --update-secrets=KITE_API_KEY=stock-kite-api-key:latest,KITE_API_SECRET=stock-kite-api-secret:latest ^
  --update-env-vars=ZERODHA_TRADING_ENABLED=true,ZERODHA_DRY_RUN=true,ZERODHA_ALLOWED_USER_EMAILS=suryaravuri9@gmail.com,ZERODHA_POST_LOGIN_REDIRECT_URL=https://stock-market-backend-331449731828.us-central1.run.app/
if errorlevel 1 exit /b 1
echo DEPLOYED. Open https://stock-market-backend-331449731828.us-central1.run.app/health/database

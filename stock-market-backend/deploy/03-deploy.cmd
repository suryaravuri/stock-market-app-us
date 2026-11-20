@echo off
setlocal
cd /d "%~dp0.."
call gcloud run deploy stock-market-backend --project=commanding-pier-324218 --region=us-central1 --image=us-central1-docker.pkg.dev/commanding-pier-324218/stock-app/backend:cloud-v1 --service-account=stock-backend@commanding-pier-324218.iam.gserviceaccount.com --set-cloudsql-instances=commanding-pier-324218:us-central1:stock-market-db --set-env-vars="CLOUD_SQL_CONNECTION_NAME=commanding-pier-324218:us-central1:stock-market-db,DATABASE_NAME=stockmarket,DATABASE_USER=stockuser,DEBUG=false,TRADING_ENABLED=false,PAPER_TRADING_ENABLED=false,LIVE_TRADING_ENABLED=false,AUTO_TRADING_ENABLED=false,ALPACA_DATA_FEED=iex" --set-secrets="DATABASE_PASSWORD=stock-db-password:1,ALPACA_API_KEY=stock-alpaca-api-key:2,ALPACA_SECRET_KEY=stock-alpaca-secret-key:2,JWT_SECRET_KEY=stock-jwt-secret-key:1" --no-allow-unauthenticated --execution-environment=gen2 --port=8080 --cpu=1 --memory=512Mi --min-instances=0 --max-instances=1 --concurrency=8 --timeout=300s
if errorlevel 1 exit /b 1
echo DEPLOY SUCCEEDED. Run deploy\04-proxy.cmd and open http://127.0.0.1:8080/health/database


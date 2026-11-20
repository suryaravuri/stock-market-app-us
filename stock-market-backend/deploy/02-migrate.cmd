@echo off
setlocal
cd /d "%~dp0.."
call gcloud run jobs deploy stock-db-migrate --project=commanding-pier-324218 --region=us-central1 --image=us-central1-docker.pkg.dev/commanding-pier-324218/stock-app/backend:cloud-v1 --service-account=stock-backend@commanding-pier-324218.iam.gserviceaccount.com --set-cloudsql-instances=commanding-pier-324218:us-central1:stock-market-db --set-env-vars="CLOUD_SQL_CONNECTION_NAME=commanding-pier-324218:us-central1:stock-market-db,DATABASE_NAME=stockmarket,DATABASE_USER=stockuser,DEBUG=false,TRADING_ENABLED=false,PAPER_TRADING_ENABLED=false,LIVE_TRADING_ENABLED=false,AUTO_TRADING_ENABLED=false,ALPACA_DATA_FEED=iex" --set-secrets="DATABASE_PASSWORD=stock-db-password:1,ALPACA_API_KEY=stock-alpaca-api-key:2,ALPACA_SECRET_KEY=stock-alpaca-secret-key:2,JWT_SECRET_KEY=stock-jwt-secret-key:1" --command=alembic --args=upgrade,head --tasks=1 --parallelism=1 --max-retries=0 --task-timeout=600s --cpu=1 --memory=512Mi
if errorlevel 1 exit /b 1
call gcloud run jobs execute stock-db-migrate --project=commanding-pier-324218 --region=us-central1 --wait
if errorlevel 1 exit /b 1
echo MIGRATION SUCCEEDED. Next run deploy\03-deploy.cmd.


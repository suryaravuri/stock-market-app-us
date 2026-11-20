@echo off
setlocal
echo Pointing the migration job at the new image...
call gcloud run jobs update stock-db-migrate --image=us-central1-docker.pkg.dev/commanding-pier-324218/stock-app/backend:dashboard-v8-20261102-zerodha --region=us-central1 --project=commanding-pier-324218
if errorlevel 1 exit /b 1
echo Running alembic upgrade head on Cloud SQL...
call gcloud run jobs execute stock-db-migrate --region=us-central1 --project=commanding-pier-324218 --wait
if errorlevel 1 exit /b 1
echo MIGRATION SUCCEEDED. Next: create the two Kite secrets, then deploy-v8\03-grant-secrets.cmd

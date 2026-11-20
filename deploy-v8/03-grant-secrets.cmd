@echo off
setlocal
for /f "delims=" %%A in ('gcloud run services describe stock-market-backend --region=us-central1 --project=commanding-pier-324218 --format^="value(spec.template.spec.serviceAccountName)"') do set SA=%%A
if "%SA%"=="" (
  echo ERROR: could not read the service account of stock-market-backend
  exit /b 1
)
echo Service account: %SA%
for %%S in (stock-kite-api-key stock-kite-api-secret) do (
  call gcloud secrets add-iam-policy-binding %%S --member=serviceAccount:%SA% --role=roles/secretmanager.secretAccessor --project=commanding-pier-324218 --condition=None
  if errorlevel 1 exit /b 1
)
echo SECRET ACCESS GRANTED. Next: deploy-v8\04-deploy.cmd

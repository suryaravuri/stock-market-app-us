# Deploy the existing React dashboard to Google Cloud

This ZIP contains changes only, NOT a complete application. Extract into your
working deployment checkout's directory containing BOTH stock-market-backend
and stock-market-ui. Do not extract into an empty directory or the backend itself.

Your current Windows directory:
C:\dev\stock-market-app\stock-market-cloud\stock-market-app

Back up stock-market-ui/package.json, package-lock.json and src/api/client.ts
before replacing them. If you have newer local edits, merge the changes.

From Git Bash, starting in your working stock-market-backend folder:

    cd ..
    ls stock-market-backend/app/core/database.py stock-market-ui/src/App.tsx
    cmd.exe //c 'deploy-dashboard\01-build-dashboard.cmd'

After DASHBOARD BUILD SUCCEEDED:

    cmd.exe //c 'deploy-dashboard\02-deploy-dashboard.cmd'

Keep the previous backend proxy running. Open http://127.0.0.1:8080/ for the
React app. If you need to restart the proxy from this parent directory:

    cmd.exe //c 'stock-market-backend\deploy\04-proxy.cmd'

Check /health and /health/database for status UP, then dashboard navigation,
watchlist data and AMD analysis. Empty recommendations can reflect the current
small dataset; intraday/daily/hourly history and active validation runs still
need configuration. This deployment does not seed records or schedule scans.

The dashboard and API share the existing private Cloud Run service and origin.
The public Cloud Run URL still requires authentication; this phase uses your
existing local proxy for browser access, not direct Google sign-in. A browser
login/IAP configuration remains separate work if you need access without a proxy.
No API keys are embedded in frontend assets. Secrets, service account, Cloud SQL
connection and access policy are retained by the service update. Trading flags
are explicitly kept false. No new database migrations are needed.

Changes: production API URL becomes /api/v1; local Vite dev keeps localhost:8000.
The Windows-only explicit build dependency is removed and the npm lock updated.
cloud_main serves the compiled UI after registering API routes and supports direct
navigation to every existing React route. It fails startup if UI assets are absent.
The separate multi-stage Dockerfile uses Node 24 for compilation and Python 3.12
for serving. The upload allowlist excludes environments, caches and node_modules.

Validation: npm ci and production TypeScript/Vite build succeeded on Linux.
HTTP checks cover all seven frontend routes, JS/CSS assets, health, Swagger and
unknown API 404 behavior. Cloud Build and actual cloud UI/API checks remain to run.

Rollback: Cloud Run console > stock-market-backend > Revisions > route traffic to
the prior healthy revision. Keep the prior cloud-v1 image available. No data changes
are made by the build or deployment scripts.

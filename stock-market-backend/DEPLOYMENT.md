# Stock app backend deployment

Prepared against Git commit 573db8611bfbc697e77536d23bf8252fc306b083.
Apply these files to the stock-market-backend directory, preserving the paths.
Back up app/core/config.py and alembic/env.py before replacing them; merge changes
if your local copies have newer edits. This is an overlay, not the full backend.
The original requirements.txt is untouched; Docker uses requirements-cloud.txt.

Run from Windows Command Prompt in the backend directory, in order:

1. deploy\01-build.cmd
2. deploy\02-migrate.cmd (only after a successful build)
3. deploy\03-deploy.cmd (only after successful migration)
4. deploy\04-proxy.cmd (keep terminal open)

The build creates the stock-app Artifact Registry repository if absent and builds
an image with Cloud Build. Build, storage and Cloud Run usage can incur charges.
The migration job upgrades the existing stockmarket database; it creates tables,
not a copy of your local data. It also adds position_state.quantity because the
previous migration is empty. Existing manually added quantity values are preserved.
Downgrade intentionally retains that column and its data.

Prerequisites already configured: PostgreSQL 17 stock-market-db in us-central1,
stockmarket database, stockuser with its saved password, stock-backend service
account with Cloud SQL Client and access to the three named secrets.
Commands use secret version 1; if you corrected a secret, update the version in
02-migrate.cmd and 03-deploy.cmd to its correct enabled version before running.
No secret values belong in these files or screenshots.

The service is private (requires IAM authentication). The local proxy uses your
gcloud identity. Open http://127.0.0.1:8080/health, /health/database and /docs.
The existing database health endpoint returns HTTP 200 even on failure, so verify
that the JSON status is UP. Validate market data through Swagger after seeding
stocks and watchlists. All four trading switches are explicitly false.

This phase deploys only the backend. The UI, scheduled market scans, data transfer
and end-to-end market validation remain to be configured. No Redis client imports
were found in the current backend, so this deployment does not provision Redis.
The default local CORS settings remain suitable for the local UI; hosted UI CORS
and authentication must be configured when deploying the frontend.

Validation completed: 88 existing tests passed with the pinned Linux dependencies;
app import, OpenAPI and health checks; Cloud SQL socket and password URL encoding;
all 11 migrations generated offline SQL successfully. Docker and a live PostgreSQL
server were unavailable here, so Cloud Build and the migration job are the remaining
live validation gates. No cloud resources were changed by the preparation step.

The runtime runs as a non-root user and copies only application and migration files.
Build upload allowlists exclude local environments and unrelated files.
Sources: https://docs.cloud.google.com/sdk/gcloud/reference/run/jobs/deploy
https://docs.cloud.google.com/sql/docs/postgres/connect-run
https://docs.sqlalchemy.org/en/20/core/engines.html

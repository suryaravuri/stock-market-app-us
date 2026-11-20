"""Cloud entry point serving the existing API and compiled React dashboard."""
import os
from pathlib import Path
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from app.main import app

ui_dir = Path(os.environ.get("UI_DIST_DIR", "/app/ui"))
if not (ui_dir / "index.html").is_file():
    raise RuntimeError("Dashboard build missing: expected UI_DIST_DIR/index.html")

async def dashboard():
    return FileResponse(ui_dir / "index.html", headers={"Cache-Control": "no-cache"})

# Preserve BrowserRouter links and direct navigation without masking API errors.
for route in (
    "/",
    "/login",
    "/change-password",
    "/user-enrollment",
    "/analysis",
    "/signals",
    "/risk",
    "/market-data",
    "/validation",
    "/watchlist",
    "/stock-master",
    "/trades",
    "/backtests",
    "/options",
    "/futures",
    "/diagnostics",
):
    app.add_api_route(route, dashboard, methods=["GET"], include_in_schema=False)
app.mount("/", StaticFiles(directory=ui_dir), name="dashboard-assets")

from fastapi import FastAPI

from app.api.v1.market import router as market_router

app = FastAPI(
    title="Stock Market Trading API",
    version="1.0.0"
)

app.include_router(
    market_router,
    prefix="/api/v1",
)

@app.get("/health")
async def health():
    return {
        "status": "UP",
        "application": "stock-market-backend"
    }


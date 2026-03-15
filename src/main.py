import logging
from fastapi import FastAPI

from src.api.routes import router
from src.utils.rate_limiter import RateLimiter

logging.basicConfig(level=logging.INFO)

app = FastAPI(
    title="Takaada Integration Service",
    description="Syncs external accounting data and exposes financial insights",
    version="0.1.0",
)

app.add_middleware(RateLimiter, requests_per_minute=60)
app.include_router(router)


@app.get("/health")
def health_check():
    return {"status": "ok"}

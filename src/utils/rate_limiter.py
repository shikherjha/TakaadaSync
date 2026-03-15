import time
import redis
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware

from src.config import REDIS_URL


class RateLimiter(BaseHTTPMiddleware):
    """Simple sliding window rate limiter using Redis."""

    def __init__(self, app, requests_per_minute: int = 60):
        super().__init__(app)
        self.rpm = requests_per_minute
        self.redis = redis.from_url(REDIS_URL)

    async def dispatch(self, request: Request, call_next):
        client_ip = request.client.host
        key = f"ratelimit:{client_ip}"
        now = time.time()
        window = 60

        pipe = self.redis.pipeline()
        pipe.zremrangebyscore(key, 0, now - window)
        pipe.zadd(key, {str(now): now})
        pipe.zcard(key)
        pipe.expire(key, window)
        results = pipe.execute()

        request_count = results[2]
        if request_count > self.rpm:
            raise HTTPException(status_code=429, detail="Rate limit exceeded")

        return await call_next(request)

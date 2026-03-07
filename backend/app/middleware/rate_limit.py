"""
Rate limiting middleware using a simple in-memory token bucket.

For production, replace with Redis-backed limiter (e.g. slowapi / fastapi-limiter).
"""

import time
from collections import defaultdict
from typing import Dict, Tuple

from fastapi import Request, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from app.middleware.error_handler import error_response


class _TokenBucket:
    """Simple token-bucket rate limiter per key."""

    def __init__(self, rate: float, capacity: int):
        self.rate = rate            # tokens per second
        self.capacity = capacity    # max burst
        self._buckets: Dict[str, Tuple[float, float]] = {}  # key → (tokens, last_time)

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        tokens, last = self._buckets.get(key, (self.capacity, now))
        elapsed = now - last
        tokens = min(self.capacity, tokens + elapsed * self.rate)
        if tokens >= 1:
            self._buckets[key] = (tokens - 1, now)
            return True
        self._buckets[key] = (tokens, now)
        return False


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Per-IP rate limiting middleware.

    Defaults: 100 requests per minute per IP.
    Override via constructor args.
    """

    # Paths exempt from rate limiting
    EXEMPT_PATHS = {"/health", "/docs", "/redoc", "/openapi.json"}

    def __init__(self, app, requests_per_minute: int = 100):
        super().__init__(app)
        rate = requests_per_minute / 60.0  # tokens per second
        self._bucket = _TokenBucket(rate=rate, capacity=requests_per_minute)

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        if request.url.path in self.EXEMPT_PATHS:
            return await call_next(request)

        # Use forwarded-for header if behind a proxy, otherwise client host
        client_ip = request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
        if not client_ip:
            client_ip = request.client.host if request.client else "unknown"

        if not self._bucket.allow(client_ip):
            request_id = getattr(request.state, "request_id", None)
            return error_response(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                error="RateLimitExceeded",
                message="Too many requests. Please slow down.",
                request_id=request_id,
            )

        return await call_next(request)

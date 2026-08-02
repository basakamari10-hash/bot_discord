import time
import asyncio
from config import CONFIG

class RateLimiter:
    def __init__(self, cooldown: float = 3.0, max_concurrent: int = 5):
        self.cooldown = cooldown
        self.user_last_request: dict[int, float] = {}
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self._lock = asyncio.Lock()

    async def is_rate_limited(self, user_id: int) -> tuple[bool, float]:
        async with self._lock:
            now = time.time()
            elapsed = now - self.user_last_request.get(user_id, 0.0)
            
            if elapsed < self.cooldown:
                return True, self.cooldown - elapsed
            
            self.user_last_request[user_id] = now
            return False, 0.0

GLOBAL_RATE_LIMITER = RateLimiter(
    cooldown=CONFIG.USER_COOLDOWN_SECONDS,
    max_concurrent=CONFIG.CONCURRENT_REQUESTS_LIMIT
)

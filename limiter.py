import time
import asyncio
from typing import Dict, Tuple

class RateLimiter:
    """Per-user cooldown and concurrent execution concurrency manager."""
    def __init__(self, cooldown: float = 3.0, max_concurrent: int = 5):
        self.cooldown = cooldown
        self.user_last_request: Dict[int, float] = {}
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self._lock = asyncio.Lock()

    async def is_rate_limited(self, user_id: int) -> Tuple[bool, float]:
        async with self._lock:
            now = time.time()
            last = self.user_last_request.get(user_id, 0.0)
            elapsed = now - last
            if elapsed < self.cooldown:
                return True, self.cooldown - elapsed
            self.user_last_request[user_id] = now
            return False, 0.0

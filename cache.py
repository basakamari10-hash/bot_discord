import time
import asyncio
from typing import Dict, Tuple, Any, Optional

class TTLCache:
    """Thread-safe and async-friendly in-memory TTL Cache."""
    def __init__(self, default_ttl: int = 3600):
        self._cache: Dict[str, Tuple[Any, float]] = {}
        self._default_ttl = default_ttl
        self._lock = asyncio.Lock()

    async def get(self, key: str) -> Optional[Any]:
        async with self._lock:
            if key not in self._cache:
                return None
            val, expiry = self._cache[key]
            if time.time() > expiry:
                del self._cache[key]
                return None
            return val

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        async with self._lock:
            expiration = time.time() + (ttl if ttl is not None else self._default_ttl)
            self._cache[key] = (value, expiration)

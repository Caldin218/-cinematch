import hashlib
from fastapi import Depends, Request
from redis.asyncio import Redis
from redis.exceptions import RedisError
from app.core.errors import ApplicationError
from app.core.runtime import get_redis

# Atomic counter+TTL avoids keys that survive forever after process interruption.
SCRIPT = "local n=redis.call('INCR',KEYS[1]); if n==1 then redis.call('EXPIRE',KEYS[1],ARGV[1]) end; return n"

class AuthLimiter:
    def __init__(self, redis: Redis, ip: str) -> None:
        self.redis, self.ip = redis, ip

    async def check(self, action: str, email: str = "") -> None:
        identities = ["ip:" + self.ip]
        if email:
            identities.append("account:" + email)
        limit, seconds = (3, 3600) if action == "register" else (5, 60) if action == "login" else (30, 60)
        try:
            for identity in identities:
                key = "cinematch:auth:" + action + ":" + hashlib.sha256(identity.encode()).hexdigest()
                count = await self.redis.eval(SCRIPT, 1, key, seconds)
                if int(count) > limit:
                    raise ApplicationError("rate_limited", "Too many attempts; try again later", 429)
        except RedisError:
            raise ApplicationError("auth_unavailable", "Authentication temporarily unavailable", 503) from None

def get_limiter(request: Request, redis: Redis = Depends(get_redis)) -> AuthLimiter:
    # Ignore caller-supplied forwarding headers; trusted proxy support is explicit future configuration.
    return AuthLimiter(redis, request.client.host if request.client else "unknown")

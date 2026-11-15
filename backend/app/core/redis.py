from redis import Redis

from app.core.config import Settings


def create_redis_client(settings: Settings) -> Redis:
    return Redis.from_url(
        settings.redis_url.get_secret_value(), decode_responses=True,
        socket_connect_timeout=3, socket_timeout=3,
    )


def check_redis(client: Redis) -> None:
    if not client.ping():
        raise ConnectionError("Redis ping failed")

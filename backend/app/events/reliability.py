"""Consumer retry state and ownership-checked Redis operations (Redis 7+)."""
from dataclasses import dataclass


@dataclass(frozen=True)
class RetryPolicy:
    max_retries: int = 5
    base_seconds: float = 2
    max_seconds: float = 300

    def __post_init__(self):
        if self.max_retries < 0 or self.base_seconds <= 0 or self.max_seconds < self.base_seconds:
            raise ValueError("Invalid retry policy")

    def delay(self, failures: int) -> float:
        return min(self.max_seconds, self.base_seconds * 2 ** min(max(failures - 1, 0), 30))


# Every mutation checks current PEL ownership. A stale consumer cannot ACK or
# quarantine work now owned by another process. Keys share one standalone Redis.
OWNED = """
local p = redis.call('XPENDING', KEYS[1], ARGV[1], ARGV[2], ARGV[2], 1)
if #p == 0 or p[1][2] ~= ARGV[3] then return 0 end
"""
HEARTBEAT = OWNED + """
redis.call('XCLAIM', KEYS[1], ARGV[1], ARGV[3], 0, ARGV[2], 'JUSTID')
return 1
"""
ACK = OWNED + """
redis.call('XACK', KEYS[1], ARGV[1], ARGV[2])
redis.call('DEL', KEYS[2])
return 1
"""
RETRY = OWNED + """
redis.call('HSET', KEYS[2], 'failures', ARGV[4], 'due', ARGV[5], 'infrastructure_failures', ARGV[6])
return 1
"""
DEAD = OWNED + """
redis.call('XADD', KEYS[3], '*', 'source_stream', KEYS[1],
    'source_group', ARGV[1], 'source_id', ARGV[2], 'consumer', ARGV[3],
    'reason', ARGV[4], 'failures', ARGV[5], 'fields', ARGV[6])
redis.call('XACK', KEYS[1], ARGV[1], ARGV[2])
redis.call('DEL', KEYS[2])
return 1
"""

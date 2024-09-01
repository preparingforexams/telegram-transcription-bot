import logging
from datetime import timezone

from rate_limiter import RateLimiter
from rate_limiter.policy import DailyLimitRateLimitingPolicy
from rate_limiter.repo import PostgresRateLimitingRepo

from bot.config import DatabaseConfig

_LOG = logging.getLogger(__name__)


class UsageTracker:
    def __init__(self, config: DatabaseConfig) -> None:
        self._rate_limiter = RateLimiter(
            policy=DailyLimitRateLimitingPolicy(limit=100),
            repo=PostgresRateLimitingRepo.connect(
                host=config.db_host,
                database=config.db_name,
                username=config.db_user,
                password=config.db_password,
                min_connections=1,
                max_connections=4,
            ),
            timezone=timezone.utc,
        )

    def close(self) -> None:
        self._rate_limiter.close()

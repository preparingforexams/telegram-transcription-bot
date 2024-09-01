import asyncio
import logging
from datetime import datetime, timezone

from rate_limiter import RateLimiter, Usage
from rate_limiter.policy import DailyLimitRateLimitingPolicy
from rate_limiter.repo import PostgresRateLimitingRepo
from telegram import Message

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

    async def get_conflict(self, user_id: int, at_time: datetime) -> Usage | None:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None,
            lambda: self._rate_limiter.get_offending_usage(
                context_id="",
                user_id=user_id,
                at_time=at_time,
            ),
        )

    async def track(
        self,
        request: Message,
        *,
        unique_file_id: str,
        response_id: int | None,
    ) -> None:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(
            None,
            lambda: self._rate_limiter.add_usage(
                time=request.date,
                context_id="",
                user_id=request.from_user.id,  # type: ignore[union-attr]
                response_id=str(response_id),
                reference_id=unique_file_id,
            ),
        )

    def close(self) -> None:
        self._rate_limiter.close()

import asyncio
import logging
from datetime import datetime, timezone

from rate_limiter import RateLimiter, RateLimitingPolicy, Usage
from rate_limiter.policy import DailyLimitRateLimitingPolicy
from rate_limiter.repo import PostgresRateLimitingRepo
from telegram import Message

from bot.config import DatabaseConfig, RateLimitConfig

_LOG = logging.getLogger(__name__)


class _UseOncePolicy(RateLimitingPolicy):
    def __init__(self) -> None:
        pass

    @property
    def requested_history(self) -> int:
        return 1

    def get_offending_usage(
        self, *, at_time: datetime, last_usages: list[Usage]
    ) -> Usage | None:
        if last_usages:
            return last_usages[0]

        return None


class UsageTracker:
    def __init__(
        self, db_config: DatabaseConfig, limit_config: RateLimitConfig
    ) -> None:
        repo = PostgresRateLimitingRepo.connect(
            host=db_config.db_host,
            database=db_config.db_name,
            username=db_config.db_user,
            password=db_config.db_password,
            min_connections=1,
            max_connections=4,
        )
        self._default_rate_limiter = RateLimiter(
            policy=DailyLimitRateLimitingPolicy(limit=limit_config.daily),
            repo=repo,
            timezone=timezone.utc,
        )
        self._relocalize_rate_limiter = RateLimiter(
            policy=_UseOncePolicy(),
            repo=repo,
            timezone=timezone.utc,
        )

    def _get_conflict(
        self,
        *,
        user_id: int,
        at_time: datetime,
        unique_file_id: str,
        locale: str | None,
    ) -> Usage | None:
        if usage := self._default_rate_limiter.get_offending_usage(
            context_id="",
            user_id=user_id,
            at_time=at_time,
        ):
            return usage

        if locale is None:
            return None

        return self._relocalize_rate_limiter.get_offending_usage(
            context_id=f"relocalize-{unique_file_id}-{locale}",
            user_id=user_id,
            at_time=at_time,
        )

    async def get_conflict(
        self,
        *,
        user_id: int,
        at_time: datetime,
        unique_file_id: str,
        locale: str | None,
    ) -> Usage | None:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None,
            lambda: self._get_conflict(
                user_id=user_id,
                at_time=at_time,
                unique_file_id=unique_file_id,
                locale=locale,
            ),
        )

    def _track(
        self,
        request: Message,
        *,
        unique_file_id: str,
        response_id: int | None,
        locale: str | None,
    ) -> None:
        if locale is None:
            self._default_rate_limiter.add_usage(
                time=request.date,
                context_id="",
                user_id=request.from_user.id,  # type: ignore[union-attr]
                response_id=str(response_id),
                reference_id=unique_file_id,
            )
        else:
            self._relocalize_rate_limiter.add_usage(
                time=request.date,
                context_id=f"relocalize-{unique_file_id}-{locale}",
                user_id=request.from_user.id,  # type: ignore[union-attr]
                response_id=str(response_id),
                reference_id=unique_file_id,
            )

    async def track(
        self,
        request: Message,
        *,
        unique_file_id: str,
        response_id: int | None,
        locale: str | None,
    ) -> None:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(
            None,
            lambda: self._track(
                request=request,
                unique_file_id=unique_file_id,
                response_id=response_id,
                locale=locale,
            ),
        )

    def close(self) -> None:
        self._default_rate_limiter.close()

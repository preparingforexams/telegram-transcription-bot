import asyncio
import logging
from datetime import UTC, datetime, timedelta
from typing import Self

from opentelemetry import trace
from rate_limiter import RateLimiter, RateLimitingPolicy, RateLimitingRepo, Usage
from rate_limiter.policy import DailyLimitRateLimitingPolicy
from rate_limiter.repo import PostgresRateLimitingRepo
from telegram import Message

from bot.config import DatabaseConfig, RateLimitConfig

_LOG = logging.getLogger(__name__)
_tracer = trace.get_tracer(__name__)


class _UseOncePolicy(RateLimitingPolicy):
    def __init__(self) -> None:
        pass

    @property
    def requested_history(self) -> int:
        return 1

    async def get_offending_usage(
        self, *, at_time: datetime, last_usages: list[Usage]
    ) -> Usage | None:
        if last_usages:
            return last_usages[0]

        return None


class UsageTracker:
    def __init__(
        self,
        repo: RateLimitingRepo,
        limit_config: RateLimitConfig,
    ) -> None:
        self._last_cleanup: datetime | None = None
        self._default_rate_limiter = RateLimiter(
            policy=DailyLimitRateLimitingPolicy(limit=limit_config.daily),
            repo=repo,
            timezone=UTC,
            retention_time=timedelta(weeks=1),
        )
        self._relocalize_rate_limiter = RateLimiter(
            policy=_UseOncePolicy(),
            repo=repo,
            timezone=UTC,
        )

    @classmethod
    async def create(
        cls, db_config: DatabaseConfig, limit_config: RateLimitConfig
    ) -> Self:
        repo = await PostgresRateLimitingRepo.connect(
            host=db_config.db_host,
            database=db_config.db_name,
            username=db_config.db_user,
            password=db_config.db_password,
            min_connections=1,
            max_connections=4,
        )
        return cls(repo, limit_config)

    async def get_conflict(
        self,
        *,
        user_id: int,
        at_time: datetime,
        unique_file_id: str,
        locale: str | None,
    ) -> Usage | None:
        if usage := await self._default_rate_limiter.get_offending_usage(
            context_id="",
            user_id=user_id,
            at_time=at_time,
        ):
            return usage

        if locale is None:
            return None

        return await self._relocalize_rate_limiter.get_offending_usage(
            context_id=f"relocalize-{unique_file_id}-{locale}",
            user_id=user_id,
            at_time=at_time,
        )

    async def _cleanup(self) -> None:
        now = datetime.now(tz=UTC)
        last_cleanup = self._last_cleanup
        if last_cleanup is not None and (now - last_cleanup) < timedelta(hours=1):
            return

        _LOG.info("Triggering rate limiter housekeeping")
        self._last_cleanup = now
        await self._default_rate_limiter.do_housekeeping()

    async def track(
        self,
        request: Message,
        *,
        unique_file_id: str,
        response_id: int | None,
        locale: str | None,
    ) -> None:
        cleanup = asyncio.create_task(self._cleanup())

        if locale is None:
            await self._default_rate_limiter.add_usage(
                time=request.date,
                context_id="",
                user_id=request.from_user.id,  # type: ignore[union-attr]
                response_id=str(response_id),
                reference_id=unique_file_id,
            )
        else:
            await self._relocalize_rate_limiter.add_usage(
                time=request.date,
                context_id=f"relocalize-{unique_file_id}-{locale}",
                user_id=request.from_user.id,  # type: ignore[union-attr]
                response_id=str(response_id),
                reference_id=unique_file_id,
            )

        await cleanup

    async def close(self) -> None:
        await self._default_rate_limiter.close()

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Self

from bs_nats_updater import NatsConfig

if TYPE_CHECKING:
    from bs_config import Env


@dataclass
class SentryConfig:
    dsn: str
    release: str

    @classmethod
    def from_env(cls, env: Env) -> Self | None:
        dsn = env.get_string("sentry-dsn")

        if not dsn:
            return None

        return cls(
            dsn=dsn,
            release=env.get_string("app-version", default="debug"),
        )


@dataclass
class AzureTtsConfig:
    region: str
    key: str

    @classmethod
    def from_env(cls, env: Env) -> Self:
        return cls(
            region=env.get_string("speech-region", default="westeurope"),
            key=env.get_string("speech-key", required=True),
        )


@dataclass
class TelegramConfig:
    admin_id: int
    token: str

    @classmethod
    def from_env(cls, env: Env) -> Self:
        return cls(
            admin_id=env.get_int("admin-id", required=True, default=133399998),
            token=env.get_string("token", required=True),
        )


@dataclass
class DatabaseConfig:
    db_host: str
    db_name: str
    db_user: str
    db_password: str

    @classmethod
    def from_env(cls, env: Env) -> Self:
        return cls(
            db_host=env.get_string("host", required=True),
            db_name=env.get_string("name", required=True),
            db_user=env.get_string("user", required=True),
            db_password=env.get_string("password", required=True),
        )


@dataclass
class RateLimitConfig:
    daily: int

    @classmethod
    def from_env(cls, env: Env) -> Self:
        return cls(
            daily=env.get_int("daily", default=10),
        )


@dataclass
class RedisStateConfig:
    host: str
    username: str
    password: str

    @classmethod
    def from_env(cls, env: Env) -> Self:
        return cls(
            host=env.get_string("host", required=True),
            username=env.get_string("username", required=True),
            password=env.get_string("password", required=True),
        )


@dataclass
class Config:
    azure_tts: AzureTtsConfig
    database: DatabaseConfig
    enable_telemetry: bool
    nats: NatsConfig
    rate_limit: RateLimitConfig
    redis: RedisStateConfig
    scratch_dir: Path | None
    sentry: SentryConfig | None
    telegram: TelegramConfig

    @classmethod
    def from_env(cls, env: Env) -> Self:
        return cls(
            azure_tts=AzureTtsConfig.from_env(env / "azure"),
            database=DatabaseConfig.from_env(env / "db"),
            enable_telemetry=env.get_bool("enable-telemetry", default=False),
            nats=NatsConfig.from_env(env / "nats"),
            rate_limit=RateLimitConfig.from_env(env / "rate-limit"),
            redis=RedisStateConfig.from_env(env / "state" / "redis"),
            scratch_dir=env.get_string("scratch-dir", transform=Path),
            sentry=SentryConfig.from_env(env),
            telegram=TelegramConfig.from_env(env / "telegram"),
        )

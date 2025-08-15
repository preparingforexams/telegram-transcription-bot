from dataclasses import dataclass
from pathlib import Path
from typing import Self

from bs_config import Env
from bs_nats_updater import NatsConfig


@dataclass
class SentryConfig:
    dsn: str
    release: str

    @classmethod
    def from_env(cls, env: Env) -> Self | None:
        dsn = env.get_string("SENTRY_DSN")

        if not dsn:
            return None

        return cls(
            dsn=dsn,
            release=env.get_string("APP_VERSION", default="debug"),
        )


@dataclass
class AzureTtsConfig:
    region: str
    key: str

    @classmethod
    def from_env(cls, env: Env) -> Self:
        return cls(
            region=env.get_string("SPEECH_REGION", default="westeurope"),
            key=env.get_string("SPEECH_KEY", required=True),
        )


@dataclass
class TelegramConfig:
    admin_id: int
    token: str

    @classmethod
    def from_env(cls, env: Env) -> Self:
        return cls(
            admin_id=env.get_int("ADMIN_ID", required=True, default=133399998),
            token=env.get_string("TOKEN", required=True),
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
            db_host=env.get_string("HOST", required=True),
            db_name=env.get_string("NAME", required=True),
            db_user=env.get_string("USER", required=True),
            db_password=env.get_string("PASSWORD", required=True),
        )


@dataclass
class RateLimitConfig:
    daily: int

    @classmethod
    def from_env(cls, env: Env) -> Self:
        return cls(
            daily=env.get_int("DAILY", default=10),
        )


@dataclass
class RedisStateConfig:
    host: str
    username: str
    password: str

    @classmethod
    def from_env(cls, env: Env) -> Self:
        return cls(
            host=env.get_string("HOST", required=True),
            username=env.get_string("USERNAME", required=True),
            password=env.get_string("PASSWORD", required=True),
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
        scratch_path = env.get_string("SCRATCH_DIR")
        if scratch_path is None:
            scratch_dir = None
        else:
            scratch_dir = Path(scratch_path)

        return cls(
            azure_tts=AzureTtsConfig.from_env(env.scoped("AZURE_")),
            database=DatabaseConfig.from_env(env.scoped("DB_")),
            enable_telemetry=env.get_bool("ENABLE_TELEMETRY", default=False),
            nats=NatsConfig.from_env(env.scoped("NATS_")),
            rate_limit=RateLimitConfig.from_env(env.scoped("RATE_LIMIT_")),
            redis=RedisStateConfig.from_env(env.scoped("STATE_REDIS_")),
            scratch_dir=scratch_dir,
            sentry=SentryConfig.from_env(env),
            telegram=TelegramConfig.from_env(env.scoped("TELEGRAM_")),
        )

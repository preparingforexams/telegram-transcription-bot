from dataclasses import dataclass
from pathlib import Path
from typing import Self

from bs_config import Env


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
    token: str

    @classmethod
    def from_env(cls, env: Env) -> Self:
        return cls(
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
class Config:
    azure_tts: AzureTtsConfig
    database: DatabaseConfig
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
            scratch_dir=scratch_dir,
            sentry=SentryConfig.from_env(env),
            telegram=TelegramConfig.from_env(env.scoped("TELEGRAM_")),
        )

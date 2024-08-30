from dataclasses import dataclass
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
    def from_env(cls, env: Env) -> Self | None:
        token = env.get_string("TOKEN")
        if token is None:
            return None

        return cls(
            token=token,
        )

@dataclass
class Config:
    azure_tts: AzureTtsConfig
    sentry: SentryConfig | None
    telegram: TelegramConfig | None

    @classmethod
    def from_env(cls, env: Env) -> Self:
        return cls(
            azure_tts=AzureTtsConfig.from_env(env.scoped("AZURE_")),
            sentry=SentryConfig.from_env(env),
            telegram=TelegramConfig.from_env(env.scoped("TELEGRAM_")),
        )

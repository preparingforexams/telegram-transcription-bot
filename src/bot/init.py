import logging

import sentry_sdk
from bs_config import Env
from opentelemetry.instrumentation.logging import LoggingInstrumentor

from bot.config import Config, SentryConfig
from bot.telemetry import setup_tracing

_LOG = logging.getLogger(__name__)


def _setup_logging() -> None:
    LoggingInstrumentor().instrument(set_logging_format=True)

    logging.root.level = logging.WARNING
    logging.getLogger(__package__).level = logging.DEBUG


def _setup_sentry(config: SentryConfig | None) -> None:
    if not config:
        _LOG.warning("Sentry not configured")
        return

    sentry_sdk.init(
        dsn=config.dsn,
        release=config.release,
    )


def initialize() -> Config:
    _setup_logging()

    config = Config.from_env(Env.load(include_default_dotenv=True))
    setup_tracing(config)
    _setup_sentry(config.sentry)
    return config

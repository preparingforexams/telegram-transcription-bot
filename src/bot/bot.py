import logging
import re
import signal
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, cast

from opentelemetry import trace
from telegram import Audio, Message, Update, User, VideoNote, Voice
from telegram.constants import ChatType, FileSizeLimit, MessageLimit
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from bot.config import Config
from bot.conversion import AudioConverter
from bot.localization import find_locale, locale_by_language
from bot.speech import Transcriber
from bot.tracing import InstrumentedHttpxRequest
from bot.usage import UsageTracker

_LOG = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)


@asynccontextmanager
async def telegram_span(*, update: Update, name: str) -> AsyncIterator[trace.Span]:
    with tracer.start_as_current_span(name) as span:
        span.set_attribute(
            "telegram.update_keys",
            list(update.to_dict(recursive=False).keys()),
        )
        span.set_attribute("telegram.update_id", update.update_id)

        if message := update.effective_message:
            span.set_attribute("telegram.message_id", message.message_id)
            span.set_attribute("telegram.message_timestamp", message.date.isoformat())

        if chat := update.effective_chat:
            span.set_attribute("telegram.chat_id", chat.id)

        if user := update.effective_user:
            span.set_attribute("telegram.user_id", user.id)

        yield span


class Bot:
    def __init__(self, config: Config):
        self.config = config
        self.converter = AudioConverter()
        self.transcriber = Transcriber(config.azure_tts)
        self.usage_tracker = UsageTracker(config.database, config.rate_limit)

    def run(self) -> None:
        app = (
            Application.builder()
            .request(InstrumentedHttpxRequest(connection_pool_size=2))
            .token(self.config.telegram.token)
            .build()
        )

        app.add_handler(
            MessageHandler(
                filters=(filters.VOICE | filters.AUDIO | filters.VIDEO_NOTE)
                & ~filters.UpdateType.EDITED,
                callback=self._handle_message,
                block=False,
            )
        )
        app.add_handler(
            CommandHandler(
                command="retry",
                has_args=1,
                callback=self._relocalize,
                filters=~filters.UpdateType.EDITED,
            )
        )
        app.run_polling(
            stop_signals=[signal.SIGTERM, signal.SIGINT],
        )

        _LOG.info("Telegram application has shut down. Cleaning up...")
        self.usage_tracker.close()

    @staticmethod
    def _easter_eggs(s: str) -> str:
        result = []
        for part in re.split(r"(\W+)", s):
            if part in {
                "VAGINA",
                "VULVA",
                "VENUSHÜGEL",
                "ABCDEFG",
            }:
                result.append("vegan")
            else:
                result.append(part)

        return "".join(result)

    async def _relocalize(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        async with telegram_span(update=update, name="relocalize"):
            if update.edited_message:
                return

            update_id = update.update_id
            _LOG.info("[%s] Received command update", update_id)

            message: Message = update.message  # type: ignore
            locale_query: str = context.args[0]  # type: ignore
            locale = find_locale(locale_query)
            if not locale:
                _LOG.info("[%s] Unsupported locale: '%s'", update_id, locale_query)
                supported_langs = ", ".join(sorted(locale_by_language.keys()))
                await message.reply_text(
                    f"Konnte die angegebene Sprache nicht verstehen. Unterstützt werden: {supported_langs}.",
                )
                return

            replied_to_message = message.reply_to_message
            if not replied_to_message or not (
                file := replied_to_message.voice
                or replied_to_message.video_note
                or replied_to_message.audio
            ):
                _LOG.info("[%s] No suitable reply_to_message", update_id)
                await message.reply_text(
                    "Das Command muss als Antwort auf eine Sprachnachricht, Videonachricht, oder Audiodatei verschickt werden."
                )
                return

            await self._process_message(
                message, file, update_id=update_id, locale=locale
            )

    async def _handle_message(self, update: Update, _: Any) -> None:
        async with telegram_span(update=update, name="handle_message"):
            update_id = update.update_id
            _LOG.info("[%s] Received message update", update_id)
            message = cast(Message, update.message)

            file = message.voice or message.audio or message.video_note

            if file is None:
                _LOG.error(
                    "[%s] Received unsupported message: %s",
                    update_id,
                    message.to_dict().keys(),
                )
                return

            await self._process_message(message, file, update_id=update_id, locale=None)

    async def _process_message(
        self,
        message: Message,
        file: Voice | Audio | VideoNote,
        *,
        update_id: int,
        locale: str | None,
    ) -> None:
        with tracer.start_as_current_span("process_message"):
            file_size = int(file.file_size or 0)
            if file_size > FileSizeLimit.FILESIZE_DOWNLOAD:
                _LOG.info("[%s] File size exceeds limit", update_id)
                await message.reply_text(
                    disable_notification=True,
                    text="Sorry, ich bearbeite nur Dateien bis zu 20 MB",
                )
                return

            user_id = cast(User, message.from_user).id
            if await self.usage_tracker.get_conflict(
                user_id=user_id,
                at_time=message.date,
                unique_file_id=file.file_unique_id,
                locale=locale,
            ):
                _LOG.info(
                    "[%s] User %d has exceeded rate limit",
                    update_id,
                    user_id,
                )
                if message.chat.type == ChatType.PRIVATE:
                    await message.reply_text("Sorry, du hast dein Limit erreicht.")
                else:
                    await message.set_reaction("👎")
                return

            with TemporaryDirectory(dir=self.config.scratch_dir) as scratch_path:
                scratch_dir = Path(scratch_path)

                _LOG.debug("[%s] Downloading file", update_id)
                original_audio_file = await self._download_file(file, scratch_dir)

                _LOG.debug("[%s] Converting file", update_id)
                converted_audio_file = await self.converter.convert_to_wave(
                    original_audio_file
                )

                _LOG.debug(
                    "[%s] Transcribing audio with locale %s",
                    update_id,
                    locale,
                )
                result = await self.transcriber.transcribe(
                    converted_audio_file, locale=locale
                )

                if not result:
                    _LOG.info("[%s] No transcription result", update_id)
                    if isinstance(file, Voice):
                        await message.set_reaction(
                            "🤷‍♂️",
                            is_big=True,
                        )
                        await self.usage_tracker.track(
                            message,
                            response_id=None,
                            unique_file_id=file.file_unique_id,
                            locale=locale,
                        )
                    return

                result = self._easter_eggs(result)

                chunks = self._split_chunks(result)
                _LOG.info(
                    "[%s] Sending message of length %d in %d chunks",
                    update_id,
                    len(result),
                    len(chunks),
                )
                first_response_message: Message | None = None
                for chunk in chunks:
                    response_message = await message.reply_text(
                        text=chunk,
                        disable_notification=True,
                    )
                    if first_response_message is None:
                        first_response_message = response_message
                await self.usage_tracker.track(
                    message,
                    response_id=first_response_message.message_id,  # type: ignore[union-attr]
                    unique_file_id=file.file_unique_id,
                    locale=locale,
                )

    async def _download_file(
        self,
        file: Voice | Audio | VideoNote,
        scratch_dir: Path,
    ) -> Path:
        with tracer.start_as_current_span("download_file"):
            prepared_file = await file.get_file()

            path = prepared_file.file_path
            if path:
                file_name = path.rsplit("/", 1)[1]
            else:
                file_name = prepared_file.file_id

            return await prepared_file.download_to_drive(scratch_dir / file_name)

    @staticmethod
    def _split_chunks(
        text: str,
        length: int = MessageLimit.MAX_TEXT_LENGTH - 7,
    ) -> list[str]:
        chunks = []
        remaining = text
        while remaining:
            if len(remaining) <= length:
                chunks.append(remaining)
                break

            end_index = length
            while not remaining[end_index - 1].isspace():
                end_index -= 1
            chunks.append(remaining[:end_index])
            remaining = remaining[end_index:]

        result = []
        chunk_count = len(chunks)

        if chunk_count > 1:
            for index, chunk in enumerate(chunks):
                result.append(f"[{index + 1}/{chunk_count}] {chunk}")
        else:
            result = chunks

        return result

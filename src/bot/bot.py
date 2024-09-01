import logging
import re
import signal
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, cast

from telegram import Audio, Message, Update, VideoNote, Voice
from telegram.constants import FileSizeLimit, MessageLimit
from telegram.ext import Application, MessageHandler, filters

from bot.config import Config
from bot.conversion import AudioConverter
from bot.speech import Transcriber
from bot.usage import UsageTracker

_LOG = logging.getLogger(__name__)


class Bot:
    def __init__(self, config: Config):
        self.config = config
        self.converter = AudioConverter()
        self.transcriber = Transcriber(config.azure_tts)
        self.usage_tracker = UsageTracker(config.database)

    def run(self) -> None:
        app = Application.builder().token(self.config.telegram.token).build()
        app.add_handler(
            MessageHandler(
                filters=filters.VOICE | filters.AUDIO | filters.VIDEO_NOTE,
                callback=self._handle_message,
                block=False,
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

    async def _handle_message(self, update: Update, _: Any) -> None:
        update_id = update.update_id
        _LOG.info("[%s] Received update", update_id)
        message = cast(Message, update.message)

        file = message.voice or message.audio or message.video_note

        if file is None:
            _LOG.error(
                "[%s] Received unsupported update", update_id, extra=update.to_dict()
            )
            return

        file_size = int(file.file_size or 0)
        if file_size > FileSizeLimit.FILESIZE_DOWNLOAD:
            _LOG.info("[%s] File size exceeds limit", update_id)
            await message.reply_text(
                disable_notification=True,
                text="Sorry, ich bearbeite nur Dateien bis zu 20 MB",
            )
            return

        with TemporaryDirectory(dir=self.config.scratch_dir) as scratch_path:
            scratch_dir = Path(scratch_path)

            _LOG.debug("[%s] Downloading file", update_id)
            original_audio_file = await self._download_file(file, scratch_dir)

            _LOG.debug("[%s] Converting file", update_id)
            converted_audio_file = await self.converter.convert_to_wave(
                original_audio_file
            )

            _LOG.debug("[%s] Transcribing audio", update_id)
            result = await self.transcriber.transcribe(converted_audio_file)

            if not result:
                _LOG.info("[%s] No transcription result", update_id)
                if isinstance(file, Voice):
                    response = await message.reply_text(
                        "Ich habe leider nichts verstanden.",
                        disable_notification=True,
                    )
                    await self.usage_tracker.track(
                        message,
                        response_id=response.message_id,
                        unique_file_id=file.file_unique_id,
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
                message = await message.reply_text(
                    text=chunk,
                    disable_notification=True,
                )
                if first_response_message is None:
                    first_response_message = message
            await self.usage_tracker.track(
                message,
                response_id=first_response_message.message_id,  # type: ignore[union-attr]
                unique_file_id=file.file_unique_id,
            )

    async def _download_file(
        self,
        file: Voice | Audio | VideoNote,
        scratch_dir: Path,
    ) -> Path:
        prepared_file = await file.get_file()

        path = prepared_file.file_path
        if path:
            file_name = path.rsplit("/", 1)[1]
        else:
            file_name = prepared_file.file_id

        return await prepared_file.download_to_drive(scratch_dir / file_name)

    @staticmethod
    def _split_chunks(
        text: str, length: int = MessageLimit.MAX_TEXT_LENGTH
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

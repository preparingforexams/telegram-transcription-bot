import asyncio
import logging
from pathlib import Path
from typing import Any

import azure.cognitiveservices.speech as speechsdk

from bot.config import AzureTtsConfig
from bot.localization import auto_detect_languages, locale_by_language

_LOG = logging.getLogger(__name__)


class Transcriber:
    def __init__(self, config: AzureTtsConfig) -> None:
        self._speech_config = speechsdk.SpeechConfig(
            subscription=config.key,
            region=config.region,
        )
        self._speech_config.set_profanity(speechsdk.ProfanityOption.Raw)

    async def transcribe(self, audio_file: Path, locale: str | None) -> str | None:
        audio_config = speechsdk.AudioConfig(filename=str(audio_file))
        if locale is None:
            recognizer = speechsdk.SpeechRecognizer(
                speech_config=self._speech_config,
                audio_config=audio_config,
                auto_detect_source_language_config=speechsdk.languageconfig.AutoDetectSourceLanguageConfig(
                    languages=[
                        locale_by_language[lang] for lang in auto_detect_languages
                    ],
                ),
            )
        else:
            recognizer = speechsdk.SpeechRecognizer(
                speech_config=self._speech_config,
                audio_config=audio_config,
                language=locale,
            )

        # TODO: clean this up.
        result_text = ""

        def on_recognized(evt) -> None:  # type: ignore[no-untyped-def]
            nonlocal result_text
            if result_text:
                result_text += " "
            result_text += evt.result.text

        recognizer.recognized.connect(on_recognized)

        done = False

        def on_stop(_: Any) -> None:
            nonlocal done
            recognizer.stop_continuous_recognition()
            done = True

        recognizer.speech_end_detected.connect(on_stop)

        try:
            recognizer.start_continuous_recognition()
            while not done:
                await asyncio.sleep(0.5)
            return result_text or None
        except BaseException as e:
            raise IOError from e

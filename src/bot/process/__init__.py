import logging
import os
import re
import subprocess
import time
from threading import Thread
from typing import Optional

import azure.cognitiveservices.speech as speechsdk
import azure.functions as func
import requests
import sentry_sdk

_speech_key = os.getenv("SPEECH_KEY")
_speech_region = os.getenv("AZURE_REGION")
_bot_token = os.getenv("TELEGRAM_TOKEN")

_speech_config = speechsdk.SpeechConfig(
    subscription=_speech_key,
    region=_speech_region,
)

_speech_config.set_profanity(speechsdk.ProfanityOption.Raw)


def _setup_sentry():
    sentry_sdk.init(
        dsn="https://7adb9f2113bb409c978f99c6bb4eeaa6@o85632.ingest.sentry.io/6117803",
        server_name="process",
        traces_sample_rate=1.0,
    )


def _easter_eggs(s: str) -> str:
    result = []
    for part in re.split(r"([^\w]+)", s):
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


def main(msg: func.QueueMessage) -> None:
    _setup_sentry()

    logging.info('Python queue trigger function processed a queue item: %s',
                 msg.get_body().decode('utf-8'))
    message = msg.get_json()
    supported_key = _get_supported_key(message)

    if not supported_key:
        return

    chat_id = message['chat']['id']
    message_id = message['message_id']

    data = message[supported_key]
    try:
        _send_chat_action(chat_id, 'record_voice')

        logging.info("Downloading file")
        in_filename = _download_file(data)

        if not in_filename:
            return

        # logging.info("Skipping conversion.")
        # out_filename = in_filename
        logging.info("Converting file")
        out_filename = _convert_file(in_filename)

        is_typing = True

        def _send_typing_action():
            while is_typing:
                _send_chat_action(chat_id, 'typing')
                time.sleep(2)

        Thread(target=_send_typing_action, daemon=True).start()

        logging.info("Transcribing file")
        transcribed = _transcribe(out_filename)

        is_typing = False
    except ValueError as e:
        logging.error("Unknown error", exc_info=e)
        return
    except IOError as e:
        logging.error("IO error during transcription", exc_info=e)
        _send_messages("Fehler bei der Verarbeitung der Nachricht.", chat_id, message_id)
        return

    if not transcribed:
        logging.info("No transcription result")
        if supported_key == 'voice':
            _send_messages('Ich habe leider nichts verstanden.', chat_id, message_id)
        return

    transcribed = _easter_eggs(transcribed)

    logging.info("Sending message of length %d", len(transcribed))
    _send_messages(transcribed, chat_id, message_id)


def _create_message(text, chat_id, message_id) -> dict:
    return {
        'chat_id': chat_id,
        'reply_to_message_id': message_id,
        'disable_notification': True,
        'text': text
    }


def _split_chunks(text: str, length=4000) -> list:
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
    for index, chunk in enumerate(chunks):
        result.append(f"[{index + 1}/{chunk_count}] {chunk}")

    return result


def _send_messages(text: str, chat_id, message_id):
    messages = []
    if len(text) <= 4096:
        messages.append(_create_message(text, chat_id, message_id))
    else:
        logging.info("Splitting message into chunks")
        chunks = _split_chunks(text)
        logging.info(
            f"Got chunks of sizes {[len(c) for c in chunks]} for text of length {len(text)}")
        for chunk in chunks:
            messages.append(_create_message(chunk, chat_id, message_id))

    for message in messages:
        response = requests.post(_request_url("sendMessage"), data=message, timeout=10)
        if response.status_code >= 400:
            logging.error("Unsuccessful response from Telegram: %d", response.status_code)


def _send_chat_action(chat_id: int, action: str):
    response = requests.post(
        _request_url("sendChatAction"),
        data=dict(chat_id=chat_id, action=action),
        timeout=10,
    )
    response.raise_for_status()


def _get_supported_key(message: dict) -> Optional[str]:
    for key in ['voice', 'audio', 'video_note']:
        if key in message:
            return key


def _download_file(data: dict) -> Optional[str]:
    try:
        audio = data
        file_id = audio['file_id']
        return _download_telegram_file(file_id)
    except KeyError as e:
        logging.error("KeyError during telegram download", exc_info=e)
        return None
    except BaseException as e:
        logging.error(f"Unknown error during telegram download", exc_info=e)
        return None


def _download_telegram_file(file_id: str) -> str:
    url = _request_url("getFile")
    response = requests.post(url, data={'file_id': file_id}, timeout=10).json()
    file_path = response['result']['file_path']
    download_url = f'https://api.telegram.org/file/bot{_bot_token}/{file_path}'
    file_bytes = requests.get(download_url, timeout=60).content
    path = f'/tmp/{file_id}'
    with open(path, 'wb') as f:
        f.write(file_bytes)
    return path


def _convert_file(in_filename) -> str:
    out_filename = f'{in_filename}.wav'
    return_code = subprocess.call(
        ['./ffmpeg', "-i", in_filename, out_filename])
    logging.info(f"Converted with code: {return_code}")

    if return_code != 0:
        raise ValueError(f"Got unexpected return code {return_code} from ffmpeg")

    return out_filename


def _get_speech_token() -> str:
    fetch_token_url = f'https://{_speech_region}.api.cognitive.microsoft.com/sts/v1.0/issueToken'
    headers = {
        'Ocp-Apim-Subscription-Key': _speech_key
    }
    response = requests.post(fetch_token_url, headers=headers, timeout=10)
    return str(response.text)


def _transcribe(filename) -> Optional[str]:
    recognizer = speechsdk.SpeechRecognizer(
        speech_config=_speech_config,
        audio_config=speechsdk.AudioConfig(filename=filename),
        auto_detect_source_language_config=speechsdk.languageconfig.AutoDetectSourceLanguageConfig(
            languages=['en-US', 'de-DE'],
        ),
    )

    result_text = ""

    def on_recognized(evt):
        nonlocal result_text
        if result_text:
            result_text += " "
        result_text += evt.result.text

    recognizer.recognized.connect(on_recognized)

    done = False

    def on_stop(evt):
        nonlocal done
        recognizer.stop_continuous_recognition()
        done = True

    recognizer.speech_end_detected.connect(on_stop)

    try:
        recognizer.start_continuous_recognition()
        while not done:
            time.sleep(.5)
        return result_text or None
    except BaseException as e:
        raise IOError from e


def _request_url(method: str):
    return f"https://api.telegram.org/bot{_bot_token}/{method}"
import subprocess
import requests
import logging

import azure.functions as func
import os
_speech_key = os.getenv("SPEECH_KEY")
_speech_region = "westeurope"
_bot_token = os.getenv("TELEGRAM_TOKEN")


def main(msg: func.QueueMessage) -> None:
    logging.info('Python queue trigger function processed a queue item: %s',
                 msg.get_body().decode('utf-8'))
    message = msg.get_json()

    try:
        logging.info("Downloading file")
        in_filename = _download_file(message)

        logging.info("Skipping conversion.")
        out_filename = in_filename
        #logging.info("Converting file")
        #out_filename = _convert_file(in_filename)

        logging.info("Transcribing file")
        transcribed = _transcribe(out_filename)
    except ValueError as e:
        logging.error("Unknown error", exc_info=e)
        return

    logging.info("Sending message")
    message = {
        'chat_id': message['chat']['id'],
        'reply_to_message_id': message['message_id'],
        'text': transcribed
    }
    requests.post(_request_url("sendMessage"), data=message)


def _download_file(message: dict) -> str:
    try:
        audio = message['voice']
        file_id = audio['file_id']
        return _download_telegram_file(file_id)

    except KeyError as e:
        logging.error(f"KeyError", exc_info=e)
        return
    except BaseException as e:
        logging.error(f"Unknown error", exc_info=e)
        return


def _download_telegram_file(file_id: str) -> str:
    url = _request_url("getFile")
    response = requests.post(url, data={'file_id': file_id}).json()
    file_path = response['result']['file_path']
    download_url = f'https://api.telegram.org/file/bot{_bot_token}/{file_path}'
    file_bytes = requests.get(download_url).content
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
        raise ValueError()

    return out_filename


def _get_speech_token() -> str:
    fetch_token_url = f'https://{_speech_region}.api.cognitive.microsoft.com/sts/v1.0/issueToken'
    headers = {
        'Ocp-Apim-Subscription-Key': _speech_key
    }
    response = requests.post(fetch_token_url, headers=headers)
    return str(response.text)


def _transcribe(filename):
    token = _get_speech_token()
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'audio/wave',
        'Accept': 'application/json'
    }
    with open(filename, "rb") as payload:
        response = requests.request(
            "POST", _build_speech_url("de-DE"), headers=headers, data=payload)
        result = response.json()
        status = result['RecognitionStatus']

        if status == "Success":
            text: str = result["DisplayText"]
            if text.strip():
                return text
            else:
                return "Ich habe leider nichts verstanden."
        elif status == "BabbleTimeout":
            return "Das waren leider nur Geräusche."
        elif status == "InitialSilenceTimeout":
            return "Sprich lauter, da war nichts zu hören."
        elif status == "NoMatch":
            return "Ich verstehe leider nur Deutsch."
        else:
            logging.error(f"Unsuccessful transcription: {status}")
            raise ValueError()


def _build_speech_url(language: str) -> str:
    return f"https://{_speech_region}.stt.speech.microsoft.com/speech/recognition/conversation/cognitiveservices/v1?language={language}&format=simple&profanity=raw"


def _request_url(method: str):
    return f"https://api.telegram.org/bot{_bot_token}/{method}"

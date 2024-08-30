import json
import logging

import azure.functions as func
import sentry_sdk

MAX_MINUTES = 10
_MAX_FILE_SIZE_BYTES = 20 * 1024 * 1024


def _setup_sentry():
    sentry_sdk.init(
        dsn="https://7adb9f2113bb409c978f99c6bb4eeaa6@o85632.ingest.sentry.io/6117803",
        server_name="handover",
        traces_sample_rate=1.0,
    )


def main(req: func.HttpRequest, msg: func.Out[func.QueueMessage]) -> func.HttpResponse:
    _setup_sentry()
    logging.info('Python HTTP trigger function processed a request.')

    update = req.get_json()
    try:
        message = update['message']
        message_id = message['message_id']
        chat_id = message['chat']['id']

        audio = _get_any_supported(message)
        size = int(audio['file_size'])
    except KeyError:
        logging.debug(f"Unhandleable update: {update}")
        return _build_response("")

    if size > _MAX_FILE_SIZE_BYTES:
        return _build_response({
            'method': 'sendMessage',
            'chat_id': chat_id,
            'reply_to_message_id': message_id,
            'disable_notification': True,
            'text': "Sorry, ich bearbeite nur Dateien bis zu 20 MB"
        })

    logging.info("Adding message to queue")
    msg.set(json.dumps(message))

    return _build_response("")


def _get_any_supported(message: dict) -> dict:
    result = message.get('voice') or message.get('audio') or message.get('video_note')
    if not result:
        raise KeyError("No supported message type found")
    return result


def _build_response(data) -> func.HttpResponse:
    return func.HttpResponse(json.dumps(data), mimetype='application/json')

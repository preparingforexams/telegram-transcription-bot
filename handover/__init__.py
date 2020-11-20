import json
import logging

import azure.functions as func


MAX_MINUTES = 10


def main(req: func.HttpRequest, msg: func.Out[func.QueueMessage]) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed a request.')

    update = req.get_json()
    try:
        message = update['message']
        message_id = message['message_id']
        chat_id = message['chat']['id']

        audio = message['voice']
        duration = int(audio['duration'])
    except KeyError:
        logging.debug(f"Unhandleable update: {update}")
        return _build_response("")

    if duration > (MAX_MINUTES * 60):
        return _build_response({
            'method': 'sendMessage',
            'chat_id': chat_id,
            'reply_to_message_id': message_id,
            'disable_notification': True,
            'text': "Sorry, ich bearbeite nur Sprachnachrichten bis zu 10 Minuten Länge."
        })

    logging.info("Adding message to queue")
    msg.set(json.dumps(message))

    return _build_response("")


def _build_response(data) -> func.HttpResponse:
    return func.HttpResponse(json.dumps(data), mimetype='application/json')

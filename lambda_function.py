import base64
import asyncio
from app import core

def lambda_handler(event, context):
    audio_response = asyncio.run(core.process_audio_logic(event))
    return {
        'statusCode': 200,
        'headers': {'Content-Type': 'audio/mpeg'},
        'body': base64.b64encode(audio_response).decode('utf-8'),
        'isBase64Encoded': True
    }

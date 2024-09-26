import base64
import asyncio
from app import core

def lambda_handler(event, context):
    response = asyncio.run(core.process_audio_logic(event))
    
    if response.status_code != 200:
        return {
            'statusCode': response.status_code,
            'headers': {'Content-Type': 'application/json'},
            'body': response.body
        }
    
    return {
        'statusCode': 200,
        'headers': {'Content-Type': 'audio/mpeg'},
        'body': base64.b64encode(response.body).decode('utf-8'),
        'isBase64Encoded': True
    }

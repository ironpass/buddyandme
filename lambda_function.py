import json
import base64
import asyncio
from app.core import process_audio_logic

def lambda_handler(event, context):
    return asyncio.run(process_audio_logic(event))

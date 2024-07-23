import json
import base64
import asyncio
from app import core

def lambda_handler(event, context):
    return asyncio.run(core.process_audio_logic(event))

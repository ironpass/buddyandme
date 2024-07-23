import socket
from fastapi import FastAPI, Request, Response, HTTPException
from dotenv import load_dotenv
load_dotenv()

from . import core

app = FastAPI()

@app.post("/upload")
async def upload(request: Request):
    event = await request.json()
    event = {
        "body": event
    }
    
    response = await core.process_audio_logic(event)
    
    if isinstance(response, dict) and 'statusCode' in response and 'body' in response:
        if response['statusCode'] != 200:
            raise HTTPException(status_code=response['statusCode'], detail=response['body'])
        return Response(
            content=response['body'],
            media_type="application/json",
            status_code=response['statusCode']
        )
    
    return Response(
        content=response,
        media_type="application/octet-stream",
        status_code=200
    )

@app.on_event("startup")
async def startup_event():
    # Get the local IP address
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # This doesn't need to be reachable. 8.8.8.8 is Google DNS.
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
    finally:
        s.close()
    
    print(f"Local IP address: {local_ip}")
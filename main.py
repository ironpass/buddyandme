import socket
from fastapi import FastAPI, Request, Response, HTTPException
from dotenv import load_dotenv
load_dotenv()

from app import core

app = FastAPI()

@app.post("/")
async def upload(request: Request):
    event = await request.json()
    event = {
        "body": event
    }
    
    response = await core.process_audio_logic(event)

    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail=response.body)
    
    return Response(
        content=bytes(response.body),
        media_type="audio/mpeg",
        status_code=response.status_code
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
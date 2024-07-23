import socket
from fastapi import FastAPI, Request, Response
from .core import process_audio_logic

app = FastAPI()

@app.post("/upload")
async def upload(request: Request):
    event = await request.json()
    event = {
        "body": event
    }
    response = await process_audio_logic(event)
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
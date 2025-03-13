import asyncio
import websockets
import json
import flask
from flask import Flask, request, jsonify

# Flask App for handling Exotel requests
app = Flask(__name__)

# ElevenLabs Configuration
ELEVENLABS_WS_URL = "wss://api.elevenlabs.io/v1/conversational-ai/{agent_id}/websocket"
API_KEY = "sk_a51aaf204357d751750aeec49cbf73bf7ecf700be744ecd0"
AGENT_ID = "PO1XewroLt5PdOgznW2p"

# Store active WebSocket connections
active_clients = set()

@app.route("/exotel", methods=["POST"])
def exotel_passthru():
    """Receive call input from Exotel and send it to the WebSocket server."""
    data = request.json  # Exotel should send JSON with audio URL/text
    
    # Forward to connected WebSocket clients
    asyncio.run(forward_to_websockets(data))
    
    return jsonify({"status": "received"}), 200

async def forward_to_websockets(data):
    """Send Exotel data to all connected WebSocket clients."""
    for ws in active_clients:
        await ws.send(json.dumps(data))

async def forward_to_elevenlabs(client_ws, elevenlabs_ws):
    """Forward messages from WebSocket client to ElevenLabs."""
    async for message in client_ws:
        await elevenlabs_ws.send(message)

async def forward_to_client(elevenlabs_ws, client_ws):
    """Forward responses from ElevenLabs back to WebSocket client."""
    async for message in elevenlabs_ws:
        data = json.loads(message)
        await client_ws.send(json.dumps(data))

async def handle_elevenlabs_connection(client_ws):
    """Connect WebSocket client to ElevenLabs API."""
    headers = {"xi-api-key": API_KEY}
    url = ELEVENLABS_WS_URL.format(agent_id=AGENT_ID)

    async with websockets.connect(url, extra_headers=headers) as elevenlabs_ws:
        await asyncio.gather(
            forward_to_elevenlabs(client_ws, elevenlabs_ws),
            forward_to_client(elevenlabs_ws, client_ws)
        )

async def handle_connection(websocket, path):
    """Handle new WebSocket connection."""
    print("New connection established")
    active_clients.add(websocket)

    try:
        await handle_elevenlabs_connection(websocket)
    except websockets.exceptions.ConnectionClosed:
        print("Connection closed")
    finally:
        active_clients.remove(websocket)

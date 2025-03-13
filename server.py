import asyncio
import websockets
import json
import threading
from flask import Flask, request, jsonify

# Flask Configuration
app = Flask(__name__)

# Replace with your actual ElevenLabs credentials
ELEVENLABS_WS_URL = "wss://api.elevenlabs.io/v1/conversational-ai/{agent_id}/websocket"
API_KEY = "sk_a51aaf204357d751750aeec49cbf73bf7ecf700be744ecd0"
AGENT_ID = "PO1XewroLt5PdOgznW2p"

# Store active WebSocket connections
active_clients = set()

# Create a global event loop for WebSocket
ws_loop = asyncio.new_event_loop()

async def forward_to_websockets(data):
    """Forward data to all active WebSocket clients asynchronously."""
    if active_clients:
        print(f"[WEBSOCKETS] Forwarding data to {len(active_clients)} clients")
        await asyncio.gather(*(ws.send(json.dumps(data)) for ws in active_clients))
    else:
        print("[WEBSOCKETS] No active clients to forward data to")

async def forward_to_elevenlabs(client_ws, elevenlabs_ws):
    """Forward messages from WebSocket client to ElevenLabs WebSocket."""
    try:
        async for message in client_ws:
            print("[WEBSOCKETS] Forwarding client message to ElevenLabs:", message)
            await elevenlabs_ws.send(message)
    except websockets.exceptions.ConnectionClosedError:
        print("[WEBSOCKETS] Client WebSocket disconnected")

async def forward_to_client(elevenlabs_ws, client_ws):
    """Forward messages from ElevenLabs back to the WebSocket client."""
    try:
        async for message in elevenlabs_ws:
            print("[WEBSOCKETS] Received from ElevenLabs, forwarding to client:", message)
            await client_ws.send(message)
    except websockets.exceptions.ConnectionClosedError:
        print("[WEBSOCKETS] ElevenLabs WebSocket closed")

async def handle_elevenlabs_connection(client_ws):
    """Handle WebSocket connection with ElevenLabs API."""
    url = ELEVENLABS_WS_URL.format(agent_id=AGENT_ID)
    print("[ELEVENLABS] Connecting to ElevenLabs WebSocket API...")

    headers = {"Authorization": f"Bearer {API_KEY}"}
    
    try:
        async with websockets.connect(url=ELEVENLABS_WS_URL.format(agent_id=AGENT_ID), extra_headers=headers) as elevenlabs_ws:
            print("[ELEVENLABS] Connected to ElevenLabs WebSocket")
            await asyncio.gather(
                forward_to_elevenlabs(client_ws, elevenlabs_ws),
                forward_to_client(elevenlabs_ws, client_ws)
            )
    except Exception as e:
        print(f"[ELEVENLABS] Connection error: {e}")

async def handle_connection(websocket, path):
    """Handle new WebSocket connections."""
    print("[WEBSOCKETS] New WebSocket connection established")
    active_clients.add(websocket)

    try:
        await handle_elevenlabs_connection(websocket)
    except websockets.exceptions.ConnectionClosedError:
        print("[WEBSOCKETS] WebSocket connection closed")
    finally:
        active_clients.remove(websocket)

async def start_ws_server():
    """Start WebSocket server asynchronously."""
    print("[SERVER] Starting WebSocket server on ws://0.0.0.0:8765")
    async with websockets.serve(handle_connection, "0.0.0.0", 8765):
        await asyncio.Future()  # Keep the server running indefinitely

def run_websocket_server():
    """Run WebSocket server in a separate thread with a new event loop."""
    global ws_loop
    ws_loop = asyncio.new_event_loop()
    asyncio.set_event_loop(ws_loop)
    ws_loop.run_until_complete(start_ws_server())

@app.route("/", methods=["GET", "POST"])
def exotel_webhook():
    """Handle Exotel webhook requests and forward data to WebSocket clients."""
    if request.method == "POST":
        data = request.get_json()  # Expecting JSON data in a POST request
    else:
        data = request.args.to_dict()  # For GET request

    print("[FLASK] Received Exotel request:", data)

    if not data:
        return jsonify({"error": "No data received"}), 400

    # Forward data to WebSocket clients asynchronously
    global ws_loop
    if ws_loop is not None:
        asyncio.run_coroutine_threadsafe(forward_to_websockets(data), ws_loop)

    return jsonify({"status": "received"}), 200

if __name__ == "__main__":
    print("[SERVER] Starting Flask and WebSocket servers...")

    # Start WebSocket server in a separate thread
    ws_thread = threading.Thread(target=run_websocket_server, daemon=True)
    ws_thread.start()

    print("[FLASK] Running Flask server on http://0.0.0.0:5000")
    app.run(host="0.0.0.0", port=5000, threaded=True)

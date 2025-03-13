import asyncio
import websockets
import json
import threading
from flask import Flask, request, jsonify

# Flask Configuration
app = Flask(__name__)

# ElevenLabs Configuration (Replace with actual credentials)
ELEVENLABS_WS_URL = "wss://api.elevenlabs.io/v1/conversational-ai/{agent_id}/websocket"
API_KEY = "sk_a51aaf204357d751750aeec49cbf73bf7ecf700be744ecd0"
AGENT_ID = "PO1XewroLt5PdOgznW2p"

# Store active WebSocket connections
active_clients = set()

# Create a global event loop for WebSocket
ws_loop = asyncio.new_event_loop()

@app.route("/", methods=["GET", "POST"])
def exotel_webhook():
    """Handle Exotel webhook requests and forward data to WebSocket clients."""
    if request.method == "POST":
        data = request.get_json()  # Expecting JSON data in a POST request
    else:
        data = request.args.to_dict()  # Handle GET requests with query parameters

    print("[FLASK] Received Exotel request:", data)

    if not data:
        print("[FLASK] Error: No data received from Exotel")
        return jsonify({"error": "No data received"}), 400

    # Forward data to all WebSocket clients asynchronously
    asyncio.run_coroutine_threadsafe(forward_to_websockets(data), ws_loop)

    return jsonify({"status": "received"}), 200

async def forward_to_websockets(data):
    """Send Exotel data to all connected WebSocket clients."""
    if active_clients:
        print(f"[WEBSOCKETS] Forwarding data to {len(active_clients)} clients")
        await asyncio.gather(*(ws.send(json.dumps(data)) for ws in active_clients))
    else:
        print("[WEBSOCKETS] No active clients to forward data to")

async def forward_to_elevenlabs(client_ws, elevenlabs_ws):
    """Forward messages from WebSocket client to ElevenLabs."""
    try:
        async for message in client_ws:
            print("[WEBSOCKETS] Forwarding client message to ElevenLabs:", message)
            await elevenlabs_ws.send(message)
    except websockets.exceptions.ConnectionClosed:
        print("[WEBSOCKETS] Client WebSocket disconnected")

async def forward_to_client(elevenlabs_ws, client_ws):
    """Forward responses from ElevenLabs back to WebSocket client."""
    try:
        async for message in elevenlabs_ws:
            data = json.loads(message)
            print("[WEBSOCKETS] Received response from ElevenLabs, forwarding to client:", data)
            await client_ws.send(json.dumps(data))
    except websockets.exceptions.ConnectionClosed:
        print("[WEBSOCKETS] ElevenLabs WebSocket disconnected")

async def handle_elevenlabs_connection(client_ws):
    """Connect WebSocket client to ElevenLabs API and forward messages."""
    headers = {"xi-api-key": API_KEY}
    url = ELEVENLABS_WS_URL.format(agent_id=AGENT_ID)
    print("[ELEVENLABS] Connecting to ElevenLabs WebSocket API")

    try:
        async with websockets.connect(url, extra_headers=headers) as elevenlabs_ws:
            print("[ELEVENLABS] Connection established with ElevenLabs API")
            await asyncio.gather(
                forward_to_elevenlabs(client_ws, elevenlabs_ws),
                forward_to_client(elevenlabs_ws, client_ws)
            )
    except websockets.exceptions.ConnectionClosed:
        print("[ELEVENLABS] Connection closed")
    except Exception as e:
        print(f"[ELEVENLABS] Connection error: {e}")

async def handle_connection(websocket, path):
    """Handle new WebSocket connection."""
    print("[WEBSOCKETS] New WebSocket connection established")
    active_clients.add(websocket)

    try:
        await handle_elevenlabs_connection(websocket)
    except websockets.exceptions.ConnectionClosed:
        print("[WEBSOCKETS] WebSocket connection closed")
    finally:
        active_clients.remove(websocket)
        print("[WEBSOCKETS] Client disconnected, remaining clients:", len(active_clients))

# def run_websocket_server():
#     """Start the WebSocket server on port 8765."""
#     print("[SERVER] Starting WebSocket server on ws://0.0.0.0:8765")
#     global ws_loop
#     asyncio.set_event_loop(ws_loop)
#     start_server = websockets.serve(handle_connection, "0.0.0.0", 8765)
#     ws_loop.run_until_complete(start_server)
#     print("[SERVER] WebSocket server is running")
#     ws_loop.run_forever()
async def start_ws_server():
    server = await websockets.serve(handle_connection, "0.0.0.0", 8765)
    await server.wait_closed()

def run_websocket_server():
    loop = asyncio.new_event_loop()  # Create a new event loop
    asyncio.set_event_loop(loop)  # Set it as the current loop
    loop.run_until_complete(start_ws_server())  # Run the WebSocket server

if __name__ == "__main__":
    print("[SERVER] Starting Flask and WebSocket servers")

    # Start WebSocket server in a separate thread
    ws_thread = threading.Thread(target=run_websocket_server, daemon=True)
    ws_thread.start()

    # Start Flask server
    print("[FLASK] Running Flask server on http://0.0.0.0:5000")
    app.run(host="0.0.0.0", port=5000, threaded=True)  # Allow multi-threading

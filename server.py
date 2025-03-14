import os
import json
import requests
import threading
import eventlet
from flask import Flask, request, Response, jsonify
from flask_socketio import SocketIO, emit
import websocket

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="eventlet")

ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
ELEVENLABS_AGENT_ID = os.getenv("ELEVENLABS_AGENT_ID")

if not ELEVENLABS_API_KEY or not ELEVENLABS_AGENT_ID:
    raise ValueError("ELEVENLABS_API_KEY or ELEVENLABS_AGENT_ID is missing.")

elevenLabsWs = None

def get_signed_url():
    """Fetch signed WebSocket URL from ElevenLabs API."""
    url = f"https://api.elevenlabs.io/v1/convai/conversation/get_signed_url?agent_id={ELEVENLABS_AGENT_ID}"
    headers = {'xi-api-key': ELEVENLABS_API_KEY}
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.json().get('signed_url')

@app.route("/incoming-call-eleven", methods=['POST'])
def handle_incoming_call():
    """Handle incoming call from Exotel and return TwiML response."""
    caller_number = request.form.get("From")
    print(f"[Exotel] Incoming call from: {caller_number}")

    # Exotel Connect XML response
    xml_response = f"""<?xml version="1.0" encoding="UTF-8"?>
    <Response>
        <Connect>
            <Number>{caller_number}</Number>
        </Connect>
    </Response>"""

    return Response(xml_response, mimetype="text/xml")

@socketio.on("connect", namespace="/media-stream")
def handle_ws_connect():
    """Handle WebSocket connection from Exotel."""
    global elevenLabsWs
    print("[WebSocket] Connected to Exotel Media Stream")
    
    signed_url = get_signed_url()
    print(f"[INFO] Connecting to ElevenLabs WebSocket at {signed_url}")
    
    elevenLabsWs = websocket.WebSocketApp(
        signed_url,
        on_message=handle_elevenlabs_message,
        on_error=handle_ws_error,
        on_close=handle_ws_close
    )
    
    ws_thread = threading.Thread(target=elevenLabsWs.run_forever)
    ws_thread.start()
    
    emit("message", {"event": "connected"})

@socketio.on("message", namespace="/media-stream")
def handle_ws_message(message):
    """Handle media messages from Exotel WebSocket and forward to ElevenLabs."""
    global elevenLabsWs
    try:
        data = json.loads(message) if isinstance(message, str) else message
        event = data.get("event")

        if event == "media":
            print("[INFO] Received media chunk from Exotel.")
            if elevenLabsWs and elevenLabsWs.sock and elevenLabsWs.sock.connected:
                audio_msg = json.dumps({"user_audio_chunk": data["payload"]})
                elevenLabsWs.send(audio_msg)
    except Exception as e:
        print(f"[Error] {str(e)}")

def handle_elevenlabs_message(ws, message):
    """Handle AI-generated audio response and send it to Exotel."""
    try:
        data = json.loads(message)
        if "ai_audio_chunk" in data:
            print("[INFO] Sending AI-generated audio to Exotel.")
            socketio.emit("message", {"event": "media", "payload": data["ai_audio_chunk"]})
    except Exception as e:
        print(f"[ERROR] Failed to process ElevenLabs message: {str(e)}")

def handle_ws_error(ws, error):
    """Handle WebSocket errors."""
    print(f"[ERROR] WebSocket error: {str(error)}")

def handle_ws_close(ws, close_status_code, close_msg):
    """Handle WebSocket closure."""
    global elevenLabsWs
    print("[WebSocket] Disconnected from ElevenLabs")
    elevenLabsWs = None

if __name__ == "__main__":
    print("[SERVER] Starting Flask and WebSocket servers...")
    socketio.run(app, host="0.0.0.0", port=5000)

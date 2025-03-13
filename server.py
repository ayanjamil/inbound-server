from flask import Flask, request
from flask_socketio import SocketIO, emit
import requests
import json
import os
from dotenv import load_dotenv  # Load environment variables from .env

# Load .env file
load_dotenv()

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='gevent')

ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
ELEVENLABS_AGENT_ID = os.getenv("ELEVENLABS_AGENT_ID")

if not ELEVENLABS_API_KEY or not ELEVENLABS_AGENT_ID:
    raise ValueError("Missing ELEVENLABS_API_KEY or ELEVENLABS_AGENT_ID")

def get_signed_url():
    response = requests.get(
        f"https://api.elevenlabs.io/v1/convai/conversation/get_signed_url?agent_id={ELEVENLABS_AGENT_ID}",
        headers={'xi-api-key': ELEVENLABS_API_KEY}
    )
    response.raise_for_status()
    return response.json()['signed_url']

@app.route("/incoming-call-eleven", methods=['GET', 'POST'])
def handle_incoming_call():
    twiml_response = f'''<?xml version="1.0" encoding="UTF-8"?>
        <Response>
            <Connect>
                <Stream url="wss://{request.host}/media-stream" />
            </Connect>
        </Response>'''
    return twiml_response, 200, {'Content-Type': 'text/xml'}

@socketio.on('connect', namespace='/media-stream')
def handle_ws_connect():
    print("[WebSocket] Connected to Twilio Media Stream")
    socketio.emit("message", {"event": "connected"})

elevenLabsWs = None

@socketio.on("message")
def handle_ws_message(data):
    global elevenLabsWs
    try:
        message = json.loads(data)
        if message.get("event") == "start":
            stream_sid = message["start"]["streamSid"]
            print(f"[Twilio] Stream started with ID: {stream_sid}")
            socketio.emit("message", {"event": "ack", "streamSid": stream_sid})
            
            # Connect to ElevenLabs WebSocket
            signed_url = get_signed_url()
            elevenLabsWs = socketio.connect(signed_url)

        elif message.get("event") == "media":
            if elevenLabsWs and elevenLabsWs.connected:
                audio_message = {
                    "user_audio_chunk": message["media"]["payload"]
                }
                elevenLabsWs.send(json.dumps(audio_message))

        elif message.get("event") == "stop":
            if elevenLabsWs:
                elevenLabsWs.disconnect()
            print("[WebSocket] Stream ended.")
    
    except Exception as e:
        print(f"[Error] {str(e)}")

@socketio.on("disconnect")
def handle_ws_disconnect():
    print("[WebSocket] Disconnected from Twilio")

if __name__ == "__main__":
    print("[SERVER] Starting Flask and WebSocket servers")
    socketio.run(app, host="0.0.0.0", port=5000)
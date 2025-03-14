import os
import requests
from flask import Flask, request, Response
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
ELEVENLABS_AGENT_ID = os.getenv("ELEVENLABS_AGENT_ID")
EXOTEL_SID = os.getenv("EXOTEL_SID")
EXOTEL_API_KEY = os.getenv("EXOTEL_API_KEY")
EXOTEL_API_TOKEN = os.getenv("EXOTEL_API_TOKEN")

@app.route("/exotel-webhook", methods=["POST", "GET"])
def webhook():
    call_data = request.form.to_dict()
    from_number = request.form.get("From")
    call_sid = request.form.get("CallSid")
    recording_url = request.form.get("RecordingUrl")

    print(f"Received call from: {from_number}, Call SID: {call_sid}, Recording URL: {recording_url}")

    if not recording_url:
        return Response("Missing recording URL", status=400)

    # Send to ElevenLabs Conversational AI
    ai_response_url = get_ai_response(recording_url)

    if not ai_response_url:
        return Response("Failed to generate AI response", status=500)

    # Send AI response back to Exotel
    play_audio(call_sid, ai_response_url)

    return Response("AI response sent to Exotel", status=200)

def get_ai_response(audio_url):
    """Send recorded audio to ElevenLabs AI agent and get response"""
    api_url = f"https://api.elevenlabs.io/v1/convai/conversation/get_signed_url?agent_id={ELEVENLABS_AGENT_ID}"
    headers = {
        "Authorization": f"Bearer {ELEVENLABS_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "audio_url": audio_url
    }

    response = requests.post(api_url, json=payload, headers=headers)
    if response.status_code != 200:
        print("ElevenLabs API error:", response.text)
        return None

    response_data = response.json()
    return response_data.get("audio_url")

def play_audio(call_sid, audio_url):
    """Use Exotel API to play AI-generated response to the caller."""
    exotel_api_url = f"https://{EXOTEL_SID}:{EXOTEL_API_TOKEN}@api.exotel.com/v1/Accounts/{EXOTEL_SID}/Calls/connect"

    payload = {
        "From": "YourExotelNumber",
        "To": call_sid,  # This should be the same call SID received from Exotel
        "CallerId": "YourExotelCallerId",
        "Url": audio_url
    }
    
    auth = (EXOTEL_API_KEY, EXOTEL_API_TOKEN)
    
    response = requests.post(exotel_api_url, data=payload, auth=auth)
    
    if response.status_code == 200:
        print("Audio response played successfully!")
    else:
        print("Error playing AI response:", response.text)

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

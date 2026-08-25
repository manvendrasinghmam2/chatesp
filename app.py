import os
import io
import json
import wave
import tempfile
import subprocess

from flask import Flask, request, jsonify, send_file
import requests
import speech_recognition as sr


app = Flask(__name__)


# =========================================================
# CONFIG
# =========================================================

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")

# Female Piper voice
PIPER_MODEL = os.environ.get(
    "PIPER_MODEL",
    "en_US-amy-medium"
)

# Wake words
WAKE_WORDS = [
    "hello",
    "helo",
    "hey hello",
    "hello hello"
]


# =========================================================
# HOME
# =========================================================

@app.route("/", methods=["GET"])
def home():
    return jsonify({
        "status": "online",
        "service": "ESP32 Voice AI Server",
        "endpoints": [
            "/wake",
            "/uploadAudio",
            "/tts"
        ]
    })


# =========================================================
# SPEECH TO TEXT
# =========================================================

def speech_to_text(audio_bytes):

    recognizer = sr.Recognizer()

    try:

        audio_file = io.BytesIO(audio_bytes)

        with sr.AudioFile(audio_file) as source:

            audio = recognizer.record(source)

        # Google Speech Recognition
        text = recognizer.recognize_google(
            audio,
            language="en-IN"
        )

        return text.strip()

    except sr.UnknownValueError:

        return ""

    except Exception as e:

        print("STT ERROR:", e)

        return ""


# =========================================================
# WAKE DETECTION
# =========================================================

def is_wake_word(text):

    if not text:
        return False

    text = text.lower().strip()

    # Remove punctuation
    cleaned = ""

    for char in text:

        if char.isalnum() or char == " ":
            cleaned += char

    cleaned = " ".join(cleaned.split())

    for word in WAKE_WORDS:

        if word in cleaned:
            return True

    return False


# =========================================================
# /wake
# =========================================================

@app.route("/wake", methods=["POST"])
def wake():

    print()
    print("========== WAKE ==========")

    audio_bytes = request.get_data()

    print("Audio bytes:", len(audio_bytes))

    if not audio_bytes:

        return jsonify({
            "wake": False
        })

    text = speech_to_text(audio_bytes)

    print("Wake transcription:", text)

    wake_detected = is_wake_word(text)

    print("Wake:", wake_detected)

    print("==========================")

    return jsonify({
        "wake": wake_detected,
        "transcription": text
    })


# =========================================================
# AI RESPONSE
# =========================================================

def ask_ai(text):

    if not OPENAI_API_KEY:

        print("OPENAI_API_KEY missing")

        return (
            "I am online, but the AI API key "
            "has not been configured."
        )

    url = "https://api.openai.com/v1/chat/completions"

    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": "gpt-4o-mini",
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a helpful voice assistant. "
                    "Answer clearly and briefly because "
                    "your answer will be spoken aloud. "
                    "Do not use markdown."
                )
            },
            {
                "role": "user",
                "content": text
            }
        ],
        "temperature": 0.5,
        "max_tokens": 200
    }

    try:

        response = requests.post(
            url,
            headers=headers,
            json=payload,
            timeout=60
        )

        print("AI HTTP:", response.status_code)

        if response.status_code != 200:

            print("AI ERROR:", response.text)

            return "Sorry, I could not get an AI response."

        data = response.json()

        answer = (
            data["choices"][0]["message"]["content"]
            .strip()
        )

        return answer

    except Exception as e:

        print("AI REQUEST ERROR:", e)

        return "Sorry, I could not process your request."


# =========================================================
# /uploadAudio
# =========================================================

@app.route("/uploadAudio", methods=["POST"])
def upload_audio():

    print()
    print("========== AUDIO ==========")

    audio_bytes = request.get_data()

    print("Received bytes:", len(audio_bytes))

    if not audio_bytes:

        return jsonify({
            "status": "error",
            "message": "No audio received"
        }), 400

    # ESP32 sends audio/wav
    content_type = request.headers.get(
        "Content-Type",
        ""
    )

    print("Content-Type:", content_type)

    # Speech-to-text
    transcription = speech_to_text(audio_bytes)

    print("Transcription:", transcription)

    if not transcription:

        return jsonify({
            "status": "error",
            "message": "Could not understand speech",
            "transcription": "",
            "english_transcription": "",
            "hindi_transcription": "",
            "ai_reply": ""
        })

    # AI
    ai_reply = ask_ai(transcription)

    print("AI Reply:", ai_reply)

    print("===========================")

    return jsonify({
        "status": "ok",

        "transcription": transcription,

        "english_transcription": transcription,

        "hindi_transcription": "",

        "ai_reply": ai_reply
    })


# =========================================================
# PIPER TTS
# =========================================================

def generate_tts(text):

    print()
    print("========== TTS ==========")

    print("Text:", text)

    temp_file = tempfile.NamedTemporaryFile(
        suffix=".wav",
        delete=False
    )

    output_file = temp_file.name

    temp_file.close()

    try:

        command = [
            "python",
            "-m",
            "piper",

            "-m",
            PIPER_MODEL,

            "-f",
            output_file,

            "--",

            text
        ]

        print("Running Piper...")

        result = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=120
        )

        if result.returncode != 0:

            print("PIPER ERROR:")
            print(result.stderr)

            return None

        if not os.path.exists(output_file):

            print("Piper output missing")

            return None

        size = os.path.getsize(
            output_file
        )

        print("TTS WAV bytes:", size)

        return output_file

    except Exception as e:

        print("TTS ERROR:", e)

        return None


# =========================================================
# /tts
# =========================================================

@app.route("/tts", methods=["POST"])
def tts():

    print()
    print("========== /tts ==========")

    data = request.get_json(
        silent=True
    )

    if not data:

        return jsonify({
            "status": "error",
            "message": "JSON required"
        }), 400

    text = data.get("text", "")

    if not isinstance(text, str):

        return jsonify({
            "status": "error",
            "message": "text must be string"
        }), 400

    text = text.strip()

    if not text:

        return jsonify({
            "status": "error",
            "message": "Empty text"
        }), 400

    # Limit extremely long TTS requests
    if len(text) > 1000:

        text = text[:1000]

    wav_file = generate_tts(text)

    if not wav_file:

        return jsonify({
            "status": "error",
            "message": "TTS generation failed"
        }), 500

    try:

        response = send_file(
            wav_file,
            mimetype="audio/wav",
            as_attachment=False,
            download_name="response.wav"
        )

        # Delete temporary file after response
        @response.call_on_close
        def cleanup():

            try:

                if os.path.exists(wav_file):
                    os.remove(wav_file)

            except Exception as e:

                print(
                    "Cleanup error:",
                    e
                )

        return response

    except Exception as e:

        print("SEND WAV ERROR:", e)

        try:

            if os.path.exists(wav_file):
                os.remove(wav_file)

        except:
            pass

        return jsonify({
            "status": "error",
            "message": "Could not send WAV"
        }), 500


# =========================================================
# HEALTH CHECK
# =========================================================

@app.route("/health", methods=["GET"])
def health():

    return jsonify({
        "status": "healthy",
        "tts": "piper",
        "voice": PIPER_MODEL
    })


# =========================================================
# START
# =========================================================

if __name__ == "__main__":

    port = int(
        os.environ.get(
            "PORT",
            10000
        )
    )

    app.run(
        host="0.0.0.0",
        port=port
    )

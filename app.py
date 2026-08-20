from flask import Flask, request, jsonify
import os
import speech_recognition as sr
import requests
import json

app = Flask(__name__)

# =====================================================
# AI CONFIG
# =====================================================

AI_API_KEY = os.environ.get("AI_API_KEY")

AI_URL = os.environ.get(
    "AI_URL",
    "https://api.groq.com/openai/v1/chat/completions"
)

AI_MODEL = os.environ.get("AI_MODEL")


# =====================================================
# HOME
# =====================================================

@app.route("/")
def home():
    return "ESP32 Voice Server is ONLINE!"


# =====================================================
# HEALTH
# =====================================================

@app.route("/health")
def health():
    return jsonify({
        "status": "online",
        "speech_engine": "Google Speech Recognition",
        "ai_engine": "Hosted AI"
    })


# =====================================================
# TEST
# =====================================================

@app.route("/test", methods=["POST"])
def test():

    data = request.get_json(silent=True)

    if not data:
        return jsonify({
            "status": "error",
            "message": "No JSON received"
        }), 400

    print("ESP32 DATA:", data)

    return jsonify({
        "status": "ok",
        "message": "Data received"
    })


# =====================================================
# AI REPLY
# =====================================================

def get_ai_reply(text):

    if not AI_API_KEY:
        print("AI_API_KEY not configured")
        return "AI response nahi mil saka."

    if not AI_MODEL:
        print("AI_MODEL not configured")
        return "AI model configured nahi hai."

    system_prompt = """
You are a helpful voice assistant.

LANGUAGE RULES:

- Hindi input -> Hindi reply.
- English input -> English reply.
- Hinglish input -> Hinglish reply.
- Do not translate unnecessarily.
- Keep answers short and natural.
- This answer will be spoken by an ESP32 voice assistant.
- Do not use markdown.
- Do not use emojis.
"""

    payload = {
        "model": AI_MODEL,

        "messages": [
            {
                "role": "system",
                "content": system_prompt
            },
            {
                "role": "user",
                "content": text
            }
        ],

        "temperature": 0.4,
        "max_tokens": 150
    }

    headers = {
        "Authorization": "Bearer " + AI_API_KEY,
        "Content-Type": "application/json"
    }

    try:

        print()
        print("==============================")
        print("AI REQUEST")
        print("==============================")
        print("Input:", text)
        print("Model:", AI_MODEL)

        response = requests.post(
            AI_URL,
            headers=headers,
            json=payload,
            timeout=30
        )

        print("AI HTTP:", response.status_code)

        if response.status_code != 200:

            print("==============================")
            print("AI ERROR")
            print("==============================")
            print(response.text)
            print("==============================")

            return "AI response nahi mil saka."

        data = response.json()

        reply = (
            data
            .get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
        )

        reply = reply.strip()

        print()
        print("==============================")
        print("AI REPLY")
        print("==============================")
        print(reply)
        print("==============================")

        if not reply:
            return "AI response nahi mil saka."

        return reply

    except Exception as e:

        print()
        print("==============================")
        print("AI EXCEPTION")
        print("==============================")
        print(str(e))
        print("==============================")

        return "AI response nahi mil saka."


# =====================================================
# UPLOAD AUDIO
# =====================================================

@app.route("/uploadAudio", methods=["POST"])
def upload_audio():

    try:

        audio_data = request.get_data()

        if not audio_data:

            return jsonify({
                "status": "error",
                "message": "No audio received"
            }), 400

        print()
        print("==============================")
        print("AUDIO RECEIVED")
        print("==============================")
        print("Bytes:", len(audio_data))

        # -------------------------------------------------
        # SAVE WAV
        # -------------------------------------------------

        filename = "/tmp/audio.wav"

        with open(filename, "wb") as f:
            f.write(audio_data)

        # -------------------------------------------------
        # SPEECH RECOGNITION
        # -------------------------------------------------

        recognizer = sr.Recognizer()

        with sr.AudioFile(filename) as source:
            audio = recognizer.record(source)

        text = None

        # =================================================
        # HINDI
        # =================================================

        try:

            text = recognizer.recognize_google(
                audio,
                language="hi-IN"
            )

            print()
            print("HINDI RESULT:")
            print(text)

        except sr.UnknownValueError:

            text = None

        except sr.RequestError as e:

            return jsonify({
                "status": "error",
                "message": "Speech service error",
                "details": str(e)
            }), 500

        # =================================================
        # ENGLISH
        # =================================================

        if not text:

            try:

                text = recognizer.recognize_google(
                    audio,
                    language="en-IN"
                )

                print()
                print("ENGLISH RESULT:")
                print(text)

            except sr.UnknownValueError:

                return jsonify({
                    "status": "error",
                    "message": "Speech not understood"
                }), 400

            except sr.RequestError as e:

                return jsonify({
                    "status": "error",
                    "message": "Speech service error",
                    "details": str(e)
                }), 500

        # =================================================
        # TRANSCRIPTION
        # =================================================

        print()
        print("==============================")
        print("TRANSCRIPTION")
        print("==============================")
        print(text)
        print("==============================")

        # =================================================
        # AI
        # =================================================

        ai_reply = get_ai_reply(text)

        # =================================================
        # FINAL RESPONSE
        # =================================================

        response_data = {
            "status": "ok",
            "transcription": text,
            "ai_reply": ai_reply
        }

        # ensure_ascii=False
        # Hindi directly JSON me jayegi

        return app.response_class(
            response=json.dumps(
                response_data,
                ensure_ascii=False
            ),
            status=200,
            mimetype="application/json"
        )

    except Exception as e:

        print()
        print("==============================")
        print("ERROR")
        print("==============================")
        print(str(e))
        print("==============================")

        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


# =====================================================
# START
# =====================================================

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

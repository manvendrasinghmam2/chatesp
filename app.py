from flask import Flask, request, jsonify, Response
from groq import Groq
import os
import io
import wave
import tempfile
import requests
import urllib.parse

app = Flask(__name__)

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

if not GROQ_API_KEY:
    print("WARNING: GROQ_API_KEY NOT SET")
    client = None
else:
    client = Groq(api_key=GROQ_API_KEY)
    print("Groq client initialized")


@app.route("/")
def home():
    return "ESP32 AI SERVER OK", 200


@app.route("/health")
def health():
    return jsonify({
        "status": "online",
        "groq": client is not None,
        "upload": "enabled",
        "tts": "enabled",
        "stt": "whisper-large-v3-turbo",
        "ai": "openai/gpt-oss-20b"
    }), 200


def check_wav(data):
    try:
        bio = io.BytesIO(data)

        with wave.open(bio, "rb") as wav:
            channels = wav.getnchannels()
            sample_width = wav.getsampwidth()
            sample_rate = wav.getframerate()
            frames = wav.getnframes()

            print("--------------------------------")
            print("WAV INFO")
            print("--------------------------------")
            print("Channels:", channels)
            print("Sample Width:", sample_width)
            print("Sample Rate:", sample_rate)
            print("Frames:", frames)
            print("--------------------------------")

            return True

    except Exception as e:
        print("WAV ERROR:", repr(e))
        return False


# ============================================================
# VOICE AI
# ============================================================

@app.route("/uploadAudio", methods=["POST"])
def upload_audio():

    temp_path = None

    try:

        data = request.get_data()

        print()
        print("================================")
        print("UPLOAD AUDIO")
        print("================================")
        print("Bytes:", len(data))

        if not data:
            return jsonify({
                "status": "error",
                "message": "No audio received",
                "text": "",
                "ai_response": ""
            }), 400

        if not check_wav(data):
            return jsonify({
                "status": "error",
                "message": "Invalid WAV",
                "text": "",
                "ai_response": ""
            }), 400

        if client is None:
            return jsonify({
                "status": "error",
                "message": "GROQ_API_KEY missing",
                "text": "",
                "ai_response": ""
            }), 500

        temp_file = tempfile.NamedTemporaryFile(
            suffix=".wav",
            delete=False
        )

        temp_path = temp_file.name
        temp_file.write(data)
        temp_file.close()

        # ====================================================
        # STT
        # ====================================================

        print("Starting Whisper...")

        with open(temp_path, "rb") as audio_file:

            transcription = client.audio.transcriptions.create(
                file=audio_file,
                model="whisper-large-v3-turbo",
                prompt=(
                    "The speaker may speak Hindi, English, "
                    "or Hinglish. Transcribe exactly what "
                    "the speaker says."
                ),
                response_format="json",
                temperature=0.0
            )

        user_text = transcription.text.strip()

        print("USER:", user_text)

        if not user_text:
            return jsonify({
                "status": "ok",
                "bytes": len(data),
                "message": "Speech not understood",
                "text": "",
                "ai_response": ""
            }), 200

        # ====================================================
        # AI
        # ====================================================

        completion = client.chat.completions.create(

            model="openai/gpt-oss-20b",

            messages=[

                {
                    "role": "system",
                    "content": (
                        "You are a helpful voice assistant. "
                        "Understand Hindi, English and Hinglish. "
                        "Reply in the same language as the user. "
                        "Keep replies concise because the reply "
                        "will be spoken through a speaker. "
                        "Do not use markdown."
                    )
                },

                {
                    "role": "user",
                    "content": user_text
                }

            ],

            temperature=0.3,
            max_completion_tokens=200,
            reasoning_effort="low"
        )

        ai_response = (
            completion.choices[0].message.content.strip()
        )

        print("AI:", ai_response)

        return jsonify({
            "status": "ok",
            "bytes": len(data),
            "message": "Audio processed successfully",
            "text": user_text,
            "ai_response": ai_response
        }), 200

    except Exception as e:

        print("ERROR:", repr(e))

        return jsonify({
            "status": "error",
            "message": "Audio processing failed",
            "error": str(e),
            "text": "",
            "ai_response": ""
        }), 500

    finally:

        if temp_path:

            try:
                os.remove(temp_path)
            except:
                pass


# ============================================================
# TTS
# ============================================================

@app.route("/tts", methods=["GET"])
def tts():

    text = request.args.get("text", "").strip()
    lang = request.args.get("lang", "en")

    print()
    print("================================")
    print("TTS REQUEST")
    print("================================")
    print("Text:", text)
    print("Language:", lang)

    if not text:
        return jsonify({
            "status": "error",
            "message": "No text"
        }), 400

    try:

        # ----------------------------------------------------
        # IMPORTANT
        # Replace this section with your actual TTS provider.
        # ESP32 expects AUDIO DATA, not JSON.
        # ----------------------------------------------------

        # Example using Google Translate TTS endpoint
        encoded = urllib.parse.quote(text)

        url = (
            "https://translate.google.com/translate_tts"
            "?ie=UTF-8"
            "&client=tw-ob"
            "&tl=" + urllib.parse.quote(lang) +
            "&q=" + encoded
        )

        print("TTS URL:")
        print(url)

        r = requests.get(
            url,
            headers={
                "User-Agent": "Mozilla/5.0"
            },
            timeout=20
        )

        print("TTS STATUS:", r.status_code)
        print("TTS BYTES:", len(r.content))

        if r.status_code != 200:
            return jsonify({
                "status": "error",
                "message": "TTS provider failed",
                "code": r.status_code
            }), 500

        return Response(
            r.content,
            status=200,
            mimetype="audio/mpeg",
            headers={
                "Content-Length": str(len(r.content)),
                "Cache-Control": "no-cache"
            }
        )

    except Exception as e:

        print("TTS ERROR:", repr(e))

        return jsonify({
            "status": "error",
            "message": "TTS failed",
            "error": str(e)
        }), 500


# ============================================================
# START
# ============================================================

if __name__ == "__main__":

    port = int(
        os.environ.get("PORT", 10000)
    )

    print("================================")
    print("ESP32 AI SERVER")
    print("PORT:", port)
    print("================================")

    app.run(
        host="0.0.0.0",
        port=port
    )

from flask import Flask, request, jsonify
import os
import tempfile
import speech_recognition as sr
from groq import Groq

app = Flask(__name__)

app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024

# ============================================================
# GROQ
# ============================================================

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

groq_client = None

if GROQ_API_KEY:
    groq_client = Groq(api_key=GROQ_API_KEY)
    print("Groq client initialized")
else:
    print("WARNING: GROQ_API_KEY not found")


# ============================================================
# HOME
# ============================================================

@app.route("/", methods=["GET"])
def home():

    return "ESP32 AI SERVER OK", 200


# ============================================================
# HEALTH
# ============================================================

@app.route("/health", methods=["GET"])
def health():

    return jsonify({
        "status": "online",
        "upload_test": "enabled",
        "ai_engine": "Groq",
        "model": "openai/gpt-oss-20b",
        "speech_engine": "Google Speech Recognition",
        "tts": "Google TTS"
    }), 200


# ============================================================
# AI
# ============================================================

def ask_groq(text):

    if not groq_client:
        raise Exception("GROQ_API_KEY missing")

    print("================================")
    print("GROQ AI")
    print("================================")

    print("USER:", text)

    response = groq_client.chat.completions.create(

        model="openai/gpt-oss-20b",

        messages=[
            {
                "role": "system",
                "content": (
                    "You are a helpful voice assistant. "
                    "Reply naturally and concisely. "
                    "If the user speaks Hindi, reply in Hindi. "
                    "If the user speaks English, reply in English."
                )
            },
            {
                "role": "user",
                "content": text
            }
        ],

        max_completion_tokens=300
    )

    answer = response.choices[0].message.content

    print("AI:", answer)

    return answer


# ============================================================
# SPEECH TO TEXT
# ============================================================

def speech_to_text(audio_data):

    print("================================")
    print("SPEECH TO TEXT")
    print("================================")

    recognizer = sr.Recognizer()

    temp_path = None

    try:

        # Temporary WAV file
        with tempfile.NamedTemporaryFile(
            suffix=".wav",
            delete=False
        ) as f:

            f.write(audio_data)

            temp_path = f.name

        print("TEMP WAV:", temp_path)
        print("AUDIO BYTES:", len(audio_data))

        with sr.AudioFile(temp_path) as source:

            audio = recognizer.record(source)

        print("Sending audio to Google Speech Recognition...")

        text = recognizer.recognize_google(
            audio,
            language="hi-IN"
        )

        print("RECOGNIZED TEXT:", text)

        return text

    finally:

        if temp_path:

            try:
                os.remove(temp_path)
            except:
                pass


# ============================================================
# UPLOAD AUDIO
# ============================================================

@app.route("/uploadAudio", methods=["POST"])
def upload_audio():

    print()
    print("################################")
    print("UPLOAD AUDIO REQUEST")
    print("################################")

    print("METHOD:", request.method)
    print("CONTENT TYPE:", request.content_type)
    print("CONTENT LENGTH:", request.content_length)

    try:

        # ----------------------------------------------------
        # READ AUDIO
        # ----------------------------------------------------

        data = request.get_data(
            cache=False,
            as_text=False
        )

        size = len(data)

        print("AUDIO RECEIVED")
        print("BYTES:", size)

        if size == 0:

            return jsonify({
                "status": "error",
                "message": "Empty audio",
                "bytes": 0
            }), 400


        # ----------------------------------------------------
        # WAV CHECK
        # ----------------------------------------------------

        if size < 12:

            return jsonify({
                "status": "error",
                "message": "Audio too small",
                "bytes": size
            }), 400


        riff = data[0:4]
        wave = data[8:12]

        print("RIFF:", riff)
        print("WAVE:", wave)

        if riff != b"RIFF" or wave != b"WAVE":

            print("WARNING: Invalid WAV header")


        # ----------------------------------------------------
        # SPEECH TO TEXT
        # ----------------------------------------------------

        try:

            user_text = speech_to_text(data)

        except sr.UnknownValueError:

            print("SPEECH NOT UNDERSTOOD")

            return jsonify({
                "status": "ok",
                "message": "Audio received but speech not understood",
                "bytes": size,
                "text": "",
                "ai_response": ""
            }), 200

        except sr.RequestError as e:

            print("GOOGLE SPEECH ERROR:", repr(e))

            return jsonify({
                "status": "error",
                "message": "Speech recognition service failed",
                "error": str(e)
            }), 502


        # ----------------------------------------------------
        # GROQ
        # ----------------------------------------------------

        try:

            ai_response = ask_groq(user_text)

        except Exception as e:

            print("GROQ ERROR:", repr(e))

            return jsonify({
                "status": "error",
                "message": "Groq AI failed",
                "text": user_text,
                "error": str(e)
            }), 500


        # ----------------------------------------------------
        # FINAL RESPONSE
        # ----------------------------------------------------

        print()
        print("################################")
        print("AI PIPELINE SUCCESS")
        print("################################")

        print("TEXT:", user_text)
        print("AI:", ai_response)
        print("BYTES:", size)

        return jsonify({

            "status": "ok",

            "message": "Audio processed",

            "bytes": size,

            "text": user_text,

            "ai_response": ai_response

        }), 200


    except Exception as e:

        print()
        print("################################")
        print("UPLOAD ERROR")
        print("################################")

        print(repr(e))

        return jsonify({

            "status": "error",

            "message": "Audio processing failed",

            "error": str(e)

        }), 500


# ============================================================
# ERROR 413
# ============================================================

@app.errorhandler(413)
def too_large(error):

    return jsonify({

        "status": "error",

        "message": "Audio file too large"

    }), 413


# ============================================================
# MAIN
# ============================================================

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

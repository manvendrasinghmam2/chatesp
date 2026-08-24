from flask import Flask, request, jsonify
import os
import io
import wave
import speech_recognition as sr
from groq import Groq

app = Flask(__name__)

# ==============================
# CONFIG
# ==============================

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

if not GROQ_API_KEY:
    print("WARNING: GROQ_API_KEY not found")

groq_client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

MODEL = "openai/gpt-oss-20b"


# ==============================
# HOME
# ==============================

@app.route("/")
def home():
    return "ESP32 AI SERVER OK", 200


# ==============================
# HEALTH
# ==============================

@app.route("/health")
def health():
    return jsonify({
        "status": "online",
        "ai_engine": "Groq",
        "model": MODEL,
        "speech_engine": "Google Speech Recognition",
        "upload_endpoint": "/uploadAudio",
        "tts_endpoint": "/tts"
    }), 200


# ==============================
# UPLOAD AUDIO
# ==============================

@app.route("/uploadAudio", methods=["POST"])
def upload_audio():

    print("\n================================")
    print("UPLOAD AUDIO REQUEST RECEIVED")
    print("================================")

    try:

        print("Method:", request.method)
        print("Content-Type:", request.content_type)
        print("Content-Length:", request.content_length)

        # --------------------------
        # RECEIVE AUDIO
        # --------------------------

        data = request.get_data()

        print("AUDIO RECEIVED")
        print("Bytes:", len(data))

        if not data:
            return jsonify({
                "status": "error",
                "error": "No audio received"
            }), 400

        # --------------------------
        # CHECK WAV
        # --------------------------

        try:
            wav_file = io.BytesIO(data)

            with wave.open(wav_file, "rb") as wf:
                channels = wf.getnchannels()
                sample_width = wf.getsampwidth()
                sample_rate = wf.getframerate()
                frames = wf.getnframes()

            print("WAV OK")
            print("Channels:", channels)
            print("Sample Width:", sample_width)
            print("Sample Rate:", sample_rate)
            print("Frames:", frames)

        except Exception as e:

            print("WAV ERROR:", repr(e))

            return jsonify({
                "status": "error",
                "error": "Invalid WAV file",
                "details": str(e)
            }), 400

        # --------------------------
        # SPEECH RECOGNITION
        # --------------------------

        print("\n================================")
        print("SPEECH RECOGNITION")
        print("================================")

        recognizer = sr.Recognizer()

        audio_buffer = io.BytesIO(data)

        with sr.AudioFile(audio_buffer) as source:

            print("Reading audio...")

            audio = recognizer.record(source)

        print("Sending to Google Speech Recognition...")

        try:

            text = recognizer.recognize_google(
                audio,
                language="hi-IN"
            )

            print("SPEECH TEXT:")
            print(text)

        except sr.UnknownValueError:

            print("SPEECH NOT UNDERSTOOD")

            return jsonify({
                "status": "ok",
                "text": "",
                "response": "माफ कीजिए, मैं आपकी आवाज़ समझ नहीं पाया।"
            }), 200

        except sr.RequestError as e:

            print("GOOGLE SPEECH ERROR:", repr(e))

            return jsonify({
                "status": "error",
                "error": "Speech recognition service unavailable",
                "details": str(e)
            }), 500

        # --------------------------
        # GROQ AI
        # --------------------------

        print("\n================================")
        print("GROQ AI")
        print("================================")

        if not groq_client:

            return jsonify({
                "status": "error",
                "error": "GROQ_API_KEY not configured"
            }), 500

        print("User:", text)
        print("Model:", MODEL)

        try:

            completion = groq_client.chat.completions.create(

                model=MODEL,

                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a helpful Hindi voice assistant. "
                            "Answer naturally and briefly because your "
                            "response will be converted to speech. "
                            "Prefer Hindi when the user speaks Hindi."
                        )
                    },
                    {
                        "role": "user",
                        "content": text
                    }
                ],

                max_completion_tokens=300,

                temperature=0.4
            )

            answer = completion.choices[0].message.content

            print("GROQ RESPONSE:")
            print(answer)

        except Exception as e:

            print("GROQ ERROR:", repr(e))

            return jsonify({
                "status": "error",
                "error": "Groq AI failed",
                "details": str(e)
            }), 500

        # --------------------------
        # FINAL RESPONSE
        # --------------------------

        print("\n================================")
        print("REQUEST COMPLETE")
        print("================================")

        return jsonify({

            "status": "ok",

            "bytes": len(data),

            "text": text,

            "response": answer

        }), 200

    except Exception as e:

        print("\nUPLOAD ERROR:")
        print(repr(e))

        return jsonify({

            "status": "error",

            "error": str(e)

        }), 500


# ==============================
# TTS
# ==============================

@app.route("/tts")
def tts():

    text = request.args.get("text", "")
    lang = request.args.get("lang", "hi")

    print("\n================================")
    print("TTS REQUEST")
    print("================================")

    print("LANG:", lang)
    print("TEXT:", text)

    if not text:

        return jsonify({
            "status": "error",
            "error": "No text"
        }), 400

    try:

        from gtts import gTTS

        audio = io.BytesIO()

        tts = gTTS(
            text=text,
            lang=lang
        )

        tts.write_to_fp(audio)

        audio.seek(0)

        from flask import Response

        return Response(
            audio.read(),
            mimetype="audio/mpeg",
            headers={
                "Content-Disposition": "inline"
            }
        )

    except Exception as e:

        print("TTS ERROR:", repr(e))

        return jsonify({
            "status": "error",
            "error": str(e)
        }), 500


# ==============================
# RUN
# ==============================

if __name__ == "__main__":

    port = int(
        os.environ.get("PORT", 10000)
    )

    app.run(
        host="0.0.0.0",
        port=port
    )

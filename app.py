from flask import Flask, request, jsonify, send_file
from groq import Groq
import os
import io
import wave
import tempfile
import urllib.parse

from gtts import gTTS


app = Flask(__name__)


# ============================================================
# GROQ
# ============================================================

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

if GROQ_API_KEY:
    client = Groq(api_key=GROQ_API_KEY)
    print("GROQ CLIENT: OK")
else:
    client = None
    print("GROQ CLIENT: MISSING")


# ============================================================
# CONFIG
# ============================================================

STT_MODEL = "whisper-large-v3-turbo"
AI_MODEL = "openai/gpt-oss-20b"

MAX_AI_TOKENS = 250


# ============================================================
# HOME
# ============================================================

@app.route("/")
def home():

    return jsonify({
        "status": "online",
        "service": "ESP32 Voice AI",
        "stt": STT_MODEL,
        "ai": AI_MODEL,
        "tts": "gTTS",
        "wake": "/wake",
        "upload": "/uploadAudio",
        "tts_endpoint": "/tts"
    })


# ============================================================
# HEALTH
# ============================================================

@app.route("/health")
def health():

    return jsonify({

        "status": "online",

        "groq": client is not None,

        "stt": STT_MODEL,

        "ai": AI_MODEL,

        "tts": "gTTS",

        "wake": True

    }), 200


# ============================================================
# WAV INFO
# ============================================================

def wav_info(data):

    try:

        bio = io.BytesIO(data)

        with wave.open(bio, "rb") as wav:

            channels = wav.getnchannels()
            width = wav.getsampwidth()
            rate = wav.getframerate()
            frames = wav.getnframes()

            duration = 0

            if rate > 0:
                duration = frames / float(rate)

            print("--------------------------------")
            print("WAV INFO")
            print("--------------------------------")
            print("Duration:", duration)
            print("Frames:", frames)
            print("Sample Rate:", rate)
            print("Sample Width:", width)
            print("Channels:", channels)
            print("--------------------------------")

            return {
                "duration": duration,
                "frames": frames,
                "sample_rate": rate,
                "sample_width": width,
                "channels": channels
            }

    except Exception as e:

        print("WAV ERROR:", repr(e))

        return None


# ============================================================
# SAVE TEMP WAV
# ============================================================

def save_wav(data):

    f = tempfile.NamedTemporaryFile(
        suffix=".wav",
        delete=False
    )

    path = f.name

    f.write(data)
    f.flush()
    f.close()

    return path


# ============================================================
# TRANSCRIBE
# ============================================================

def transcribe(path):

    print()
    print("================================")
    print("WHISPER STT")
    print("================================")

    print("MODEL:", STT_MODEL)

    with open(path, "rb") as audio:

        result = client.audio.transcriptions.create(

            file=audio,

            model=STT_MODEL,

            prompt=(
                "The speaker can speak Hindi, English, "
                "or Hinglish. "
                "Transcribe what the speaker actually says. "
                "Do not translate. "
                "Preserve Hindi and Hinglish naturally."
            ),

            response_format="json",

            temperature=0.0
        )

    text = result.text.strip()

    print("TEXT:", text)

    return text


# ============================================================
# AI
# ============================================================

def ask_ai(text):

    print()
    print("================================")
    print("GROQ AI")
    print("================================")

    print("MODEL:", AI_MODEL)
    print("USER:", text)

    completion = client.chat.completions.create(

        model=AI_MODEL,

        messages=[

            {
                "role": "system",

                "content": (
                    "You are a voice assistant. "

                    "The user may speak Hindi, English, "
                    "or Hinglish. "

                    "Understand all three. "

                    "If the user speaks Hindi, answer in Hindi. "

                    "If the user speaks English, answer in English. "

                    "If the user speaks Hinglish, answer in natural "
                    "Hinglish. "

                    "Keep answers short and natural because the "
                    "answer will be spoken through a speaker. "

                    "Do not use markdown. "

                    "Do not use emojis. "
                )
            },

            {
                "role": "user",
                "content": text
            }

        ],

        temperature=0.3,

        max_completion_tokens=MAX_AI_TOKENS,

        reasoning_effort="low"
    )

    answer = (
        completion
        .choices[0]
        .message
        .content
        .strip()
    )

    print()
    print("AI RESPONSE:")
    print(answer)

    return answer


# ============================================================
# WAKE WORD CHECK
# ============================================================

def is_wake_word(text):

    if not text:
        return False

    t = text.lower().strip()

    print("WAKE CHECK:", t)

    wake_words = [

        "hello",

        "hello wolne",

        "hello wolfram",

        "hello wolven",

        "hey hello",

        "hello assistant",

        "हेलो",

        "हैलो"

    ]

    for word in wake_words:

        if word in t:
            return True

    return False


# ============================================================
# WAKE ENDPOINT
# ============================================================

@app.route("/wake", methods=["POST"])
def wake():

    print()
    print("================================")
    print("WAKE WORD REQUEST")
    print("================================")

    try:

        data = request.get_data()

        print("BYTES:", len(data))

        if not data:

            return jsonify({

                "status": "error",

                "wake": False,

                "text": ""

            }), 400


        info = wav_info(data)

        if info is None:

            return jsonify({

                "status": "error",

                "wake": False,

                "text": "",

                "message": "Invalid WAV"

            }), 400


        if client is None:

            return jsonify({

                "status": "error",

                "wake": False,

                "message": "GROQ_API_KEY missing"

            }), 500


        path = save_wav(data)

        try:

            text = transcribe(path)

        finally:

            try:
                os.remove(path)
            except:
                pass


        print("WAKE TEXT:", text)

        detected = is_wake_word(text)


        if detected:

            print("################################")
            print("WAKE WORD DETECTED")
            print("################################")

            return jsonify({

                "status": "ok",

                "wake": True,

                "active_seconds": 120,

                "text": text,

                "message": "Voice assistant activated"

            }), 200


        return jsonify({

            "status": "ok",

            "wake": False,

            "text": text

        }), 200


    except Exception as e:

        print("WAKE ERROR:", repr(e))

        return jsonify({

            "status": "error",

            "wake": False,

            "text": "",

            "error": str(e)

        }), 500


# ============================================================
# MAIN VOICE AI
# ============================================================

@app.route("/uploadAudio", methods=["POST"])
def upload_audio():

    print()
    print("================================")
    print("VOICE AI REQUEST")
    print("================================")

    temp_path = None

    try:

        data = request.get_data()

        print("AUDIO BYTES:", len(data))

        if not data:

            return jsonify({

                "status": "error",

                "message": "No audio",

                "text": "",

                "ai_response": ""

            }), 400


        # ----------------------------------------------------
        # WAV
        # ----------------------------------------------------

        info = wav_info(data)

        if info is None:

            return jsonify({

                "status": "error",

                "message": "Invalid WAV",

                "text": "",

                "ai_response": ""

            }), 400


        # ----------------------------------------------------
        # GROQ
        # ----------------------------------------------------

        if client is None:

            return jsonify({

                "status": "error",

                "message": "GROQ_API_KEY missing",

                "text": "",

                "ai_response": ""

            }), 500


        # ----------------------------------------------------
        # SAVE
        # ----------------------------------------------------

        temp_path = save_wav(data)

        # ----------------------------------------------------
        # STT
        # ----------------------------------------------------

        user_text = transcribe(temp_path)

        if not user_text:

            return jsonify({

                "status": "ok",

                "bytes": len(data),

                "message": "No speech detected",

                "text": "",

                "ai_response": ""

            }), 200


        # ----------------------------------------------------
        # AI
        # ----------------------------------------------------

        ai_response = ask_ai(user_text)


        # ----------------------------------------------------
        # SUCCESS
        # ----------------------------------------------------

        print()
        print("################################")
        print("AI PIPELINE SUCCESS")
        print("################################")

        return jsonify({

            "status": "ok",

            "bytes": len(data),

            "message": "Audio processed successfully",

            "text": user_text,

            "ai_response": ai_response

        }), 200


    except Exception as e:

        print()
        print("================================")
        print("VOICE AI ERROR")
        print("================================")

        print(repr(e))

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

    print()
    print("================================")
    print("TTS REQUEST")
    print("================================")

    try:

        text = request.args.get(
            "text",
            ""
        ).strip()

        lang = request.args.get(
            "lang",
            "en"
        ).strip()


        print("TEXT:", text)
        print("LANG:", lang)


        if not text:

            return jsonify({

                "status": "error",

                "message": "No text"

            }), 400


        # ----------------------------------------------------
        # LANGUAGE
        # ----------------------------------------------------

        lower = text.lower()

        # Hindi unicode detected
        has_hindi = any(
            "\u0900" <= c <= "\u097f"
            for c in text
        )

        if has_hindi:

            language = "hi"

        elif lang in ["hi", "en"]:

            language = lang

        else:

            language = "en"


        # ----------------------------------------------------
        # TEMP MP3
        # ----------------------------------------------------

        output = tempfile.NamedTemporaryFile(
            suffix=".mp3",
            delete=False
        )

        path = output.name

        output.close()


        print("Generating TTS...")
        print("LANGUAGE:", language)


        tts = gTTS(

            text=text,

            lang=language,

            slow=False
        )


        tts.save(path)


        print("TTS CREATED")


        # ----------------------------------------------------
        # SEND MP3
        # ----------------------------------------------------

        response = send_file(

            path,

            mimetype="audio/mpeg",

            as_attachment=False,

            download_name="reply.mp3"
        )


        # delete after response
        @response.call_on_close
        def cleanup():

            try:
                os.remove(path)
                print("TTS FILE DELETED")
            except:
                pass


        return response


    except Exception as e:

        print()
        print("TTS ERROR:")
        print(repr(e))

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
        os.environ.get(
            "PORT",
            10000
        )
    )

    print()
    print("================================")
    print("ESP32 VOICE AI SERVER")
    print("================================")

    print("PORT:", port)

    app.run(

        host="0.0.0.0",

        port=port,

        threaded=True
    )

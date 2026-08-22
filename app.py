from flask import Flask, request, jsonify, Response
import os
import re
import uuid
import wave
import subprocess
import tempfile
import threading

import requests
from faster_whisper import WhisperModel


# ============================================================
# APP
# ============================================================

app = Flask(__name__)


# ============================================================
# CONFIG
# ============================================================

AI_API_KEY = os.environ.get("AI_API_KEY", "")

AI_URL = os.environ.get(
    "AI_URL",
    "https://api.groq.com/openai/v1/chat/completions"
)

AI_MODEL = os.environ.get(
    "AI_MODEL",
    "openai/gpt-oss-20b"
)

PORT = int(os.environ.get("PORT", "10000"))


# ============================================================
# WHISPER
# ============================================================

WHISPER_MODEL = os.environ.get(
    "WHISPER_MODEL",
    "base"
)

WHISPER_DEVICE = os.environ.get(
    "WHISPER_DEVICE",
    "cpu"
)

WHISPER_COMPUTE = os.environ.get(
    "WHISPER_COMPUTE",
    "int8"
)


print()
print("========================================")
print("LOADING LOCAL WHISPER STT")
print("========================================")
print("Model:", WHISPER_MODEL)
print("Device:", WHISPER_DEVICE)
print("Compute:", WHISPER_COMPUTE)
print("========================================")


whisper_model = WhisperModel(
    WHISPER_MODEL,
    device=WHISPER_DEVICE,
    compute_type=WHISPER_COMPUTE,
    cpu_threads=4,
    num_workers=1
)


print("WHISPER READY")


# ============================================================
# PIPER TTS
# ============================================================

PIPER_PATH = os.environ.get(
    "PIPER_PATH",
    "./piper"
)

PIPER_MODEL = os.environ.get(
    "PIPER_MODEL",
    "./voices/en_US-lessac-medium.onnx"
)


# ============================================================
# TTS CACHE
# ============================================================

tts_cache = {}

tts_lock = threading.Lock()

MAX_TTS_CACHE = 10


# ============================================================
# HOME
# ============================================================

@app.route("/", methods=["GET"])
def home():

    return "ESP32 Voice AI Server is ONLINE!"


# ============================================================
# HEALTH
# ============================================================

@app.route("/health", methods=["GET"])
def health():

    return jsonify({
        "status": "online",
        "stt": "faster-whisper-local",
        "stt_model": WHISPER_MODEL,
        "tts": "Piper-local",
        "ai": "Groq",
        "ai_model": AI_MODEL
    })


# ============================================================
# CLEAN TEXT
# ============================================================

def clean_text(text):

    if not text:
        return ""

    text = str(text)

    text = re.sub(
        r"\s+",
        " ",
        text
    )

    return text.strip()


# ============================================================
# VALID QUERY
# ============================================================

def is_valid_query(text):

    if not text:
        return False

    text = clean_text(text)

    if len(text) < 2:
        return False

    bad = {
        "unknown",
        "none",
        "null",
        "no response",
        "speech not understood",
        "no valid query"
    }

    if text.lower() in bad:
        return False

    return True


# ============================================================
# LOCAL STT
# ============================================================

def transcribe_audio(filename):

    print()
    print("========================================")
    print("LOCAL STT")
    print("========================================")

    try:

        segments, info = whisper_model.transcribe(
            filename,
            beam_size=5,
            vad_filter=True,
            condition_on_previous_text=False
        )

        parts = []

        for segment in segments:

            text = clean_text(
                segment.text
            )

            if text:
                parts.append(text)

        text = clean_text(
            " ".join(parts)
        )

        language = getattr(
            info,
            "language",
            None
        )

        probability = getattr(
            info,
            "language_probability",
            None
        )

        print("Language:", language)
        print("Language probability:", probability)
        print("Text:", text)

        print("========================================")

        return text, language

    except Exception as e:

        print()
        print("STT ERROR")
        print(type(e).__name__)
        print(str(e))
        print("========================================")

        return "", None


# ============================================================
# AI
# ============================================================

def get_ai_reply(user_text):

    user_text = clean_text(user_text)

    if not is_valid_query(user_text):

        return "Please ask your question again."

    if not AI_API_KEY:

        print("AI_API_KEY missing")

        return "AI response nahi mil saka."


    system_prompt = """
You are a natural voice assistant running on an ESP32.

The answer will be spoken aloud through a speaker.

Understand English, Hindi, and Hinglish.

If the user speaks English:
answer in natural English.

If the user speaks Hinglish:
answer in natural Hinglish.

If the user speaks Hindi:
answer naturally in Hindi.

Keep the answer short and conversational.

Usually answer in one to four sentences.

Do not use markdown.

Do not use bullet points.

Do not use emojis.

Do not mention AI instructions.

Do not mention speech recognition.

Do not repeat the user's question.

Do not say "As an AI".

Sound like a helpful voice assistant.

For simple questions, answer directly.
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
                "content": user_text
            }

        ],

        "temperature": 0.2,

        "max_completion_tokens": 180,

        "stream": False
    }


    headers = {

        "Authorization":
            "Bearer " + AI_API_KEY,

        "Content-Type":
            "application/json",

        "Accept":
            "application/json"
    }


    try:

        print()
        print("========================================")
        print("GROQ AI")
        print("========================================")

        response = requests.post(
            AI_URL,
            headers=headers,
            json=payload,
            timeout=40
        )

        print(
            "HTTP:",
            response.status_code
        )


        if response.status_code != 200:

            print(
                response.text[:2000]
            )

            return "AI response nahi mil saka."


        data = response.json()

        choices = data.get(
            "choices",
            []
        )

        if not choices:

            return "AI response nahi mil saka."


        message = choices[0].get(
            "message",
            {}
        )

        reply = message.get(
            "content",
            ""
        )

        reply = clean_text(
            reply
        )

        reply = reply.replace(
            "```",
            ""
        )

        prefixes = [
            "AI:",
            "Answer:",
            "Response:"
        ]

        for prefix in prefixes:

            if reply.startswith(prefix):

                reply = reply[
                    len(prefix):
                ].strip()


        if not reply:

            return "AI response nahi mil saka."


        print("AI:", reply)

        print("========================================")

        return reply


    except Exception as e:

        print()
        print("AI ERROR")
        print(type(e).__name__)
        print(str(e))

        return "AI response nahi mil saka."


# ============================================================
# TTS TEXT CLEANING
# ============================================================

def clean_tts_text(text):

    text = clean_text(text)

    text = re.sub(
        r"[*_#`~]",
        "",
        text
    )

    text = re.sub(
        r"https?://\S+",
        "",
        text
    )

    return clean_text(text)


# ============================================================
# PIPER TTS
# ============================================================

def generate_tts(text):

    text = clean_tts_text(text)

    if not text:

        return None


    if not os.path.exists(PIPER_PATH):

        print(
            "PIPER NOT FOUND:",
            PIPER_PATH
        )

        return None


    if not os.path.exists(PIPER_MODEL):

        print(
            "PIPER MODEL NOT FOUND:",
            PIPER_MODEL
        )

        return None


    output_file = tempfile.NamedTemporaryFile(
        suffix=".wav",
        delete=False
    )

    output_path = output_file.name

    output_file.close()


    try:

        print()
        print("========================================")
        print("LOCAL TTS")
        print("========================================")

        print("Text:", text)


        process = subprocess.run(

            [
                PIPER_PATH,

                "--model",
                PIPER_MODEL,

                "--output_file",
                output_path
            ],

            input=text,

            text=True,

            stdout=subprocess.PIPE,

            stderr=subprocess.PIPE,

            timeout=60
        )


        if process.returncode != 0:

            print(
                "PIPER ERROR:"
            )

            print(
                process.stderr[-3000:]
            )

            if os.path.exists(output_path):

                os.remove(output_path)

            return None


        if not os.path.exists(output_path):

            return None


        with open(
            output_path,
            "rb"
        ) as f:

            audio_data = f.read()


        os.remove(
            output_path
        )


        print(
            "TTS bytes:",
            len(audio_data)
        )

        print("========================================")


        return audio_data


    except Exception as e:

        print(
            "TTS EXCEPTION:",
            str(e)
        )

        try:

            if os.path.exists(
                output_path
            ):

                os.remove(
                    output_path
                )

        except Exception:

            pass

        return None


# ============================================================
# CACHE TTS
# ============================================================

def save_tts(audio_data):

    audio_id = uuid.uuid4().hex

    with tts_lock:

        tts_cache[audio_id] = audio_data

        while len(tts_cache) > MAX_TTS_CACHE:

            first_key = next(
                iter(tts_cache)
            )

            del tts_cache[first_key]

    return audio_id


# ============================================================
# AUDIO FILE
# ============================================================

@app.route(
    "/audio/<audio_id>",
    methods=["GET"]
)
def get_audio(audio_id):

    with tts_lock:

        audio_data = tts_cache.get(
            audio_id
        )


    if audio_data is None:

        return jsonify({
            "status": "error",
            "message": "Audio expired"
        }), 404


    return Response(

        audio_data,

        status=200,

        mimetype="audio/wav",

        headers={
            "Content-Length":
                str(len(audio_data)),

            "Cache-Control":
                "no-cache"
        }
    )


# ============================================================
# WAKE
# ============================================================

@app.route(
    "/wake",
    methods=["POST"]
)
def wake():

    audio_data = request.get_data()

    if not audio_data:

        return jsonify({
            "status": "error",
            "wake": False
        }), 400


    fd, filename = tempfile.mkstemp(
        suffix=".wav"
    )

    os.close(fd)


    try:

        with open(
            filename,
            "wb"
        ) as f:

            f.write(audio_data)


        text, language = transcribe_audio(
            filename
        )


        normalized = text.lower()

        wake_words = [

            "hello",

            "हेलो",

            "हैलो",

            "hey",

            "hi",

            "हाय"
        ]


        detected = False

        for word in wake_words:

            if word in normalized:

                detected = True
                break


        print(
            "WAKE TEXT:",
            text
        )

        print(
            "WAKE:",
            detected
        )


        return jsonify({

            "status": "ok",

            "wake": detected,

            "transcription": text,

            "language": language
        })


    finally:

        try:

            if os.path.exists(
                filename
            ):

                os.remove(
                    filename
                )

        except Exception:

            pass


# ============================================================
# UPLOAD AUDIO
# ============================================================

@app.route(
    "/uploadAudio",
    methods=["POST"]
)
def upload_audio():

    audio_data = request.get_data()

    if not audio_data:

        return jsonify({

            "status":
                "error",

            "message":
                "No audio received",

            "ai_reply":
                "Please ask your question again."

        }), 400


    print()
    print()
    print("########################################")
    print("NEW VOICE REQUEST")
    print("########################################")

    print(
        "Audio bytes:",
        len(audio_data)
    )


    fd, filename = tempfile.mkstemp(
        suffix=".wav"
    )

    os.close(fd)


    try:

        # --------------------------------------------
        # SAVE WAV
        # --------------------------------------------

        with open(
            filename,
            "wb"
        ) as f:

            f.write(
                audio_data
            )


        # --------------------------------------------
        # STT
        # --------------------------------------------

        transcription, language = (
            transcribe_audio(
                filename
            )
        )


        if not is_valid_query(
            transcription
        ):

            return jsonify({

                "status":
                    "error",

                "message":
                    "Speech not understood",

                "transcription":
                    transcription,

                "ai_reply":
                    "Please ask your question again.",

                "tts_id":
                    None

            }), 400


        # --------------------------------------------
        # AI
        # --------------------------------------------

        ai_reply = get_ai_reply(
            transcription
        )


        # --------------------------------------------
        # TTS
        # --------------------------------------------

        audio_data = generate_tts(
            ai_reply
        )


        tts_id = None


        if audio_data:

            tts_id = save_tts(
                audio_data
            )


        # --------------------------------------------
        # FINAL RESPONSE
        # --------------------------------------------

        response_data = {

            "status":
                "ok",

            "transcription":
                transcription,

            "language":
                language,

            "ai_reply":
                ai_reply,

            "tts_id":
                tts_id
        }


        print()
        print("########################################")
        print("FINAL")
        print("########################################")

        print(
            response_data
        )

        print("########################################")


        return jsonify(
            response_data
        )


    except Exception as e:

        print()
        print("SERVER ERROR")
        print(
            type(e).__name__
        )
        print(
            str(e)
        )


        return jsonify({

            "status":
                "error",

            "message":
                str(e),

            "ai_reply":
                "Server error."

        }), 500


    finally:

        try:

            if os.path.exists(
                filename
            ):

                os.remove(
                    filename
                )

        except Exception:

            pass


# ============================================================
# MANUAL TTS TEST
# ============================================================

@app.route(
    "/tts",
    methods=["POST"]
)
def manual_tts():

    data = request.get_json(
        silent=True
    )


    if not data:

        return jsonify({
            "status": "error"
        }), 400


    text = clean_text(
        data.get(
            "text",
            ""
        )
    )


    if not text:

        return jsonify({
            "status": "error",
            "message": "No text"
        }), 400


    audio_data = generate_tts(
        text
    )


    if not audio_data:

        return jsonify({
            "status": "error",
            "message": "TTS failed"
        }), 500


    audio_id = save_tts(
        audio_data
    )


    return jsonify({

        "status":
            "ok",

        "tts_id":
            audio_id
    })


# ============================================================
# START
# ============================================================

if __name__ == "__main__":

    print()
    print("========================================")
    print("ESP32 VOICE AI SERVER")
    print("========================================")

    print(
        "PORT:",
        PORT
    )

    print(
        "WHISPER:",
        WHISPER_MODEL
    )

    print(
        "PIPER:",
        PIPER_MODEL
    )

    print(
        "AI:",
        AI_MODEL
    )

    print("========================================")


    app.run(
        host="0.0.0.0",
        port=PORT,
        threaded=True
    )

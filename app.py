from flask import Flask, request, jsonify, Response
import os
import speech_recognition as sr
import requests
import re
import tempfile
import subprocess
import uuid
import threading
import time

app = Flask(__name__)

# =====================================================
# CONFIGURATION
# =====================================================

AI_API_KEY = os.environ.get("AI_API_KEY")

AI_URL = os.environ.get(
    "AI_URL",
    "https://api.groq.com/openai/v1/chat/completions"
)

AI_MODEL = os.environ.get(
    "AI_MODEL",
    "openai/gpt-oss-20b"
)

# =====================================================
# PIPER TTS
# =====================================================

# Piper is free/local TTS.
#
# We use Piper command line from Python.
#
# The voice must exist in the Render environment.
#
# Example:
# en_US-lessac-medium
#
PIPER_MODEL = os.environ.get(
    "PIPER_MODEL",
    "en_US-lessac-medium"
)

PIPER_DATA_DIR = os.environ.get(
    "PIPER_DATA_DIR",
    "/opt/render/project/src/voices"
)

# =====================================================
# AUDIO CACHE
# =====================================================

AUDIO_DIR = os.environ.get(
    "AUDIO_DIR",
    "/tmp/tts_audio"
)

os.makedirs(
    AUDIO_DIR,
    exist_ok=True
)

# =====================================================
# HOME
# =====================================================

@app.route("/", methods=["GET"])
def home():

    return "ESP32 Voice Server is ONLINE!"


# =====================================================
# HEALTH
# =====================================================

@app.route("/health", methods=["GET"])
def health():

    return jsonify({
        "status": "online",
        "speech_engine": "Google Speech Recognition",
        "ai_engine": "Groq",
        "model": AI_MODEL,
        "tts_engine": "Piper",
        "tts_model": PIPER_MODEL
    })


# =====================================================
# CLEAN TEXT
# =====================================================

def clean_text(text):

    if not text:
        return ""

    text = str(text).strip()

    text = re.sub(
        r"\s+",
        " ",
        text
    )

    return text


# =====================================================
# VALID QUERY
# =====================================================

def is_valid_query(text):

    if not text:
        return False

    text = str(text).strip()

    if len(text) < 2:
        return False

    bad_values = [
        "unknown",
        "none",
        "null",
        "no response",
        "no valid query",
        "speech not understood"
    ]

    if text.lower() in bad_values:
        return False

    return True


# =====================================================
# AI REPLY
# =====================================================

def get_ai_reply(
    hindi_text,
    english_text
):

    hindi_text = clean_text(
        hindi_text
    )

    english_text = clean_text(
        english_text
    )

    if not AI_API_KEY:

        print()
        print("==============================")
        print("AI ERROR")
        print("==============================")
        print("AI_API_KEY is NOT configured!")
        print("==============================")

        return "AI response nahi mil saka."

    if (
        not is_valid_query(hindi_text)
        and
        not is_valid_query(english_text)
    ):

        return "Please ask your question again."

    system_prompt = """
You are a professional bilingual voice assistant running on an ESP32.

Understand the user's intended meaning and answer naturally.

The speech recognition system provides:

1. Hindi recognition
2. English recognition

The recognition can sometimes be inaccurate.

Compare both results and determine the intended meaning.

LANGUAGE RULES:

If the user clearly speaks English,
answer completely in natural English.

If the user clearly speaks Hindi,
answer completely in Hindi using Devanagari script.

If the user speaks Roman Hindi or Hinglish,
answer naturally in Hinglish.

If Hindi recognition contains phonetic English,
understand the intended English.

If the user naturally mixes Hindi and English,
use natural Hinglish.

Do not mention speech recognition.

Do not explain your language decision.

Just answer the user's question.

VOICE RESPONSE STYLE:

The answer will be spoken aloud.

Keep answers concise.

Usually 1 to 4 sentences.

Be professional and natural.

Do not use markdown.

Do not use bullet points.

Do not use emojis.

Do not use headings.

Do not repeat the question.

Do not say "Sure" unnecessarily.

Do not say "As an AI".

Answer factual questions accurately.

For simple questions, give a direct answer.

Always answer in the language the user intended.
"""

    user_content = f"""
Hindi speech recognition:
{hindi_text if hindi_text else "No result"}

English speech recognition:
{english_text if english_text else "No result"}

Determine the user's intended meaning and language.

Then answer the user naturally.
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
                "content": user_content
            }

        ],

        "temperature": 0.2,

        "max_completion_tokens": 200,

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
        print("==============================")
        print("AI REQUEST")
        print("==============================")

        print("MODEL:", AI_MODEL)

        response = requests.post(

            AI_URL,

            headers=headers,

            json=payload,

            timeout=35
        )

        print(
            "AI HTTP:",
            response.status_code
        )

        if response.status_code != 200:

            print(
                response.text[:2000]
            )

            return "AI response nahi mil saka."

        try:

            data = response.json()

        except Exception as e:

            print(
                "AI JSON ERROR:",
                str(e)
            )

            return "AI response nahi mil saka."

        choices = data.get(
            "choices"
        )

        if not choices:

            print(
                "NO AI CHOICE"
            )

            print(data)

            return "AI response nahi mil saka."

        message = choices[0].get(
            "message",
            {}
        )

        reply = message.get(
            "content",
            ""
        )

        if reply is None:
            reply = ""

        reply = str(
            reply
        ).strip()

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

        print()
        print("==============================")
        print("AI REPLY")
        print("==============================")
        print(reply)
        print("==============================")

        return reply

    except requests.exceptions.Timeout:

        print("AI TIMEOUT")

        return "AI response nahi mil saka."

    except requests.exceptions.ConnectionError as e:

        print(
            "AI CONNECTION ERROR:",
            str(e)
        )

        return "AI response nahi mil saka."

    except Exception as e:

        print(
            "AI EXCEPTION:",
            type(e).__name__,
            str(e)
        )

        return "AI response nahi mil saka."


# =====================================================
# PIPER TTS
# =====================================================

def generate_tts(text):

    text = clean_text(text)

    if not text:
        return None

    filename = (
        str(uuid.uuid4())
        + ".wav"
    )

    output_file = os.path.join(
        AUDIO_DIR,
        filename
    )

    print()
    print("==============================")
    print("TTS")
    print("==============================")
    print("TEXT:")
    print(text)
    print("MODEL:", PIPER_MODEL)

    try:

        command = [

            "python",

            "-m",

            "piper",

            "--model",

            PIPER_MODEL,

            "--data-dir",

            PIPER_DATA_DIR,

            "--output_file",

            output_file
        ]

        result = subprocess.run(

            command,

            input=text,

            text=True,

            capture_output=True,

            timeout=60
        )

        if result.returncode != 0:

            print(
                "PIPER ERROR:"
            )

            print(
                result.stderr
            )

            return None

        if not os.path.exists(
            output_file
        ):

            print(
                "TTS FILE NOT CREATED"
            )

            return None

        size = os.path.getsize(
            output_file
        )

        print(
            "TTS WAV:",
            size,
            "bytes"
        )

        print("==============================")

        return filename

    except subprocess.TimeoutExpired:

        print(
            "PIPER TTS TIMEOUT"
        )

        return None

    except Exception as e:

        print(
            "PIPER EXCEPTION:",
            type(e).__name__,
            str(e)
        )

        return None


# =====================================================
# TTS AUDIO FILE
# =====================================================

@app.route(
    "/tts/<filename>",
    methods=["GET"]
)
def tts_file(filename):

    # Security
    if "/" in filename or "\\" in filename:

        return "Invalid filename", 400

    filepath = os.path.join(
        AUDIO_DIR,
        filename
    )

    if not os.path.exists(
        filepath
    ):

        return "Audio not found", 404

    try:

        with open(
            filepath,
            "rb"
        ) as f:

            audio = f.read()

        return Response(

            audio,

            mimetype="audio/wav",

            headers={
                "Cache-Control":
                    "no-cache"
            }
        )

    except Exception as e:

        print(
            "TTS FILE ERROR:",
            str(e)
        )

        return "Audio error", 500


# =====================================================
# WAKE
# =====================================================

@app.route(
    "/wake",
    methods=["POST", "GET"]
)
def wake():

    print()
    print("==============================")
    print("WAKE REQUEST")
    print("==============================")

    if request.method == "POST":

        audio_data = request.get_data()

        print(
            "AUDIO BYTES:",
            len(audio_data)
        )

    # TEST MODE
    #
    # Every wake request returns true.
    #
    response_data = {

        "status": "ok",

        "wake": True,

        "english": "Hello",

        "hindi": None
    }

    print(
        response_data
    )

    return jsonify(
        response_data
    )


# =====================================================
# TEST
# =====================================================

@app.route(
    "/test",
    methods=["POST"]
)
def test():

    data = request.get_json(
        silent=True
    )

    if not data:

        return jsonify({

            "status": "error",

            "message":
                "No JSON received"

        }), 400

    return jsonify({

        "status": "ok",

        "message":
            "Data received",

        "data":
            data

    })


# =====================================================
# UPLOAD AUDIO
# =====================================================

@app.route(
    "/uploadAudio",
    methods=["POST"]
)
def upload_audio():

    filename = None

    try:

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
        print("==============================")
        print("AUDIO RECEIVED")
        print("==============================")
        print(
            "Audio bytes:",
            len(audio_data)
        )
        print("==============================")

        # -------------------------------------------------
        # SAVE WAV
        # -------------------------------------------------

        fd, filename = tempfile.mkstemp(
            suffix=".wav"
        )

        os.close(fd)

        with open(
            filename,
            "wb"
        ) as f:

            f.write(
                audio_data
            )

        # -------------------------------------------------
        # SPEECH RECOGNITION
        # -------------------------------------------------

        recognizer = sr.Recognizer()

        with sr.AudioFile(
            filename
        ) as source:

            audio = recognizer.record(
                source
            )

        hindi_text = None

        english_text = None

        # -------------------------------------------------
        # HINDI
        # -------------------------------------------------

        print()
        print("==============================")
        print("HINDI SPEECH")
        print("==============================")

        try:

            hindi_text = recognizer.recognize_google(

                audio,

                language="hi-IN"
            )

            hindi_text = clean_text(
                hindi_text
            )

            print(
                "Hindi:",
                hindi_text
            )

        except sr.UnknownValueError:

            print(
                "Hindi not understood."
            )

        except sr.RequestError as e:

            print(
                "Google Speech error:",
                str(e)
            )

            return jsonify({

                "status":
                    "error",

                "message":
                    "Speech service error",

                "details":
                    str(e),

                "ai_reply":
                    "Speech service error."

            }), 500

        # -------------------------------------------------
        # ENGLISH
        # -------------------------------------------------

        print()
        print("==============================")
        print("ENGLISH SPEECH")
        print("==============================")

        try:

            english_text = recognizer.recognize_google(

                audio,

                language="en-IN"
            )

            english_text = clean_text(
                english_text
            )

            print(
                "English:",
                english_text
            )

        except sr.UnknownValueError:

            print(
                "English not understood."
            )

        except sr.RequestError as e:

            print(
                "Google Speech error:",
                str(e)
            )

            return jsonify({

                "status":
                    "error",

                "message":
                    "Speech service error",

                "details":
                    str(e),

                "ai_reply":
                    "Speech service error."

            }), 500

        # -------------------------------------------------
        # VALIDATION
        # -------------------------------------------------

        if (
            not is_valid_query(
                hindi_text
            )
            and
            not is_valid_query(
                english_text
            )
        ):

            return jsonify({

                "status":
                    "error",

                "message":
                    "Speech not understood",

                "transcription":
                    None,

                "hindi_transcription":
                    hindi_text,

                "english_transcription":
                    english_text,

                "ai_reply":
                    "Please ask your question again."

            }), 400

        # -------------------------------------------------
        # AI
        # -------------------------------------------------

        ai_reply = get_ai_reply(

            hindi_text,

            english_text
        )

        # -------------------------------------------------
        # TRANSCRIPTION
        # -------------------------------------------------

        if is_valid_query(
            english_text
        ):

            transcription = (
                english_text
            )

        else:

            transcription = (
                hindi_text
            )

        # -------------------------------------------------
        # TTS
        # -------------------------------------------------

        tts_filename = generate_tts(
            ai_reply
        )

        # -------------------------------------------------
        # AUDIO URL
        # -------------------------------------------------

        audio_url = None

        if tts_filename:

            host = request.host_url.rstrip("/")

            audio_url = (
                host
                + "/tts/"
                + tts_filename
            )

        # -------------------------------------------------
        # FINAL RESPONSE
        # -------------------------------------------------

        response_data = {

            "status":
                "ok",

            "transcription":
                transcription,

            "hindi_transcription":
                hindi_text,

            "english_transcription":
                english_text,

            "ai_reply":
                ai_reply,

            "tts_engine":
                "Piper",

            "audio_url":
                audio_url
        }

        print()
        print("==============================")
        print("FINAL RESPONSE")
        print("==============================")
        print(
            response_data
        )
        print("==============================")

        return jsonify(
            response_data
        )

    except Exception as e:

        print()
        print("==============================")
        print("SERVER ERROR")
        print("==============================")

        print(
            "TYPE:",
            type(e).__name__
        )

        print(
            "ERROR:",
            str(e)
        )

        print("==============================")

        return jsonify({

            "status":
                "error",

            "message":
                str(e),

            "ai_reply":
                "AI response nahi mil saka.",

            "audio_url":
                None

        }), 500

    finally:

        if filename:

            try:

                if os.path.exists(
                    filename
                ):

                    os.remove(
                        filename
                    )

            except Exception:

                pass


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

    print()
    print("==============================")
    print("ESP32 VOICE SERVER")
    print("==============================")

    print(
        "PORT:",
        port
    )

    print(
        "AI MODEL:",
        AI_MODEL
    )

    print(
        "TTS:",
        "Piper"
    )

    print(
        "TTS MODEL:",
        PIPER_MODEL
    )

    print(
        "AI KEY:",
        "CONFIGURED"
        if AI_API_KEY
        else "MISSING"
    )

    print("==============================")

    app.run(

        host="0.0.0.0",

        port=port,

        threaded=True
    )

from flask import Flask, request, jsonify, Response
import os
import requests
import tempfile
import re

app = Flask(__name__)


# =====================================================
# CONFIG
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
# GROQ STT
# =====================================================

STT_URL = os.environ.get(
    "STT_URL",
    "https://api.groq.com/openai/v1/audio/transcriptions"
)

STT_MODEL = os.environ.get(
    "STT_MODEL",
    "whisper-large-v3-turbo"
)


# =====================================================
# GROQ TTS
# =====================================================

TTS_URL = os.environ.get(
    "TTS_URL",
    "https://api.groq.com/openai/v1/audio/speech"
)

TTS_MODEL = os.environ.get(
    "TTS_MODEL",
    "canopylabs/orpheus-v1-english"
)

# FEMALE HANNAH
TTS_VOICE = os.environ.get(
    "TTS_VOICE",
    "hannah"
)

TTS_MAX_CHARS = 200


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
        "stt_engine": "Groq Whisper",
        "stt_model": STT_MODEL,
        "ai_engine": "Groq",
        "ai_model": AI_MODEL,
        "tts_engine": "Groq Orpheus",
        "tts_model": TTS_MODEL,
        "tts_voice": TTS_VOICE
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
# VALID TEXT
# =====================================================

def is_valid_query(text):

    if not text:
        return False

    text = clean_text(text)

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
# WAKE
# =====================================================

@app.route(
    "/wake",
    methods=["POST", "GET"]
)
def wake():

    print()
    print("========================================")
    print("WAKE REQUEST")
    print("========================================")

    audio_data = request.get_data()

    print(
        "AUDIO BYTES:",
        len(audio_data)
    )

    # -------------------------------------------------
    # CURRENT MODE:
    # Any wake request activates device.
    # -------------------------------------------------

    response_data = {
        "status": "ok",
        "wake": True,
        "english": "Hello",
        "hindi": None
    }

    print(
        "WAKE:",
        True
    )

    print("========================================")

    return jsonify(response_data)


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
            "message": "No JSON received"
        }), 400

    return jsonify({
        "status": "ok",
        "message": "Data received",
        "data": data
    })


# =====================================================
# GROQ TRANSCRIPTION
# =====================================================

def transcribe_audio(
    filename,
    language
):

    if not AI_API_KEY:
        print("STT ERROR: AI_API_KEY missing")
        return None

    try:

        print()
        print("----------------------------------------")
        print("GROQ STT")
        print("LANGUAGE:", language)
        print("MODEL:", STT_MODEL)
        print("----------------------------------------")

        headers = {
            "Authorization":
                "Bearer " + AI_API_KEY
        }

        with open(
            filename,
            "rb"
        ) as audio_file:

            files = {
                "file": (
                    "audio.wav",
                    audio_file,
                    "audio/wav"
                )
            }

            data = {
                "model": STT_MODEL,
                "language": language,
                "response_format": "json",
                "temperature": "0"
            }

            response = requests.post(
                STT_URL,
                headers=headers,
                files=files,
                data=data,
                timeout=35
            )

        print(
            "STT HTTP:",
            response.status_code
        )

        if response.status_code != 200:

            print(
                "STT ERROR:",
                response.text[:2000]
            )

            return None

        result = response.json()

        text = clean_text(
            result.get("text")
        )

        if text:

            print(
                "STT RESULT:",
                text
            )

            return text

        print(
            "STT EMPTY RESULT"
        )

        return None

    except requests.exceptions.Timeout:

        print("STT TIMEOUT")
        return None

    except requests.exceptions.ConnectionError:

        print("STT CONNECTION ERROR")
        return None

    except Exception as e:

        print(
            "STT ERROR:",
            type(e).__name__,
            str(e)
        )

        return None


# =====================================================
# AI
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

        return (
            "AI response nahi mil saka."
        )

    if (
        not is_valid_query(hindi_text)
        and
        not is_valid_query(english_text)
    ):

        return (
            "Please ask your question again."
        )

    system_prompt = """
You are a professional bilingual voice assistant running on an ESP32.

You receive two possible speech recognition results:
1. Hindi transcription
2. English transcription

Determine what the user actually intended.

LANGUAGE RULES:

If the user speaks English,
answer in natural English.

If the user speaks Hindi,
answer in natural Hindi.

If the user speaks Roman Hindi or Hinglish,
answer in natural Hinglish.

Sometimes Hindi recognition may convert English
speech phonetically into Devanagari.
In that case understand the intended English meaning.

Never mention speech recognition.

Never explain your language decision.

VOICE STYLE:

Your answer will be spoken aloud.

Keep it short and natural.

Usually one or two sentences.

Maximum about 150 characters when possible.

No markdown.

No bullets.

No headings.

No emojis.

Do not repeat the question.

Do not say "As an AI".
"""

    user_content = f"""
Hindi transcription:
{hindi_text if hindi_text else "No result"}

English transcription:
{english_text if english_text else "No result"}

Understand the intended question and answer naturally.
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
        print("----------------------------------------")
        print("AI REQUEST")
        print("----------------------------------------")

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

            return (
                "AI response nahi mil saka."
            )

        data = response.json()

        choices = data.get(
            "choices"
        )

        if not choices:

            return (
                "AI response nahi mil saka."
            )

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
        ).strip()

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

            return (
                "AI response nahi mil saka."
            )

        print(
            "AI REPLY:",
            reply
        )

        return reply

    except requests.exceptions.Timeout:

        print("AI TIMEOUT")

        return (
            "AI response nahi mil saka."
        )

    except Exception as e:

        print(
            "AI ERROR:",
            type(e).__name__,
            str(e)
        )

        return (
            "AI response nahi mil saka."
        )


# =====================================================
# TTS
# =====================================================

def generate_tts(text):

    text = clean_text(text)

    if not text:

        return None

    if not AI_API_KEY:

        print(
            "TTS ERROR: AI_API_KEY missing"
        )

        return None

    # Groq Orpheus max input = 200 chars
    if len(text) > TTS_MAX_CHARS:

        text = text[:TTS_MAX_CHARS]

        last_dot = text.rfind(".")

        if last_dot > 40:

            text = text[
                :last_dot + 1
            ]

    payload = {
        "model": TTS_MODEL,
        "voice": TTS_VOICE,
        "input": text,
        "response_format": "wav",
        "sample_rate": 16000
    }

    headers = {
        "Authorization":
            "Bearer " + AI_API_KEY,

        "Content-Type":
            "application/json",

        "Accept":
            "audio/wav"
    }

    try:

        print()
        print("========================================")
        print("HANNAH FEMALE TTS")
        print("========================================")

        print(
            "MODEL:",
            TTS_MODEL
        )

        print(
            "VOICE:",
            TTS_VOICE
        )

        print(
            "TEXT:",
            text
        )

        response = requests.post(
            TTS_URL,
            headers=headers,
            json=payload,
            timeout=35
        )

        print(
            "TTS HTTP:",
            response.status_code
        )

        if response.status_code != 200:

            print(
                "TTS ERROR:"
            )

            print(
                response.text[:3000]
            )

            return None

        audio_data = response.content

        if not audio_data:

            print(
                "TTS EMPTY AUDIO"
            )

            return None

        print(
            "TTS AUDIO BYTES:",
            len(audio_data)
        )

        return audio_data

    except requests.exceptions.Timeout:

        print(
            "TTS TIMEOUT"
        )

        return None

    except requests.exceptions.ConnectionError:

        print(
            "TTS CONNECTION ERROR"
        )

        return None

    except Exception as e:

        print(
            "TTS ERROR:",
            type(e).__name__,
            str(e)
        )

        return None


# =====================================================
# TTS ENDPOINT
# =====================================================

@app.route(
    "/tts",
    methods=["POST"]
)
def tts():

    try:

        data = request.get_json(
            silent=True
        )

        if not data:

            return jsonify({
                "status": "error",
                "message": "No JSON received"
            }), 400

        text = clean_text(
            data.get("text")
        )

        if not text:

            return jsonify({
                "status": "error",
                "message": "No text received"
            }), 400

        audio_data = generate_tts(
            text
        )

        if audio_data is None:

            return jsonify({
                "status": "error",
                "message": "TTS generation failed",
                "voice": TTS_VOICE
            }), 500

        # IMPORTANT:
        # Explicit Content-Length prevents
        # ESP32 from getting chunked TTS.
        return Response(
            audio_data,
            status=200,
            mimetype="audio/wav",
            headers={
                "Content-Type":
                    "audio/wav",

                "Content-Length":
                    str(len(audio_data)),

                "Content-Disposition":
                    "inline",

                "Cache-Control":
                    "no-cache",

                "Connection":
                    "close"
            }
        )

    except Exception as e:

        print(
            "TTS SERVER ERROR:",
            type(e).__name__,
            str(e)
        )

        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


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

        print()
        print("========================================")
        print("AUDIO REQUEST")
        print("========================================")

        print(
            "CONTENT TYPE:",
            request.content_type
        )

        print(
            "CONTENT LENGTH:",
            request.content_length
        )

        print(
            "AUDIO BYTES:",
            len(audio_data)
        )

        print("========================================")

        if not audio_data:

            return jsonify({
                "status": "ok",
                "speech_ok": False,
                "message": "No audio received",
                "transcription": None,
                "hindi_transcription": None,
                "english_transcription": None,
                "ai_reply":
                    "Please speak again."
            })

        # =================================================
        # SAVE WAV
        # =================================================

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

        print(
            "WAV FILE:",
            filename
        )

        # =================================================
        # HINDI STT
        # =================================================

        hindi_text = transcribe_audio(
            filename,
            "hi"
        )

        # =================================================
        # ENGLISH STT
        # =================================================

        english_text = transcribe_audio(
            filename,
            "en"
        )

        # =================================================
        # VALIDATION
        # =================================================

        hindi_valid = is_valid_query(
            hindi_text
        )

        english_valid = is_valid_query(
            english_text
        )

        if not hindi_valid and not english_valid:

            print(
                "SPEECH NOT UNDERSTOOD"
            )

            # Return HTTP 200 so ESP32 does not
            # treat this as a server/network error.
            return jsonify({
                "status": "ok",
                "speech_ok": False,
                "message":
                    "Speech not understood",
                "transcription": None,
                "hindi_transcription":
                    hindi_text,
                "english_transcription":
                    english_text,
                "ai_reply":
                    "Please speak again."
            })

        # =================================================
        # AI
        # =================================================

        ai_reply = get_ai_reply(
            hindi_text,
            english_text
        )

        # =================================================
        # BEST TRANSCRIPTION
        # =================================================

        if english_valid:

            transcription = english_text

        else:

            transcription = hindi_text

        # =================================================
        # FINAL
        # =================================================

        response_data = {
            "status": "ok",
            "speech_ok": True,
            "transcription":
                transcription,
            "hindi_transcription":
                hindi_text,
            "english_transcription":
                english_text,
            "ai_reply":
                ai_reply
        }

        print()
        print("========================================")
        print("FINAL RESPONSE")
        print("========================================")

        print(
            response_data
        )

        print("========================================")

        return jsonify(
            response_data
        )

    except Exception as e:

        print()
        print("========================================")
        print("SERVER ERROR")
        print("========================================")

        print(
            type(e).__name__,
            str(e)
        )

        return jsonify({
            "status": "error",
            "speech_ok": False,
            "message": str(e),
            "transcription": None,
            "hindi_transcription": None,
            "english_transcription": None,
            "ai_reply":
                "Server error. Please try again."
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
    print("========================================")
    print("ESP32 VOICE SERVER")
    print("========================================")

    print(
        "PORT:",
        port
    )

    print(
        "STT MODEL:",
        STT_MODEL
    )

    print(
        "AI MODEL:",
        AI_MODEL
    )

    print(
        "TTS MODEL:",
        TTS_MODEL
    )

    print(
        "TTS VOICE:",
        TTS_VOICE
    )

    print(
        "AI KEY:",
        "CONFIGURED"
        if AI_API_KEY
        else "MISSING"
    )

    print("========================================")

    app.run(
        host="0.0.0.0",
        port=port,
        threaded=True
    )

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

# Groq Chat
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
    "whisper-large-v3"
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

TTS_MAX_CHARS = 190


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
        "speech not understood",
        "could not understand audio"
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
    # Current wake behaviour:
    # ESP32 sends 2 sec audio.
    # Server accepts it and wakes device.
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
# GROQ WHISPER TRANSCRIPTION
# =====================================================

def transcribe_audio(filename):

    if not AI_API_KEY:

        print(
            "STT ERROR: AI_API_KEY missing"
        )

        return None

    headers = {
        "Authorization":
            "Bearer " + AI_API_KEY
    }

    try:

        print()
        print("========================================")
        print("GROQ WHISPER STT")
        print("========================================")

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

                # Let Whisper automatically identify
                # Hindi / English / Hinglish.
                "response_format": "json",

                "temperature": "0"
            }

            response = requests.post(
                STT_URL,
                headers=headers,
                files=files,
                data=data,
                timeout=40
            )

        print(
            "STT HTTP:",
            response.status_code
        )

        if response.status_code != 200:

            print(
                "STT ERROR BODY:"
            )

            print(
                response.text[:3000]
            )

            return None

        try:

            result = response.json()

        except Exception:

            print(
                "STT JSON ERROR"
            )

            print(
                response.text[:2000]
            )

            return None

        text = clean_text(
            result.get(
                "text",
                ""
            )
        )

        language = result.get(
            "language"
        )

        print(
            "STT LANGUAGE:",
            language
        )

        print(
            "TRANSCRIPTION:",
            text
        )

        print(
            "========================================"
        )

        if not is_valid_query(text):

            return None

        return {
            "text": text,
            "language": language
        }

    except requests.exceptions.Timeout:

        print(
            "STT TIMEOUT"
        )

        return None

    except requests.exceptions.ConnectionError:

        print(
            "STT CONNECTION ERROR"
        )

        return None

    except Exception as e:

        print(
            "STT ERROR:",
            str(e)
        )

        return None


# =====================================================
# AI
# =====================================================

def get_ai_reply(
    transcription,
    language=None
):

    transcription = clean_text(
        transcription
    )

    if not AI_API_KEY:

        return (
            "AI response nahi mil saka."
        )

    if not is_valid_query(
        transcription
    ):

        return (
            "Please ask your question again."
        )

    system_prompt = """
You are a professional bilingual voice assistant
running on an ESP32.

The user may speak:

English,
Hindi,
Roman Hindi,
or Hinglish.

Understand the actual meaning of the user's speech.

LANGUAGE RULES:

If the user speaks English,
answer naturally in English.

If the user speaks Hindi,
answer naturally in Hindi.

If the user speaks Roman Hindi or Hinglish,
answer naturally in Hinglish.

Do not mention transcription.

Do not mention Whisper.

Do not explain language selection.

Just answer the user.

VOICE STYLE:

Your answer will be spoken aloud by a female voice.

Keep the answer short and natural.

Usually one or two sentences.

Maximum about 150 characters when possible.

No markdown.

No bullet points.

No headings.

No emojis.

Do not repeat the question.

Do not say "As an AI".

Sound like a helpful female voice assistant.
"""

    user_content = f"""
Detected language:
{language if language else "unknown"}

User said:
{transcription}

Answer naturally.
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
        print("========================================")
        print("AI REQUEST")
        print("========================================")

        response = requests.post(
            AI_URL,
            headers=headers,
            json=payload,
            timeout=40
        )

        print(
            "AI HTTP:",
            response.status_code
        )

        if response.status_code != 200:

            print(
                "AI ERROR:"
            )

            print(
                response.text[:3000]
            )

            return (
                "AI response nahi mil saka."
            )

        try:

            data = response.json()

        except Exception:

            print(
                "AI JSON ERROR"
            )

            print(
                response.text[:2000]
            )

            return (
                "AI response nahi mil saka."
            )

        choices = data.get(
            "choices"
        )

        if not choices:

            print(
                "AI NO CHOICES"
            )

            print(
                data
            )

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

        reply = clean_text(
            reply
        )

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

            if reply.startswith(
                prefix
            ):

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

        print(
            "========================================"
        )

        return reply

    except requests.exceptions.Timeout:

        print(
            "AI TIMEOUT"
        )

        return (
            "AI response nahi mil saka."
        )

    except requests.exceptions.ConnectionError:

        print(
            "AI CONNECTION ERROR"
        )

        return (
            "AI response nahi mil saka."
        )

    except Exception as e:

        print(
            "AI ERROR:",
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

    # Groq Orpheus input limit is 200 chars.
    if len(text) > TTS_MAX_CHARS:

        text = text[
            :TTS_MAX_CHARS
        ]

        last_space = text.rfind(" ")

        if last_space > 40:

            text = text[
                :last_space
            ]

    payload = {
        "model":
            TTS_MODEL,

        "voice":
            "hannah",

        "input":
            text,

        "response_format":
            "wav"
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
            "hannah"
        )

        print(
            "TEXT:",
            text
        )

        response = requests.post(
            TTS_URL,
            headers=headers,
            json=payload,
            timeout=40
        )

        print(
            "TTS HTTP:",
            response.status_code
        )

        print(
            "TTS CONTENT TYPE:",
            response.headers.get(
                "Content-Type"
            )
        )

        if response.status_code != 200:

            print(
                "TTS ERROR BODY:"
            )

            print(
                response.text[:4000]
            )

            return None

        audio_data = response.content

        if not audio_data:

            print(
                "TTS EMPTY AUDIO"
            )

            return None

        # WAV should start with RIFF.
        if (
            len(audio_data) < 12
            or
            audio_data[0:4] != b"RIFF"
            or
            audio_data[8:12] != b"WAVE"
        ):

            print(
                "TTS DID NOT RETURN WAV"
            )

            print(
                audio_data[:500]
            )

            return None

        print(
            "TTS AUDIO BYTES:",
            len(audio_data)
        )

        print(
            "HANNAH TTS SUCCESS"
        )

        print(
            "========================================"
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
                "message":
                    "No JSON received",
                "voice":
                    "hannah"
            }), 400

        text = clean_text(
            data.get("text")
        )

        if not text:

            return jsonify({
                "status": "error",
                "message":
                    "No text received",
                "voice":
                    "hannah"
            }), 400

        audio_data = generate_tts(
            text
        )

        if audio_data is None:

            return jsonify({
                "status": "error",
                "message":
                    "TTS generation failed",
                "voice":
                    "hannah"
            }), 500

        return Response(
            audio_data,
            status=200,
            mimetype="audio/wav",

            headers={
                "Cache-Control":
                    "no-cache",

                "Content-Disposition":
                    "inline; filename=hannah.wav"
            }
        )

    except Exception as e:

        print(
            "TTS SERVER ERROR:",
            str(e)
        )

        return jsonify({
            "status": "error",
            "message": str(e),
            "voice": "hannah"
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

        print(
            "========================================"
        )

        if not audio_data:

            return jsonify({
                "status": "error",
                "speech_ok": False,
                "message":
                    "No audio received",
                "transcription": None,
                "ai_reply":
                    "Please speak again."
            }), 400

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

        print(
            "WAV FILE:",
            filename
        )

        # -------------------------------------------------
        # GROQ WHISPER
        # -------------------------------------------------

        transcription_result = \
            transcribe_audio(
                filename
            )

        if not transcription_result:

            return jsonify({
                "status": "error",
                "speech_ok": False,
                "message":
                    "Speech not understood",
                "transcription": None,
                "english_transcription":
                    None,
                "hindi_transcription":
                    None,
                "ai_reply":
                    "Please speak again."
            }), 400

        transcription = clean_text(
            transcription_result.get(
                "text"
            )
        )

        language = transcription_result.get(
            "language"
        )

        # -------------------------------------------------
        # AI
        # -------------------------------------------------

        ai_reply = get_ai_reply(
            transcription,
            language
        )

        # -------------------------------------------------
        # RESPONSE
        # -------------------------------------------------

        response_data = {
            "status": "ok",

            "speech_ok": True,

            "transcription":
                transcription,

            "language":
                language,

            # Kept for ESP32 compatibility.
            "english_transcription":
                transcription
                if language == "en"
                else None,

            "hindi_transcription":
                transcription
                if language == "hi"
                else None,

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

        print(
            "========================================"
        )

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
            "english_transcription":
                None,
            "hindi_transcription":
                None,
            "ai_reply":
                "Please speak again."
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
    print("ESP32 FEMALE HANNAH VOICE SERVER")
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
        "hannah"
    )

    print(
        "AI KEY:",
        "CONFIGURED"
        if AI_API_KEY
        else "MISSING"
    )

    print(
        "========================================"
    )

    app.run(
        host="0.0.0.0",
        port=port,
        threaded=True
    )

from flask import Flask, request, jsonify, Response
import os
import requests
import re
import tempfile
import time

app = Flask(__name__)

# =====================================================
# CONFIG
# =====================================================

AI_API_KEY = os.environ.get("AI_API_KEY")

AI_URL = os.environ.get(
    "AI_URL",
    "https://api.groq.com/openai/v1/chat/completions"
)

# FAST MODEL
AI_MODEL = os.environ.get(
    "AI_MODEL",
    "llama-3.1-8b-instant"
)

# =====================================================
# STT
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
# TTS
# =====================================================

TTS_URL = os.environ.get(
    "TTS_URL",
    "https://api.groq.com/openai/v1/audio/speech"
)

TTS_MODEL = os.environ.get(
    "TTS_MODEL",
    "canopylabs/orpheus-v1-english"
)

# FEMALE VOICE
TTS_VOICE = os.environ.get(
    "TTS_VOICE",
    "autumn"
)

# Orpheus max input = 200 chars
TTS_MAX_CHARS = 200

# Fast but natural
TTS_SPEED = float(
    os.environ.get(
        "TTS_SPEED",
        "1.15"
    )
)

TTS_SAMPLE_RATE = 16000


# =====================================================
# HOME
# =====================================================

@app.route("/", methods=["GET"])
def home():

    return "ESP32 Female Voice Server is ONLINE!"


# =====================================================
# HEALTH
# =====================================================

@app.route("/health", methods=["GET"])
def health():

    return jsonify({
        "status": "online",

        "speech_engine": "Groq Whisper",
        "speech_model": STT_MODEL,

        "ai_engine": "Groq",
        "model": AI_MODEL,

        "tts_engine": "Groq Orpheus",
        "tts_model": TTS_MODEL,
        "tts_voice": TTS_VOICE,
        "tts_speed": TTS_SPEED,

        "female_voice": True
    })


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
    print("WAKE REQUEST RECEIVED")
    print("========================================")

    audio_data = request.get_data()

    print(
        "AUDIO BYTES:",
        len(audio_data)
    )

    response_data = {
        "status": "ok",
        "wake": True,
        "english": "Hello",
        "hindi": None
    }

    print(
        "WAKE RESPONSE:",
        response_data
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
# STT
# =====================================================

def transcribe_audio(filename):

    if not AI_API_KEY:

        print("STT ERROR: AI_API_KEY missing")

        return None

    try:

        print()
        print("========================================")
        print("GROQ WHISPER STT")
        print("========================================")

        start_time = time.time()

        headers = {
            "Authorization":
                "Bearer " + AI_API_KEY,

            "Accept":
                "application/json"
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
                "response_format": "json",
                "temperature": "0"
            }

            response = requests.post(
                STT_URL,
                headers=headers,
                files=files,
                data=data,
                timeout=15
            )

        elapsed = (
            time.time() -
            start_time
        )

        print(
            "STT HTTP:",
            response.status_code
        )

        print(
            "STT TIME:",
            round(elapsed, 2),
            "seconds"
        )

        if response.status_code != 200:

            print(
                "STT ERROR:",
                response.text[:2000]
            )

            return None

        result = response.json()

        text = result.get(
            "text",
            ""
        )

        text = clean_text(text)

        print(
            "TRANSCRIPTION:",
            text
        )

        print("========================================")

        if not is_valid_query(text):
            return None

        return text

    except requests.exceptions.Timeout:

        print("STT TIMEOUT")
        return None

    except requests.exceptions.ConnectionError:

        print("STT CONNECTION ERROR")
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

def get_ai_reply(user_text):

    user_text = clean_text(
        user_text
    )

    if not AI_API_KEY:

        return "AI response nahi mil saka."

    if not is_valid_query(
        user_text
    ):

        return "Please ask your question again."

    system_prompt = """
You are a very fast bilingual voice assistant.

Understand Hindi, English and Hinglish.

Reply naturally in the same language style as the user.

Hindi input = natural Hindi.
English input = natural English.
Hinglish input = natural Hinglish.

Your response will be spoken by a female voice.

Keep responses extremely short and conversational.

Usually one short sentence.
Maximum 80 characters when possible.

Do not use markdown.
Do not use bullets.
Do not use emojis.
Do not repeat the question.
Do not mention AI.
Do not explain your language choice.

Be warm, natural and direct.
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

        "max_tokens": 60,

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
        print("FAST AI REQUEST")
        print("========================================")

        start_time = time.time()

        response = requests.post(
            AI_URL,
            headers=headers,
            json=payload,
            timeout=15
        )

        elapsed = (
            time.time() -
            start_time
        )

        print(
            "AI HTTP:",
            response.status_code
        )

        print(
            "AI TIME:",
            round(elapsed, 2),
            "seconds"
        )

        if response.status_code != 200:

            print(
                response.text[:2000]
            )

            return "AI response nahi mil saka."

        data = response.json()

        choices = data.get(
            "choices"
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

            return "AI response nahi mil saka."

        print(
            "AI REPLY:",
            reply
        )

        print("========================================")

        return reply

    except requests.exceptions.Timeout:

        print("AI TIMEOUT")

        return "AI response nahi mil saka."

    except requests.exceptions.ConnectionError:

        print("AI CONNECTION ERROR")

        return "AI response nahi mil saka."

    except Exception as e:

        print(
            "AI ERROR:",
            str(e)
        )

        return "AI response nahi mil saka."


# =====================================================
# TTS
# =====================================================

def generate_tts(text):

    text = clean_text(
        text
    )

    if not text:
        return None

    if not AI_API_KEY:

        print(
            "TTS ERROR: AI_API_KEY missing"
        )

        return None

    # Orpheus maximum 200 chars
    if len(text) > TTS_MAX_CHARS:

        text = text[
            :TTS_MAX_CHARS
        ]

        last_space = text.rfind(" ")

        if last_space > 80:

            text = text[
                :last_space
            ]

    payload = {
        "model": TTS_MODEL,

        # FEMALE
        "voice": TTS_VOICE,

        "input": text,

        "response_format": "wav",

        "sample_rate":
            TTS_SAMPLE_RATE,

        "speed":
            TTS_SPEED
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
        print("FEMALE TTS REQUEST")
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
            "SPEED:",
            TTS_SPEED
        )

        print(
            "TEXT:",
            text
        )

        start_time = time.time()

        response = requests.post(
            TTS_URL,
            headers=headers,
            json=payload,
            timeout=15
        )

        elapsed = (
            time.time() -
            start_time
        )

        print(
            "TTS HTTP:",
            response.status_code
        )

        print(
            "TTS TIME:",
            round(elapsed, 2),
            "seconds"
        )

        if response.status_code != 200:

            print(
                "TTS ERROR:"
            )

            print(
                response.text[:2000]
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

        print("========================================")

        return audio_data

    except requests.exceptions.Timeout:

        print("TTS TIMEOUT")
        return None

    except requests.exceptions.ConnectionError:

        print("TTS CONNECTION ERROR")
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
                    "No JSON received"
            }), 400

        text = clean_text(
            data.get("text")
        )

        if not text:

            return jsonify({
                "status": "error",
                "message":
                    "No text received"
            }), 400

        audio_data = generate_tts(
            text
        )

        if audio_data is None:

            return jsonify({
                "status": "error",
                "message":
                    "TTS generation failed"
            }), 500

        return Response(
            audio_data,

            status=200,

            mimetype="audio/wav",

            headers={
                "Cache-Control":
                    "no-cache",

                "Content-Length":
                    str(len(audio_data))
            }
        )

    except Exception as e:

        print(
            "TTS SERVER ERROR:",
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

    total_start = time.time()

    try:

        audio_data = request.get_data()

        print()
        print("========================================")
        print("AUDIO REQUEST RECEIVED")
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

                "status": "error",

                "message":
                    "No audio received",

                "transcription":
                    None,

                "hindi_transcription":
                    None,

                "english_transcription":
                    None,

                "ai_reply":
                    "Please ask your question again."

            }), 400

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
        # STT
        # =================================================

        transcription = transcribe_audio(
            filename
        )

        if not is_valid_query(
            transcription
        ):

            return jsonify({

                "status": "error",

                "message":
                    "Speech not understood",

                "transcription":
                    None,

                "hindi_transcription":
                    None,

                "english_transcription":
                    None,

                "ai_reply":
                    "Please ask your question again."

            }), 400

        # =================================================
        # AI
        # =================================================

        ai_reply = get_ai_reply(
            transcription
        )

        # =================================================
        # FINAL RESPONSE
        # =================================================

        total_time = (
            time.time() -
            total_start
        )

        response_data = {

            "status":
                "ok",

            "transcription":
                transcription,

            "hindi_transcription":
                transcription,

            "english_transcription":
                transcription,

            "ai_reply":
                ai_reply,

            "processing_time":
                round(
                    total_time,
                    2
                )
        }

        print()
        print("========================================")
        print("FINAL RESPONSE")
        print("========================================")

        print(
            response_data
        )

        print(
            "TOTAL TIME:",
            round(
                total_time,
                2
            ),
            "seconds"
        )

        print("========================================")

        return jsonify(
            response_data
        )

    except Exception as e:

        print()
        print("SERVER ERROR")

        print(
            type(e).__name__,
            str(e)
        )

        return jsonify({

            "status":
                "error",

            "message":
                str(e),

            "transcription":
                None,

            "hindi_transcription":
                None,

            "english_transcription":
                None,

            "ai_reply":
                "AI response nahi mil saka."

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
    print("ESP32 FAST FEMALE VOICE SERVER")
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
        "FEMALE VOICE:",
        TTS_VOICE
    )

    print(
        "TTS SPEED:",
        TTS_SPEED
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

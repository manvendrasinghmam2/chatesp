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

# FAST AI MODEL
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

TTS_MAX_CHARS = 200

TTS_SPEED = float(
    os.environ.get(
        "TTS_SPEED",
        "1.08"
    )
)

TTS_SAMPLE_RATE = 16000


# =====================================================
# HOME
# =====================================================

@app.route("/", methods=["GET"])
def home():

    print("[HOME] Request")

    return "ESP32 Female Voice Server is ONLINE!"


# =====================================================
# HEALTH
# =====================================================

@app.route("/health", methods=["GET"])
def health():

    data = {
        "status": "online",
        "stt_model": STT_MODEL,
        "ai_model": AI_MODEL,
        "tts_model": TTS_MODEL,
        "tts_voice": TTS_VOICE,
        "tts_speed": TTS_SPEED
    }

    print("[HEALTH]", data)

    return jsonify(data)


# =====================================================
# WAKE
# =====================================================

@app.route("/wake", methods=["POST", "GET"])
def wake():

    print()
    print("========================================")
    print("WAKE REQUEST RECEIVED")
    print("========================================")

    audio_data = request.get_data()

    print("METHOD:", request.method)
    print("CONTENT TYPE:", request.content_type)
    print("CONTENT LENGTH:", request.content_length)
    print("AUDIO BYTES:", len(audio_data))

    response_data = {
        "status": "ok",
        "wake": True,
        "english": "Hello",
        "hindi": None
    }

    print("WAKE RESPONSE:", response_data)
    print("========================================")

    return jsonify(response_data)


# =====================================================
# TEST
# =====================================================

@app.route("/test", methods=["POST"])
def test():

    print()
    print("========== TEST ==========")

    data = request.get_json(silent=True)

    print("DATA:", data)

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

        print("[STT] ERROR: AI_API_KEY missing")

        return None

    try:

        print()
        print("========================================")
        print("STT START")
        print("========================================")

        start = time.time()

        headers = {
            "Authorization":
                "Bearer " + AI_API_KEY,
            "Accept":
                "application/json"
        }

        with open(filename, "rb") as audio_file:

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

        elapsed = time.time() - start

        print("[STT] HTTP:", response.status_code)
        print("[STT] TIME:", round(elapsed, 2), "sec")

        if response.status_code != 200:

            print("[STT] ERROR:")
            print(response.text[:2000])

            return None

        result = response.json()

        text = clean_text(
            result.get("text", "")
        )

        print("[STT] TEXT:", text)
        print("========================================")

        if not is_valid_query(text):

            return None

        return text

    except Exception as e:

        print("[STT] EXCEPTION:", repr(e))

        return None


# =====================================================
# AI
# =====================================================

def get_ai_reply(user_text):

    user_text = clean_text(user_text)

    if not is_valid_query(user_text):

        return "Please ask your question again."

    if not AI_API_KEY:

        return "AI response nahi mil saka."

    print()
    print("========================================")
    print("AI START")
    print("========================================")

    system_prompt = """
You are a fast bilingual voice assistant.

Understand Hindi, English and Hinglish.

Reply naturally in the same language style.

Hindi input -> Hindi reply.
English input -> English reply.
Hinglish input -> natural Hinglish reply.

Keep answers very short.
Usually one sentence.
Maximum around 100 characters.

No markdown.
No bullets.
No emojis.
No AI mention.
No unnecessary explanation.

Sound natural and conversational.
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

        "max_tokens": 80,

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

        start = time.time()

        response = requests.post(
            AI_URL,
            headers=headers,
            json=payload,
            timeout=15
        )

        elapsed = time.time() - start

        print("[AI] HTTP:", response.status_code)
        print("[AI] TIME:", round(elapsed, 2), "sec")

        if response.status_code != 200:

            print("[AI] ERROR:")
            print(response.text[:2000])

            return "AI response nahi mil saka."

        data = response.json()

        choices = data.get("choices", [])

        if not choices:

            return "AI response nahi mil saka."

        reply = choices[0].get(
            "message",
            {}
        ).get(
            "content",
            ""
        )

        reply = clean_text(reply)

        reply = reply.replace(
            "```",
            ""
        ).strip()

        print("[AI] QUERY:", user_text)
        print("[AI] REPLY:", reply)

        print("========================================")

        if not reply:

            return "AI response nahi mil saka."

        return reply

    except Exception as e:

        print("[AI] EXCEPTION:", repr(e))

        return "AI response nahi mil saka."


# =====================================================
# TTS
# =====================================================

def generate_tts(text):

    text = clean_text(text)

    if not text:

        return None

    if not AI_API_KEY:

        print("[TTS] ERROR: API KEY missing")

        return None

    if len(text) > TTS_MAX_CHARS:

        text = text[:TTS_MAX_CHARS]

        last_dot = text.rfind(".")

        if last_dot > 40:

            text = text[:last_dot + 1]

    print()
    print("========================================")
    print("TTS START")
    print("========================================")

    print("[TTS] MODEL:", TTS_MODEL)
    print("[TTS] VOICE:", TTS_VOICE)
    print("[TTS] SPEED:", TTS_SPEED)
    print("[TTS] SAMPLE RATE:", TTS_SAMPLE_RATE)
    print("[TTS] TEXT:", text)

    payload = {

        "model": TTS_MODEL,

        "voice": TTS_VOICE,

        "input": text,

        "response_format": "wav",

        "sample_rate": TTS_SAMPLE_RATE,

        "speed": TTS_SPEED
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

        start = time.time()

        response = requests.post(
            TTS_URL,
            headers=headers,
            json=payload,
            timeout=20
        )

        elapsed = time.time() - start

        print("[TTS] HTTP:", response.status_code)
        print("[TTS] TIME:", round(elapsed, 2), "sec")

        if response.status_code != 200:

            print("[TTS] ERROR:")
            print(response.text[:2000])

            return None

        audio_data = response.content

        print(
            "[TTS] AUDIO BYTES:",
            len(audio_data)
        )

        print("========================================")

        return audio_data

    except Exception as e:

        print("[TTS] EXCEPTION:", repr(e))

        return None


# =====================================================
# TTS ENDPOINT
# =====================================================

@app.route("/tts", methods=["POST"])
def tts():

    print()
    print("========================================")
    print("TTS ENDPOINT")
    print("========================================")

    try:

        data = request.get_json(
            silent=True
        )

        print("[TTS ENDPOINT] JSON:", data)

        if not data:

            return jsonify({
                "status": "error",
                "message": "No JSON received"
            }), 400

        text = clean_text(
            data.get("text")
        )

        print("[TTS ENDPOINT] TEXT:", text)

        if not text:

            return jsonify({
                "status": "error",
                "message": "No text received"
            }), 400

        audio_data = generate_tts(text)

        if audio_data is None:

            return jsonify({
                "status": "error",
                "message": "TTS generation failed"
            }), 500

        print(
            "[TTS ENDPOINT] RETURNING:",
            len(audio_data),
            "bytes"
        )

        return Response(
            audio_data,
            status=200,
            mimetype="audio/wav",
            headers={
                "Cache-Control": "no-cache",
                "Content-Length":
                    str(len(audio_data))
            }
        )

    except Exception as e:

        print(
            "[TTS ENDPOINT] ERROR:",
            repr(e)
        )

        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


# =====================================================
# UPLOAD AUDIO
# =====================================================

@app.route("/uploadAudio", methods=["POST"])
def upload_audio():

    filename = None

    total_start = time.time()

    print()
    print("========================================")
    print("UPLOAD AUDIO START")
    print("========================================")

    try:

        audio_data = request.get_data()

        print(
            "[UPLOAD] CONTENT TYPE:",
            request.content_type
        )

        print(
            "[UPLOAD] CONTENT LENGTH:",
            request.content_length
        )

        print(
            "[UPLOAD] AUDIO BYTES:",
            len(audio_data)
        )

        if not audio_data:

            return jsonify({
                "status": "error",
                "message": "No audio received",
                "transcription": None,
                "ai_reply":
                    "Please ask your question again."
            }), 400

        fd, filename = tempfile.mkstemp(
            suffix=".wav"
        )

        os.close(fd)

        with open(filename, "wb") as f:

            f.write(audio_data)

        print(
            "[UPLOAD] WAV SAVED:",
            filename
        )

        # ================================
        # STT
        # ================================

        transcription = transcribe_audio(
            filename
        )

        print(
            "[UPLOAD] TRANSCRIPTION:",
            transcription
        )

        if not is_valid_query(
            transcription
        ):

            return jsonify({
                "status": "error",
                "message": "Speech not understood",
                "transcription": None,
                "hindi_transcription": None,
                "english_transcription": None,
                "ai_reply":
                    "Please ask your question again."
            }), 400

        # ================================
        # AI
        # ================================

        ai_reply = get_ai_reply(
            transcription
        )

        print(
            "[UPLOAD] AI REPLY:",
            ai_reply
        )

        total_time = (
            time.time() -
            total_start
        )

        response_data = {

            "status": "ok",

            "transcription":
                transcription,

            "hindi_transcription":
                transcription,

            "english_transcription":
                transcription,

            "ai_reply":
                ai_reply,

            "processing_time":
                round(total_time, 2)
        }

        print()
        print("========================================")
        print("UPLOAD FINAL RESPONSE")
        print("========================================")
        print(response_data)
        print(
            "TOTAL TIME:",
            round(total_time, 2),
            "sec"
        )
        print("========================================")

        return jsonify(response_data)

    except Exception as e:

        print(
            "[UPLOAD] SERVER ERROR:",
            repr(e)
        )

        return jsonify({
            "status": "error",
            "message": str(e),
            "transcription": None,
            "ai_reply":
                "AI response nahi mil saka."
        }), 500

    finally:

        if filename:

            try:

                if os.path.exists(filename):

                    os.remove(filename)

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
    print("ESP32 FEMALE VOICE SERVER")
    print("========================================")

    print("PORT:", port)
    print("STT:", STT_MODEL)
    print("AI:", AI_MODEL)
    print("TTS:", TTS_MODEL)
    print("VOICE:", TTS_VOICE)
    print("SPEED:", TTS_SPEED)

    print(
        "API KEY:",
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

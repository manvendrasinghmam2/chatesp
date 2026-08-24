from flask import Flask, request, jsonify, Response
import os
import io
import time
import wave
import requests
import tempfile


app = Flask(__name__)


# ============================================================
# CONFIG
# ============================================================

GROQ_API_KEY = os.environ.get("GROQ_API_KEY") or os.environ.get("AI_API_KEY")

GROQ_BASE = "https://api.groq.com/openai/v1"

CHAT_URL = os.environ.get(
    "AI_URL",
    f"{GROQ_BASE}/chat/completions"
)

STT_URL = os.environ.get(
    "STT_URL",
    f"{GROQ_BASE}/audio/transcriptions"
)

TTS_URL = os.environ.get(
    "TTS_URL",
    f"{GROQ_BASE}/audio/speech"
)


# Fast multilingual STT
STT_MODEL = os.environ.get(
    "STT_MODEL",
    "whisper-large-v3-turbo"
)


# Fast AI
AI_MODEL = os.environ.get(
    "AI_MODEL",
    "openai/gpt-oss-20b"
)


# Female TTS
TTS_MODEL = os.environ.get(
    "TTS_MODEL",
    "canopylabs/orpheus-v1-english"
)

TTS_VOICE = os.environ.get(
    "TTS_VOICE",
    "hannah"
)


TTS_MAX_CHARS = 200


# ============================================================
# HTTP SESSION
# ============================================================

session = requests.Session()

session.headers.update({
    "User-Agent": "ESP32-Advanced-Voice-Assistant/2.0"
})


# ============================================================
# HELPERS
# ============================================================

def clean_text(text):

    if text is None:
        return ""

    text = str(text).strip()

    text = " ".join(text.split())

    return text


def valid_text(text):

    text = clean_text(text)

    if len(text) < 1:
        return False

    bad = {
        "",
        "none",
        "null",
        "unknown",
        "no response",
        "no valid query",
        "speech not understood",
    }

    return text.lower() not in bad


def json_error(message, code=400):

    return jsonify({
        "status": "error",
        "message": message
    }), code


# ============================================================
# RETRY HTTP POST
# ============================================================

def post_with_retry(
    url,
    *,
    headers=None,
    data=None,
    json=None,
    files=None,
    timeout=30,
    retries=2
):

    last_error = None

    for attempt in range(retries + 1):

        try:

            response = session.post(
                url,
                headers=headers,
                data=data,
                json=json,
                files=files,
                timeout=timeout
            )

            # Successful
            if response.status_code < 400:
                return response

            # Retry temporary errors
            if response.status_code in (
                408,
                409,
                429,
                500,
                502,
                503,
                504
            ):

                retry_after = response.headers.get(
                    "Retry-After"
                )

                if retry_after:

                    try:
                        wait = min(
                            float(retry_after),
                            5
                        )

                    except Exception:
                        wait = 0.8

                else:

                    wait = 0.5 * (attempt + 1)

                print(
                    f"HTTP {response.status_code}, "
                    f"retry {attempt + 1}/{retries}"
                )

                if attempt < retries:

                    time.sleep(wait)

                    continue

            return response

        except requests.RequestException as e:

            last_error = e

            print(
                "NETWORK ERROR:",
                str(e)
            )

            if attempt < retries:

                time.sleep(
                    0.5 * (attempt + 1)
                )

                continue

    raise last_error


# ============================================================
# HEALTH
# ============================================================

@app.route("/", methods=["GET"])
def home():

    return "ESP32 Advanced Voice Server ONLINE"


@app.route("/health", methods=["GET"])
def health():

    return jsonify({
        "status": "online",
        "stt": STT_MODEL,
        "ai": AI_MODEL,
        "tts": TTS_MODEL,
        "voice": TTS_VOICE,
        "voice_gender": "female"
    })


# ============================================================
# WAKE
# ============================================================

@app.route(
    "/wake",
    methods=["POST"]
)
def wake():

    # Keep wake extremely fast.
    # ESP32 has already decided to ask wake endpoint.

    return jsonify({
        "status": "ok",
        "wake": True
    })


# ============================================================
# TRANSCRIBE
# ============================================================

def transcribe_audio(
    audio_data
):

    if not audio_data:
        return None

    if not GROQ_API_KEY:
        print("GROQ_API_KEY missing")
        return None

    headers = {
        "Authorization":
            f"Bearer {GROQ_API_KEY}"
    }

    files = {
        "file": (
            "audio.wav",
            audio_data,
            "audio/wav"
        )
    }

    data = {
        "model": STT_MODEL,

        # Multilingual:
        # don't force hi/en here.
        "response_format": "json",

        "temperature": "0",

        "prompt": (
            "This is a voice assistant conversation. "
            "The user may speak English, Hindi, or Hinglish. "
            "Transcribe exactly what the user says."
        )
    }

    try:

        start = time.monotonic()

        response = post_with_retry(
            STT_URL,
            headers=headers,
            files=files,
            data=data,
            timeout=25,
            retries=2
        )

        elapsed = (
            time.monotonic() - start
        ) * 1000

        print(
            f"STT HTTP: {response.status_code} "
            f"TIME: {elapsed:.0f} ms"
        )

        if response.status_code != 200:

            print(
                "STT ERROR:",
                response.text[:1000]
            )

            return None

        result = response.json()

        text = clean_text(
            result.get("text")
        )

        print(
            "TRANSCRIPTION:",
            text
        )

        return text if valid_text(text) else None

    except Exception as e:

        print(
            "STT EXCEPTION:",
            str(e)
        )

        return None


# ============================================================
# AI
# ============================================================

def get_ai_reply(
    user_text
):

    user_text = clean_text(
        user_text
    )

    if not valid_text(user_text):

        return (
            "Please ask your question again."
        )

    if not GROQ_API_KEY:

        return (
            "AI service is not configured."
        )

    system_prompt = """
You are an advanced voice assistant running on an ESP32.

The user may speak:
- English
- Hindi
- Hinglish
- Roman Hindi

Understand the user's actual meaning.

LANGUAGE:
English question -> answer in English.
Hindi question -> answer in Hindi.
Hinglish/Roman Hindi -> answer naturally in Hinglish.

IMPORTANT:
Do not translate unnecessarily.
Do not mention transcription.
Do not mention AI.
Do not explain your reasoning.

VOICE:
Your response will be spoken by a female voice.

Be natural, friendly and conversational.

Keep the answer concise.
Normally 1 or 2 sentences.
Maximum about 180 characters.

No markdown.
No bullet points.
No headings.
No emojis.
Do not repeat the question.

For simple greetings, respond naturally.
For factual questions, give the direct answer.
For calculations, give the result directly.
"""


    payload = {

        "model":
            AI_MODEL,

        "messages": [

            {
                "role":
                    "system",

                "content":
                    system_prompt
            },

            {
                "role":
                    "user",

                "content":
                    user_text
            }
        ],

        "temperature":
            0.15,

        "max_completion_tokens":
            180,

        "stream":
            False
    }


    headers = {

        "Authorization":
            f"Bearer {GROQ_API_KEY}",

        "Content-Type":
            "application/json"
    }


    try:

        start = time.monotonic()

        response = post_with_retry(
            CHAT_URL,
            headers=headers,
            json=payload,
            timeout=25,
            retries=2
        )

        elapsed = (
            time.monotonic() - start
        ) * 1000

        print(
            f"AI HTTP: {response.status_code} "
            f"TIME: {elapsed:.0f} ms"
        )

        if response.status_code != 200:

            print(
                "AI ERROR:",
                response.text[:1500]
            )

            return (
                "AI response nahi mil saka."
            )

        data = response.json()

        choices = data.get(
            "choices",
            []
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
            "content"
        )

        reply = clean_text(
            reply
        )

        if not reply:

            return (
                "AI response nahi mil saka."
            )

        # Remove accidental markdown
        reply = reply.replace(
            "```",
            ""
        )

        reply = clean_text(
            reply
        )

        print(
            "AI REPLY:",
            reply
        )

        return reply

    except Exception as e:

        print(
            "AI EXCEPTION:",
            str(e)
        )

        return (
            "AI response nahi mil saka."
        )


# ============================================================
# TTS
# ============================================================

def generate_tts(
    text
):

    text = clean_text(
        text
    )

    if not text:
        return None

    if not GROQ_API_KEY:
        return None

    # Orpheus input max = 200 characters
    if len(text) > TTS_MAX_CHARS:

        text = text[:TTS_MAX_CHARS]

        cut = max(
            text.rfind("."),
            text.rfind("?"),
            text.rfind("!")
        )

        if cut > 60:

            text = text[:cut + 1]

    payload = {

        "model":
            TTS_MODEL,

        "voice":
            TTS_VOICE,

        "input":
            text,

        "response_format":
            "wav"
    }

    headers = {

        "Authorization":
            f"Bearer {GROQ_API_KEY}",

        "Content-Type":
            "application/json",

        "Accept":
            "audio/wav"
    }


    try:

        start = time.monotonic()

        response = post_with_retry(
            TTS_URL,
            headers=headers,
            json=payload,
            timeout=30,
            retries=2
        )

        elapsed = (
            time.monotonic() - start
        ) * 1000

        print(
            f"TTS HTTP: {response.status_code} "
            f"TIME: {elapsed:.0f} ms"
        )

        if response.status_code != 200:

            print(
                "TTS ERROR:",
                response.text[:1500]
            )

            return None

        audio = response.content

        if len(audio) < 44:

            print(
                "TTS WAV TOO SMALL"
            )

            return None

        # Validate WAV
        try:

            with wave.open(
                io.BytesIO(audio),
                "rb"
            ) as wav:

                channels = wav.getnchannels()
                rate = wav.getframerate()
                width = wav.getsampwidth()
                frames = wav.getnframes()

                print(
                    "TTS WAV:",
                    rate,
                    "Hz",
                    channels,
                    "CH",
                    width * 8,
                    "BIT",
                    frames,
                    "FRAMES"
                )

        except Exception as e:

            print(
                "TTS WAV VALIDATION ERROR:",
                str(e)
            )

            return None

        print(
            "TTS AUDIO BYTES:",
            len(audio)
        )

        print(
            "FEMALE VOICE:",
            TTS_VOICE
        )

        return audio

    except Exception as e:

        print(
            "TTS EXCEPTION:",
            str(e)
        )

        return None


# ============================================================
# TTS ENDPOINT
# ============================================================

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

            return json_error(
                "No JSON received"
            )

        text = clean_text(
            data.get("text")
        )

        if not text:

            return json_error(
                "No text received"
            )

        audio = generate_tts(
            text
        )

        if audio is None:

            return jsonify({
                "status":
                    "error",

                "message":
                    "TTS generation failed"
            }), 502

        response = Response(
            audio,
            status=200,
            content_type="audio/wav"
        )

        response.headers[
            "Content-Length"
        ] = str(len(audio))

        response.headers[
            "Cache-Control"
        ] = "no-cache, no-store"

        response.headers[
            "Connection"
        ] = "close"

        return response

    except Exception as e:

        print(
            "TTS ROUTE ERROR:",
            str(e)
        )

        return jsonify({
            "status":
                "error",

            "message":
                "TTS server error"
        }), 500


# ============================================================
# MAIN AUDIO ENDPOINT
# ============================================================

@app.route(
    "/uploadAudio",
    methods=["POST"]
)
def upload_audio():

    start_total = time.monotonic()

    try:

        audio_data = request.get_data(
            cache=False
        )

        print()
        print("========================================")
        print("AUDIO REQUEST")
        print("========================================")

        print(
            "CONTENT TYPE:",
            request.content_type
        )

        print(
            "AUDIO BYTES:",
            len(audio_data)
        )

        if not audio_data:

            return jsonify({
                "status":
                    "error",

                "message":
                    "No audio received",

                "ai_reply":
                    "Please ask your question again."
            }), 400


        # ----------------------------------------------------
        # STT
        # ----------------------------------------------------

        user_text = transcribe_audio(
            audio_data
        )

        if not valid_text(user_text):

            print(
                "SPEECH NOT UNDERSTOOD"
            )

            return jsonify({

                "status":
                    "error",

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


        # ----------------------------------------------------
        # AI
        # ----------------------------------------------------

        ai_reply = get_ai_reply(
            user_text
        )


        # ----------------------------------------------------
        # FINAL
        # ----------------------------------------------------

        elapsed = (
            time.monotonic() -
            start_total
        ) * 1000

        response_data = {

            "status":
                "ok",

            "transcription":
                user_text,

            "hindi_transcription":
                None,

            "english_transcription":
                user_text,

            "ai_reply":
                ai_reply,

            "tts_voice":
                TTS_VOICE,

            "processing_ms":
                round(elapsed)
        }

        print(
            "FINAL:",
            response_data
        )

        return jsonify(
            response_data
        )

    except Exception as e:

        print(
            "UPLOAD ERROR:",
            type(e).__name__,
            str(e)
        )

        return jsonify({

            "status":
                "error",

            "message":
                "Server error",

            "ai_reply":
                "Please try again."
        }), 500


# ============================================================
# START
# ============================================================

if __name__ == "__main__":

    port = int(
        os.environ.get(
            "PORT",
            "10000"
        )
    )

    print()
    print("========================================")
    print("ESP32 ADVANCED VOICE SERVER")
    print("========================================")

    print(
        "PORT:",
        port
    )

    print(
        "STT:",
        STT_MODEL
    )

    print(
        "AI:",
        AI_MODEL
    )

    print(
        "TTS:",
        TTS_MODEL
    )

    print(
        "VOICE:",
        TTS_VOICE
    )

    print(
        "GROQ KEY:",
        "CONFIGURED"
        if GROQ_API_KEY
        else "MISSING"
    )

    print("========================================")

    app.run(
        host="0.0.0.0",
        port=port,
        threaded=True
    )

from flask import Flask, request, jsonify, Response
import os
import re
import tempfile
import requests
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

AI_MODEL = os.environ.get(
    "AI_MODEL",
    "openai/gpt-oss-20b"
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

# Female Hannah
TTS_VOICE = os.environ.get(
    "TTS_VOICE",
    "hannah"
)

TTS_MAX_CHARS = 200

# =====================================================
# HTTP SESSION
# =====================================================

http = requests.Session()

http.headers.update({
    "User-Agent": "ESP32-Advanced-Voice/2.0",
    "Connection": "keep-alive"
})

# =====================================================
# HOME
# =====================================================

@app.route("/")
def home():

    return "ESP32 Advanced Voice Server ONLINE"


# =====================================================
# HEALTH
# =====================================================

@app.route("/health")
def health():

    return jsonify({
        "status": "online",
        "stt": STT_MODEL,
        "ai": AI_MODEL,
        "tts": TTS_MODEL,
        "voice": TTS_VOICE,
        "gender": "female"
    })


# =====================================================
# WAKE
# =====================================================

@app.route(
    "/wake",
    methods=["POST"]
)
def wake():

    audio = request.get_data()

    print()
    print("========== WAKE ==========")
    print(
        "AUDIO:",
        len(audio)
    )

    # -------------------------------------------------
    # IMPORTANT
    # -------------------------------------------------
    #
    # Current behavior:
    # ESP32 enters wake mode by asking server.
    #
    # If you want REAL "HELLO" detection,
    # use /wake STT separately.
    #
    # For maximum speed/stability this endpoint
    # simply confirms the wake request.
    #
    # -------------------------------------------------

    return jsonify({
        "status": "ok",
        "wake": True
    })


# =====================================================
# CLEAN
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
# VALID
# =====================================================

def is_valid_query(text):

    if not text:
        return False

    text = clean_text(text)

    if len(text) < 2:
        return False

    bad = {
        "",
        "unknown",
        "none",
        "null",
        "no response",
        "no speech",
        "speech not understood"
    }

    if text.lower() in bad:
        return False

    return True


# =====================================================
# STT
# =====================================================

def transcribe_audio(
    filename
):

    if not AI_API_KEY:
        return None

    try:

        print()
        print(
            "========== WHISPER STT =========="
        )

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
                "language": "hi",
                "response_format": "json",
                "temperature": "0"
            }

            headers = {
                "Authorization":
                    "Bearer " + AI_API_KEY
            }

            start = time.time()

            response = http.post(
                STT_URL,
                headers=headers,
                files=files,
                data=data,
                timeout=(5, 25)
            )

        elapsed = (
            time.time() - start
        )

        print(
            "STT HTTP:",
            response.status_code
        )

        print(
            "STT TIME:",
            round(elapsed, 2),
            "sec"
        )

        if response.status_code != 200:

            print(
                "STT ERROR:",
                response.text[:1000]
            )

            return None

        result = response.json()

        text = clean_text(
            result.get(
                "text",
                ""
            )
        )

        print(
            "STT:",
            text
        )

        return text if text else None

    except requests.exceptions.Timeout:

        print(
            "STT TIMEOUT"
        )

        return None

    except Exception as e:

        print(
            "STT ERROR:",
            type(e).__name__,
            str(e)
        )

        return None


# =====================================================
# LANGUAGE DETECTION
# =====================================================

def contains_devanagari(text):

    if not text:
        return False

    return bool(
        re.search(
            r"[\u0900-\u097F]",
            text
        )
    )


def likely_english(text):

    if not text:
        return False

    english_words = {
        "what",
        "why",
        "how",
        "when",
        "where",
        "who",
        "which",
        "is",
        "are",
        "was",
        "were",
        "can",
        "could",
        "would",
        "should",
        "tell",
        "give",
        "show",
        "explain",
        "hello",
        "hi",
        "thanks",
        "thank",
        "you",
        "good",
        "morning",
        "weather",
        "time"
    }

    words = set(
        re.findall(
            r"[a-zA-Z]+",
            text.lower()
        )
    )

    return bool(
        words.intersection(
            english_words
        )
    )


# =====================================================
# AI
# =====================================================

def get_ai_reply(
    transcription
):

    transcription = clean_text(
        transcription
    )

    if not transcription:
        return (
            "Please ask your question again."
        )

    system_prompt = """
You are an advanced voice assistant running on ESP32.

The user speaks naturally in Hindi, English,
Roman Hindi or Hinglish.

Understand the intended meaning.

LANGUAGE:

If English -> answer in English.

If Hindi -> answer in Hindi.

If Hinglish/Roman Hindi -> answer in natural Hinglish.

Do not explain the language choice.

VOICE:

This answer will be spoken aloud by a female voice.

Keep it short, natural and conversational.

Normally 1 or 2 sentences.

Maximum 180 characters.

Do not use markdown.

Do not use bullets.

Do not use emojis.

Do not use headings.

Do not repeat the user's question.

Do not say "As an AI".

Never output JSON.

Give only the spoken answer.
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
                "content": transcription
            }
        ],

        "temperature": 0.2,

        "max_completion_tokens": 120,

        "stream": False
    }

    headers = {
        "Authorization":
            "Bearer " + AI_API_KEY,

        "Content-Type":
            "application/json"
    }

    for attempt in range(2):

        try:

            print()
            print(
                "========== AI =========="
            )

            start = time.time()

            response = http.post(
                AI_URL,
                headers=headers,
                json=payload,
                timeout=(5, 20)
            )

            print(
                "AI HTTP:",
                response.status_code
            )

            print(
                "AI TIME:",
                round(
                    time.time() - start,
                    2
                ),
                "sec"
            )

            if response.status_code == 200:

                data = response.json()

                choices = data.get(
                    "choices",
                    []
                )

                if not choices:
                    continue

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

                reply = re.sub(
                    r"^```.*?```$",
                    "",
                    reply,
                    flags=re.S
                )

                reply = clean_text(
                    reply
                )

                if reply:

                    # Hard safety limit for TTS
                    if len(reply) > 180:

                        reply = reply[:180]

                        last = max(
                            reply.rfind("."),
                            reply.rfind("!"),
                            reply.rfind("?")
                        )

                        if last > 60:
                            reply = reply[:last + 1]

                    print(
                        "AI:",
                        reply
                    )

                    return reply

            else:

                print(
                    response.text[:1000]
                )

        except requests.exceptions.Timeout:

            print(
                "AI TIMEOUT"
            )

        except Exception as e:

            print(
                "AI ERROR:",
                str(e)
            )

        time.sleep(0.15)

    return (
        "Sorry, please try again."
    )


# =====================================================
# TTS
# =====================================================

def generate_tts(
    text
):

    text = clean_text(text)

    if not text:
        return None

    if not AI_API_KEY:
        return None

    # Groq Orpheus max 200 chars.
    text = text[:TTS_MAX_CHARS]

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
            "Bearer " + AI_API_KEY,

        "Content-Type":
            "application/json",

        "Accept":
            "audio/wav"
    }

    for attempt in range(2):

        try:

            print()
            print(
                "========== TTS =========="
            )

            print(
                "VOICE:",
                TTS_VOICE
            )

            print(
                "TEXT:",
                text
            )

            start = time.time()

            response = http.post(
                TTS_URL,
                headers=headers,
                json=payload,
                timeout=(5, 35)
            )

            elapsed = (
                time.time() - start
            )

            print(
                "TTS HTTP:",
                response.status_code
            )

            print(
                "TTS TIME:",
                round(elapsed, 2),
                "sec"
            )

            if response.status_code != 200:

                print(
                    response.text[:1000]
                )

                continue

            audio = response.content

            if not audio:
                continue

            print(
                "TTS BYTES:",
                len(audio)
            )

            return audio

        except requests.exceptions.Timeout:

            print(
                "TTS TIMEOUT"
            )

        except Exception as e:

            print(
                "TTS ERROR:",
                str(e)
            )

        time.sleep(0.2)

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

        audio = generate_tts(
            text
        )

        if audio is None:

            return jsonify({
                "status": "error",
                "message":
                    "TTS failed"
            }), 500

        response = Response(
            audio,
            status=200,
            mimetype="audio/wav"
        )

        response.headers[
            "Content-Length"
        ] = str(len(audio))

        response.headers[
            "Cache-Control"
        ] = (
            "no-cache, no-store, must-revalidate"
        )

        response.headers[
            "Connection"
        ] = "close"

        return response

    except Exception as e:

        print(
            "TTS ENDPOINT ERROR:",
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

    request_start = time.time()

    try:

        audio_data =
            request.get_data()

        print()
        print(
            "========================================"
        )

        print(
            "AUDIO REQUEST"
        )

        print(
            "BYTES:",
            len(audio_data)
        )

        print(
            "========================================"
        )

        if not audio_data:

            return jsonify({
                "status": "error",
                "message":
                    "No audio received",
                "ai_reply":
                    "Please ask your question again."
            }), 400

        # ---------------------------------------------
        # SAVE
        # ---------------------------------------------

        fd, filename = tempfile.mkstemp(
            suffix=".wav"
        )

        os.close(fd)

        with open(
            filename,
            "wb"
        ) as f:

            f.write(audio_data)

        # ---------------------------------------------
        # STT
        # ---------------------------------------------

        transcription = transcribe_audio(
            filename
        )

        if not is_valid_query(
            transcription
        ):

            print(
                "SPEECH NOT UNDERSTOOD"
            )

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

        # ---------------------------------------------
        # LANGUAGE FIELDS
        # ---------------------------------------------

        if contains_devanagari(
            transcription
        ):

            hindi_text = transcription
            english_text = None

        else:

            hindi_text = None
            english_text = transcription

        # ---------------------------------------------
        # AI
        # ---------------------------------------------

        ai_reply = get_ai_reply(
            transcription
        )

        # ---------------------------------------------
        # RESPONSE
        # ---------------------------------------------

        result = {
            "status": "ok",

            "transcription":
                transcription,

            "hindi_transcription":
                hindi_text,

            "english_transcription":
                english_text,

            "ai_reply":
                ai_reply,

            "tts_voice":
                TTS_VOICE
        }

        print()
        print(
            "========== FINAL =========="
        )

        print(
            result
        )

        print(
            "TOTAL TIME:",
            round(
                time.time() -
                request_start,
                2
            ),
            "sec"
        )

        return jsonify(result)

    except Exception as e:

        print(
            "UPLOAD ERROR:",
            type(e).__name__,
            str(e)
        )

        return jsonify({
            "status": "error",

            "message":
                "Server error",

            "transcription":
                None,

            "hindi_transcription":
                None,

            "english_transcription":
                None,

            "ai_reply":
                "Please try again."
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
    print(
        "========================================"
    )

    print(
        "ESP32 ADVANCED FEMALE VOICE SERVER"
    )

    print(
        "========================================"
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
        "PORT:",
        port
    )

    print(
        "API KEY:",
        "YES"
        if AI_API_KEY
        else "NO"
    )

    print(
        "========================================"
    )

    app.run(
        host="0.0.0.0",
        port=port,
        threaded=True
    )

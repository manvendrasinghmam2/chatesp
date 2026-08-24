from flask import Flask, request, jsonify, Response
import os
import re
import tempfile
import time

import requests
import speech_recognition as sr


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

TTS_URL = os.environ.get(
    "TTS_URL",
    "https://api.groq.com/openai/v1/audio/speech"
)

TTS_MODEL = os.environ.get(
    "TTS_MODEL",
    "canopylabs/orpheus-v1-english"
)

TTS_VOICE = os.environ.get(
    "TTS_VOICE",
    "hannah"
)

TTS_MAX_CHARS = 200

HTTP_TIMEOUT = (
    8,
    35
)

session = requests.Session()

session.headers.update({
    "User-Agent":
        "ESP32-Advanced-Voice-Server"
})

# =====================================================
# HOME
# =====================================================

@app.route("/")
def home():

    return jsonify({
        "status": "online",
        "service": "ESP32 Voice Assistant",
        "tts_voice": TTS_VOICE
    })

# =====================================================
# HEALTH
# =====================================================

@app.route("/health")
def health():

    return jsonify({
        "status": "online",
        "ai_model": AI_MODEL,
        "tts_model": TTS_MODEL,
        "tts_voice": TTS_VOICE,
        "voice_gender": "female"
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

    print(
        "WAKE:",
        len(audio),
        "bytes"
    )

    if not audio:

        return jsonify({
            "status": "error",
            "wake": False
        }), 400

    # Current architecture:
    # ESP32 enters active mode after wake request.
    return jsonify({
        "status": "ok",
        "wake": True
    })

# =====================================================
# CLEAN
# =====================================================

def clean_text(text):

    if text is None:
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

def valid_text(text):

    text = clean_text(text)

    if len(text) < 2:
        return False

    bad = {
        "",
        "unknown",
        "none",
        "null",
        "no response",
        "speech not understood"
    }

    return text.lower() not in bad

# =====================================================
# AI
# =====================================================

def get_ai_reply(
    hindi_text,
    english_text
):

    hindi_text =
        clean_text(hindi_text)

    english_text =
        clean_text(english_text)

    if (
        not valid_text(hindi_text)
        and
        not valid_text(english_text)
    ):

        return (
            "Please ask your question again."
        )

    system_prompt = """
You are an advanced bilingual voice assistant.

You are speaking through an ESP32 speaker.

Determine the user's intended language and meaning.

Rules:

English speech -> natural English.

Hindi speech -> natural Hindi.

Hinglish/Roman Hindi -> natural Hinglish.

If one transcription is obviously wrong,
use the other transcription.

Never mention transcription.

Never mention AI.

Never explain language selection.

Answer directly.

Voice style:

Natural.
Friendly.
Short.
Clear.
Conversational.

Usually one or two sentences.

Keep the response under 180 characters.

No markdown.
No bullets.
No emojis.
No headings.
No unnecessary explanation.
"""

    user_prompt = f"""
Hindi recognition:
{hindi_text or "No result"}

English recognition:
{english_text or "No result"}

Answer the user's intended question.
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
                "content": user_prompt
            }
        ],

        "temperature": 0.15,

        "max_completion_tokens": 180,

        "stream": False
    }

    headers = {
        "Authorization":
            f"Bearer {AI_API_KEY}",

        "Content-Type":
            "application/json",

        "Accept":
            "application/json"
    }

    for attempt in range(2):

        try:

            started = time.time()

            response = session.post(
                AI_URL,
                headers=headers,
                json=payload,
                timeout=HTTP_TIMEOUT
            )

            elapsed = (
                time.time() -
                started
            )

            print(
                f"AI HTTP={response.status_code} "
                f"time={elapsed:.2f}s"
            )

            if response.status_code != 200:

                print(
                    response.text[:1000]
                )

                if attempt == 0:
                    time.sleep(0.15)
                    continue

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
                "content",
                ""
            )

            reply = clean_text(
                reply
            )

            reply = reply.replace(
                "```",
                ""
            ).strip()

            for prefix in (
                "AI:",
                "Answer:",
                "Response:"
            ):

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

        except Exception as e:

            print(
                "AI ERROR:",
                type(e).__name__,
                str(e)
            )

            if attempt == 0:
                time.sleep(0.15)

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
            "TTS: API KEY MISSING"
        )

        return None

    if len(text) > TTS_MAX_CHARS:

        text =
            text[:TTS_MAX_CHARS]

        dot =
            text.rfind(".")

        if dot > 50:

            text =
                text[:dot + 1]

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
            f"Bearer {AI_API_KEY}",

        "Content-Type":
            "application/json",

        "Accept":
            "audio/wav"
    }

    for attempt in range(2):

        try:

            started =
                time.time()

            response = session.post(
                TTS_URL,
                headers=headers,
                json=payload,
                timeout=HTTP_TIMEOUT
            )

            elapsed = (
                time.time() -
                started
            )

            print(
                f"TTS HTTP={response.status_code} "
                f"time={elapsed:.2f}s"
            )

            if response.status_code != 200:

                print(
                    response.text[:1000]
                )

                if attempt == 0:

                    time.sleep(0.15)
                    continue

                return None

            audio =
                response.content

            if not audio:

                return None

            print(
                "TTS BYTES:",
                len(audio)
            )

            print(
                "TTS VOICE:",
                TTS_VOICE
            )

            return audio

        except Exception as e:

            print(
                "TTS ERROR:",
                type(e).__name__,
                str(e)
            )

            if attempt == 0:

                time.sleep(0.15)

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

        data =
            request.get_json(
                silent=True
            )

        if not data:

            return jsonify({
                "status": "error",
                "message":
                    "No JSON received"
            }), 400

        text =
            clean_text(
                data.get("text")
            )

        if not text:

            return jsonify({
                "status": "error",
                "message":
                    "No text received"
            }), 400

        audio =
            generate_tts(text)

        if not audio:

            return jsonify({
                "status": "error",
                "message":
                    "TTS generation failed"
            }), 502

        response =
            Response(
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
            "no-cache, no-store, "
            "must-revalidate"
        )

        response.headers[
            "Connection"
        ] = "close"

        response.headers[
            "X-TTS-Voice"
        ] = TTS_VOICE

        return response

    except Exception as e:

        print(
            "TTS ENDPOINT ERROR:",
            str(e)
        )

        return jsonify({
            "status": "error",
            "message":
                "TTS server error"
        }), 500

# =====================================================
# SPEECH RECOGNITION
# =====================================================

def recognize_audio(
    audio
):

    recognizer =
        sr.Recognizer()

    # More reliable for voice commands
    recognizer.energy_threshold = 300
    recognizer.dynamic_energy_threshold = True

    hindi = None
    english = None

    # -----------------------------------------------
    # Hindi
    # -----------------------------------------------

    try:

        hindi =
            recognizer.recognize_google(
                audio,
                language="hi-IN"
            )

        hindi =
            clean_text(hindi)

        print(
            "HINDI:",
            hindi
        )

    except sr.UnknownValueError:

        print(
            "HINDI: NO MATCH"
        )

    except sr.RequestError as e:

        print(
            "HINDI SERVICE ERROR:",
            str(e)
        )

    # -----------------------------------------------
    # English
    # -----------------------------------------------

    try:

        english =
            recognizer.recognize_google(
                audio,
                language="en-IN"
            )

        english =
            clean_text(english)

        print(
            "ENGLISH:",
            english
        )

    except sr.UnknownValueError:

        print(
            "ENGLISH: NO MATCH"
        )

    except sr.RequestError as e:

        print(
            "ENGLISH SERVICE ERROR:",
            str(e)
        )

    return hindi, english

# =====================================================
# UPLOAD AUDIO
# =====================================================

@app.route(
    "/uploadAudio",
    methods=["POST"]
)
def upload_audio():

    filename = None

    started =
        time.time()

    try:

        audio_data =
            request.get_data()

        print()
        print(
            "================================"
        )

        print(
            "AUDIO REQUEST"
        )

        print(
            "BYTES:",
            len(audio_data)
        )

        print(
            "CONTENT TYPE:",
            request.content_type
        )

        print(
            "================================"
        )

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

        # -------------------------------------------
        # Save WAV
        # -------------------------------------------

        fd, filename =
            tempfile.mkstemp(
                suffix=".wav"
            )

        os.close(fd)

        with open(
            filename,
            "wb"
        ) as f:

            f.write(audio_data)

        # -------------------------------------------
        # Read WAV
        # -------------------------------------------

        recognizer =
            sr.Recognizer()

        with sr.AudioFile(
            filename
        ) as source:

            audio =
                recognizer.record(
                    source
                )

        # -------------------------------------------
        # Recognition
        # -------------------------------------------

        hindi, english =
            recognize_audio(
                audio
            )

        if (
            not valid_text(hindi)
            and
            not valid_text(english)
        ):

            print(
                "SPEECH: NOT UNDERSTOOD"
            )

            return jsonify({
                "status": "error",
                "message":
                    "Speech not understood",
                "transcription":
                    None,
                "hindi_transcription":
                    hindi,
                "english_transcription":
                    english,
                "ai_reply":
                    "Please ask your question again."
            }), 400

        # -------------------------------------------
        # AI
        # -------------------------------------------

        ai_reply =
            get_ai_reply(
                hindi,
                english
            )

        if valid_text(english):

            transcription =
                english

        else:

            transcription =
                hindi

        elapsed =
            time.time() - started

        response = {

            "status":
                "ok",

            "transcription":
                transcription,

            "hindi_transcription":
                hindi,

            "english_transcription":
                english,

            "ai_reply":
                ai_reply,

            "tts_voice":
                TTS_VOICE,

            "processing_time":
                round(elapsed, 3)
        }

        print(
            "FINAL:",
            response
        )

        return jsonify(
            response
        )

    except Exception as e:

        print(
            "UPLOAD ERROR:",
            type(e).__name__,
            str(e)
        )

        return jsonify({
            "status": "error",
            "message":
                "Server processing error",
            "transcription":
                None,
            "hindi_transcription":
                None,
            "english_transcription":
                None,
            "ai_reply":
                "Please ask your question again."
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

    port =
        int(
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
        "ESP32 ADVANCED VOICE SERVER"
    )

    print(
        "========================================"
    )

    print(
        "PORT:",
        port
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
        "========================================"
    )

    app.run(
        host="0.0.0.0",
        port=port,
        threaded=True
    )

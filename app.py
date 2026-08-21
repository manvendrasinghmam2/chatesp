from flask import Flask, request, jsonify
import os
import tempfile
import logging
import time

import requests
import speech_recognition as sr


# =====================================================
# APP
# =====================================================

app = Flask(__name__)

# Maximum HTTP request size
app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024


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
    "llama-3.1-8b-instant"
)

PORT = int(
    os.environ.get(
        "PORT",
        "10000"
    )
)

# Speech recognition
SPEECH_TIMEOUT = int(
    os.environ.get(
        "SPEECH_TIMEOUT",
        "15"
    )
)

# Groq
AI_TIMEOUT = int(
    os.environ.get(
        "AI_TIMEOUT",
        "30"
    )
)

AI_RETRIES = int(
    os.environ.get(
        "AI_RETRIES",
        "2"
    )
)


# =====================================================
# LOGGING
# =====================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

logger = logging.getLogger("esp32-voice")


# =====================================================
# HEALTH
# =====================================================

@app.route("/", methods=["GET"])
def home():

    return "ESP32 Voice Server is ONLINE!"


@app.route("/health", methods=["GET"])
def health():

    return jsonify({

        "status": "online",

        "speech_engine":
            "Google Speech Recognition",

        "ai_engine":
            "Groq",

        "model":
            AI_MODEL,

        "ai_configured":
            bool(AI_API_KEY)

    })


# =====================================================
# WAKE ENDPOINT
#
# IMPORTANT:
# Existing ESP32 wake code should call /wake.
#
# We don't require a separate wake system.
# ESP32 can use this endpoint for HELLO detection.
# =====================================================

@app.route("/wake", methods=["POST", "GET"])
def wake():

    return jsonify({

        "status": "ok",

        "wake": True,

        "english": "Hello",

        "hindi": None

    })


# =====================================================
# CLEAN TEXT
# =====================================================

def clean_text(text):

    if text is None:
        return None

    text = str(text).strip()

    if not text:
        return None

    # Remove excessive whitespace
    text = " ".join(
        text.split()
    )

    if len(text) < 2:
        return None

    return text


# =====================================================
# CHOOSE BEST TRANSCRIPTION
# =====================================================

def choose_best_transcription(
    hindi_text,
    english_text
):

    hindi_text = clean_text(
        hindi_text
    )

    english_text = clean_text(
        english_text
    )

    # -------------------------------------------------
    # Nothing
    # -------------------------------------------------

    if not hindi_text and not english_text:
        return None

    # -------------------------------------------------
    # Only English
    # -------------------------------------------------

    if english_text and not hindi_text:

        return english_text

    # -------------------------------------------------
    # Only Hindi
    # -------------------------------------------------

    if hindi_text and not english_text:

        return hindi_text

    # -------------------------------------------------
    # Both available
    #
    # We send BOTH to AI so AI can determine intent.
    # For the visible transcription choose English
    # because Google en-IN often produces the cleaner
    # Roman/Hinglish form.
    # -------------------------------------------------

    return english_text


# =====================================================
# AI
# =====================================================

def get_ai_reply(
    user_text,
    hindi_text=None,
    english_text=None
):

    user_text = clean_text(
        user_text
    )

    if not user_text:

        return (
            "Please ask your question again.",
            "empty_query"
        )

    # -------------------------------------------------
    # API KEY
    # -------------------------------------------------

    if not AI_API_KEY:

        logger.error(
            "AI_API_KEY is missing"
        )

        return (
            "AI service is not configured.",
            "missing_api_key"
        )

    # -------------------------------------------------
    # IMPORTANT:
    # Keep system instruction SHORT.
    # No huge language prompt.
    # -------------------------------------------------

    system_prompt = (
        "You are a professional voice assistant. "
        "Answer naturally and accurately. "
        "Reply in the same language the user intended: "
        "English, Hindi, or Hinglish. "
        "Keep voice responses concise. "
        "Do not use markdown, emojis, headings, or bullet points."
    )

    # -------------------------------------------------
    # LANGUAGE CONTEXT
    # -------------------------------------------------

    context = ""

    if hindi_text and english_text:

        context = f"""
Speech recognition produced two versions.

Hindi recognition:
{hindi_text}

English recognition:
{english_text}

Determine the user's intended language from both results.
Do not blindly follow the script.
"""

    elif hindi_text:

        context = f"""
Hindi speech recognition:
{hindi_text}
"""

    elif english_text:

        context = f"""
English speech recognition:
{english_text}
"""

    # -------------------------------------------------
    # USER MESSAGE
    # -------------------------------------------------

    user_message = f"""
{context}

User's question:
{user_text}

Answer the user's question directly.
"""

    # -------------------------------------------------
    # PAYLOAD
    # -------------------------------------------------

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
                    user_message
            }

        ],

        "temperature":
            0.2,

        "max_completion_tokens":
            180,

        "stream":
            False
    }

    # -------------------------------------------------
    # HEADERS
    # -------------------------------------------------

    headers = {

        "Authorization":
            "Bearer " + AI_API_KEY,

        "Content-Type":
            "application/json",

        "Accept":
            "application/json",

        "User-Agent":
            "ESP32-Voice-Server/2.0"
    }

    # -------------------------------------------------
    # REQUEST WITH RETRY
    # -------------------------------------------------

    last_error = None

    for attempt in range(
        AI_RETRIES + 1
    ):

        try:

            logger.info(
                "AI request attempt %s/%s | model=%s",
                attempt + 1,
                AI_RETRIES + 1,
                AI_MODEL
            )

            response = requests.post(

                AI_URL,

                headers=headers,

                json=payload,

                timeout=AI_TIMEOUT
            )

            # -------------------------------------------------
            # SUCCESS
            # -------------------------------------------------

            if response.status_code == 200:

                try:

                    data = response.json()

                except Exception as e:

                    logger.error(
                        "AI JSON parse error: %s",
                        e
                    )

                    last_error = (
                        "invalid_ai_json"
                    )

                    continue

                # -------------------------------------------------
                # CHOICES
                # -------------------------------------------------

                choices = data.get(
                    "choices"
                )

                if not choices:

                    logger.error(
                        "AI response has no choices: %s",
                        data
                    )

                    last_error = (
                        "no_choices"
                    )

                    continue

                # -------------------------------------------------
                # MESSAGE
                # -------------------------------------------------

                message = choices[0].get(
                    "message",
                    {}
                )

                reply = message.get(
                    "content"
                )

                if reply is None:

                    reply = ""

                reply = str(
                    reply
                ).strip()

                # -------------------------------------------------
                # EMPTY
                # -------------------------------------------------

                if not reply:

                    logger.error(
                        "AI returned empty content: %s",
                        data
                    )

                    last_error = (
                        "empty_ai_reply"
                    )

                    continue

                # -------------------------------------------------
                # CLEAN RESPONSE
                # -------------------------------------------------

                reply = clean_ai_reply(
                    reply
                )

                logger.info(
                    "AI success"
                )

                return (
                    reply,
                    None
                )

            # -------------------------------------------------
            # RATE LIMIT
            # -------------------------------------------------

            if response.status_code == 429:

                logger.warning(
                    "AI rate limited: %s",
                    response.text[:500]
                )

                last_error = (
                    "rate_limited"
                )

                if attempt < AI_RETRIES:

                    time.sleep(
                        1.5 * (attempt + 1)
                    )

                    continue

                break

            # -------------------------------------------------
            # AUTH
            # -------------------------------------------------

            if response.status_code in (
                401,
                403
            ):

                logger.error(
                    "AI authentication error: HTTP %s | %s",
                    response.status_code,
                    response.text[:1000]
                )

                return (
                    "AI service authentication failed.",
                    "authentication_error"
                )

            # -------------------------------------------------
            # BAD REQUEST
            # -------------------------------------------------

            if response.status_code == 400:

                logger.error(
                    "AI BAD REQUEST: %s",
                    response.text[:2000]
                )

                return (
                    "AI request was rejected.",
                    "bad_ai_request"
                )

            # -------------------------------------------------
            # OTHER SERVER ERROR
            # -------------------------------------------------

            logger.error(
                "AI HTTP %s: %s",
                response.status_code,
                response.text[:2000]
            )

            last_error = (
                f"ai_http_{response.status_code}"
            )

        # -------------------------------------------------
        # TIMEOUT
        # -------------------------------------------------

        except requests.exceptions.Timeout:

            logger.error(
                "AI request timeout"
            )

            last_error = (
                "ai_timeout"
            )

        # -------------------------------------------------
        # CONNECTION
        # -------------------------------------------------

        except requests.exceptions.ConnectionError as e:

            logger.error(
                "AI connection error: %s",
                e
            )

            last_error = (
                "ai_connection_error"
            )

        # -------------------------------------------------
        # GENERAL
        # -------------------------------------------------

        except Exception as e:

            logger.exception(
                "AI unexpected error"
            )

            last_error = (
                type(e).__name__
            )

        # -------------------------------------------------
        # RETRY DELAY
        # -------------------------------------------------

        if attempt < AI_RETRIES:

            time.sleep(
                0.8 * (attempt + 1)
            )

    # -------------------------------------------------
    # FINAL FAILURE
    # -------------------------------------------------

    logger.error(
        "AI failed after retries: %s",
        last_error
    )

    return (
        "AI response nahi mil saka.",
        last_error or "unknown_ai_error"
    )


# =====================================================
# CLEAN AI OUTPUT
# =====================================================

def clean_ai_reply(
    reply
):

    reply = str(
        reply
    ).strip()

    # Remove common markdown
    reply = reply.replace(
        "**",
        ""
    )

    reply = reply.replace(
        "__",
        ""
    )

    reply = reply.replace(
        "```",
        ""
    )

    # Remove excessive whitespace
    reply = " ".join(
        reply.split()
    )

    return reply


# =====================================================
# SPEECH RECOGNITION
# =====================================================

def recognize_speech(
    audio
):

    recognizer = sr.Recognizer()

    recognizer.dynamic_energy_threshold = True

    recognizer.pause_threshold = 0.8

    recognizer.non_speaking_duration = 0.3

    hindi_text = None

    english_text = None

    # -------------------------------------------------
    # HINDI
    # -------------------------------------------------

    try:

        logger.info(
            "Speech recognition: hi-IN"
        )

        hindi_text = recognizer.recognize_google(

            audio,

            language="hi-IN"
        )

        hindi_text = clean_text(
            hindi_text
        )

    except sr.UnknownValueError:

        logger.info(
            "Hindi speech not understood"
        )

    except sr.RequestError as e:

        logger.error(
            "Hindi speech API error: %s",
            e
        )

        return (
            None,
            None,
            "speech_service_error"
        )

    except Exception as e:

        logger.error(
            "Hindi recognition error: %s",
            e
        )

    # -------------------------------------------------
    # ENGLISH
    # -------------------------------------------------

    try:

        logger.info(
            "Speech recognition: en-IN"
        )

        english_text = recognizer.recognize_google(

            audio,

            language="en-IN"
        )

        english_text = clean_text(
            english_text
        )

    except sr.UnknownValueError:

        logger.info(
            "English speech not understood"
        )

    except sr.RequestError as e:

        logger.error(
            "English speech API error: %s",
            e
        )

        return (
            hindi_text,
            None,
            "speech_service_error"
        )

    except Exception as e:

        logger.error(
            "English recognition error: %s",
            e
        )

    return (
        hindi_text,
        english_text,
        None
    )


# =====================================================
# UPLOAD AUDIO
# =====================================================

@app.route(
    "/uploadAudio",
    methods=["POST"]
)
def upload_audio():

    request_id = (
        f"{int(time.time() * 1000)}"
    )

    temp_filename = None

    try:

        logger.info(
            "Audio request received | id=%s",
            request_id
        )

        # -------------------------------------------------
        # CONTENT TYPE
        # -------------------------------------------------

        content_type = (
            request.headers.get(
                "Content-Type",
                ""
            )
        )

        logger.info(
            "Content-Type: %s",
            content_type
        )

        # -------------------------------------------------
        # AUDIO
        # -------------------------------------------------

        audio_data = request.get_data(
            cache=False
        )

        if not audio_data:

            logger.warning(
                "Empty audio | id=%s",
                request_id
            )

            return jsonify({

                "status":
                    "error",

                "error":
                    "empty_audio",

                "message":
                    "No audio received",

                "transcription":
                    None,

                "ai_reply":
                    "Please ask your question again."

            }), 200

        logger.info(
            "Audio bytes: %s | id=%s",
            len(audio_data),
            request_id
        )

        # -------------------------------------------------
        # BASIC WAV CHECK
        # -------------------------------------------------

        if len(audio_data) < 44:

            logger.warning(
                "Audio too small | id=%s",
                request_id
            )

            return jsonify({

                "status":
                    "error",

                "error":
                    "invalid_audio",

                "message":
                    "Invalid WAV audio",

                "transcription":
                    None,

                "ai_reply":
                    "Please ask your question again."

            }), 200

        # -------------------------------------------------
        # WAV SIGNATURE
        # -------------------------------------------------

        if (
            audio_data[0:4] != b"RIFF"
            or
            audio_data[8:12] != b"WAVE"
        ):

            logger.warning(
                "Invalid WAV header | id=%s",
                request_id
            )

            return jsonify({

                "status":
                    "error",

                "error":
                    "invalid_wav",

                "message":
                    "Audio is not a valid WAV file",

                "transcription":
                    None,

                "ai_reply":
                    "Please ask your question again."

            }), 200

        # -------------------------------------------------
        # SAVE TEMP FILE
        # -------------------------------------------------

        fd, temp_filename = tempfile.mkstemp(
            suffix=".wav"
        )

        os.close(
            fd
        )

        with open(
            temp_filename,
            "wb"
        ) as f:

            f.write(
                audio_data
            )

        logger.info(
            "WAV saved | id=%s",
            request_id
        )

        # -------------------------------------------------
        # LOAD AUDIO
        # -------------------------------------------------

        recognizer = sr.Recognizer()

        with sr.AudioFile(
            temp_filename
        ) as source:

            audio = recognizer.record(
                source
            )

        # -------------------------------------------------
        # RECOGNIZE
        # -------------------------------------------------

        (
            hindi_text,
            english_text,
            speech_error
        ) = recognize_speech(
            audio
        )

        if speech_error:

            return jsonify({

                "status":
                    "error",

                "error":
                    speech_error,

                "message":
                    "Speech recognition service error",

                "transcription":
                    None,

                "hindi_transcription":
                    hindi_text,

                "english_transcription":
                    english_text,

                "ai_reply":
                    "Speech service is temporarily unavailable."

            }), 200

        # -------------------------------------------------
        # NO SPEECH
        # -------------------------------------------------

        if (
            not hindi_text
            and
            not english_text
        ):

            logger.info(
                "No valid speech | id=%s",
                request_id
            )

            return jsonify({

                "status":
                    "error",

                "error":
                    "no_speech",

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

            }), 200

        # -------------------------------------------------
        # BEST TEXT
        # -------------------------------------------------

        user_text = choose_best_transcription(

            hindi_text,

            english_text

        )

        logger.info(
            "Hindi: %s",
            hindi_text
        )

        logger.info(
            "English: %s",
            english_text
        )

        logger.info(
            "Selected: %s",
            user_text
        )

        # -------------------------------------------------
        # AI
        # -------------------------------------------------

        (
            ai_reply,
            ai_error
        ) = get_ai_reply(

            user_text,

            hindi_text,

            english_text

        )

        # -------------------------------------------------
        # FINAL
        # -------------------------------------------------

        response_data = {

            "status":
                "ok",

            "transcription":
                user_text,

            "hindi_transcription":
                hindi_text,

            "english_transcription":
                english_text,

            "ai_reply":
                ai_reply

        }

        # Add internal error only when AI failed
        # This helps debugging without breaking ESP32.
        if ai_error:

            response_data[
                "ai_error"
            ] = ai_error

        logger.info(
            "Completed | id=%s",
            request_id
        )

        return jsonify(
            response_data
        ), 200

    # =================================================
    # REQUEST TOO LARGE
    # =================================================

    except Exception as e:

        logger.exception(
            "UPLOAD ERROR | id=%s",
            request_id
        )

        return jsonify({

            "status":
                "error",

            "error":
                "server_error",

            "message":
                "Server error",

            "transcription":
                None,

            "ai_reply":
                "Sorry, something went wrong."

        }), 200

    finally:

        # -------------------------------------------------
        # DELETE TEMP WAV
        # -------------------------------------------------

        if (
            temp_filename
            and
            os.path.exists(
                temp_filename
            )
        ):

            try:

                os.remove(
                    temp_filename
                )

            except Exception:

                pass


# =====================================================
# 413 ERROR
# =====================================================

@app.errorhandler(
    413
)
def request_too_large(error):

    return jsonify({

        "status":
            "error",

        "error":
            "audio_too_large",

        "message":
            "Audio file is too large",

        "transcription":
            None,

        "ai_reply":
            "Audio is too large."

    }), 200


# =====================================================
# 404
# =====================================================

@app.errorhandler(
    404
)
def not_found(error):

    return jsonify({

        "status":
            "error",

        "error":
            "not_found",

        "message":
            "Endpoint not found"

    }), 404


# =====================================================
# 500
# =====================================================

@app.errorhandler(
    500
)
def internal_error(error):

    logger.exception(
        "Flask internal error"
    )

    return jsonify({

        "status":
            "error",

        "error":
            "internal_server_error",

        "message":
            "Internal server error",

        "ai_reply":
            "Sorry, something went wrong."

    }), 200


# =====================================================
# START
# =====================================================

if __name__ == "__main__":

    print()
    print("==============================")
    print("ESP32 VOICE AI SERVER")
    print("==============================")

    print(
        "PORT:",
        PORT
    )

    print(
        "AI URL:",
        AI_URL
    )

    print(
        "AI MODEL:",
        AI_MODEL
    )

    print(
        "AI KEY:",
        "CONFIGURED"
        if AI_API_KEY
        else "MISSING"
    )

    print(
        "UPLOAD ENDPOINT:",
        "/uploadAudio"
    )

    print(
        "WAKE ENDPOINT:",
        "/wake"
    )

    print("==============================")
    print()

    app.run(

        host="0.0.0.0",

        port=PORT,

        threaded=True
    )

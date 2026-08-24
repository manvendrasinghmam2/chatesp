from flask import Flask, request, jsonify, Response
import os
import speech_recognition as sr
import requests
import re
import tempfile


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

TTS_VOICE = os.environ.get(
    "TTS_VOICE",
    "troy"
)

# Keep responses short because current Orpheus
# documentation limits input to 200 characters.
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

        "speech_engine":
            "Google Speech Recognition",

        "ai_engine":
            "Groq",

        "model":
            AI_MODEL,

        "tts_engine":
            "Groq Orpheus",

        "tts_model":
            TTS_MODEL,

        "tts_voice":
            TTS_VOICE
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

    # -------------------------------------------------
    # TEMPORARY WAKE TEST
    #
    # IMPORTANT:
    # This still returns TRUE for every request.
    # Actual HELLO detection is not implemented here.
    # -------------------------------------------------

    response_data = {

        "status":
            "ok",

        "wake":
            True,

        "english":
            "Hello",

        "hindi":
            None
    }

    print(
        "WAKE RESPONSE:",
        response_data
    )

    print("========================================")

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

            "status":
                "error",

            "message":
                "No JSON received"

        }), 400

    return jsonify({

        "status":
            "ok",

        "message":
            "Data received",

        "data":
            data
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

Understand the user's actual spoken language.

The speech recognition system provides:
1. Hindi recognition
2. English recognition

Compare both results and determine the intended meaning.

LANGUAGE RULES:

If the user clearly speaks English,
answer completely in natural English.

If the user clearly speaks Hindi,
answer in Hindi.

If the user speaks Roman Hindi or Hinglish,
answer in natural Hinglish.

If Hindi recognition converts English speech
into Devanagari phonetically, identify the
intended English meaning.

Do not mention speech recognition.

Do not explain your language decision.

Just answer the question.

VOICE STYLE:

The answer will be spoken aloud.

Keep answers very concise.

Usually one or two sentences.

Maximum about 150 characters when possible.

Do not use markdown.

Do not use bullet points.

Do not use emojis.

Do not use headings.

Do not repeat the question.

Do not say "As an AI".

Sound natural and conversational.
"""

    user_content = f"""
Hindi speech recognition:
{hindi_text if hindi_text else "No result"}

English speech recognition:
{english_text if english_text else "No result"}

Determine the intended meaning and answer naturally.
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
                    user_content
            }
        ],

        "temperature":
            0.2,

        "max_completion_tokens":
            200,

        "stream":
            False
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

        try:

            data = response.json()

        except Exception:

            return (
                "AI response nahi mil saka."
            )

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

        print()
        print("AI REPLY:")
        print(reply)

        print("========================================")

        return reply

    except requests.exceptions.Timeout:

        return (
            "AI response nahi mil saka."
        )

    except requests.exceptions.ConnectionError:

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

def generate_tts(
    text
):

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

    # -------------------------------------------------
    # CURRENT GROQ ORPHEUS LIMIT
    # -------------------------------------------------

    if len(text) > TTS_MAX_CHARS:

        text = text[
            :TTS_MAX_CHARS
        ]

        # Try to end at a sentence.
        last_dot = text.rfind(".")

        if last_dot > 40:

            text = text[
                :last_dot + 1
            ]

    payload = {

        "model":
            TTS_MODEL,

        "voice":
            TTS_VOICE,

        "input":
            text,

        "response_format":
            "wav",

        "sample_rate":
            16000
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
        print("TTS REQUEST")
        print("========================================")

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
                response.text[:2000]
            )

            print("========================================")

            return None

        audio_data = response.content

        if not audio_data:

            print(
                "TTS returned empty audio"
            )

            return None

        print(
            "TTS AUDIO BYTES:",
            len(audio_data)
        )

        print("========================================")

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

                "status":
                    "error",

                "message":
                    "No JSON received"

            }), 400

        text = clean_text(
            data.get("text")
        )

        if not text:

            return jsonify({

                "status":
                    "error",

                "message":
                    "No text received"

            }), 400

        audio_data = generate_tts(
            text
        )

        if audio_data is None:

            return jsonify({

                "status":
                    "error",

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

            "status":
                "error",

            "message":
                str(e)

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

                "status":
                    "error",

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
        # SPEECH RECOGNIZER
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

        # =================================================
        # HINDI
        # =================================================

        print()
        print("HINDI SPEECH")

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
                    str(e)

            }), 500

        # =================================================
        # ENGLISH
        # =================================================

        print()
        print("ENGLISH SPEECH")

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

                "hindi_transcription":
                    hindi_text,

                "english_transcription":
                    None

            }), 500

        # =================================================
        # VALIDATION
        # =================================================

        if (

            not is_valid_query(hindi_text)

            and

            not is_valid_query(english_text)

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

        # =================================================
        # FINAL RESPONSE
        # =================================================

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
# START SERVER
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

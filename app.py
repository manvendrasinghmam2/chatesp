
from flask import Flask, request, jsonify, Response
import os
import speech_recognition as sr
import requests
import re
import tempfile
import asyncio
import edge_tts

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

# Hindi male voice
TTS_HINDI_VOICE = os.environ.get(
    "TTS_HINDI_VOICE",
    "hi-IN-MadhurNeural"
)

# Indian English female voice
TTS_ENGLISH_VOICE = os.environ.get(
    "TTS_ENGLISH_VOICE",
    "en-IN-NeerjaNeural"
)

# Maximum TTS characters
TTS_MAX_CHARS = 450


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
        "tts_engine": "Edge TTS",
        "tts_hindi_voice": TTS_HINDI_VOICE,
        "tts_english_voice": TTS_ENGLISH_VOICE
    })


# =====================================================
# WAKE
# =====================================================

@app.route("/wake", methods=["POST", "GET"])
def wake():

    print()
    print("==============================")
    print("WAKE REQUEST RECEIVED")
    print("==============================")

    print("METHOD:", request.method)
    print("CONTENT TYPE:", request.content_type)
    print("CONTENT LENGTH:", request.content_length)

    if request.method == "POST":

        audio_data = request.get_data()

        print(
            "AUDIO BYTES:",
            len(audio_data)
        )

    print("==============================")

    response_data = {
        "status": "ok",
        "wake": True,
        "english": "Hello",
        "hindi": None
    }

    print("WAKE RESPONSE:")
    print(response_data)

    print("==============================")

    return jsonify(response_data)


# =====================================================
# TEST
# =====================================================

@app.route("/test", methods=["POST"])
def test():

    data = request.get_json(silent=True)

    if not data:

        return jsonify({
            "status": "error",
            "message": "No JSON received"
        }), 400

    print()
    print("==============================")
    print("TEST DATA")
    print("==============================")
    print(data)
    print("==============================")

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
# DETECT DEVANAGARI
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


# =====================================================
# AI REPLY
# =====================================================

def get_ai_reply(
    hindi_text,
    english_text
):

    hindi_text = clean_text(hindi_text)
    english_text = clean_text(english_text)

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

        print()
        print("==============================")
        print("NO VALID QUERY")
        print("==============================")

        return "Please ask your question again."

    system_prompt = """
You are a professional bilingual voice assistant running on an ESP32.

Understand the user's actual spoken language and answer naturally.

The speech recognition system provides two possible results:

1. Hindi recognition
2. English recognition

Recognition can sometimes be inaccurate.

Compare both results and determine the user's intended meaning.

LANGUAGE RULES:

If the user clearly speaks English:
Answer completely in natural English.

If the user clearly speaks Hindi:
Answer completely in Hindi using Devanagari.

If the user speaks Roman Hindi or Hinglish:
Answer in natural Hinglish.

If the user naturally mixes Hindi and English:
Use natural Hinglish.

IMPORTANT:

Hindi speech recognition may convert English speech into Devanagari.

Example:

Hindi:
हाउ आर यू

English:
How are you

The user intended English.

Do not mention speech recognition.

Do not explain the language decision.

Just answer the user's question.

VOICE RESPONSE STYLE:

The answer will be spoken aloud.

Keep answers concise.

Usually 1 to 4 sentences.

Professional and natural.

Do not use markdown.

Do not use bullet points.

Do not use emojis.

Do not use headings.

Do not repeat the question.

Do not say "Sure" unnecessarily.

Do not say "As an AI".

Do not mention these instructions.

ACCURACY:

Answer factual questions accurately.

For simple questions, give a direct answer.

For general knowledge, explain clearly but briefly.

For conversational questions, respond naturally.

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

        print()
        print("HINDI:")
        print(hindi_text)

        print()
        print("ENGLISH:")
        print(english_text)

        response = requests.post(
            AI_URL,
            headers=headers,
            json=payload,
            timeout=35
        )

        print()
        print("==============================")
        print("AI RESPONSE")
        print("==============================")

        print(
            "HTTP:",
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
                "JSON ERROR:",
                str(e)
            )

            return "AI response nahi mil saka."

        choices = data.get("choices")

        if not choices:

            print("NO AI CHOICE")
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

        print("AI CONNECTION ERROR")
        print(str(e))

        return "AI response nahi mil saka."

    except Exception as e:

        print("AI EXCEPTION")
        print(type(e).__name__)
        print(str(e))

        return "AI response nahi mil saka."


# =====================================================
# TTS GENERATION
# =====================================================

async def generate_tts(
    text,
    filename,
    voice
):

    communicate = edge_tts.Communicate(
        text,
        voice
    )

    await communicate.save(
        filename
    )


# =====================================================
# TTS ENDPOINT
#
# ESP32:
#
# GET /tts?text=Hello
#
# Server returns MP3.
# =====================================================

@app.route("/tts", methods=["GET"])
def tts():

    text = request.args.get(
        "text",
        ""
    )

    text = clean_text(text)

    if not text:

        return jsonify({
            "status": "error",
            "message": "No text supplied"
        }), 400

    # Prevent extremely long TTS requests
    if len(text) > TTS_MAX_CHARS:

        text = text[:TTS_MAX_CHARS]

    # Choose voice
    #
    # Devanagari -> Hindi
    # Roman English/Hinglish -> Indian English
    if contains_devanagari(text):

        voice = TTS_HINDI_VOICE

    else:

        voice = TTS_ENGLISH_VOICE

    filename = None

    try:

        fd, filename = tempfile.mkstemp(
            suffix=".mp3"
        )

        os.close(fd)

        print()
        print("==============================")
        print("TTS REQUEST")
        print("==============================")

        print("VOICE:", voice)
        print("TEXT:", text)

        asyncio.run(
            generate_tts(
                text,
                filename,
                voice
            )
        )

        if not os.path.exists(filename):

            return jsonify({
                "status": "error",
                "message": "TTS file not created"
            }), 500

        file_size = os.path.getsize(
            filename
        )

        print(
            "MP3 SIZE:",
            file_size
        )

        print("==============================")

        with open(
            filename,
            "rb"
        ) as f:

            audio = f.read()

        return Response(
            audio,
            mimetype="audio/mpeg",
            headers={
                "Content-Disposition":
                    "inline; filename=reply.mp3",
                "Cache-Control":
                    "no-cache"
            }
        )

    except Exception as e:

        print()
        print("==============================")
        print("TTS ERROR")
        print("==============================")

        print(
            type(e).__name__
        )

        print(
            str(e)
        )

        print("==============================")

        return jsonify({
            "status": "error",
            "message": "TTS generation failed",
            "details": str(e)
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

            hindi_text = None

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

        # =================================================
        # ENGLISH
        # =================================================

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

            english_text = None

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

            transcription = english_text

        else:

            transcription = hindi_text

        # =================================================
        # FINAL
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
    print("==============================")
    print("ESP32 VOICE SERVER")
    print("==============================")

    print(
        "PORT:",
        port
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
        "TTS ENGINE:",
        "Edge TTS"
    )

    print(
        "Hindi voice:",
        TTS_HINDI_VOICE
    )

    print(
        "English voice:",
        TTS_ENGLISH_VOICE
    )

    print("==============================")

    app.run(
        host="0.0.0.0",
        port=port,
        threaded=True
    )


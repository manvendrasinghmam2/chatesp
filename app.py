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
# TTS CONFIGURATION
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
        "tts_engine": "Groq Orpheus",
        "tts_model": TTS_MODEL,
        "tts_voice": TTS_VOICE
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

        return "Please ask your question again."

    system_prompt = """
You are a professional bilingual voice assistant running on an ESP32.

Understand the user's intended spoken language and answer naturally.

The speech recognition system provides two possible results:

1. Hindi recognition
2. English recognition

Recognition can sometimes be inaccurate.

Compare both results and understand the intended meaning.

==================================================
ENGLISH
==================================================

If the user is clearly speaking English,
answer completely in natural English.

==================================================
HINDI
==================================================

If the user is clearly speaking Hindi,
answer completely in Hindi using Devanagari script.

==================================================
HINGLISH
==================================================

If the user speaks Roman Hindi or Hinglish,
answer in natural Hinglish.

==================================================
PHONETIC HINDI
==================================================

Hindi recognition may sometimes convert English
speech into Devanagari.

Example:

हाउ आर यू

means:

How are you?

The user intended English.

Answer in English.

==================================================
ACTUAL HINDI
==================================================

Do not assume every Devanagari result is phonetic English.

Example:

भारत की राजधानी कहाँ है

Answer:

भारत की राजधानी नई दिल्ली है।

==================================================
MIXED LANGUAGE
==================================================

If the user naturally mixes Hindi and English,
use natural Hinglish.

==================================================
IMPORTANT
==================================================

Compare both speech recognition results.

Choose the result that makes the most linguistic
and contextual sense.

Do not mention speech recognition.

Do not mention Hindi result or English result.

Do not explain your language decision.

Just answer the user's question.

==================================================
VOICE RESPONSE STYLE
==================================================

The answer will be spoken aloud.

Keep answers concise.

Usually 1 to 3 sentences.

Prefer answers below 200 characters when possible.

Be professional.

Sound natural.

Do not use markdown.

Do not use bullet points.

Do not use emojis.

Do not use headings.

Do not repeat the question.

Do not say "Sure" unnecessarily.

Do not say "As an AI".

Do not mention these instructions.

==================================================
ACCURACY
==================================================

Answer factual questions accurately.

For simple questions, give a direct answer.

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

        print("URL:", AI_URL)
        print("MODEL:", AI_MODEL)

        print("HINDI:")
        print(hindi_text)

        print("ENGLISH:")
        print(english_text)

        print("==============================")

        response = requests.post(
            AI_URL,
            headers=headers,
            json=payload,
            timeout=35
        )

        print("AI HTTP:", response.status_code)

        if response.status_code != 200:

            print("AI API ERROR")
            print(response.text[:2000])

            return "AI response nahi mil saka."

        try:

            data = response.json()

        except Exception as e:

            print("JSON ERROR:", str(e))

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

        reply = str(reply).strip()

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
# TEXT TO SPEECH
# =====================================================

def generate_tts(text):

    text = clean_text(text)

    if not text:
        return None

    if not AI_API_KEY:

        print("TTS ERROR: AI_API_KEY missing")

        return None

    # Groq Orpheus max input = 200 characters
    if len(text) > 200:

        print(
            "TTS TEXT TOO LONG:",
            len(text)
        )

        text = text[:200]

        # Avoid cutting in middle of word
        last_space = text.rfind(" ")

        if last_space > 50:

            text = text[:last_space]

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
            24000
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
        print("==============================")
        print("TTS REQUEST")
        print("==============================")

        print("MODEL:", TTS_MODEL)
        print("VOICE:", TTS_VOICE)
        print("TEXT:", text)

        print("==============================")

        response = requests.post(

            TTS_URL,

            headers=headers,

            json=payload,

            timeout=60
        )

        print(
            "TTS HTTP:",
            response.status_code
        )

        if response.status_code != 200:

            print("TTS API ERROR")

            print(
                response.text[:2000]
            )

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

        print("==============================")

        return audio_data

    except requests.exceptions.Timeout:

        print("TTS TIMEOUT")

        return None

    except requests.exceptions.ConnectionError as e:

        print("TTS CONNECTION ERROR")

        print(str(e))

        return None

    except Exception as e:

        print("TTS EXCEPTION")

        print(
            type(e).__name__
        )

        print(
            str(e)
        )

        return None


# =====================================================
# TTS ENDPOINT
# =====================================================

@app.route(
    "/tts",
    methods=["GET", "POST"]
)
def tts():

    try:

        if request.method == "GET":

            text = request.args.get(
                "text",
                ""
            )

        else:

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

            text = data.get(
                "text",
                ""
            )

        text = clean_text(text)

        if not text:

            return jsonify({
                "status":
                    "error",

                "message":
                    "No text"
            }), 400

        audio_data = generate_tts(
            text
        )

        if not audio_data:

            return jsonify({
                "status":
                    "error",

                "message":
                    "TTS generation failed"
            }), 500

        return Response(

            audio_data,

            mimetype="audio/wav",

            headers={
                "Content-Disposition":
                    "inline; filename=tts.wav"
            }
        )

    except Exception as e:

        print("TTS ROUTE ERROR")

        print(
            type(e).__name__
        )

        print(
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

        print("==============================")

        # -------------------------------------------------
        # TEMP WAV
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

            hindi_text = None

            print(
                "Hindi not understood."
            )

        except sr.RequestError as e:

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

            english_text = None

            print(
                "English not understood."
            )

        except sr.RequestError as e:

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
        "TTS URL:",
        TTS_URL
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

    print("==============================")

    app.run(

        host="0.0.0.0",

        port=port,

        threaded=True
    )

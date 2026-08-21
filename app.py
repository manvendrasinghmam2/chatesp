from flask import Flask, request, jsonify
import os
import speech_recognition as sr
import requests
import re
import time

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
# BASIC SETTINGS
# =====================================================

MAX_AUDIO_BYTES = 250000

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
        "model": AI_MODEL
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

    text = clean_text(text)

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
# WAKE WORD CHECK
# =====================================================

def is_hello(text):

    if not text:
        return False

    text = clean_text(text).lower()

    # Remove punctuation
    text = re.sub(
        r"[^a-zA-Z0-9\s]",
        " ",
        text
    )

    text = re.sub(
        r"\s+",
        " ",
        text
    ).strip()

    # Exact / common variations
    hello_words = [
        "hello",
        "helo",
        "heloo",
        "hellow",
        "hello hello",
        "hi",
        "hey"
    ]

    if text in hello_words:
        return True

    # If Google gives something like:
    # "hello assistant"
    words = text.split()

    if len(words) <= 3:

        for word in words:

            if word in [
                "hello",
                "helo",
                "heloo",
                "hellow"
            ]:
                return True

    return False


# =====================================================
# RECOGNIZE GOOGLE
# =====================================================

def recognize_audio(audio, language):

    recognizer = sr.Recognizer()

    try:

        text = recognizer.recognize_google(
            audio,
            language=language
        )

        return clean_text(text)

    except sr.UnknownValueError:

        return None

    except sr.RequestError as e:

        raise e

    except Exception:

        return None


# =====================================================
# WAKE
# =====================================================

@app.route(
    "/wake",
    methods=["POST"]
)
def wake():

    try:

        audio_data = request.get_data()

        if not audio_data:

            return jsonify({
                "status": "error",
                "wake": False,
                "message": "No audio received"
            }), 400

        if len(audio_data) > MAX_AUDIO_BYTES:

            return jsonify({
                "status": "error",
                "wake": False,
                "message": "Audio too large"
            }), 413

        filename = "/tmp/wake.wav"

        with open(
            filename,
            "wb"
        ) as f:

            f.write(audio_data)

        recognizer = sr.Recognizer()

        with sr.AudioFile(filename) as source:

            audio = recognizer.record(source)

        # ---------------------------------------------
        # ENGLISH
        # ---------------------------------------------

        english_text = None

        try:

            english_text = recognizer.recognize_google(
                audio,
                language="en-IN"
            )

            english_text = clean_text(
                english_text
            )

        except sr.UnknownValueError:

            english_text = None

        except sr.RequestError as e:

            print(
                "Google wake speech error:",
                str(e)
            )

        # ---------------------------------------------
        # HINDI
        # ---------------------------------------------

        hindi_text = None

        try:

            hindi_text = recognizer.recognize_google(
                audio,
                language="hi-IN"
            )

            hindi_text = clean_text(
                hindi_text
            )

        except sr.UnknownValueError:

            hindi_text = None

        except sr.RequestError as e:

            print(
                "Google wake Hindi error:",
                str(e)
            )

        # ---------------------------------------------
        # DEBUG
        # ---------------------------------------------

        print()
        print("==============================")
        print("WAKE REQUEST")
        print("==============================")

        print(
            "English:",
            english_text
        )

        print(
            "Hindi:",
            hindi_text
        )

        # ---------------------------------------------
        # DETECT
        # ---------------------------------------------

        detected = (
            is_hello(english_text)
            or
            is_hello(hindi_text)
        )

        if detected:

            print(
                "WAKE DETECTED: HELLO"
            )

        else:

            print(
                "WAKE NOT DETECTED"
            )

        print("==============================")

        return jsonify({

            "status": "ok",

            "wake": detected,

            "english": english_text,

            "hindi": hindi_text

        })

    except Exception as e:

        print()
        print("==============================")
        print("WAKE SERVER ERROR")
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

            "wake": False,

            "message": str(e)

        }), 500


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

    print(
        "TEST DATA:",
        data
    )

    return jsonify({

        "status": "ok",

        "message": "Data received",

        "data": data

    })


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

    # ---------------------------------------------
    # API KEY
    # ---------------------------------------------

    if not AI_API_KEY:

        print(
            "AI_API_KEY is NOT configured"
        )

        return "AI response nahi mil saka."

    # ---------------------------------------------
    # QUERY
    # ---------------------------------------------

    if (
        not is_valid_query(hindi_text)
        and
        not is_valid_query(english_text)
    ):

        return "Please ask your question again."

    # ---------------------------------------------
    # SYSTEM PROMPT
    # ---------------------------------------------

    system_prompt = """
You are a professional bilingual voice assistant running on an ESP32.

Understand the user's intended language and meaning.

You receive two speech recognition results:
Hindi recognition and English recognition.

The recognitions may sometimes be inaccurate.

Compare both results and determine what the user actually meant.

LANGUAGE RULES:

If the user clearly speaks English,
answer completely in natural English.

If the user clearly speaks Hindi,
answer completely in Hindi using Devanagari.

If the user speaks Roman Hindi or Hinglish,
answer naturally in Hinglish.

If Hindi recognition contains phonetic English written in Devanagari,
but English recognition clearly contains the English sentence,
answer in English.

Example:

Hindi:
हाउ आर यू

English:
How are you

Answer:
I'm doing well. How are you?

Do not mention transcription.

Do not mention speech recognition.

Do not explain your language decision.

Just answer the user.

VOICE STYLE:

Keep answers concise.

Usually 1 to 4 sentences.

No markdown.

No bullet points.

No headings.

No emojis.

No unnecessary symbols.

Do not repeat the question.

Do not say "As an AI".

Be natural and conversational.

Answer factual questions accurately.
"""

    # ---------------------------------------------
    # USER CONTENT
    # ---------------------------------------------

    user_content = f"""
Hindi speech recognition:
{hindi_text if hindi_text else "No result"}

English speech recognition:
{english_text if english_text else "No result"}

Determine the intended meaning and language.

Then answer naturally.
"""

    # ---------------------------------------------
    # PAYLOAD
    # ---------------------------------------------

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
            "application/json"
    }

    # ---------------------------------------------
    # REQUEST
    # ---------------------------------------------

    try:

        print()
        print("==============================")
        print("AI REQUEST")
        print("==============================")

        print(
            "MODEL:",
            AI_MODEL
        )

        print(
            "HINDI:",
            hindi_text
        )

        print(
            "ENGLISH:",
            english_text
        )

        response = requests.post(

            AI_URL,

            headers=headers,

            json=payload,

            timeout=35
        )

        print(
            "HTTP:",
            response.status_code
        )

        # -----------------------------------------
        # ERROR
        # -----------------------------------------

        if response.status_code != 200:

            print(
                "AI ERROR:"
            )

            print(
                response.text
            )

            return "AI response nahi mil saka."

        # -----------------------------------------
        # JSON
        # -----------------------------------------

        try:

            data = response.json()

        except Exception:

            print(
                "AI JSON ERROR"
            )

            return "AI response nahi mil saka."

        # -----------------------------------------
        # CHOICES
        # -----------------------------------------

        choices = data.get(
            "choices"
        )

        if not choices:

            print(
                "NO AI CHOICE"
            )

            print(
                data
            )

            return "AI response nahi mil saka."

        # -----------------------------------------
        # MESSAGE
        # -----------------------------------------

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

        # -----------------------------------------
        # CLEAN
        # -----------------------------------------

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

        # -----------------------------------------
        # EMPTY
        # -----------------------------------------

        if not reply:

            return "AI response nahi mil saka."

        # -----------------------------------------
        # SUCCESS
        # -----------------------------------------

        print()
        print("==============================")
        print("AI REPLY")
        print("==============================")
        print(reply)
        print("==============================")

        return reply

    except requests.exceptions.Timeout:

        print(
            "AI TIMEOUT"
        )

        return "AI response nahi mil saka."

    except requests.exceptions.ConnectionError as e:

        print(
            "AI CONNECTION ERROR:",
            str(e)
        )

        return "AI response nahi mil saka."

    except Exception as e:

        print(
            "AI ERROR:",
            type(e).__name__,
            str(e)
        )

        return "AI response nahi mil saka."


# =====================================================
# UPLOAD AUDIO
# =====================================================

@app.route(
    "/uploadAudio",
    methods=["POST"]
)
def upload_audio():

    try:

        # ---------------------------------------------
        # AUDIO
        # ---------------------------------------------

        audio_data = request.get_data()

        if not audio_data:

            return jsonify({

                "status": "error",

                "message": "No audio received",

                "ai_reply":
                    "Please ask your question again."

            }), 400

        if len(audio_data) > MAX_AUDIO_BYTES:

            return jsonify({

                "status": "error",

                "message": "Audio too large",

                "ai_reply":
                    "Please ask your question again."

            }), 413

        print()
        print("==============================")
        print("AUDIO RECEIVED")
        print("==============================")

        print(
            "Bytes:",
            len(audio_data)
        )

        # ---------------------------------------------
        # SAVE
        # ---------------------------------------------

        filename = "/tmp/audio.wav"

        with open(
            filename,
            "wb"
        ) as f:

            f.write(audio_data)

        # ---------------------------------------------
        # RECOGNIZER
        # ---------------------------------------------

        recognizer = sr.Recognizer()

        with sr.AudioFile(filename) as source:

            audio = recognizer.record(source)

        hindi_text = None
        english_text = None

        # =============================================
        # HINDI
        # =============================================

        try:

            hindi_text = recognizer.recognize_google(

                audio,

                language="hi-IN"
            )

            hindi_text = clean_text(
                hindi_text
            )

        except sr.UnknownValueError:

            hindi_text = None

        except sr.RequestError as e:

            print(
                "Google Speech Error:",
                str(e)
            )

            return jsonify({

                "status": "error",

                "message":
                    "Speech service error",

                "details":
                    str(e),

                "ai_reply":
                    "Speech service error."

            }), 500

        # =============================================
        # ENGLISH
        # =============================================

        try:

            english_text = recognizer.recognize_google(

                audio,

                language="en-IN"
            )

            english_text = clean_text(
                english_text
            )

        except sr.UnknownValueError:

            english_text = None

        except sr.RequestError as e:

            print(
                "Google Speech Error:",
                str(e)
            )

            return jsonify({

                "status": "error",

                "message":
                    "Speech service error",

                "details":
                    str(e),

                "ai_reply":
                    "Speech service error."

            }), 500

        # ---------------------------------------------
        # PRINT
        # ---------------------------------------------

        print()
        print("==============================")
        print("SPEECH RESULTS")
        print("==============================")

        print(
            "Hindi:",
            hindi_text
        )

        print(
            "English:",
            english_text
        )

        # ---------------------------------------------
        # VALIDATION
        # ---------------------------------------------

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

        # ---------------------------------------------
        # AI
        # ---------------------------------------------

        ai_reply = get_ai_reply(

            hindi_text,

            english_text
        )

        # ---------------------------------------------
        # TRANSCRIPTION
        # ---------------------------------------------

        if is_valid_query(
            english_text
        ):

            transcription = english_text

        else:

            transcription = hindi_text

        # ---------------------------------------------
        # RESPONSE
        # ---------------------------------------------

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
            type(e).__name__
        )

        print(
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

    print("==============================")

    app.run(
        host="0.0.0.0",
        port=port
    )

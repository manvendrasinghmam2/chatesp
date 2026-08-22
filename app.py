from flask import Flask, request, jsonify
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
# VALID QUERY
# =====================================================

def is_valid_query(text):

    if not text:
        return False

    text = str(text).strip()

    if len(text) < 2:
        return False

    bad_values = {
        "unknown",
        "none",
        "null",
        "no response",
        "no valid query",
        "speech not understood"
    }

    if text.lower() in bad_values:
        return False

    return True


# =====================================================
# WAKE WORD DETECTION
# =====================================================

def is_wake_word(hindi_text, english_text):

    combined = " ".join([
        clean_text(hindi_text).lower(),
        clean_text(english_text).lower()
    ])

    if not combined:
        return False

    # English wake words
    english_patterns = [
        r"\bhello\b",
        r"\bhelo\b",
        r"\bhellow\b",
        r"\bhey\b",
        r"\bhi\b"
    ]

    # Hindi / Hinglish
    hindi_patterns = [
        r"\bnamaste\b",
        r"\bnamaskar\b",
        r"\bनमस्ते\b",
        r"\bनमस्कार\b",
        r"\bहेलो\b"
    ]

    for pattern in english_patterns + hindi_patterns:

        if re.search(pattern, combined):
            return True

    return False


# =====================================================
# AI REPLY
# =====================================================

def get_ai_reply(hindi_text, english_text):

    hindi_text = clean_text(hindi_text)
    english_text = clean_text(english_text)

    # -------------------------------------------------
    # API KEY
    # -------------------------------------------------

    if not AI_API_KEY:

        print("ERROR: AI_API_KEY is missing")

        return "AI response nahi mil saka."

    # -------------------------------------------------
    # VALID INPUT
    # -------------------------------------------------

    if (
        not is_valid_query(hindi_text)
        and
        not is_valid_query(english_text)
    ):

        return "Please ask your question again."

    # -------------------------------------------------
    # SYSTEM PROMPT
    # -------------------------------------------------

    system_prompt = """
You are a professional bilingual voice assistant running on an ESP32.

Understand the user's intended language and meaning.

The speech recognition system provides two possible transcriptions:

1. Hindi recognition
2. English recognition

The recognition can sometimes be inaccurate.

Compare both results and determine what the user actually intended.

LANGUAGE RULES:

If the user clearly speaks English,
answer completely in natural English.

If the user clearly speaks Hindi,
answer completely in Hindi using Devanagari.

If the user speaks Roman Hindi or Hinglish,
answer naturally in Hinglish.

If English speech was incorrectly converted into Devanagari phonetics,
recognize the intended English meaning and answer in English.

Example:

Hindi:
हाउ आर यू

English:
How are you

Answer:
I'm doing well. How are you?

Do not mention speech recognition.

Do not mention Hindi result or English result.

Do not explain your language decision.

Just answer the user's question.

VOICE STYLE:

The answer will be spoken aloud.

Keep answers concise.

Usually 1 to 4 sentences.

Be natural and professional.

Do not use markdown.

Do not use bullet points.

Do not use emojis.

Do not use headings.

Do not repeat the question.

Do not say "Sure" unnecessarily.

Do not say "As an AI".

Answer factual questions accurately.

For simple questions, give a direct answer.
"""

    # -------------------------------------------------
    # USER CONTENT
    # -------------------------------------------------

    user_content = f"""
Hindi speech recognition:
{hindi_text if hindi_text else "No result"}

English speech recognition:
{english_text if english_text else "No result"}

Determine the user's intended meaning and language.

Then answer naturally.
"""

    # -------------------------------------------------
    # PAYLOAD
    # -------------------------------------------------

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

        "stream": False,

        "include_reasoning": False
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
            "application/json"
    }

    # -------------------------------------------------
    # API REQUEST
    # -------------------------------------------------

    try:

        print()
        print("==============================")
        print("GROQ REQUEST")
        print("==============================")

        print("MODEL:", AI_MODEL)

        print("HINDI:", hindi_text)
        print("ENGLISH:", english_text)

        response = requests.post(
            AI_URL,
            headers=headers,
            json=payload,
            timeout=40
        )

        print("HTTP:", response.status_code)

        # -------------------------------------------------
        # ERROR
        # -------------------------------------------------

        if response.status_code != 200:

            print("GROQ ERROR:")
            print(response.text[:2000])

            return "AI response nahi mil saka."

        # -------------------------------------------------
        # JSON
        # -------------------------------------------------

        try:

            data = response.json()

        except Exception as e:

            print("JSON ERROR:", str(e))

            return "AI response nahi mil saka."

        # -------------------------------------------------
        # CHOICES
        # -------------------------------------------------

        choices = data.get("choices")

        if not choices:

            print("NO CHOICES")
            print(data)

            return "AI response nahi mil saka."

        # -------------------------------------------------
        # MESSAGE
        # -------------------------------------------------

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

        # -------------------------------------------------
        # CLEAN
        # -------------------------------------------------

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

        # -------------------------------------------------
        # EMPTY
        # -------------------------------------------------

        if not reply:

            print("EMPTY AI RESPONSE")
            print(data)

            return "AI response nahi mil saka."

        # -------------------------------------------------
        # SUCCESS
        # -------------------------------------------------

        print()
        print("==============================")
        print("AI REPLY")
        print("==============================")

        print(reply)

        print("==============================")

        return reply

    except requests.exceptions.Timeout:

        print("GROQ TIMEOUT")

        return "AI response nahi mil saka."

    except requests.exceptions.ConnectionError as e:

        print("GROQ CONNECTION ERROR")
        print(str(e))

        return "AI response nahi mil saka."

    except Exception as e:

        print("GROQ EXCEPTION")
        print(type(e).__name__)
        print(str(e))

        return "AI response nahi mil saka."


# =====================================================
# WAKE
# =====================================================

@app.route("/wake", methods=["POST"])
def wake():

    filename = None

    try:

        print()
        print("==============================")
        print("WAKE REQUEST")
        print("==============================")

        audio_data = request.get_data()

        print(
            "Audio bytes:",
            len(audio_data)
        )

        if not audio_data:

            return jsonify({
                "status": "error",
                "wake": False,
                "message": "No audio received"
            }), 400

        # -------------------------------------------------
        # SAVE WAV
        # -------------------------------------------------

        fd, filename = tempfile.mkstemp(
            suffix=".wav"
        )

        os.close(fd)

        with open(filename, "wb") as f:

            f.write(audio_data)

        # -------------------------------------------------
        # RECOGNIZER
        # -------------------------------------------------

        recognizer = sr.Recognizer()

        with sr.AudioFile(filename) as source:

            audio = recognizer.record(source)

        hindi_text = None
        english_text = None

        # -------------------------------------------------
        # HINDI
        # -------------------------------------------------

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

            print("Google Speech Error:", e)

        # -------------------------------------------------
        # ENGLISH
        # -------------------------------------------------

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

            print("Google Speech Error:", e)

        # -------------------------------------------------
        # DETECT
        # -------------------------------------------------

        wake_detected = is_wake_word(
            hindi_text,
            english_text
        )

        print()
        print("HINDI:", hindi_text)
        print("ENGLISH:", english_text)
        print("WAKE:", wake_detected)

        return jsonify({

            "status": "ok",

            "wake": wake_detected,

            "english": english_text,

            "hindi": hindi_text
        })

    except Exception as e:

        print("WAKE SERVER ERROR:")
        print(type(e).__name__)
        print(str(e))

        return jsonify({

            "status": "error",

            "wake": False,

            "message": str(e)

        }), 500

    finally:

        if filename:

            try:

                if os.path.exists(filename):

                    os.remove(filename)

            except Exception:

                pass


# =====================================================
# TEST
# =====================================================

@app.route("/test", methods=["POST"])
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
        print("==============================")
        print("QUESTION AUDIO")
        print("==============================")

        print(
            "Audio bytes:",
            len(audio_data)
        )

        if not audio_data:

            return jsonify({

                "status": "error",

                "message": "No audio received",

                "ai_reply":
                    "Please ask your question again."

            }), 400

        # -------------------------------------------------
        # TEMP WAV
        # -------------------------------------------------

        fd, filename = tempfile.mkstemp(
            suffix=".wav"
        )

        os.close(fd)

        with open(filename, "wb") as f:

            f.write(audio_data)

        # -------------------------------------------------
        # SPEECH RECOGNITION
        # -------------------------------------------------

        recognizer = sr.Recognizer()

        with sr.AudioFile(filename) as source:

            audio = recognizer.record(source)

        hindi_text = None
        english_text = None

        # -------------------------------------------------
        # HINDI
        # -------------------------------------------------

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

            print("Google Speech Error:", e)

            return jsonify({

                "status": "error",

                "message":
                    "Speech service error",

                "ai_reply":
                    "Speech service error."

            }), 500

        # -------------------------------------------------
        # ENGLISH
        # -------------------------------------------------

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

            print("Google Speech Error:", e)

            return jsonify({

                "status": "error",

                "message":
                    "Speech service error",

                "ai_reply":
                    "Speech service error."

            }), 500

        # -------------------------------------------------
        # VALIDATION
        # -------------------------------------------------

        if (
            not is_valid_query(hindi_text)
            and
            not is_valid_query(english_text)
        ):

            return jsonify({

                "status": "error",

                "message":
                    "Speech not understood",

                "transcription": None,

                "hindi_transcription":
                    hindi_text,

                "english_transcription":
                    english_text,

                "ai_reply":
                    "Please ask your question again."

            }), 400

        # -------------------------------------------------
        # AI
        # -------------------------------------------------

        ai_reply = get_ai_reply(
            hindi_text,
            english_text
        )

        # -------------------------------------------------
        # BEST TRANSCRIPTION
        # -------------------------------------------------

        if is_valid_query(english_text):

            transcription = english_text

        else:

            transcription = hindi_text

        # -------------------------------------------------
        # RESPONSE
        # -------------------------------------------------

        response_data = {

            "status": "ok",

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

        print(response_data)

        print("==============================")

        return jsonify(response_data)

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

            "status": "error",

            "message": str(e),

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

    print("PORT:", port)
    print("AI URL:", AI_URL)
    print("AI MODEL:", AI_MODEL)

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

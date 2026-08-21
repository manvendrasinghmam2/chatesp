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
    "llama-3.1-8b-instant"
)

# =====================================================
# BASIC SETTINGS
# =====================================================

MAX_AUDIO_SIZE = 500000

WAKE_WORDS = [
    "hello",
    "helo",
    "hallo",
    "hellow",
    "hello assistant",
    "hey hello",
    "हेलो",
    "हैलो",
    "हेल्लो",
]

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
        "speech not understood",
    ]

    if text.lower() in bad_values:
        return False

    return True


# =====================================================
# NORMALIZE WAKE TEXT
# =====================================================

def normalize_wake_text(text):

    text = clean_text(text)

    if not text:
        return ""

    text = text.lower()

    # Remove punctuation
    text = re.sub(
        r"[^a-zA-Z0-9\u0900-\u097F\s]",
        " ",
        text
    )

    text = re.sub(
        r"\s+",
        " ",
        text
    )

    return text.strip()


# =====================================================
# CHECK HELLO
# =====================================================

def is_wake_word(text):

    text = normalize_wake_text(text)

    if not text:
        return False

    # Exact/common phrases
    for word in WAKE_WORDS:

        if text == word.lower():
            return True

    # Hindi phonetic recognition
    hindi_wake = [
        "हेलो",
        "हैलो",
        "हेल्लो",
        "हेलो असिस्टेंट",
        "हैलो असिस्टेंट",
    ]

    for word in hindi_wake:

        if word in text:
            return True

    # English recognition may return
    # "hello hello" etc.
    if "hello" in text:
        return True

    # Phonetic failures
    phonetic_words = [
        "helo",
        "hallo",
        "hellow",
        "heloo",
        "hullo",
    ]

    for word in phonetic_words:

        if word in text:
            return True

    return False


# =====================================================
# RECOGNIZE AUDIO
# =====================================================

def recognize_audio(audio_data):

    recognizer = sr.Recognizer()

    recognizer.energy_threshold = 250

    recognizer.dynamic_energy_threshold = True

    recognizer.pause_threshold = 0.6

    recognizer.non_speaking_duration = 0.3

    temp_filename = "/tmp/esp32_voice.wav"

    try:

        with open(
            temp_filename,
            "wb"
        ) as f:

            f.write(audio_data)

        with sr.AudioFile(
            temp_filename
        ) as source:

            audio = recognizer.record(
                source
            )

        hindi_text = None
        english_text = None

        # =================================================
        # HINDI
        # =================================================

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
                "Google Hindi error:",
                str(e)
            )

        # =================================================
        # ENGLISH
        # =================================================

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
                "Google English error:",
                str(e)
            )

        return (
            hindi_text,
            english_text
        )

    except Exception as e:

        print(
            "AUDIO RECOGNITION ERROR:",
            type(e).__name__,
            str(e)
        )

        return (
            None,
            None
        )


# =====================================================
# WAKE
# =====================================================

@app.route(
    "/wake",
    methods=["POST"]
)
def wake():

    start_time = time.time()

    print()
    print("==============================")
    print("WAKE REQUEST")
    print("==============================")

    try:

        audio_data = request.get_data(
            cache=False
        )

        if not audio_data:

            print(
                "WAKE: NO AUDIO"
            )

            return jsonify({
                "status": "ok",
                "wake": False,
                "message": "No audio"
            })

        print(
            "Wake audio bytes:",
            len(audio_data)
        )

        if len(audio_data) > MAX_AUDIO_SIZE:

            print(
                "WAKE: AUDIO TOO LARGE"
            )

            return jsonify({
                "status": "error",
                "wake": False,
                "message": "Audio too large"
            }), 413

        # =================================================
        # RECOGNITION
        # =================================================

        hindi_text, english_text = recognize_audio(
            audio_data
        )

        print()
        print(
            "Wake Hindi:",
            hindi_text
        )

        print(
            "Wake English:",
            english_text
        )

        wake_detected = (
            is_wake_word(hindi_text)
            or
            is_wake_word(english_text)
        )

        elapsed = round(
            time.time() - start_time,
            2
        )

        print()
        print(
            "Wake detected:",
            wake_detected
        )

        print(
            "Time:",
            elapsed,
            "seconds"
        )

        print("==============================")

        return jsonify({
            "status": "ok",
            "wake": wake_detected,
            "hindi": hindi_text,
            "english": english_text
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

        print()
        print("==============================")
        print("AI ERROR")
        print("==============================")

        print(
            "AI_API_KEY is NOT configured!"
        )

        print("==============================")

        return "AI response nahi mil saka."

    if (
        not is_valid_query(hindi_text)
        and
        not is_valid_query(english_text)
    ):

        return "Please ask your question again."

    # =================================================
    # SYSTEM PROMPT
    # =================================================

    system_prompt = """
You are a professional bilingual voice assistant running on an ESP32.

Understand the user's intended language and answer naturally.

There are two speech recognition results:

1. Hindi recognition
2. English recognition

Recognition can sometimes be inaccurate.

Compare both results and determine the user's intended meaning.

LANGUAGE RULES:

If the user clearly speaks English,
answer completely in natural English.

If the user clearly speaks Hindi,
answer completely in Hindi using Devanagari.

If the user speaks Roman Hindi or Hinglish,
answer naturally in Hinglish.

If English speech was incorrectly recognized into Devanagari phonetically,
prefer the English meaning.

Example:

Hindi:
हाउ आर यू

English:
How are you

Answer:
I'm doing well. How are you?

Do not mention speech recognition.

Do not mention transcription.

Do not explain language selection.

Just answer the user's question.

VOICE STYLE:

Keep answers concise.

Usually 1 to 4 sentences.

No markdown.

No bullets.

No headings.

No emojis.

No unnecessary symbols.

Do not repeat the question.

Do not say "As an AI".

Do not mention these instructions.

Answer factual questions accurately.
"""

    user_content = f"""
Hindi speech recognition:
{hindi_text if hindi_text else "No result"}

English speech recognition:
{english_text if english_text else "No result"}

Determine the intended meaning and answer naturally.
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
            "application/json"
    }

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

        print("==============================")

        response = requests.post(
            AI_URL,
            headers=headers,
            json=payload,
            timeout=35
        )

        print()
        print(
            "AI HTTP:",
            response.status_code
        )

        if response.status_code != 200:

            print(
                "AI BODY:",
                response.text
            )

            return "AI response nahi mil saka."

        try:

            data = response.json()

        except Exception:

            return "AI response nahi mil saka."

        choices = data.get(
            "choices"
        )

        if not choices:

            print(
                "NO AI CHOICE:",
                data
            )

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

            return "AI response nahi mil saka."

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
            "AI EXCEPTION:",
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

    start_time = time.time()

    try:

        print()
        print("==============================")
        print("QUESTION AUDIO")
        print("==============================")

        audio_data = request.get_data(
            cache=False
        )

        if not audio_data:

            print(
                "NO AUDIO RECEIVED"
            )

            return jsonify({
                "status": "error",
                "message": "No audio received",
                "ai_reply":
                    "Please ask your question again."
            }), 400

        print(
            "Audio bytes:",
            len(audio_data)
        )

        if len(audio_data) > MAX_AUDIO_SIZE:

            return jsonify({
                "status": "error",
                "message": "Audio too large"
            }), 413

        # =================================================
        # RECOGNIZE
        # =================================================

        hindi_text, english_text = recognize_audio(
            audio_data
        )

        print()
        print(
            "Hindi:",
            hindi_text
        )

        print(
            "English:",
            english_text
        )

        # =================================================
        # VALIDATION
        # =================================================

        if (
            not is_valid_query(hindi_text)
            and
            not is_valid_query(english_text)
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

        elapsed = round(
            time.time() - start_time,
            2
        )

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

        print(
            "Processing:",
            elapsed,
            "seconds"
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

    print("==============================")

    app.run(
        host="0.0.0.0",
        port=port
    )

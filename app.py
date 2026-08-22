from flask import Flask, request, jsonify
import os
import re
import tempfile
import requests
import speech_recognition as sr

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
# TEXT CLEAN
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

    text = clean_text(text)

    if len(text) < 2:
        return False

    bad_values = {
        "",
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
# NORMALIZE WAKE TEXT
# =====================================================

def normalize_wake_text(text):

    text = clean_text(text).lower()

    # Remove punctuation
    text = re.sub(
        r"[^\w\s\u0900-\u097F]",
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
# WAKE WORD
# =====================================================

def is_wake_word(hindi_text, english_text):

    hindi = normalize_wake_text(hindi_text)
    english = normalize_wake_text(english_text)

    print("WAKE CHECK HINDI:", hindi)
    print("WAKE CHECK ENGLISH:", english)

    # -------------------------------------------------
    # English
    # -------------------------------------------------

    english_words = [
        "hello",
        "helo",
        "hellow",
        "hallo",
        "hullo",
        "hey",
        "hi"
    ]

    # -------------------------------------------------
    # Hindi / Devanagari
    # -------------------------------------------------

    hindi_words = [
        "नमस्ते",
        "नमस्कार",
        "हेलो",
        "हैलो",
        "हे"
    ]

    # -------------------------------------------------
    # Exact / phrase matching
    # -------------------------------------------------

    for word in english_words:

        if re.search(
            r"\b" + re.escape(word) + r"\b",
            english
        ):
            return True

    for word in hindi_words:

        if word in hindi:
            return True

    # -------------------------------------------------
    # Recognition sometimes produces:
    #
    # "hello hello"
    # "hey assistant"
    # "hello there"
    # -------------------------------------------------

    for word in english_words:

        if word in english.split():
            return True

    return False


# =====================================================
# SPEECH RECOGNITION
# =====================================================

def recognize_audio(audio):

    recognizer = sr.Recognizer()

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

        print("HINDI RESULT:", hindi_text)

    except sr.UnknownValueError:

        print("HINDI: Could not understand")

    except sr.RequestError as e:

        print(
            "HINDI GOOGLE ERROR:",
            str(e)
        )

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

        print(
            "ENGLISH RESULT:",
            english_text
        )

    except sr.UnknownValueError:

        print("ENGLISH: Could not understand")

    except sr.RequestError as e:

        print(
            "ENGLISH GOOGLE ERROR:",
            str(e)
        )

    return hindi_text, english_text


# =====================================================
# GROQ AI
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

    # -------------------------------------------------
    # API KEY
    # -------------------------------------------------

    if not AI_API_KEY:

        print("ERROR: AI_API_KEY missing")

        return "AI response nahi mil saka."

    # -------------------------------------------------
    # INPUT
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
You are a professional bilingual voice assistant.

You receive two speech recognition results:

Hindi recognition:
English recognition:

The recognition may contain mistakes.

Understand the user's intended meaning by comparing both results.

LANGUAGE RULES:

If the user clearly speaks English,
answer completely in natural English.

If the user clearly speaks Hindi,
answer completely in Hindi using Devanagari script.

If the user speaks Roman Hindi or Hinglish,
answer naturally in Hinglish.

If English speech was incorrectly recognized as
Devanagari phonetic Hindi, understand the English
meaning and answer in English.

Do not mention speech recognition.

Do not mention Hindi transcription.

Do not mention English transcription.

Do not explain your language decision.

Only answer the user's question.

VOICE STYLE:

Keep the answer short.

Usually 1 to 4 sentences.

The answer will be spoken aloud.

Do not use markdown.

Do not use bullet points.

Do not use emojis.

Do not use headings.

Do not repeat the question.

Do not say "As an AI".

Do not say "Sure" unnecessarily.

Be natural and professional.
"""

    user_content = f"""
Hindi recognition:
{hindi_text if hindi_text else "No result"}

English recognition:
{english_text if english_text else "No result"}

Understand the intended question and answer naturally.
"""

    # -------------------------------------------------
    # GROQ PAYLOAD
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

    headers = {

        "Authorization":
            "Bearer " + AI_API_KEY,

        "Content-Type":
            "application/json",

        "Accept":
            "application/json"
    }

    # -------------------------------------------------
    # REQUEST
    # -------------------------------------------------

    try:

        print()
        print("==============================")
        print("GROQ REQUEST")
        print("==============================")

        print("URL:", AI_URL)
        print("MODEL:", AI_MODEL)

        print("HINDI:", hindi_text)
        print("ENGLISH:", english_text)

        response = requests.post(

            AI_URL,

            headers=headers,

            json=payload,

            timeout=40
        )

        print(
            "HTTP:",
            response.status_code
        )

        # -------------------------------------------------
        # API ERROR
        # -------------------------------------------------

        if response.status_code != 200:

            print()
            print("GROQ ERROR")
            print("==============================")
            print(
                response.text[:4000]
            )
            print("==============================")

            return "AI response nahi mil saka."

        # -------------------------------------------------
        # JSON
        # -------------------------------------------------

        try:

            data = response.json()

        except Exception as e:

            print(
                "JSON ERROR:",
                str(e)
            )

            return "AI response nahi mil saka."

        # -------------------------------------------------
        # CHOICES
        # -------------------------------------------------

        choices = data.get(
            "choices"
        )

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

        reply = str(
            reply
        ).strip()

        # -------------------------------------------------
        # REMOVE MARKDOWN
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

@app.route(
    "/wake",
    methods=["POST"]
)
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

        # -------------------------------------------------
        # CHECK AUDIO
        # -------------------------------------------------

        if not audio_data:

            return jsonify({

                "status": "error",

                "wake": False,

                "english": None,

                "hindi": None,

                "message":
                    "No audio received"

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
            "WAV saved:",
            filename
        )

        # -------------------------------------------------
        # OPEN AUDIO
        # -------------------------------------------------

        recognizer = sr.Recognizer()

        with sr.AudioFile(
            filename
        ) as source:

            audio = recognizer.record(
                source
            )

        print(
            "WAV duration:",
            audio.sample_width,
            "bytes/sample"
        )

        # -------------------------------------------------
        # RECOGNIZE
        # -------------------------------------------------

        hindi_text, english_text = recognize_audio(
            audio
        )

        # -------------------------------------------------
        # WAKE
        # -------------------------------------------------

        wake_detected = is_wake_word(
            hindi_text,
            english_text
        )

        print()
        print("==============================")
        print("WAKE RESULT")
        print("==============================")

        print(
            "HINDI:",
            hindi_text
        )

        print(
            "ENGLISH:",
            english_text
        )

        print(
            "WAKE:",
            wake_detected
        )

        print("==============================")

        # -------------------------------------------------
        # RESPONSE
        # -------------------------------------------------

        return jsonify({

            "status": "ok",

            "wake":
                wake_detected,

            "english":
                english_text,

            "hindi":
                hindi_text

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

            "english": None,

            "hindi": None,

            "message":
                str(e)

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

            "message":
                "No JSON received"

        }), 400

    return jsonify({

        "status": "ok",

        "message":
            "Data received",

        "data":
            data

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

        print()
        print("==============================")
        print("QUESTION AUDIO")
        print("==============================")

        audio_data = request.get_data()

        print(
            "Audio bytes:",
            len(audio_data)
        )

        if not audio_data:

            return jsonify({

                "status": "error",

                "message":
                    "No audio received",

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

        # -------------------------------------------------
        # READ WAV
        # -------------------------------------------------

        recognizer = sr.Recognizer()

        with sr.AudioFile(
            filename
        ) as source:

            audio = recognizer.record(
                source
            )

        # -------------------------------------------------
        # RECOGNITION
        # -------------------------------------------------

        hindi_text, english_text = recognize_audio(
            audio
        )

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

                "transcription":
                    None,

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
        # TRANSCRIPTION
        # -------------------------------------------------

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

        # -------------------------------------------------
        # RESPONSE
        # -------------------------------------------------

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

    print("==============================")

    app.run(

        host="0.0.0.0",

        port=port,

        threaded=True
    )

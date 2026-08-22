from flask import Flask, request, jsonify, Response
import os
import re
import tempfile
import requests
import speech_recognition as sr
from gtts import gTTS

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
        "tts": "gTTS"
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
# WAKE WORD DETECTION
# =====================================================

def is_hello(text):

    if not text:
        return False

    text = clean_text(text).lower()

    print("Wake recognition:", text)

    # Remove punctuation
    normalized = re.sub(
        r"[^a-zA-Z0-9\u0900-\u097F ]",
        " ",
        text
    )

    normalized = re.sub(
        r"\s+",
        " ",
        normalized
    ).strip()

    # -------------------------------------------------
    # Exact / common English results
    # -------------------------------------------------

    hello_words = [
        "hello",
        "helo",
        "hellow",
        "hallo",
        "hullo",
        "heloo",
        "helloo",
        "hello hello",
        "hey hello",
        "hello there"
    ]

    if normalized in hello_words:
        return True

    # -------------------------------------------------
    # Hindi recognition
    # -------------------------------------------------

    hindi_words = [
        "हेलो",
        "हैलो",
        "हेल्लो",
        "हलो"
    ]

    for word in hindi_words:

        if word in normalized:
            return True

    # -------------------------------------------------
    # Sometimes Google returns sentence
    # -------------------------------------------------

    english_pattern = re.search(
        r"\bhello\b",
        normalized
    )

    if english_pattern:
        return True

    return False


# =====================================================
# WAKE
# =====================================================

@app.route(
    "/wake",
    methods=["POST"]
)
def wake():

    print()
    print("================================")
    print("WAKE REQUEST")
    print("================================")

    audio_data = request.get_data()

    print(
        "Audio bytes:",
        len(audio_data)
    )

    if not audio_data:

        return jsonify({
            "status": "error",
            "wake": False,
            "message": "No audio"
        }), 400

    filename = None

    try:

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

            f.write(audio_data)

        print(
            "WAV saved:",
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

        english_text = None
        hindi_text = None

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

            print(
                "Wake English:",
                english_text
            )

        except sr.UnknownValueError:

            print(
                "Wake English: not understood"
            )

        except sr.RequestError as e:

            print(
                "Google wake error:",
                str(e)
            )

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

            print(
                "Wake Hindi:",
                hindi_text
            )

        except sr.UnknownValueError:

            print(
                "Wake Hindi: not understood"
            )

        except sr.RequestError as e:

            print(
                "Google wake Hindi error:",
                str(e)
            )

        # =================================================
        # DETECT
        # =================================================

        wake_detected = (
            is_hello(english_text)
            or
            is_hello(hindi_text)
        )

        print()
        print(
            "WAKE DETECTED:",
            wake_detected
        )

        print("================================")

        return jsonify({

            "status": "ok",

            "wake": wake_detected,

            "english": english_text,

            "hindi": hindi_text
        })

    except Exception as e:

        print()
        print("WAKE ERROR:")
        print(
            type(e).__name__,
            str(e)
        )

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
# AI
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

        print(
            "ERROR: AI_API_KEY missing"
        )

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

    # -------------------------------------------------
    # SYSTEM PROMPT
    # -------------------------------------------------

    system_prompt = """
You are a professional bilingual voice assistant running on an ESP32.

Understand the user's intended language.

If the user speaks English:
Answer in English.

If the user speaks Hindi:
Answer in Hindi using Devanagari.

If the user speaks Hinglish:
Answer naturally in Hinglish.

Compare the Hindi and English speech recognition results
and determine the intended meaning.

Do not mention speech recognition.

Do not explain your language decision.

The answer will be spoken aloud.

Keep answers concise.

Usually 1 to 4 sentences.

Do not use markdown.

Do not use bullet points.

Do not use emojis.

Do not use headings.

Do not repeat the question.

Do not say "As an AI".

Be natural and conversational.
"""

    user_content = f"""
Hindi speech recognition:
{hindi_text if hindi_text else "No result"}

English speech recognition:
{english_text if english_text else "No result"}

Answer the user's question naturally.
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
        print("================================")
        print("AI REQUEST")
        print("================================")

        print(
            "English:",
            english_text
        )

        print(
            "Hindi:",
            hindi_text
        )

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
                "AI ERROR:",
                response.text[:2000]
            )

            return (
                "AI response nahi mil saka."
            )

        data = response.json()

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
        )

        reply = reply.strip()

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

            return (
                "AI response nahi mil saka."
            )

        print()
        print("================================")
        print("AI REPLY")
        print("================================")

        print(reply)

        print("================================")

        return reply

    except requests.exceptions.Timeout:

        print(
            "AI timeout"
        )

        return (
            "AI response nahi mil saka."
        )

    except Exception as e:

        print(
            "AI exception:",
            type(e).__name__,
            str(e)
        )

        return (
            "AI response nahi mil saka."
        )


# =====================================================
# TTS
# =====================================================

def create_tts(
    text
):

    if not text:

        return None

    text = clean_text(
        text
    )

    if not text:

        return None

    filename = tempfile.mktemp(
        suffix=".mp3"
    )

    try:

        # -------------------------------------------------
        # Detect language
        # -------------------------------------------------

        has_devanagari = bool(
            re.search(
                r"[\u0900-\u097F]",
                text
            )
        )

        if has_devanagari:

            language = "hi"

        else:

            language = "en"

        print()
        print("================================")
        print("TTS")
        print("================================")

        print(
            "Language:",
            language
        )

        print(
            "Text:",
            text
        )

        # -------------------------------------------------
        # gTTS
        # -------------------------------------------------

        tts = gTTS(
            text=text,
            lang=language,
            slow=False
        )

        tts.save(
            filename
        )

        print(
            "TTS created:",
            filename
        )

        print("================================")

        return filename

    except Exception as e:

        print(
            "TTS ERROR:",
            type(e).__name__,
            str(e)
        )

        try:

            if os.path.exists(filename):

                os.remove(filename)

        except Exception:

            pass

        return None


# =====================================================
# TTS ENDPOINT
# =====================================================

@app.route(
    "/tts",
    methods=["POST"]
)
def tts_endpoint():

    filename = None

    try:

        data = request.get_json(
            silent=True
        )

        if not data:

            return jsonify({
                "status": "error",
                "message": "JSON required"
            }), 400

        text = data.get(
            "text",
            ""
        )

        text = clean_text(
            text
        )

        if not text:

            return jsonify({
                "status": "error",
                "message": "No text"
            }), 400

        filename = create_tts(
            text
        )

        if not filename:

            return jsonify({
                "status": "error",
                "message": "TTS failed"
            }), 500

        with open(
            filename,
            "rb"
        ) as f:

            audio_data = f.read()

        return Response(

            audio_data,

            mimetype="audio/mpeg",

            headers={
                "Content-Disposition":
                    "inline; filename=reply.mp3"
            }
        )

    except Exception as e:

        return jsonify({

            "status": "error",

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
# UPLOAD AUDIO
# =====================================================

@app.route(
    "/uploadAudio",
    methods=["POST"]
)
def upload_audio():

    filename = None

    try:

        # -------------------------------------------------
        # RECEIVE WAV
        # -------------------------------------------------

        audio_data = request.get_data()

        print()
        print("================================")
        print("AUDIO RECEIVED")
        print("================================")

        print(
            "Bytes:",
            len(audio_data)
        )

        if not audio_data:

            return jsonify({

                "status":
                    "error",

                "message":
                    "No audio received",

                "transcription":
                    None,

                "ai_reply":
                    "Please ask your question again."

            }), 400

        # -------------------------------------------------
        # SAVE
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
        # SPEECH
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
                "Hindi not understood"
            )

        except sr.RequestError as e:

            print(
                "Hindi Google error:",
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

            print(
                "English:",
                english_text
            )

        except sr.UnknownValueError:

            print(
                "English not understood"
            )

        except sr.RequestError as e:

            print(
                "English Google error:",
                str(e)
            )

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
        print("================================")
        print("FINAL")
        print("================================")

        print(
            "USER:",
            transcription
        )

        print(
            "AI:",
            ai_reply
        )

        print("================================")

        return jsonify(
            response_data
        )

    except Exception as e:

        print()
        print("================================")
        print("SERVER ERROR")
        print("================================")

        print(
            type(e).__name__,
            str(e)
        )

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

                if os.path.exists(filename):

                    os.remove(filename)

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
    print("================================")
    print("ESP32 VOICE SERVER")
    print("================================")

    print(
        "PORT:",
        port
    )

    print(
        "MODEL:",
        AI_MODEL
    )

    print(
        "AI KEY:",
        "CONFIGURED"
        if AI_API_KEY
        else "MISSING"
    )

    print("================================")

    app.run(
        host="0.0.0.0",
        port=port,
        threaded=True
    )

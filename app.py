from flask import Flask, request, jsonify, send_file
import os
import speech_recognition as sr
import requests
import re
import tempfile
import uuid
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

BASE_URL = os.environ.get(
    "BASE_URL",
    "https://chatesp-2.onrender.com"
)


# =====================================================
# TTS DIRECTORY
# =====================================================

TTS_DIR = os.path.join(
    tempfile.gettempdir(),
    "esp32_tts"
)

os.makedirs(
    TTS_DIR,
    exist_ok=True
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
        "tts_engine": "Google gTTS",
        "model": AI_MODEL
    })


# =====================================================
# WAKE
# =====================================================

@app.route("/wake", methods=["POST"])
def wake():

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
    # IMPORTANT
    #
    # First test:
    # only actual spoken HELLO should wake.
    #
    # -------------------------------------------------

    if not audio_data:

        return jsonify({
            "status": "ok",
            "wake": False
        })

    filename = None

    try:

        fd, filename = tempfile.mkstemp(
            suffix=".wav"
        )

        os.close(fd)

        with open(
            filename,
            "wb"
        ) as f:

            f.write(audio_data)

        recognizer = sr.Recognizer()

        with sr.AudioFile(filename) as source:

            audio = recognizer.record(source)

        # -------------------------------------------------
        # ENGLISH WAKE
        # -------------------------------------------------

        try:

            text = recognizer.recognize_google(
                audio,
                language="en-IN"
            )

            text = clean_text(text)

            print(
                "Wake recognition:",
                text
            )

            normalized = text.lower()

            # -------------------------------------------------
            # ACCEPT ONLY HELLO / HI HELLO TYPE
            # -------------------------------------------------

            wake_words = [
                "hello",
                "hello there",
                "hey hello",
                "hi hello",
                "helo",
                "hullo"
            ]

            for word in wake_words:

                if normalized == word:

                    print(
                        "HELLO DETECTED"
                    )

                    return jsonify({
                        "status": "ok",
                        "wake": True,
                        "text": text
                    })

            print(
                "NO HELLO"
            )

            return jsonify({
                "status": "ok",
                "wake": False,
                "text": text
            })

        except sr.UnknownValueError:

            print(
                "Wake speech not understood"
            )

            return jsonify({
                "status": "ok",
                "wake": False
            })

        except sr.RequestError as e:

            print(
                "Wake Google error:",
                str(e)
            )

            return jsonify({
                "status": "error",
                "wake": False
            })

    except Exception as e:

        print(
            "WAKE ERROR:",
            type(e).__name__,
            str(e)
        )

        return jsonify({
            "status": "error",
            "wake": False
        })

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

@app.route("/test", methods=["GET"])
def test():

    return jsonify({
        "status": "ok",
        "message": "Server working"
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
            "AI_API_KEY missing"
        )

        return "AI response nahi mil saka."

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
You are a professional bilingual voice assistant running on ESP32.

Understand the user's intended spoken language.

If English is intended:
answer in natural English.

If Hindi is intended:
answer in Hindi using Devanagari.

If Hinglish is intended:
answer in natural Hinglish.

Compare Hindi and English speech recognition results
and determine what the user actually meant.

Keep answers short because the answer will be spoken aloud.

Usually 1 to 4 sentences.

Do not use markdown.

Do not use bullet points.

Do not use emojis.

Do not use headings.

Do not repeat the question.

Do not mention speech recognition.

Do not explain your language decision.

Do not say "As an AI".

Answer naturally.
"""

    user_content = f"""
Hindi speech recognition:
{hindi_text if hindi_text else "No result"}

English speech recognition:
{english_text if english_text else "No result"}

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

            return "AI response nahi mil saka."

        data = response.json()

        choices = data.get(
            "choices"
        )

        if not choices:

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

        for prefix in [
            "AI:",
            "Answer:",
            "Response:"
        ]:

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

    except Exception as e:

        print(
            "AI ERROR:",
            type(e).__name__,
            str(e)
        )

        return "AI response nahi mil saka."


# =====================================================
# CREATE TTS
# =====================================================

def create_tts(
    text,
    language_hint
):

    text = clean_text(text)

    if not text:

        return None

    filename = os.path.join(
        TTS_DIR,
        "tts_" +
        uuid.uuid4().hex +
        ".mp3"
    )

    try:

        # -------------------------------------------------
        # LANGUAGE
        # -------------------------------------------------

        # Hindi Devanagari -> Hindi voice
        if re.search(
            r"[\u0900-\u097F]",
            text
        ):

            lang = "hi"

        else:

            lang = "en"

        print()
        print("==============================")
        print("TTS")
        print("==============================")

        print(
            "Language:",
            lang
        )

        print(
            "Text:",
            text
        )

        tts = gTTS(
            text=text,
            lang=lang,
            slow=False
        )

        tts.save(
            filename
        )

        print(
            "TTS FILE:",
            filename
        )

        print("==============================")

        return filename

    except Exception as e:

        print(
            "TTS ERROR:",
            type(e).__name__,
            str(e)
        )

        return None


# =====================================================
# SERVE TTS
# =====================================================

@app.route(
    "/tts/<filename>",
    methods=["GET"]
)
def serve_tts(filename):

    # Security
    if "/" in filename or "\\" in filename:

        return "Invalid filename", 400

    filepath = os.path.join(
        TTS_DIR,
        filename
    )

    if not os.path.exists(filepath):

        return "Audio not found", 404

    return send_file(
        filepath,
        mimetype="audio/mpeg",
        download_name=filename
    )


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
        print("==============================")
        print("AUDIO RECEIVED")
        print("==============================")

        print(
            "Bytes:",
            len(audio_data)
        )

        print("==============================")

        if not audio_data:

            return jsonify({

                "status":
                    "error",

                "transcription":
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

            f.write(audio_data)

        # -------------------------------------------------
        # SPEECH
        # -------------------------------------------------

        recognizer = sr.Recognizer()

        with sr.AudioFile(filename) as source:

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

            hindi_text = None

        except sr.RequestError as e:

            print(
                "Speech API error:",
                str(e)
            )

            return jsonify({

                "status":
                    "error",

                "message":
                    "Speech service error"

            }), 500

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

            english_text = None

        except sr.RequestError as e:

            print(
                "Speech API error:",
                str(e)
            )

            return jsonify({

                "status":
                    "error",

                "message":
                    "Speech service error"

            }), 500

        # =================================================
        # VALIDATION
        # =================================================

        if (
            not is_valid_query(hindi_text)
            and
            not is_valid_query(english_text)
        ):

            print(
                "Speech not understood"
            )

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
        # TTS
        # =================================================

        tts_file = create_tts(
            ai_reply,
            transcription
        )

        tts_url = None

        if tts_file:

            tts_filename = os.path.basename(
                tts_file
            )

            tts_url = (
                BASE_URL.rstrip("/")
                +
                "/tts/"
                +
                tts_filename
            )

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
                ai_reply,

            "tts_url":
                tts_url
        }

        print()
        print("==============================")
        print("FINAL")
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
            type(e).__name__,
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
    print("==============================")
    print("ESP32 VOICE SERVER")
    print("==============================")

    print(
        "PORT:",
        port
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

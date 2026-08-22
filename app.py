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

PORT = int(
    os.environ.get(
        "PORT",
        10000
    )
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
        "tts_engine": "Google TTS",
        "model": AI_MODEL
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
    print("==============================")
    print("WAKE REQUEST")
    print("==============================")

    if request.method == "POST":

        audio_data = request.get_data()

        print(
            "AUDIO BYTES:",
            len(audio_data)
        )

    # -------------------------------------------------
    # CURRENT TEST MODE
    # -------------------------------------------------

    response_data = {
        "status": "ok",
        "wake": True,
        "english": "Hello",
        "hindi": None
    }

    print(
        "WAKE RESPONSE:",
        response_data
    )

    print("==============================")

    return jsonify(
        response_data
    )

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

    # =================================================
    # SYSTEM PROMPT
    # =================================================

    system_prompt = """
You are a professional bilingual voice assistant.

Understand the user's intended language.

If the user speaks English,
answer in natural English.

If the user speaks Hindi,
answer in Hindi using Devanagari.

If the user speaks Hinglish,
answer in natural Hinglish.

Compare the Hindi and English recognition results
and choose the interpretation that makes the most
linguistic and contextual sense.

Keep the answer short because it will be spoken aloud.

Usually answer in 1 to 4 sentences.

Do not use markdown.

Do not use bullet points.

Do not use emojis.

Do not use headings.

Do not repeat the question.

Do not say "As an AI".

Do not mention speech recognition.

Just answer naturally.
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
            "application/json",

        "Accept":
            "application/json"
    }

    try:

        print()
        print("==============================")
        print("AI REQUEST")
        print("==============================")

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

        if response.status_code != 200:

            print(
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

        if not reply:

            return (
                "AI response nahi mil saka."
            )

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

        return (
            "AI response nahi mil saka."
        )

    except requests.exceptions.ConnectionError as e:

        print(
            "AI CONNECTION ERROR:",
            str(e)
        )

        return (
            "AI response nahi mil saka."
        )

    except Exception as e:

        print(
            "AI ERROR:",
            type(e).__name__,
            str(e)
        )

        return (
            "AI response nahi mil saka."
        )

# =====================================================
# CREATE TTS
# =====================================================

def create_tts(
    text,
    language_hint=None
):

    text = clean_text(
        text
    )

    if not text:

        return None

    filename = (
        str(uuid.uuid4())
        + ".mp3"
    )

    filepath = os.path.join(
        TTS_DIR,
        filename
    )

    # =================================================
    # LANGUAGE DETECTION
    # =================================================

    # Devanagari -> Hindi
    if re.search(
        r"[\u0900-\u097F]",
        text
    ):

        lang = "hi"

    else:

        lang = "en"

    try:

        print()
        print("==============================")
        print("TTS REQUEST")
        print("==============================")

        print(
            "TEXT:",
            text
        )

        print(
            "LANG:",
            lang
        )

        tts = gTTS(
            text=text,
            lang=lang,
            slow=False
        )

        tts.save(
            filepath
        )

        print(
            "TTS FILE:",
            filepath
        )

        print("==============================")

        return filename

    except Exception as e:

        print()
        print(
            "TTS ERROR:",
            type(e).__name__,
            str(e)
        )

        return None

# =====================================================
# TTS FILE
# =====================================================

@app.route(
    "/tts/<filename>",
    methods=["GET"]
)
def tts_file(filename):

    # Security
    if "/" in filename:
        return "Invalid filename", 400

    if "\\" in filename:
        return "Invalid filename", 400

    if not filename.endswith(".mp3"):
        return "Invalid file", 400

    filepath = os.path.join(
        TTS_DIR,
        filename
    )

    if not os.path.isfile(filepath):

        return (
            "TTS file not found",
            404
        )

    print(
        "TTS DOWNLOAD:",
        filename
    )

    return send_file(
        filepath,
        mimetype="audio/mpeg",
        as_attachment=False,
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

        # =================================================
        # RECEIVE AUDIO
        # =================================================

        audio_data = request.get_data()

        if not audio_data:

            return jsonify({

                "status": "error",

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

        # =================================================
        # TEMP WAV
        # =================================================

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

        # =================================================
        # SPEECH
        # =================================================

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

            hindi_text = (
                recognizer.recognize_google(
                    audio,
                    language="hi-IN"
                )
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
                "Hindi not understood"
            )

        except sr.RequestError as e:

            print(
                "Speech API error:",
                str(e)
            )

            return jsonify({

                "status": "error",

                "message":
                    "Speech service error",

                "ai_reply":
                    "Speech service error."

            }), 500

        # =================================================
        # ENGLISH
        # =================================================

        try:

            english_text = (
                recognizer.recognize_google(
                    audio,
                    language="en-IN"
                )
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
                "English not understood"
            )

        except sr.RequestError as e:

            print(
                "Speech API error:",
                str(e)
            )

            return jsonify({

                "status": "error",

                "message":
                    "Speech service error",

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

            print(
                "SPEECH NOT UNDERSTOOD"
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
        # AI
        # =================================================

        ai_reply = get_ai_reply(
            hindi_text,
            english_text
        )

        # =================================================
        # TTS
        # =================================================

        tts_filename = create_tts(
            ai_reply
        )

        # =================================================
        # TTS URL
        # =================================================

        tts_url = None

        if tts_filename:

            # Render HTTPS URL
            render_url = os.environ.get(
                "RENDER_EXTERNAL_URL"
            )

            if render_url:

                tts_url = (
                    render_url.rstrip("/")
                    + "/tts/"
                    + tts_filename
                )

            else:

                # fallback
                tts_url = (
                    "/tts/"
                    + tts_filename
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

        # =================================================
        # SERIAL
        # =================================================

        print()
        print("==============================")
        print("FINAL RESPONSE")
        print("==============================")

        print(
            "USER:",
            transcription
        )

        print(
            "AI:",
            ai_reply
        )

        print(
            "TTS:",
            tts_url
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

                if os.path.exists(
                    filename
                ):

                    os.remove(
                        filename
                    )

            except Exception:

                pass

# =====================================================
# START
# =====================================================

if __name__ == "__main__":

    print()
    print("==============================")
    print("ESP32 VOICE SERVER")
    print("==============================")

    print(
        "PORT:",
        PORT
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
        port=PORT,
        threaded=True
    )

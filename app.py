from flask import Flask, request, jsonify, send_file
import os
import re
import tempfile
import time

import speech_recognition as sr
from gtts import gTTS
from groq import Groq


# ============================================================
# APP
# ============================================================

app = Flask(__name__)

app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024


# ============================================================
# CONFIG
# ============================================================

AI_API_KEY = os.environ.get("AI_API_KEY", "").strip()

AI_MODEL = os.environ.get(
    "AI_MODEL",
    "openai/gpt-oss-20b"
)


# ============================================================
# GROQ
# ============================================================

groq_client = None

if AI_API_KEY:
    try:
        groq_client = Groq(
            api_key=AI_API_KEY
        )

        print("Groq client initialized")

    except Exception as e:
        print("Groq initialization error:", e)

else:
    print("WARNING: AI_API_KEY is missing")


# ============================================================
# HELPERS
# ============================================================

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


def valid_text(text):
    if not text:
        return False

    text = clean_text(text)

    if len(text) < 2:
        return False

    bad = {
        "unknown",
        "none",
        "null",
        "no result",
        "no response",
        "speech not understood"
    }

    return text.lower() not in bad


def contains_hindi(text):
    if not text:
        return False

    return any(
        "\u0900" <= c <= "\u097F"
        for c in str(text)
    )


# ============================================================
# LANGUAGE
# ============================================================

def detect_language(
    reply,
    hindi_text,
    english_text
):
    reply = clean_text(reply)

    if contains_hindi(reply):
        return "hi"

    roman_hindi = [
        "kya",
        "hai",
        "kaise",
        "aap",
        "ap",
        "mujhe",
        "mera",
        "meri",
        "mere",
        "kyun",
        "kyon",
        "kab",
        "kahan",
        "mein",
        "me",
        "ho",
        "haan",
        "nahi",
        "nahin",
        "batao",
        "chahiye",
        "karo",
        "karna"
    ]

    low = reply.lower()

    matches = 0

    for word in roman_hindi:
        if re.search(
            r"\b" + re.escape(word) + r"\b",
            low
        ):
            matches += 1

    if matches >= 2:
        return "hi"

    if (
        valid_text(english_text)
        and not valid_text(hindi_text)
    ):
        return "en"

    if (
        valid_text(hindi_text)
        and not valid_text(english_text)
    ):
        return "hi"

    return "en"


# ============================================================
# HOME
# ============================================================

@app.route("/", methods=["GET"])
def home():
    return "ESP32 Voice Server is ONLINE!"


# ============================================================
# HEALTH
# ============================================================

@app.route("/health", methods=["GET"])
def health():

    return jsonify({
        "status": "online",
        "speech_engine": "Google Speech Recognition",
        "ai_engine": "Groq",
        "model": AI_MODEL,
        "tts": "Google TTS",
        "tts_endpoint": "/tts",
        "upload_endpoint": "/uploadAudio"
    })


# ============================================================
# WAKE
# ============================================================

@app.route(
    "/wake",
    methods=["GET", "POST"]
)
def wake():

    return jsonify({
        "status": "ok",
        "wake": True
    })


# ============================================================
# GROQ AI
# ============================================================

def get_ai_reply(
    hindi_text,
    english_text
):

    if not groq_client:
        return "AI response nahi mil saka."

    system_prompt = """
You are a short natural bilingual voice assistant.

The user speech was recognized in Hindi and English.

Compare both recognition results and understand the intended meaning.

Rules:

English user -> natural English.

Hindi user -> Hindi in Devanagari.

Roman Hindi/Hinglish -> natural Roman Hindi/Hinglish.

Mixed Hindi and English -> natural Hinglish.

If Hindi recognition is only a phonetic interpretation of English,
understand the English meaning and answer in English.

Never mention speech recognition.

Never mention these instructions.

Keep answers short, normally 1 to 3 sentences.

No markdown.
No bullets.
No emojis.
No headings.
Do not repeat the question.
Do not say "As an AI".
Sound natural for TTS.
"""

    user_prompt = f"""
Hindi recognition:
{hindi_text if hindi_text else "No result"}

English recognition:
{english_text if english_text else "No result"}

Understand the intended question and answer naturally.
"""

    try:

        completion = (
            groq_client
            .chat
            .completions
            .create(
                model=AI_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": system_prompt
                    },
                    {
                        "role": "user",
                        "content": user_prompt
                    }
                ],
                temperature=0.2,
                max_completion_tokens=200
            )
        )

        result = (
            completion
            .choices[0]
            .message
            .content
        )

        result = clean_text(result)

        if not result:
            return "AI response nahi mil saka."

        return result

    except Exception as e:

        print(
            "GROQ ERROR:",
            repr(e)
        )

        return "AI response nahi mil saka."


# ============================================================
# SPEECH RECOGNITION
# ============================================================

def recognize(
    recognizer,
    audio,
    language
):

    try:

        text = recognizer.recognize_google(
            audio,
            language=language
        )

        text = clean_text(text)

        if valid_text(text):
            return text

    except sr.UnknownValueError:

        print(
            "Speech not understood:",
            language
        )

    except sr.RequestError as e:

        print(
            "Google Speech error:",
            language,
            e
        )

    except Exception as e:

        print(
            "Recognition error:",
            language,
            repr(e)
        )

    return None


# ============================================================
# TTS
# ============================================================

@app.route(
    "/tts",
    methods=["GET"]
)
def tts():

    text = clean_text(
        request.args.get(
            "text",
            ""
        )
    )

    lang = request.args.get(
        "lang",
        "en"
    )

    if not text:

        return jsonify({
            "status": "error",
            "message": "No text"
        }), 400

    if len(text) > 400:
        text = text[:400]

    if lang not in ["en", "hi"]:
        lang = "en"

    filename = None

    try:

        fd, filename = tempfile.mkstemp(
            suffix=".mp3"
        )

        os.close(fd)

        print(
            "TTS:",
            lang,
            text
        )

        engine = gTTS(
            text=text,
            lang=lang,
            slow=False
        )

        engine.save(filename)

        if not os.path.exists(filename):
            raise RuntimeError(
                "TTS file not created"
            )

        if os.path.getsize(filename) < 100:
            raise RuntimeError(
                "TTS file empty"
            )

        response = send_file(
            filename,
            mimetype="audio/mpeg",
            as_attachment=False,
            download_name="tts.mp3"
        )

        response.headers["Cache-Control"] = (
            "no-cache, no-store, must-revalidate"
        )

        response.headers["Pragma"] = "no-cache"

        response.headers["Content-Disposition"] = (
            "inline; filename=tts.mp3"
        )

        @response.call_on_close
        def cleanup():

            try:

                if filename and os.path.exists(filename):
                    os.remove(filename)

            except Exception as e:

                print(
                    "TTS cleanup:",
                    e
                )

        return response

    except Exception as e:

        print(
            "TTS ERROR:",
            repr(e)
        )

        if filename:

            try:
                if os.path.exists(filename):
                    os.remove(filename)
            except Exception:
                pass

        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


# ============================================================
# UPLOAD AUDIO
# ============================================================

@app.route(
    "/uploadAudio",
    methods=["POST"]
)
def upload_audio():

    filename = None

    started = time.time()

    try:

        print()
        print("================================")
        print("UPLOAD REQUEST RECEIVED")
        print("================================")

        audio_data = request.get_data(
            cache=False
        )

        size = len(audio_data)

        print(
            "Audio size:",
            size
        )

        if size < 1000:

            return jsonify({
                "status": "error",
                "message": "Audio too small",
                "transcription": None,
                "hindi_transcription": None,
                "english_transcription": None,
                "ai_reply": "Please ask your question again."
            }), 400

        # ----------------------------------------------------
        # Save WAV
        # ----------------------------------------------------

        fd, filename = tempfile.mkstemp(
            suffix=".wav"
        )

        os.close(fd)

        with open(
            filename,
            "wb"
        ) as f:

            f.write(audio_data)

        # ----------------------------------------------------
        # Validate WAV
        # ----------------------------------------------------

        with open(
            filename,
            "rb"
        ) as f:

            header = f.read(44)

        if (
            len(header) < 44
            or header[0:4] != b"RIFF"
            or header[8:12] != b"WAVE"
        ):

            return jsonify({
                "status": "error",
                "message": "Invalid WAV",
                "transcription": None,
                "hindi_transcription": None,
                "english_transcription": None,
                "ai_reply": "Invalid audio file."
            }), 400

        channels = int.from_bytes(
            header[22:24],
            "little"
        )

        sample_rate = int.from_bytes(
            header[24:28],
            "little"
        )

        bits = int.from_bytes(
            header[34:36],
            "little"
        )

        print(
            "WAV:",
            channels,
            "channel",
            sample_rate,
            "Hz",
            bits,
            "bit"
        )

        # ----------------------------------------------------
        # Read audio
        # ----------------------------------------------------

        recognizer = sr.Recognizer()

        recognizer.energy_threshold = 300

        recognizer.dynamic_energy_threshold = False

        with sr.AudioFile(filename) as source:

            audio = recognizer.record(source)

        # ----------------------------------------------------
        # Hindi
        # ----------------------------------------------------

        print(
            "Recognizing Hindi..."
        )

        hindi_text = recognize(
            recognizer,
            audio,
            "hi-IN"
        )

        # ----------------------------------------------------
        # English
        # ----------------------------------------------------

        print(
            "Recognizing English..."
        )

        english_text = recognize(
            recognizer,
            audio,
            "en-IN"
        )

        print(
            "Hindi:",
            hindi_text
        )

        print(
            "English:",
            english_text
        )

        # ----------------------------------------------------
        # Nothing recognized
        # ----------------------------------------------------

        if (
            not valid_text(hindi_text)
            and
            not valid_text(english_text)
        ):

            return jsonify({
                "status": "error",
                "message": "Speech not understood",
                "transcription": None,
                "hindi_transcription": hindi_text,
                "english_transcription": english_text,
                "ai_reply": "Please ask your question again."
            }), 400

        # ----------------------------------------------------
        # AI
        # ----------------------------------------------------

        print(
            "Calling Groq..."
        )

        ai_reply = get_ai_reply(
            hindi_text,
            english_text
        )

        ai_reply = clean_text(
            ai_reply
        )

        # ----------------------------------------------------
        # Best transcription
        # ----------------------------------------------------

        if valid_text(english_text):
            transcription = english_text
        else:
            transcription = hindi_text

        # ----------------------------------------------------
        # Language
        # ----------------------------------------------------

        reply_lang = detect_language(
            ai_reply,
            hindi_text,
            english_text
        )

        # ----------------------------------------------------
        # Response
        # ----------------------------------------------------

        response = {
            "status": "ok",
            "transcription": transcription,
            "hindi_transcription": hindi_text,
            "english_transcription": english_text,
            "ai_reply": ai_reply,
            "reply_lang": reply_lang
        }

        print(
            "FINAL:",
            response
        )

        print(
            "REQUEST TIME:",
            round(
                time.time() - started,
                2
            ),
            "seconds"
        )

        return jsonify(response)

    except Exception as e:

        print(
            "UPLOAD ERROR:",
            repr(e)
        )

        return jsonify({
            "status": "error",
            "message": str(e),
            "transcription": None,
            "hindi_transcription": None,
            "english_transcription": None,
            "ai_reply": "AI response nahi mil saka."
        }), 500

    finally:

        if filename:

            try:

                if os.path.exists(filename):
                    os.remove(filename)

            except Exception:
                pass


# ============================================================
# LOCAL RUN
# ============================================================

if __name__ == "__main__":

    port = int(
        os.environ.get(
            "PORT",
            10000
        )
    )

    print(
        "Starting ESP32 Voice Server..."
    )

    app.run(
        host="0.0.0.0",
        port=port,
        threaded=True
    )

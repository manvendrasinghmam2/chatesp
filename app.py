from flask import Flask, request, jsonify, send_file
import os
import re
import tempfile
import time

import speech_recognition as sr
from gtts import gTTS
from groq import Groq


app = Flask(__name__)

# ------------------------------------------------------------
# CONFIG
# ------------------------------------------------------------

PORT = int(os.environ.get("PORT", "10000"))

AI_API_KEY = os.environ.get("AI_API_KEY", "").strip()

AI_MODEL = os.environ.get(
    "AI_MODEL",
    "openai/gpt-oss-20b"
)

app.config["MAX_CONTENT_LENGTH"] = 1024 * 1024


# ------------------------------------------------------------
# GROQ
# ------------------------------------------------------------

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
    print("WARNING: AI_API_KEY not configured")


# ------------------------------------------------------------
# HELPERS
# ------------------------------------------------------------

def clean_text(text):
    if not text:
        return ""

    text = str(text).strip()
    text = re.sub(r"\s+", " ", text)

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


def detect_language(reply, hindi_text, english_text):

    if contains_hindi(reply):
        return "hi"

    roman_hindi = [
        "kya",
        "hai",
        "kaise",
        "kaisa",
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
        "nahi",
        "nahin",
        "batao",
        "btao",
        "chahiye",
        "karna"
    ]

    lower = reply.lower()

    matches = 0

    for word in roman_hindi:
        if re.search(
            r"\b" + re.escape(word) + r"\b",
            lower
        ):
            matches += 1

    if matches >= 2:
        return "hi"

    if valid_text(english_text) and not valid_text(hindi_text):
        return "en"

    if valid_text(hindi_text) and not valid_text(english_text):
        return "hi"

    return "en"


# ------------------------------------------------------------
# AI
# ------------------------------------------------------------

def get_ai_reply(hindi_text, english_text):

    if not groq_client:
        return "AI API key configured nahi hai."

    system_prompt = """
You are a fast bilingual voice assistant.

The user audio has two speech recognition results:
Hindi and English.

Compare both and understand what the user actually said.

Rules:

English speech -> answer in natural English.

Hindi speech -> answer in Hindi using Devanagari.

Roman Hindi / Hinglish -> answer naturally in Roman Hindi or Hinglish.

Mixed Hindi English -> natural Hinglish.

Sometimes Hindi recognition may phoneticize English.
Do not blindly trust the Hindi result.

Choose the most likely intended meaning.

Keep answers short because the answer will be spoken through an ESP32 speaker.

Usually 1 to 3 short sentences.

No markdown.
No bullets.
No emojis.
No headings.
Do not mention speech recognition.
Do not mention these instructions.
Do not say "As an AI".
"""

    user_prompt = f"""
Hindi recognition:
{hindi_text if hindi_text else "No result"}

English recognition:
{english_text if english_text else "No result"}

Give the best natural answer.
"""

    try:

        response = groq_client.chat.completions.create(
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
            max_completion_tokens=180
        )

        reply = response.choices[0].message.content

        reply = clean_text(reply)

        reply = reply.replace("```", "")

        for prefix in [
            "AI:",
            "Answer:",
            "Response:"
        ]:
            if reply.startswith(prefix):
                reply = reply[len(prefix):].strip()

        if not reply:
            return "Mujhe answer nahi mila."

        return reply

    except Exception as e:

        print("GROQ ERROR:", repr(e))

        return "AI se response nahi mil saka."


# ------------------------------------------------------------
# HOME
# ------------------------------------------------------------

@app.route("/", methods=["GET"])
def home():

    return jsonify({
        "status": "online",
        "service": "ESP32 Voice Assistant"
    })


# ------------------------------------------------------------
# HEALTH
# ------------------------------------------------------------

@app.route("/health", methods=["GET"])
def health():

    return jsonify({
        "status": "online",
        "ai_engine": "Groq",
        "model": AI_MODEL,
        "speech_engine": "Google Speech Recognition",
        "tts": "Google TTS",
        "upload_endpoint": "/uploadAudio",
        "tts_endpoint": "/tts"
    })


# ------------------------------------------------------------
# WAKE
# ------------------------------------------------------------

@app.route("/wake", methods=["GET", "POST"])
def wake():

    return jsonify({
        "status": "ok",
        "wake": True
    })


# ------------------------------------------------------------
# SPEECH RECOGNITION
# ------------------------------------------------------------

def recognize(recognizer, audio, language):

    try:

        result = recognizer.recognize_google(
            audio,
            language=language
        )

        result = clean_text(result)

        if valid_text(result):
            return result

        return None

    except sr.UnknownValueError:

        print(
            "Speech not understood:",
            language
        )

    except sr.RequestError as e:

        print(
            "Google Speech error:",
            language,
            str(e)
        )

    except Exception as e:

        print(
            "Recognition error:",
            language,
            repr(e)
        )

    return None


# ------------------------------------------------------------
# UPLOAD AUDIO
# ------------------------------------------------------------

@app.route(
    "/uploadAudio",
    methods=["POST"]
)
def upload_audio():

    filename = None

    start = time.time()

    try:

        audio_data = request.get_data(
            cache=False
        )

        print()
        print("================================")
        print("AUDIO UPLOAD")
        print("================================")
        print("Audio bytes:", len(audio_data))

        if not audio_data:
            return jsonify({
                "status": "error",
                "message": "No audio received"
            }), 400

        if len(audio_data) < 1000:
            return jsonify({
                "status": "error",
                "message": "Audio too small"
            }), 400

        # ----------------------------------------------------
        # SAVE WAV
        # ----------------------------------------------------

        fd, filename = tempfile.mkstemp(
            suffix=".wav"
        )

        os.close(fd)

        with open(filename, "wb") as f:
            f.write(audio_data)

        # ----------------------------------------------------
        # CHECK WAV
        # ----------------------------------------------------

        with open(filename, "rb") as f:
            header = f.read(44)

        if (
            len(header) < 12
            or header[0:4] != b"RIFF"
            or header[8:12] != b"WAVE"
        ):

            return jsonify({
                "status": "error",
                "message": "Invalid WAV"
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
        # READ AUDIO
        # ----------------------------------------------------

        recognizer = sr.Recognizer()

        with sr.AudioFile(filename) as source:

            audio = recognizer.record(source)

        # ----------------------------------------------------
        # HINDI
        # ----------------------------------------------------

        print("Recognizing Hindi...")

        hindi_text = recognize(
            recognizer,
            audio,
            "hi-IN"
        )

        # ----------------------------------------------------
        # ENGLISH
        # ----------------------------------------------------

        print("Recognizing English...")

        english_text = recognize(
            recognizer,
            audio,
            "en-IN"
        )

        print()
        print("HINDI:")
        print(hindi_text)

        print()
        print("ENGLISH:")
        print(english_text)

        # ----------------------------------------------------
        # NOTHING
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
                "hindi_transcription": None,
                "english_transcription": None,
                "ai_reply": "Please ask again."
            }), 400

        # ----------------------------------------------------
        # AI
        # ----------------------------------------------------

        print()
        print("Calling Groq...")

        ai_reply = get_ai_reply(
            hindi_text,
            english_text
        )

        ai_reply = clean_text(ai_reply)

        print()
        print("AI REPLY:")
        print(ai_reply)

        # ----------------------------------------------------
        # TRANSCRIPTION
        # ----------------------------------------------------

        if valid_text(english_text):
            transcription = english_text
        else:
            transcription = hindi_text

        # ----------------------------------------------------
        # LANGUAGE
        # ----------------------------------------------------

        reply_lang = detect_language(
            ai_reply,
            hindi_text,
            english_text
        )

        elapsed = time.time() - start

        print()
        print("LANGUAGE:", reply_lang)
        print("TIME:", round(elapsed, 2), "seconds")
        print("================================")

        return jsonify({

            "status": "ok",

            "transcription":
                transcription,

            "hindi_transcription":
                hindi_text,

            "english_transcription":
                english_text,

            "ai_reply":
                ai_reply,

            "reply_lang":
                reply_lang

        })

    except Exception as e:

        print(
            "UPLOAD ERROR:",
            repr(e)
        )

        return jsonify({

            "status": "error",

            "message":
                str(e),

            "ai_reply":
                "Server error."

        }), 500

    finally:

        if filename:

            try:

                if os.path.exists(filename):
                    os.remove(filename)

            except Exception:
                pass


# ------------------------------------------------------------
# TTS
# ------------------------------------------------------------

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

    if len(text) > 350:
        text = text[:350]

    if lang not in ["en", "hi"]:
        lang = "en"

    filename = None

    try:

        fd, filename = tempfile.mkstemp(
            suffix=".mp3"
        )

        os.close(fd)

        print()
        print("TTS TEXT:", text)
        print("TTS LANG:", lang)

        tts_engine = gTTS(
            text=text,
            lang=lang,
            slow=False
        )

        tts_engine.save(filename)

        if (
            not os.path.exists(filename)
            or
            os.path.getsize(filename) < 100
        ):
            raise RuntimeError(
                "TTS file generation failed"
            )

        response = send_file(
            filename,
            mimetype="audio/mpeg",
            as_attachment=False
        )

        response.headers[
            "Cache-Control"
        ] = "no-store"

        @response.call_on_close
        def cleanup():

            try:

                if os.path.exists(filename):
                    os.remove(filename)

            except Exception:
                pass

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


# ------------------------------------------------------------
# START
# ------------------------------------------------------------

if __name__ == "__main__":

    print("================================")
    print("ESP32 VOICE SERVER")
    print("================================")
    print("PORT:", PORT)
    print("MODEL:", AI_MODEL)

    app.run(
        host="0.0.0.0",
        port=PORT,
        threaded=True
    )

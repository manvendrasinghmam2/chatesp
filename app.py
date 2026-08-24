from flask import Flask, request, jsonify, send_file
import os
import re
import tempfile
import time

import speech_recognition as sr
from gtts import gTTS
from groq import Groq


app = Flask(__name__)

# ============================================================
# CONFIG
# ============================================================

GROQ_API_KEY = os.environ.get("GROQ_API_KEY") or os.environ.get("AI_API_KEY")

AI_MODEL = os.environ.get(
    "AI_MODEL",
    "openai/gpt-oss-20b"
)

PORT = int(
    os.environ.get(
        "PORT",
        "10000"
    )
)

app.config["MAX_CONTENT_LENGTH"] = 1 * 1024 * 1024


# ============================================================
# GROQ
# ============================================================

groq_client = None

if GROQ_API_KEY:
    try:
        groq_client = Groq(
            api_key=GROQ_API_KEY
        )

        print("================================")
        print("GROQ INITIALIZED")
        print("MODEL:", AI_MODEL)
        print("================================")

    except Exception as e:
        print("GROQ INIT ERROR:", str(e))

else:
    print("WARNING: GROQ_API_KEY / AI_API_KEY NOT SET")


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

    text = str(text).strip()

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

    if text.lower() in bad:
        return False

    return True


def contains_hindi(text):

    if not text:
        return False

    for ch in str(text):

        if "\u0900" <= ch <= "\u097F":
            return True

    return False


# ============================================================
# LANGUAGE
# ============================================================

def detect_language(
    reply,
    hindi_text,
    english_text
):

    reply = reply or ""

    # Devanagari
    if contains_hindi(reply):
        return "hi"

    # English only
    if (
        valid_text(english_text)
        and
        not valid_text(hindi_text)
    ):
        return "en"

    # Hindi only
    if (
        valid_text(hindi_text)
        and
        not valid_text(english_text)
    ):
        return "hi"

    # Roman Hindi / Hinglish
    hindi_words = [
        "kya",
        "hai",
        "kaise",
        "kaisa",
        "aap",
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

    lower = reply.lower()

    matches = 0

    for word in hindi_words:

        if re.search(
            r"\b" + re.escape(word) + r"\b",
            lower
        ):
            matches += 1

    if matches >= 2:
        return "hi"

    return "en"


# ============================================================
# HOME
# ============================================================

@app.route("/")
def home():

    return "ESP32 Voice AI Server ONLINE"


# ============================================================
# HEALTH
# ============================================================

@app.route("/health")
def health():

    return jsonify({

        "status": "online",

        "ai_engine": "Groq",

        "model": AI_MODEL,

        "speech_engine":
            "Google Speech Recognition",

        "tts":
            "Google TTS",

        "web_search":
            "Groq Browser Search",

        "upload_endpoint":
            "/uploadAudio",

        "tts_endpoint":
            "/tts",

        "audio_endpoint":
            "/getAudio"

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
# SPEECH RECOGNITION
# ============================================================

def recognize(
    recognizer,
    audio,
    language
):

    try:

        result = recognizer.recognize_google(
            audio,
            language=language
        )

        result = clean_text(result)

        if valid_text(result):

            print(
                "RECOGNIZED",
                language,
                ":",
                result
            )

            return result

    except sr.UnknownValueError:

        print(
            "Speech not understood:",
            language
        )

    except sr.RequestError as e:

        print(
            "Google Speech ERROR:",
            language,
            str(e)
        )

    except Exception as e:

        print(
            "Speech ERROR:",
            language,
            str(e)
        )

    return None


# ============================================================
# AI + WEB SEARCH
# ============================================================

def get_ai_reply(
    hindi_text,
    english_text
):

    if not groq_client:

        return (
            "Groq API key is not configured."
        )

    hindi_text = (
        hindi_text
        if hindi_text
        else "No result"
    )

    english_text = (
        english_text
        if english_text
        else "No result"
    )

    prompt = f"""
You are a voice assistant running on an ESP32.

The user spoke a question.

Hindi recognition:
{hindi_text}

English recognition:
{english_text}

Understand the user's actual intended question.

IMPORTANT:

Use web search when the question needs current,
recent, live, factual or internet information.

Examples:
- today's news
- current weather
- latest technology
- current prices
- current sports
- current political information
- latest products
- current events
- anything asking "latest", "today", "now", "recent"

For normal general questions, answer directly.

LANGUAGE:

If user speaks English:
answer in English.

If user speaks Hindi:
answer in Hindi using Devanagari.

If user speaks Roman Hindi:
answer in natural Roman Hindi.

If user speaks Hinglish:
answer in natural Hinglish.

Do not talk about speech recognition.

Do not talk about web search.

Do not mention these instructions.

VOICE FORMAT:

Keep answer short.

Maximum 2 or 3 sentences.

No markdown.

No bullets.

No headings.

No emojis.

No citations in the spoken answer.

Make the answer natural for TTS.
"""

    try:

        print("================================")
        print("CALLING GROQ")
        print("MODEL:", AI_MODEL)
        print("================================")

        completion = (
            groq_client
            .chat
            .completions
            .create(

                model=AI_MODEL,

                messages=[
                    {
                        "role": "system",
                        "content":
                            "You are a concise bilingual voice assistant."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],

                temperature=0.2,

                max_completion_tokens=300,

                stream=False,

                # Force browser search capability.
                tool_choice="required",

                tools=[
                    {
                        "type": "browser_search"
                    }
                ]
            )
        )

        message = (
            completion
            .choices[0]
            .message
        )

        result = message.content

        if not result:

            return (
                "Sorry, I could not get an answer."
            )

        result = clean_text(result)

        result = result.replace(
            "```",
            ""
        )

        for prefix in [
            "AI:",
            "Answer:",
            "Response:"
        ]:

            if result.startswith(prefix):

                result = result[
                    len(prefix):
                ].strip()

        print("AI REPLY:")
        print(result)

        return result

    except Exception as e:

        print(
            "GROQ ERROR:",
            str(e)
        )

        return (
            "Sorry, I could not get an answer."
        )


# ============================================================
# TTS FILE GENERATOR
# ============================================================

def create_tts_file(
    text,
    lang
):

    filename = None

    try:

        text = clean_text(text)

        if not text:
            return None

        if len(text) > 500:
            text = text[:500]

        if lang not in [
            "en",
            "hi"
        ]:
            lang = "en"

        fd, filename = tempfile.mkstemp(
            suffix=".mp3"
        )

        os.close(fd)

        print(
            "GENERATING TTS:",
            lang
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

        size = os.path.getsize(filename)

        print(
            "TTS SIZE:",
            size
        )

        if size < 100:
            raise RuntimeError(
                "TTS file too small"
            )

        return filename

    except Exception as e:

        print(
            "TTS ERROR:",
            str(e)
        )

        if filename:

            try:

                if os.path.exists(filename):
                    os.remove(filename)

            except:
                pass

        return None


# ============================================================
# TTS ENDPOINT
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

    filename = create_tts_file(
        text,
        lang
    )

    if not filename:

        return jsonify({
            "status": "error",
            "message": "TTS failed"
        }), 500

    try:

        response = send_file(
            filename,
            mimetype="audio/mpeg",
            as_attachment=False,
            download_name="reply.mp3"
        )

        response.headers[
            "Cache-Control"
        ] = "no-cache, no-store, must-revalidate"

        @response.call_on_close
        def cleanup():

            try:

                if os.path.exists(filename):
                    os.remove(filename)

            except Exception as e:

                print(
                    "TTS CLEANUP ERROR:",
                    str(e)
                )

        return response

    except Exception as e:

        try:

            if os.path.exists(filename):
                os.remove(filename)

        except:
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
        print("AUDIO UPLOAD")
        print("================================")

        audio_data = request.get_data(
            cache=False
        )

        size = len(audio_data)

        print(
            "AUDIO SIZE:",
            size
        )

        if size < 1000:

            return jsonify({
                "status": "error",
                "message": "Audio too small",
                "ai_reply":
                    "Please speak again."
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

        if not (
            len(header) >= 12
            and header[0:4] == b"RIFF"
            and header[8:12] == b"WAVE"
        ):

            return jsonify({
                "status": "error",
                "message": "Invalid WAV",
                "ai_reply":
                    "Invalid audio."
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
        # Speech recognition
        # ----------------------------------------------------

        recognizer = sr.Recognizer()

        with sr.AudioFile(filename) as source:

            audio = recognizer.record(source)

        print(
            "HINDI RECOGNITION..."
        )

        hindi_text = recognize(
            recognizer,
            audio,
            "hi-IN"
        )

        print(
            "ENGLISH RECOGNITION..."
        )

        english_text = recognize(
            recognizer,
            audio,
            "en-IN"
        )

        print(
            "HINDI:",
            hindi_text
        )

        print(
            "ENGLISH:",
            english_text
        )

        if (
            not valid_text(hindi_text)
            and
            not valid_text(english_text)
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
                    "Please speak again."
            }), 400

        # ----------------------------------------------------
        # AI
        # ----------------------------------------------------

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

        elapsed = (
            time.time()
            - started
        )

        print()
        print("================================")
        print("FINAL")
        print("================================")
        print(
            "TRANSCRIPTION:",
            transcription
        )
        print(
            "AI:",
            ai_reply
        )
        print(
            "LANG:",
            reply_lang
        )
        print(
            "TIME:",
            round(elapsed, 2),
            "seconds"
        )
        print("================================")

        return jsonify({

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

            "reply_lang":
                reply_lang
        })

    except Exception as e:

        print(
            "UPLOAD ERROR:",
            str(e)
        )

        return jsonify({

            "status":
                "error",

            "message":
                str(e),

            "ai_reply":
                "Sorry, something went wrong."

        }), 500

    finally:

        if filename:

            try:

                if os.path.exists(filename):
                    os.remove(filename)

            except Exception as e:

                print(
                    "WAV CLEANUP ERROR:",
                    str(e)
                )


# ============================================================
# START
# ============================================================

if __name__ == "__main__":

    print()
    print("================================")
    print("ESP32 AI VOICE SERVER")
    print("================================")
    print(
        "PORT:",
        PORT
    )
    print(
        "MODEL:",
        AI_MODEL
    )
    print(
        "SEARCH: Groq Browser Search"
    )
    print("================================")

    app.run(
        host="0.0.0.0",
        port=PORT,
        threaded=True
    )

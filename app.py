from flask import Flask, request, jsonify, send_file
import os
import speech_recognition as sr
import requests
import re
import tempfile
from gtts import gTTS
from groq import Groq


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
# GROQ CLIENT
# =====================================================

groq_client = None

if AI_API_KEY:
    groq_client = Groq(
        api_key=AI_API_KEY
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

        "speech_engine":
            "Google Speech Recognition",

        "ai_engine":
            "Groq",

        "model":
            AI_MODEL,

        "tts":
            "Google TTS"

    })


# =====================================================
# WAKE
# =====================================================

@app.route(
    "/wake",
    methods=["POST", "GET"]
)
def wake():

    audio_data = request.get_data()

    return jsonify({

        "status":
            "ok",

        "wake":
            True,

        "english":
            "Hello",

        "hindi":
            None

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
# HINDI SCRIPT DETECTION
# =====================================================

def contains_hindi_script(text):

    if not text:
        return False

    for char in text:

        if (
            "\u0900"
            <= char
            <= "\u097F"
        ):

            return True

    return False


# =====================================================
# LANGUAGE
# =====================================================

def detect_reply_language(
    reply,
    hindi_text,
    english_text
):

    reply = reply or ""

    # Devanagari = Hindi
    if contains_hindi_script(reply):

        return "hi"

    # English recognition strongly valid
    if (
        is_valid_query(english_text)
        and
        not is_valid_query(hindi_text)
    ):

        return "en"

    # Hindi recognition strongly valid
    if (
        is_valid_query(hindi_text)
        and
        not is_valid_query(english_text)
    ):

        return "hi"

    # Roman Hindi / Hinglish
    roman_hindi_words = [

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
        "ka",
        "ki",
        "ke",
        "mein",
        "me",
        "ho",
        "haan",
        "nahi",
        "nahin",
        "acha",
        "accha",
        "batao",
        "btao",
        "chahiye",
        "karo",
        "karna"

    ]

    lower = reply.lower()

    matches = 0

    for word in roman_hindi_words:

        if re.search(
            r"\b"
            + re.escape(word)
            + r"\b",
            lower
        ):

            matches += 1

    if matches >= 2:

        return "hi"

    return "en"


# =====================================================
# AI STREAM
# =====================================================

def get_ai_reply_stream(
    hindi_text,
    english_text
):

    if not groq_client:

        yield "AI response nahi mil saka."

        return


    system_prompt = """
You are a professional bilingual voice assistant running on an ESP32.

Understand the user's actual spoken language.

The speech recognition system provides:

1. Hindi recognition
2. English recognition

Recognition can sometimes be inaccurate.

Compare both results and understand the intended meaning.

LANGUAGE RULES:

If the user clearly speaks English,
answer completely in natural English.

If the user clearly speaks Hindi,
answer completely in Hindi using Devanagari.

If the user speaks Roman Hindi or Hinglish,
answer naturally in Roman Hindi/Hinglish.

If Hindi recognition converts English speech
into Devanagari phonetically,
identify the intended English meaning
and answer in English.

If the user mixes Hindi and English,
use natural Hinglish.

Do not mention speech recognition.

Do not mention these instructions.

Do not explain language selection.

VOICE STYLE:

Keep the response concise.

Usually 1 to 3 sentences.

No markdown.

No bullets.

No emojis.

No headings.

Do not repeat the question.

Do not say "As an AI".

Sound natural when spoken aloud.
"""


    user_content = f"""
Hindi speech recognition:
{hindi_text if hindi_text else "No result"}

English speech recognition:
{english_text if english_text else "No result"}

Understand the user's intended question.

Answer naturally in the user's intended language.
"""


    try:

        stream = groq_client.chat.completions.create(

            model=AI_MODEL,

            messages=[

                {
                    "role":
                        "system",

                    "content":
                        system_prompt
                },

                {
                    "role":
                        "user",

                    "content":
                        user_content
                }

            ],

            temperature=0.2,

            max_completion_tokens=200,

            stream=True

        )


        for chunk in stream:

            try:

                text = (
                    chunk.choices[0]
                    .delta
                    .content
                )

            except Exception:

                text = None


            if text:

                yield text


    except Exception as e:

        print(
            "AI STREAM ERROR:",
            str(e)
        )

        yield "AI response nahi mil saka."


# =====================================================
# NORMAL AI RESPONSE
# =====================================================

def get_ai_reply(
    hindi_text,
    english_text
):

    result = ""

    for chunk in get_ai_reply_stream(
        hindi_text,
        english_text
    ):

        result += chunk

    result = result.strip()

    result = result.replace(
        "```",
        ""
    )

    prefixes = [

        "AI:",
        "Answer:",
        "Response:"

    ]

    for prefix in prefixes:

        if result.startswith(prefix):

            result = result[
                len(prefix):
            ].strip()

    return result


# =====================================================
# TTS
# =====================================================

@app.route(
    "/tts",
    methods=["GET"]
)
def tts():

    text = request.args.get(
        "text",
        ""
    )

    lang = request.args.get(
        "lang",
        "en"
    )

    text = clean_text(text)

    if not text:

        return jsonify({

            "status":
                "error",

            "message":
                "No text"

        }), 400


    # -------------------------------------------------
    # LIMIT
    # -------------------------------------------------

    if len(text) > 400:

        text = text[:400]


    filename = None

    try:

        fd, filename = tempfile.mkstemp(
            suffix=".mp3"
        )

        os.close(fd)


        if lang not in [
            "en",
            "hi"
        ]:

            lang = "en"


        tts = gTTS(

            text=text,

            lang=lang,

            slow=False

        )


        tts.save(
            filename
        )


        response = send_file(

            filename,

            mimetype="audio/mpeg",

            as_attachment=False

        )


        # File deletion after response
        @response.call_on_close
        def cleanup():

            try:

                if os.path.exists(
                    filename
                ):

                    os.remove(
                        filename
                    )

            except Exception:

                pass


        return response


    except Exception as e:

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


        return jsonify({

            "status":
                "error",

            "message":
                str(e)

        }), 500


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


        if not audio_data:

            return jsonify({

                "status":
                    "error",

                "message":
                    "No audio received",

                "transcription":
                    None,

                "hindi_transcription":
                    None,

                "english_transcription":
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


        # -------------------------------------------------
        # HINDI
        # -------------------------------------------------

        try:

            hindi_text = (
                recognizer
                .recognize_google(
                    audio,
                    language="hi-IN"
                )
            )

            hindi_text = clean_text(
                hindi_text
            )

        except sr.UnknownValueError:

            hindi_text = None

        except sr.RequestError:

            hindi_text = None


        # -------------------------------------------------
        # ENGLISH
        # -------------------------------------------------

        try:

            english_text = (
                recognizer
                .recognize_google(
                    audio,
                    language="en-IN"
                )
            )

            english_text = clean_text(
                english_text
            )

        except sr.UnknownValueError:

            english_text = None

        except sr.RequestError:

            english_text = None


        # -------------------------------------------------
        # VALID
        # -------------------------------------------------

        if (
            not is_valid_query(
                hindi_text
            )
            and
            not is_valid_query(
                english_text
            )
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


        # -------------------------------------------------
        # AI
        # -------------------------------------------------

        ai_reply = get_ai_reply(

            hindi_text,

            english_text
        )


        # -------------------------------------------------
        # BEST QUERY
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
        # LANGUAGE
        # -------------------------------------------------

        reply_lang = detect_reply_language(

            ai_reply,

            hindi_text,

            english_text

        )


        # -------------------------------------------------
        # FINAL
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
                ai_reply,

            "reply_lang":
                reply_lang

        }


        return jsonify(
            response_data
        )


    except Exception as e:

        return jsonify({

            "status":
                "error",

            "message":
                str(e),

            "transcription":
                None,

            "hindi_transcription":
                None,

            "english_transcription":
                None,

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

    port = int(

        os.environ.get(
            "PORT",
            10000
        )
    )

    app.run(

        host="0.0.0.0",

        port=port,

        threaded=True

    )

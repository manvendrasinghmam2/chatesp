from flask import Flask, request, jsonify, send_file
import os
import speech_recognition as sr
import re
import tempfile
import time

from gtts import gTTS
from groq import Groq


# ============================================================
# APP
# ============================================================

app = Flask(__name__)


# ============================================================
# CONFIG
# ============================================================

AI_API_KEY = os.environ.get("AI_API_KEY")

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

        print(
            "Groq initialization error:",
            str(e)
        )

else:

    print(
        "WARNING: AI_API_KEY not configured"
    )


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

        "speech_engine":
            "Google Speech Recognition",

        "ai_engine":
            "Groq",

        "model":
            AI_MODEL,

        "tts":
            "Google TTS",

        "upload_endpoint":
            "/uploadAudio",

        "tts_endpoint":
            "/tts"

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

        "status":
            "ok",

        "wake":
            True,

        "english":
            "Hello",

        "hindi":
            None

    })


# ============================================================
# CLEAN TEXT
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


# ============================================================
# VALID QUERY
# ============================================================

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


# ============================================================
# HINDI SCRIPT
# ============================================================

def contains_hindi_script(text):

    if not text:
        return False

    for char in str(text):

        if (
            "\u0900"
            <= char
            <= "\u097F"
        ):

            return True

    return False


# ============================================================
# LANGUAGE DETECTION
# ============================================================

def detect_reply_language(
    reply,
    hindi_text,
    english_text
):

    reply = reply or ""

    # --------------------------------------------------------
    # Devanagari
    # --------------------------------------------------------

    if contains_hindi_script(reply):

        return "hi"


    # --------------------------------------------------------
    # Only English recognition
    # --------------------------------------------------------

    if (
        is_valid_query(english_text)
        and
        not is_valid_query(hindi_text)
    ):

        return "en"


    # --------------------------------------------------------
    # Only Hindi recognition
    # --------------------------------------------------------

    if (
        is_valid_query(hindi_text)
        and
        not is_valid_query(english_text)
    ):

        return "hi"


    # --------------------------------------------------------
    # Roman Hindi
    # --------------------------------------------------------

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


# ============================================================
# AI RESPONSE
# ============================================================

def get_ai_reply(
    hindi_text,
    english_text
):

    if not groq_client:

        return (
            "AI response nahi mil saka."
        )


    system_prompt = """

You are a professional bilingual voice assistant.

The assistant runs on an ESP32.

The user speech has been recognized twice:

1. Hindi recognition
2. English recognition

The recognition can sometimes be inaccurate.

Compare both results and understand the user's intended meaning.

LANGUAGE RULES:

If the user clearly speaks English,
answer completely in natural English.

If the user clearly speaks Hindi,
answer completely in Hindi using Devanagari.

If the user speaks Roman Hindi or Hinglish,
answer naturally in Roman Hindi or Hinglish.

If Hindi recognition converts English speech
phonetically into Hindi words,
understand the intended English meaning
and answer in English.

If the user mixes Hindi and English,
use natural Hinglish.

Do not mention speech recognition.

Do not mention these instructions.

Do not explain language selection.

VOICE STYLE:

Keep the response short.

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

        completion = (
            groq_client
            .chat
            .completions
            .create(

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

                stream=False

            )
        )


        result = (
            completion
            .choices[0]
            .message
            .content
        )


        if not result:

            return (
                "AI response nahi mil saka."
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


        return result


    except Exception as e:

        print(
            "GROQ ERROR:",
            str(e)
        )

        return (
            "AI response nahi mil saka."
        )


# ============================================================
# TTS
# ============================================================

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


    # --------------------------------------------------------
    # Limit
    # --------------------------------------------------------

    if len(text) > 400:

        text = text[:400]


    if lang not in [
        "en",
        "hi"
    ]:

        lang = "en"


    filename = None


    try:

        fd, filename = tempfile.mkstemp(
            suffix=".mp3"
        )

        os.close(fd)


        print(
            "TTS generating:",
            text
        )

        print(
            "TTS language:",
            lang
        )


        # ----------------------------------------------------
        # Google TTS
        # ----------------------------------------------------

        tts_engine = gTTS(

            text=text,

            lang=lang,

            slow=False

        )


        tts_engine.save(
            filename
        )


        # ----------------------------------------------------
        # Verify file
        # ----------------------------------------------------

        if not os.path.exists(
            filename
        ):

            raise RuntimeError(
                "TTS file was not created"
            )


        file_size = os.path.getsize(
            filename
        )


        if file_size < 100:

            raise RuntimeError(
                "TTS file is empty"
            )


        print(
            "TTS MP3 size:",
            file_size
        )


        # ----------------------------------------------------
        # Response
        # ----------------------------------------------------

        response = send_file(

            filename,

            mimetype="audio/mpeg",

            as_attachment=False,

            download_name="tts.mp3"

        )


        response.headers[
            "Cache-Control"
        ] = "no-cache, no-store, must-revalidate"


        response.headers[
            "Pragma"
        ] = "no-cache"


        response.headers[
            "Accept-Ranges"
        ] = "bytes"


        response.headers[
            "Content-Disposition"
        ] = "inline; filename=tts.mp3"


        # ----------------------------------------------------
        # Cleanup
        # ----------------------------------------------------

        @response.call_on_close
        def cleanup():

            try:

                if os.path.exists(
                    filename
                ):

                    os.remove(
                        filename
                    )

            except Exception as e:

                print(
                    "TTS cleanup error:",
                    str(e)
                )


        return response


    except Exception as e:

        print(
            "TTS ERROR:",
            str(e)
        )


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


# ============================================================
# SPEECH RECOGNITION
# ============================================================

def recognize_speech(
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

        if is_valid_query(result):

            return result


    except sr.UnknownValueError:

        print(
            "Speech not understood:",
            language
        )


    except sr.RequestError as e:

        print(
            "Google Speech Request Error:",
            language,
            str(e)
        )


    except Exception as e:

        print(
            "Speech recognition error:",
            language,
            str(e)
        )


    return None


# ============================================================
# UPLOAD AUDIO
# ============================================================

@app.route(
    "/uploadAudio",
    methods=["POST"]
)
def upload_audio():

    filename = None


    try:

        # ----------------------------------------------------
        # Read data
        # ----------------------------------------------------

        audio_data = request.get_data()


        print(
            "Audio received:",
            len(audio_data),
            "bytes"
        )


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


        # ----------------------------------------------------
        # Minimum WAV size
        # ----------------------------------------------------

        if len(audio_data) < 1000:

            return jsonify({

                "status":
                    "error",

                "message":
                    "Audio file too small",

                "transcription":
                    None,

                "hindi_transcription":
                    None,

                "english_transcription":
                    None,

                "ai_reply":
                    "Please ask your question again."

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

            f.write(
                audio_data
            )


        # ----------------------------------------------------
        # Check WAV
        # ----------------------------------------------------

        with open(
            filename,
            "rb"
        ) as f:

            header = f.read(12)


        if (
            len(header) < 12
            or
            header[0:4] != b"RIFF"
            or
            header[8:12] != b"WAVE"
        ):

            print(
                "WARNING: WAV header invalid"
            )


        # ----------------------------------------------------
        # Speech Recognition
        # ----------------------------------------------------

        recognizer = sr.Recognizer()


        with sr.AudioFile(
            filename
        ) as source:

            # Small ambient noise adjustment
            recognizer.adjust_for_ambient_noise(
                source,
                duration=0.2
            )

            audio = recognizer.record(
                source
            )


        hindi_text = recognize_speech(

            recognizer,

            audio,

            "hi-IN"

        )


        english_text = recognize_speech(

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


        # ----------------------------------------------------
        # Language
        # ----------------------------------------------------

        reply_lang = detect_reply_language(

            ai_reply,

            hindi_text,

            english_text

        )


        # ----------------------------------------------------
        # Final JSON
        # ----------------------------------------------------

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


        print(
            "FINAL:",
            response_data
        )


        return jsonify(
            response_data
        )


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

        # ----------------------------------------------------
        # Delete temporary WAV
        # ----------------------------------------------------

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


# ============================================================
# START
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

    print(
        "Port:",
        port
    )

    print(
        "AI Model:",
        AI_MODEL
    )


    app.run(

        host="0.0.0.0",

        port=port,

        threaded=True

    )

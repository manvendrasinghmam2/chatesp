from flask import Flask, request, jsonify, send_file
import os
import speech_recognition as sr
import requests
import re
import tempfile
import subprocess
import uuid
import threading
import time


app = Flask(__name__)


# =====================================================
# CONFIGURATION
# =====================================================

AI_API_KEY = os.environ.get(
    "AI_API_KEY"
)

AI_URL = os.environ.get(
    "AI_URL",
    "https://api.groq.com/openai/v1/chat/completions"
)

AI_MODEL = os.environ.get(
    "AI_MODEL",
    "openai/gpt-oss-20b"
)


# =====================================================
# TTS CONFIGURATION
# =====================================================

TTS_DIR = "tts_audio"

TTS_MODEL_DIR = "tts_models"

os.makedirs(
    TTS_DIR,
    exist_ok=True
)

os.makedirs(
    TTS_MODEL_DIR,
    exist_ok=True
)

# English Piper voice
EN_TTS_MODEL = "en_US-lessac-medium"

# Hindi Piper voice
HI_TTS_MODEL = "hi_IN-priyamvada-medium"


# =====================================================
# HOME
# =====================================================

@app.route(
    "/",
    methods=["GET"]
)
def home():

    return "ESP32 Voice Server is ONLINE!"


# =====================================================
# HEALTH
# =====================================================

@app.route(
    "/health",
    methods=["GET"]
)
def health():

    return jsonify({

        "status":
            "online",

        "speech_engine":
            "Google Speech Recognition",

        "ai_engine":
            "Groq",

        "model":
            AI_MODEL,

        "tts_engine":
            "Piper TTS",

        "english_tts":
            EN_TTS_MODEL,

        "hindi_tts":
            HI_TTS_MODEL

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
    print("WAKE REQUEST RECEIVED")
    print("==============================")

    print(
        "METHOD:",
        request.method
    )

    print(
        "CONTENT TYPE:",
        request.content_type
    )

    print(
        "CONTENT LENGTH:",
        request.content_length
    )

    if request.method == "POST":

        audio_data = request.get_data()

        print(
            "AUDIO BYTES:",
            len(audio_data)
        )

    print("==============================")

    response_data = {

        "status":
            "ok",

        "wake":
            True,

        "english":
            "Hello",

        "hindi":
            None
    }

    print(
        "WAKE RESPONSE:"
    )

    print(
        response_data
    )

    print("==============================")

    return jsonify(
        response_data
    )


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

            "status":
                "error",

            "message":
                "No JSON received"

        }), 400

    print()
    print("==============================")
    print("TEST DATA")
    print("==============================")

    print(
        data
    )

    print("==============================")

    return jsonify({

        "status":
            "ok",

        "message":
            "Data received",

        "data":
            data

    })


# =====================================================
# CLEAN TEXT
# =====================================================

def clean_text(text):

    if not text:
        return ""

    text = str(
        text
    ).strip()

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

    text = str(
        text
    ).strip()

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
# DETECT HINDI SCRIPT
# =====================================================

def contains_devanagari(text):

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
# DOWNLOAD PIPER VOICES
# =====================================================

def download_tts_models():

    print()
    print("==============================")
    print("CHECKING PIPER VOICES")
    print("==============================")


    models = [

        EN_TTS_MODEL,
        HI_TTS_MODEL

    ]


    for model in models:

        print()
        print(
            "Checking:",
            model
        )

        try:

            command = [

                "python",
                "-m",
                "piper.download_voices",

                model,

                "--data-dir",
                TTS_MODEL_DIR

            ]

            result = subprocess.run(

                command,

                capture_output=True,

                text=True,

                timeout=300

            )


            if result.returncode != 0:

                print(
                    "VOICE DOWNLOAD ERROR:"
                )

                print(
                    result.stderr
                )

            else:

                print(
                    "VOICE READY:",
                    model
                )

        except Exception as e:

            print(
                "VOICE ERROR:",
                type(e).__name__,
                str(e)
            )


    print("==============================")


# =====================================================
# GENERATE TTS
# =====================================================

def generate_tts(text):

    text = clean_text(
        text
    )

    if not text:

        print(
            "TTS: Empty text"
        )

        return None


    # -------------------------------------------------
    # CHOOSE VOICE
    # -------------------------------------------------

    if contains_devanagari(
        text
    ):

        model = HI_TTS_MODEL

        print(
            "TTS LANGUAGE: Hindi"
        )

    else:

        model = EN_TTS_MODEL

        print(
            "TTS LANGUAGE: English/Hinglish"
        )


    # -------------------------------------------------
    # FILE
    # -------------------------------------------------

    filename = os.path.join(

        TTS_DIR,

        "response_" +
        uuid.uuid4().hex +
        ".wav"

    )


    print()
    print("==============================")
    print("TEXT TO SPEECH")
    print("==============================")

    print(
        "TEXT:",
        text
    )

    print(
        "MODEL:",
        model
    )

    print(
        "OUTPUT:",
        filename
    )


    try:

        command = [

            "python",
            "-m",
            "piper",

            "--model",
            model,

            "--data-dir",
            TTS_MODEL_DIR,

            "--output_file",
            filename

        ]


        result = subprocess.run(

            command,

            input=text,

            text=True,

            capture_output=True,

            timeout=120

        )


        if result.returncode != 0:

            print()
            print(
                "PIPER ERROR"
            )

            print(
                result.stderr
            )

            return None


        if not os.path.exists(
            filename
        ):

            print(
                "TTS FILE NOT CREATED"
            )

            return None


        size = os.path.getsize(
            filename
        )


        if size < 100:

            print(
                "TTS FILE TOO SMALL"
            )

            return None


        print(
            "TTS CREATED:",
            size,
            "bytes"
        )

        print("==============================")


        return filename


    except subprocess.TimeoutExpired:

        print(
            "PIPER TIMEOUT"
        )

        return None


    except Exception as e:

        print()
        print(
            "PIPER EXCEPTION"
        )

        print(
            type(e).__name__
        )

        print(
            str(e)
        )

        return None


# =====================================================
# AUDIO FILE
# =====================================================

@app.route(
    "/audio/<filename>",
    methods=["GET"]
)
def audio_file(filename):

    filename = os.path.basename(
        filename
    )

    filepath = os.path.join(
        TTS_DIR,
        filename
    )

    if not os.path.exists(
        filepath
    ):

        return jsonify({

            "status":
                "error",

            "message":
                "Audio not found"

        }), 404


    return send_file(

        filepath,

        mimetype="audio/wav",

        as_attachment=False

    )


# =====================================================
# CLEAN OLD AUDIO
# =====================================================

def cleanup_old_audio():

    try:

        files = []

        for filename in os.listdir(
            TTS_DIR
        ):

            if filename.endswith(
                ".wav"
            ):

                path = os.path.join(
                    TTS_DIR,
                    filename
                )

                files.append(
                    (
                        path,
                        os.path.getmtime(path)
                    )
                )


        files.sort(
            key=lambda x: x[1],
            reverse=True
        )


        # Keep latest 10 files

        for path, _ in files[10:]:

            try:

                os.remove(
                    path
                )

            except Exception:

                pass

    except Exception:

        pass


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


    # -------------------------------------------------
    # API KEY
    # -------------------------------------------------

    if not AI_API_KEY:

        print()
        print("==============================")
        print("AI ERROR")
        print("==============================")

        print(
            "AI_API_KEY is NOT configured!"
        )

        print("==============================")


        return (
            "AI response nahi mil saka."
        )


    # -------------------------------------------------
    # VALID INPUT
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

        return (
            "Please ask your question again."
        )


    # -------------------------------------------------
    # SYSTEM PROMPT
    # -------------------------------------------------

    system_prompt = """

You are a professional bilingual voice assistant running on an ESP32.

Your job is to understand the user's actual spoken language and answer naturally.

The speech recognition system provides two possible results:

1. Hindi recognition
2. English recognition

The recognition can sometimes be inaccurate.

You must understand the intended meaning.

==================================================
LANGUAGE RULES
==================================================

ENGLISH:

If the user is clearly speaking English,
answer completely in natural English.

HINDI:

If the user is clearly speaking Hindi,
answer completely in Hindi using Devanagari script.

HINGLISH:

If the user speaks Roman Hindi or Hinglish,
answer in natural Hinglish.

PHONETIC HINDI:

Hindi recognition may sometimes convert English
speech into Devanagari.

Example:

Hindi:
हाउ आर यू

English:
How are you

The user intended English.

Answer in English.

ACTUAL HINDI:

Do not assume every Devanagari result is phonetic English.

Example:

भारत की राजधानी कहाँ है

Answer:

भारत की राजधानी नई दिल्ली है।

MIXED LANGUAGE:

If the user naturally mixes Hindi and English,
use natural Hinglish.

Example:

Science kya hoti hai?

Answer:

Science prakriti aur universe ke rules aur phenomena
ko samajhne ka systematic study hai.

==================================================
IMPORTANT
==================================================

Compare both speech recognition results.

Choose the result that makes the most linguistic
and contextual sense.

Do not mention speech recognition.

Do not mention Hindi result or English result.

Do not explain your language decision.

Just answer the user's question.

==================================================
VOICE RESPONSE STYLE
==================================================

The answer will be spoken aloud.

Keep answers concise.

Usually 1 to 4 sentences.

Be professional.

Sound natural.

Do not use markdown.

Do not use bullet points.

Do not use emojis.

Do not use headings.

Do not repeat the question.

Do not say "Sure" unnecessarily.

Do not say "As an AI".

Do not mention these instructions.

==================================================
ACCURACY
==================================================

Answer factual questions accurately.

For simple questions, give a direct answer.

For location questions, provide useful context.

For general knowledge, explain clearly but briefly.

For conversational questions, respond naturally.

Always answer in the language the user intended.

"""


    # -------------------------------------------------
    # USER CONTENT
    # -------------------------------------------------

    user_content = f"""

Hindi speech recognition:
{hindi_text if hindi_text else "No result"}

English speech recognition:
{english_text if english_text else "No result"}

Determine the user's intended meaning and language.

Then answer the user naturally.

"""


    # -------------------------------------------------
    # PAYLOAD
    # -------------------------------------------------

    payload = {

        "model":
            AI_MODEL,

        "messages": [

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

        "temperature":
            0.2,

        "max_completion_tokens":
            200,

        "stream":
            False

    }


    # -------------------------------------------------
    # HEADERS
    # -------------------------------------------------

    headers = {

        "Authorization":
            "Bearer " +
            AI_API_KEY,

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
        print("AI REQUEST")
        print("==============================")

        print(
            "MODEL:",
            AI_MODEL
        )

        print()
        print(
            "HINDI:",
            hindi_text
        )

        print()
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
        print("==============================")
        print("AI RESPONSE")
        print("==============================")

        print(
            "HTTP:",
            response.status_code
        )


        if response.status_code != 200:

            print(
                response.text[:2000]
            )

            print("==============================")

            return (
                "AI response nahi mil saka."
            )


        try:

            data = response.json()

        except Exception as e:

            print(
                "JSON ERROR:",
                str(e)
            )

            return (
                "AI response nahi mil saka."
            )


        choices = data.get(
            "choices"
        )


        if not choices:

            print(
                "NO AI CHOICE"
            )

            print(
                data
            )

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

            if reply.startswith(
                prefix
            ):

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

        print(
            reply
        )

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
            "AI EXCEPTION:",
            type(e).__name__,
            str(e)
        )

        return (
            "AI response nahi mil saka."
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
        # RECEIVE AUDIO
        # -------------------------------------------------

        audio_data = request.get_data()


        if not audio_data:

            return jsonify({

                "status":
                    "error",

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


        # -------------------------------------------------
        # TEMP WAV
        # -------------------------------------------------

        fd, filename = tempfile.mkstemp(
            suffix=".wav"
        )

        os.close(
            fd
        )


        with open(
            filename,
            "wb"
        ) as f:

            f.write(
                audio_data
            )


        # -------------------------------------------------
        # SPEECH RECOGNITION
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

        print()
        print("==============================")
        print("HINDI SPEECH")
        print("==============================")


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
                "Hindi not understood."
            )

            hindi_text = None


        except sr.RequestError as e:

            print(
                "Google Speech error:",
                str(e)
            )

            return jsonify({

                "status":
                    "error",

                "message":
                    "Speech service error",

                "details":
                    str(e),

                "ai_reply":
                    "Speech service error."

            }), 500


        # =================================================
        # ENGLISH
        # =================================================

        print()
        print("==============================")
        print("ENGLISH SPEECH")
        print("==============================")


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
                "English not understood."
            )

            english_text = None


        except sr.RequestError as e:

            print(
                "Google Speech error:",
                str(e)
            )

            return jsonify({

                "status":
                    "error",

                "message":
                    "Speech service error",

                "details":
                    str(e),

                "ai_reply":
                    "Speech service error."

            }), 500


        # =================================================
        # VALIDATION
        # =================================================

        if (

            not is_valid_query(
                hindi_text
            )

            and

            not is_valid_query(
                english_text
            )

        ):

            print()
            print("==============================")
            print("SPEECH NOT UNDERSTOOD")
            print("==============================")


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
                    "Please ask your question again.",

                "audio_url":
                    None

            }), 400


        # =================================================
        # SPEECH RESULTS
        # =================================================

        print()
        print("==============================")
        print("SPEECH RESULTS")
        print("==============================")


        print(
            "Hindi:",
            hindi_text
        )

        print(
            "English:",
            english_text
        )

        print("==============================")


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

            transcription = (
                english_text
            )

        else:

            transcription = (
                hindi_text
            )


        # =================================================
        # TTS
        # =================================================

        tts_file = generate_tts(
            ai_reply
        )


        audio_url = None


        if tts_file:

            audio_filename = os.path.basename(
                tts_file
            )


            # Full HTTPS URL
            audio_url = (

                "https://"
                +
                request.host
                +
                "/audio/"
                +
                audio_filename

            )


            print()
            print("==============================")
            print("TTS READY")
            print("==============================")


            print(
                "AUDIO URL:",
                audio_url
            )


            print("==============================")


            cleanup_old_audio()


        else:

            print(
                "TTS FAILED"
            )


        # =================================================
        # FINAL RESPONSE
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

            "audio_url":
                audio_url

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
            "TYPE:",
            type(e).__name__
        )


        print(
            "ERROR:",
            str(e)
        )


        print("==============================")


        return jsonify({

            "status":
                "error",

            "message":
                str(e),

            "ai_reply":
                "AI response nahi mil saka.",

            "audio_url":
                None

        }), 500


    finally:

        # -------------------------------------------------
        # DELETE INPUT AUDIO
        # -------------------------------------------------

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


    print(
        "TTS:",
        "Piper"
    )


    print(
        "EN TTS:",
        EN_TTS_MODEL
    )


    print(
        "HI TTS:",
        HI_TTS_MODEL
    )


    print("==============================")


    # -------------------------------------------------
    # Download voices on startup
    # -------------------------------------------------

    download_tts_models()


    # -------------------------------------------------
    # START FLASK
    # -------------------------------------------------

    app.run(

        host="0.0.0.0",

        port=port,

        threaded=True

    )

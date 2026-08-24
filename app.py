from flask import Flask, request, jsonify, Response
import os
import re
import tempfile
import requests
import speech_recognition as sr
from concurrent.futures import ThreadPoolExecutor

from google.oauth2 import service_account
from google.auth.transport.requests import Request as GoogleAuthRequest


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
# GOOGLE TTS
# =====================================================

GOOGLE_TTS_URL = (
    "https://texttospeech.googleapis.com/v1/text:synthesize"
)

# Indian female Hindi voice
GOOGLE_HINDI_VOICE = os.environ.get(
    "GOOGLE_HINDI_VOICE",
    "hi-IN-Neural2-A"
)

# Indian female English voice
GOOGLE_ENGLISH_VOICE = os.environ.get(
    "GOOGLE_ENGLISH_VOICE",
    "en-IN-Neural2-A"
)

GOOGLE_PROJECT_ID = os.environ.get(
    "GOOGLE_PROJECT_ID"
)

GOOGLE_SERVICE_ACCOUNT_JSON = os.environ.get(
    "GOOGLE_SERVICE_ACCOUNT_JSON"
)


# =====================================================
# GOOGLE AUTH
# =====================================================

google_credentials = None


def get_google_credentials():

    global google_credentials

    if not GOOGLE_SERVICE_ACCOUNT_JSON:
        print("GOOGLE_SERVICE_ACCOUNT_JSON missing")
        return None

    try:

        if google_credentials is None:

            import json

            service_account_info = json.loads(
                GOOGLE_SERVICE_ACCOUNT_JSON
            )

            google_credentials = (
                service_account.Credentials.from_service_account_info(
                    service_account_info,
                    scopes=[
                        "https://www.googleapis.com/auth/cloud-platform"
                    ]
                )
            )

        if (
            google_credentials.expired
            or not google_credentials.valid
        ):

            google_credentials.refresh(
                GoogleAuthRequest()
            )

        return google_credentials

    except Exception as e:

        print(
            "GOOGLE AUTH ERROR:",
            str(e)
        )

        return None


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

        "ai_engine": "Groq",

        "ai_model": AI_MODEL,

        "tts_engine": "Google Cloud Text-to-Speech",

        "hindi_voice":
            GOOGLE_HINDI_VOICE,

        "english_voice":
            GOOGLE_ENGLISH_VOICE

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


    system_prompt = """
You are a natural Indian voice assistant.

Understand the user's actual spoken language.

Hindi recognition:
Use it when the user speaks Hindi.

English recognition:
Use it when the user speaks English.

If the user speaks Hinglish or Roman Hindi,
answer naturally in Hinglish.

LANGUAGE:

English -> natural Indian English.

Hindi -> natural Hindi.

Hinglish -> natural Hinglish.

Do not mention speech recognition.

Do not explain your language decision.

VOICE STYLE:

Your answer will be spoken by a female Indian voice.

Keep the answer very short.

Usually one sentence.

Maximum around 120 characters when possible.

No markdown.

No bullet points.

No emojis.

No headings.

Do not repeat the question.

Do not say "As an AI".

Sound natural and conversational.
"""


    user_content = f"""
Hindi recognition:
{hindi_text if hindi_text else "No result"}

English recognition:
{english_text if english_text else "No result"}

Answer the user's question naturally.
"""


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
            120,

        "stream":
            False
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

            timeout=20

        )


        if response.status_code != 200:

            print(
                "AI ERROR:",
                response.text[:1000]
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


        reply = clean_text(
            reply
        )


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


        return reply


    except Exception as e:

        print(
            "AI EXCEPTION:",
            str(e)
        )

        return (
            "AI response nahi mil saka."
        )


# =====================================================
# GOOGLE TTS
# =====================================================

def generate_tts(
    text,
    use_hindi=False
):

    text = clean_text(
        text
    )

    if not text:
        return None


    credentials = get_google_credentials()

    if credentials is None:
        return None


    # Keep TTS short for faster response.

    if len(text) > 180:

        text = text[:180]

        last_space = text.rfind(" ")

        if last_space > 50:

            text = text[:last_space]


    if use_hindi:

        language_code = "hi-IN"

        voice_name = (
            GOOGLE_HINDI_VOICE
        )

    else:

        language_code = "en-IN"

        voice_name = (
            GOOGLE_ENGLISH_VOICE
        )


    payload = {

        "input": {

            "text":
                text

        },

        "voice": {

            "languageCode":
                language_code,

            "name":
                voice_name,

            "ssmlGender":
                "FEMALE"

        },

        "audioConfig": {

            "audioEncoding":
                "LINEAR16",

            "sampleRateHertz":
                16000,

            "speakingRate":
                1.05,

            "pitch":
                0.0

        }

    }


    try:

        access_token = (
            credentials.token
        )


        headers = {

            "Authorization":
                "Bearer " + access_token,

            "Content-Type":
                "application/json",

            "Accept":
                "application/json"

        }


        response = requests.post(

            GOOGLE_TTS_URL,

            headers=headers,

            json=payload,

            timeout=15

        )


        if response.status_code != 200:

            print(
                "GOOGLE TTS ERROR:",
                response.text[:1000]
            )

            return None


        data = response.json()


        audio_base64 = data.get(
            "audioContent"
        )


        if not audio_base64:

            return None


        import base64

        audio_data = base64.b64decode(
            audio_base64
        )


        return audio_data


    except Exception as e:

        print(
            "GOOGLE TTS EXCEPTION:",
            str(e)
        )

        return None


# =====================================================
# DETECT TTS LANGUAGE
# =====================================================

def is_hindi_text(text):

    if not text:
        return False

    # Devanagari characters

    hindi_chars = 0

    total_chars = 0

    for c in text:

        if c.isalpha():

            total_chars += 1

            if "\u0900" <= c <= "\u097F":

                hindi_chars += 1


    if total_chars == 0:
        return False


    return (
        hindi_chars / total_chars
        > 0.20
    )


# =====================================================
# TTS ENDPOINT
# =====================================================

@app.route(
    "/tts",
    methods=["POST"]
)
def tts():

    try:

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


        text = clean_text(
            data.get("text")
        )


        if not text:

            return jsonify({

                "status":
                    "error",

                "message":
                    "No text received"

            }), 400


        hindi = is_hindi_text(
            text
        )


        audio_data = generate_tts(

            text,

            use_hindi=hindi

        )


        if audio_data is None:

            return jsonify({

                "status":
                    "error",

                "message":
                    "Google TTS failed"

            }), 500


        return Response(

            audio_data,

            status=200,

            mimetype="audio/wav",

            headers={

                "Cache-Control":
                    "no-cache",

                "Content-Length":
                    str(len(audio_data))

            }

        )


    except Exception as e:

        return jsonify({

            "status":
                "error",

            "message":
                str(e)

        }), 500


# =====================================================
# WAKE
# =====================================================

@app.route(
    "/wake",
    methods=["POST", "GET"]
)
def wake():

    audio_data = request.get_data()


    # Current wake behaviour:
    # every wake request activates the assistant.

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
# SPEECH RECOGNITION
# =====================================================

def recognize_hindi(
    audio
):

    recognizer = sr.Recognizer()

    try:

        result = recognizer.recognize_google(

            audio,

            language="hi-IN"

        )

        return clean_text(
            result
        )

    except Exception:

        return None


def recognize_english(
    audio
):

    recognizer = sr.Recognizer()

    try:

        result = recognizer.recognize_google(

            audio,

            language="en-IN"

        )

        return clean_text(
            result
        )

    except Exception:

        return None


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
        # READ AUDIO
        # -------------------------------------------------

        recognizer = sr.Recognizer()


        with sr.AudioFile(
            filename
        ) as source:

            audio = recognizer.record(
                source
            )


        # -------------------------------------------------
        # PARALLEL RECOGNITION
        # -------------------------------------------------

        with ThreadPoolExecutor(
            max_workers=2
        ) as executor:

            hindi_future = executor.submit(
                recognize_hindi,
                audio
            )

            english_future = executor.submit(
                recognize_english,
                audio
            )


            hindi_text = (
                hindi_future.result()
            )

            english_text = (
                english_future.result()
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
        # FINAL JSON
        # -------------------------------------------------

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
                ai_reply

        })


    except Exception as e:

        print(
            "SERVER ERROR:",
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

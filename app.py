from flask import Flask, request, jsonify, Response
import os
import base64
import requests
import speech_recognition as sr
import re
import tempfile


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

GOOGLE_TTS_API_KEY = os.environ.get(
    "GOOGLE_TTS_API_KEY"
)

GOOGLE_TTS_URL = (
    "https://texttospeech.googleapis.com/v1/text:synthesize"
)


# English India female
GOOGLE_EN_VOICE = "en-IN-Wavenet-A"

# Hindi India female
GOOGLE_HI_VOICE = "hi-IN-Wavenet-A"


TTS_MAX_CHARS = 200


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

        "ai_model":
            AI_MODEL,

        "tts_engine":
            "Google Cloud TTS",

        "google_tts":
            "configured"
            if GOOGLE_TTS_API_KEY
            else "missing"
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

    print(
        "WAKE AUDIO:",
        len(audio_data)
    )

    # -------------------------------------------------
    # CURRENT WAKE MODE
    #
    # Every wake request returns true.
    #
    # This keeps ESP32 active.
    # -------------------------------------------------

    return jsonify({

        "status":
            "ok",

        "wake":
            True
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
# DETECT HINDI
# =====================================================

def contains_devanagari(text):

    if not text:

        return False

    return bool(
        re.search(
            r"[\u0900-\u097F]",
            text
        )
    )


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
You are a fast bilingual voice assistant running on an ESP32.

Understand the user's actual spoken language.

The speech recognition system provides:
1. Hindi recognition
2. English recognition

Use both results to understand the intended question.

LANGUAGE:

If the user speaks English:
answer in natural English.

If the user speaks Hindi:
answer in natural Hindi.

If the user speaks Hinglish or Roman Hindi:
answer in natural Hinglish.

IMPORTANT:

Do not mention speech recognition.

Do not explain your language choice.

Answer directly.

VOICE STYLE:

The answer will be spoken by an Indian female voice.

Keep the answer very short.

Usually one sentence.

Maximum about 120 characters when possible.

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

Answer the user's intended question.
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

            timeout=25
        )


        if response.status_code != 200:

            print(
                "AI ERROR:",
                response.status_code
            )

            print(
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

            return (
                "AI response nahi mil saka."
            )


        return reply


    except Exception as e:

        print(
            "AI ERROR:",
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
    hindi=False
):

    text = clean_text(
        text
    )


    if not text:

        return None


    if not GOOGLE_TTS_API_KEY:

        print(
            "GOOGLE_TTS_API_KEY missing"
        )

        return None


    # Keep TTS fast
    if len(text) > TTS_MAX_CHARS:

        text = text[
            :TTS_MAX_CHARS
        ]

        last_dot = text.rfind(".")

        if last_dot > 40:

            text = text[
                :last_dot + 1
            ]


    if hindi:

        language_code = "hi-IN"

        voice_name = (
            GOOGLE_HI_VOICE
        )

    else:

        language_code = "en-IN"

        voice_name = (
            GOOGLE_EN_VOICE
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
                voice_name
        },

        "audioConfig": {

            "audioEncoding":
                "LINEAR16",

            "sampleRateHertz":
                16000,

            "speakingRate":
                1.08,

            "pitch":
                0.0,

            "volumeGainDb":
                1.0
        }
    }


    headers = {

        "X-goog-api-key":
            GOOGLE_TTS_API_KEY,

        "Content-Type":
            "application/json",

        "Accept":
            "application/json"
    }


    try:

        print(
            "TTS:",
            text
        )

        response = requests.post(

            GOOGLE_TTS_URL,

            headers=headers,

            json=payload,

            timeout=15
        )


        print(
            "GOOGLE TTS HTTP:",
            response.status_code
        )


        if response.status_code != 200:

            print(
                response.text[:2000]
            )

            return None


        data = response.json()


        audio_base64 = data.get(
            "audioContent"
        )


        if not audio_base64:

            return None


        audio_data = base64.b64decode(
            audio_base64
        )


        print(
            "TTS AUDIO:",
            len(audio_data)
        )


        return audio_data


    except Exception as e:

        print(
            "TTS ERROR:",
            str(e)
        )

        return None


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


        # Detect Hindi automatically
        hindi = contains_devanagari(
            text
        )


        audio_data = generate_tts(

            text,

            hindi
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

                "Content-Length":
                    str(len(audio_data)),

                "Cache-Control":
                    "no-cache"
            }
        )


    except Exception as e:

        print(
            "TTS ROUTE ERROR:",
            str(e)
        )

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
                    "No audio received"

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


        except sr.UnknownValueError:

            hindi_text = None


        except sr.RequestError as e:

            print(
                "Hindi speech error:",
                str(e)
            )


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


        except sr.UnknownValueError:

            english_text = None


        except sr.RequestError as e:

            print(
                "English speech error:",
                str(e)
            )


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
        # BEST QUERY
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
        # RESPONSE
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


        return jsonify(
            response_data
        )


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


    print(
        "ESP32 VOICE SERVER"
    )


    app.run(

        host="0.0.0.0",

        port=port,

        threaded=True
    )

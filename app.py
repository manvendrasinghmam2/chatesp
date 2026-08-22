from flask import Flask, request, jsonify, send_file
import os
import re
import base64
import tempfile
import requests
import speech_recognition as sr

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

GOOGLE_TTS_KEY = os.environ.get(
    "GOOGLE_TTS_KEY"
)

GOOGLE_TTS_URL = (
    "https://texttospeech.googleapis.com/v1/text:synthesize"
)

AUDIO_DIR = "/tmp/tts"

os.makedirs(
    AUDIO_DIR,
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
        "tts_engine": "Google Cloud TTS",
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
    print("WAKE REQUEST RECEIVED")
    print("==============================")

    if request.method == "POST":

        audio_data = request.get_data()

        print(
            "Audio bytes:",
            len(audio_data)
        )

    return jsonify({
        "status": "ok",
        "wake": True,
        "english": "Hello",
        "hindi": None
    })


# =====================================================
# CLEAN
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
            "ERROR: AI_API_KEY missing"
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

    system_prompt = """
You are a professional bilingual voice assistant
running on an ESP32.

Understand the user's intended language and meaning.

If the user clearly speaks English,
answer in natural English.

If the user clearly speaks Hindi,
answer in Hindi using Devanagari.

If the user speaks Roman Hindi or Hinglish,
answer in natural Hinglish.

If the user mixes Hindi and English,
answer naturally in Hinglish.

The speech recognition system provides two results.
Compare both results and understand the intended meaning.

Do not mention speech recognition.

Do not explain your language decision.

VOICE STYLE:

Keep answers concise.

Usually 1 to 4 sentences.

Sound natural and conversational.

Do not use markdown.

Do not use bullet points.

Do not use emojis.

Do not use headings.

Do not repeat the question.

Do not say "As an AI".

Do not say "Sure" unnecessarily.

Answer directly.
"""

    user_content = f"""
Hindi speech recognition:
{hindi_text if hindi_text else "No result"}

English speech recognition:
{english_text if english_text else "No result"}

Determine the user's intended meaning.

Then answer naturally.
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
            "AI HTTP:",
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

            print(
                "No AI choices"
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
# TTS LANGUAGE
# =====================================================

def detect_tts_language(
    hindi_text,
    english_text
):

    hindi_text = clean_text(
        hindi_text
    )

    english_text = clean_text(
        english_text
    )

    # If Hindi contains Devanagari,
    # prefer Hindi.

    if is_valid_query(hindi_text):

        if re.search(
            r"[\u0900-\u097F]",
            hindi_text
        ):

            return "hi"

    # Otherwise English

    if is_valid_query(
        english_text
    ):

        return "en"

    return "en"


# =====================================================
# GOOGLE TTS
# =====================================================

def generate_tts(
    text,
    language
):

    if not GOOGLE_TTS_KEY:

        print(
            "ERROR: GOOGLE_TTS_KEY missing"
        )

        return None

    text = clean_text(
        text
    )

    if not text:

        return None

    # -------------------------------------------------
    # VOICE
    # -------------------------------------------------

    if language == "hi":

        language_code = "hi-IN"

        voice_name = "hi-IN-Standard-A"

    else:

        language_code = "en-IN"

        voice_name = "en-IN-Standard-A"

    payload = {

        "input": {
            "text": text
        },

        "voice": {

            "languageCode":
                language_code,

            "name":
                voice_name
        },

        "audioConfig": {

            "audioEncoding":
                "MP3",

            "speakingRate":
                1.0,

            "pitch":
                0.0,

            "volumeGainDb":
                2.0
        }
    }

    url = (
        GOOGLE_TTS_URL
        + "?key="
        + GOOGLE_TTS_KEY
    )

    try:

        print()
        print("==============================")
        print("TTS REQUEST")
        print("==============================")

        print(
            "Language:",
            language_code
        )

        print(
            "Text:",
            text
        )

        response = requests.post(
            url,
            json=payload,
            headers={
                "Content-Type":
                    "application/json"
            },
            timeout=30
        )

        print(
            "TTS HTTP:",
            response.status_code
        )

        if response.status_code != 200:

            print(
                "TTS ERROR:"
            )

            print(
                response.text[:2000]
            )

            return None

        data = response.json()

        audio_content = data.get(
            "audioContent"
        )

        if not audio_content:

            print(
                "TTS audioContent missing"
            )

            return None

        audio_bytes = base64.b64decode(
            audio_content
        )

        filename = (
            "voice_"
            + str(abs(hash(text)))
            + ".mp3"
        )

        filepath = os.path.join(
            AUDIO_DIR,
            filename
        )

        with open(
            filepath,
            "wb"
        ) as audio_file:

            audio_file.write(
                audio_bytes
            )

        print(
            "TTS FILE:",
            filename
        )

        print(
            "TTS BYTES:",
            len(audio_bytes)
        )

        print("==============================")

        return filename

    except requests.exceptions.Timeout:

        print(
            "TTS TIMEOUT"
        )

        return None

    except Exception as e:

        print(
            "TTS ERROR:",
            type(e).__name__,
            str(e)
        )

        return None


# =====================================================
# TTS DOWNLOAD
# =====================================================

@app.route(
    "/tts/<path:filename>",
    methods=["GET"]
)
def tts_file(filename):

    # Prevent path traversal

    filename = os.path.basename(
        filename
    )

    filepath = os.path.join(
        AUDIO_DIR,
        filename
    )

    if not os.path.isfile(filepath):

        return (
            "Audio not found",
            404
        )

    return send_file(
        filepath,
        mimetype="audio/mpeg",
        as_attachment=False
    )


# =====================================================
# UPLOAD AUDIO
# =====================================================

@app.route(
    "/uploadAudio",
    methods=["POST"]
)
def upload_audio():

    temp_filename = None

    try:

        # -------------------------------------------------
        # RECEIVE
        # -------------------------------------------------

        audio_data = request.get_data()

        print()
        print("==============================")
        print("AUDIO RECEIVED")
        print("==============================")

        print(
            "Audio bytes:",
            len(audio_data)
        )

        if not audio_data:

            return jsonify({

                "status":
                    "error",

                "message":
                    "No audio received",

                "transcription":
                    None,

                "ai_reply":
                    "Please ask your question again.",

                "audio_url":
                    None

            }), 400

        # -------------------------------------------------
        # TEMP WAV
        # -------------------------------------------------

        fd, temp_filename = tempfile.mkstemp(
            suffix=".wav"
        )

        os.close(fd)

        with open(
            temp_filename,
            "wb"
        ) as audio_file:

            audio_file.write(
                audio_data
            )

        # -------------------------------------------------
        # SPEECH RECOGNITION
        # -------------------------------------------------

        recognizer = sr.Recognizer()

        with sr.AudioFile(
            temp_filename
        ) as source:

            audio = recognizer.record(
                source
            )

        hindi_text = None

        english_text = None

        # -------------------------------------------------
        # HINDI
        # -------------------------------------------------

        print()
        print(
            "HINDI SPEECH"
        )

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

            print(
                "Hindi not understood"
            )

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
                    "Speech service error",

                "audio_url":
                    None

            }), 500

        # -------------------------------------------------
        # ENGLISH
        # -------------------------------------------------

        print()
        print(
            "ENGLISH SPEECH"
        )

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

            print(
                "English not understood"
            )

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
                    "Speech service error",

                "audio_url":
                    None

            }), 500

        # -------------------------------------------------
        # VALIDATION
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
                    "Please ask your question again.",

                "audio_url":
                    None

            }), 400

        # -------------------------------------------------
        # AI
        # -------------------------------------------------

        ai_reply = get_ai_reply(
            hindi_text,
            english_text
        )

        # -------------------------------------------------
        # TRANSCRIPTION
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

        language = detect_tts_language(
            hindi_text,
            english_text
        )

        # -------------------------------------------------
        # TTS
        # -------------------------------------------------

        audio_filename = generate_tts(
            ai_reply,
            language
        )

        # -------------------------------------------------
        # AUDIO URL
        # -------------------------------------------------

        audio_url = None

        if audio_filename:

            scheme = (
                "https"
                if request.is_secure
                else "https"
            )

            audio_url = (
                scheme
                + "://"
                + request.host
                + "/tts/"
                + audio_filename
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

            "transcription":
                None,

            "ai_reply":
                "AI response nahi mil saka.",

            "audio_url":
                None

        }), 500

    finally:

        if temp_filename:

            try:

                if os.path.exists(
                    temp_filename
                ):

                    os.remove(
                        temp_filename
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
        "TTS KEY:",
        "CONFIGURED"
        if GOOGLE_TTS_KEY
        else "MISSING"
    )

    print("==============================")

    app.run(
        host="0.0.0.0",
        port=port,
        threaded=True
    )

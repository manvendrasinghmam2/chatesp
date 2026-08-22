from flask import Flask, request, jsonify, Response
import os
import speech_recognition as sr
import requests
import re
import tempfile
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
        "tts_engine": "Google gTTS",
        "model": AI_MODEL
    })


# =====================================================
# WAKE
# =====================================================

@app.route("/wake", methods=["POST", "GET"])
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
        # TEMPORARY WAKE TEST
        #
        # IMPORTANT:
        # This is FALSE.
        #
        # So ESP32 will NOT automatically wake.
        # -------------------------------------------------

        response_data = {
            "status": "ok",
            "wake": False
        }

        print(
            "WAKE:",
            False
        )

        print("==============================")

        return jsonify(response_data)

    return jsonify({
        "status": "ok",
        "wake": False
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

    hindi_text = clean_text(hindi_text)
    english_text = clean_text(english_text)

    if not AI_API_KEY:

        print("AI_API_KEY missing")

        return "AI response nahi mil saka."

    if (
        not is_valid_query(hindi_text)
        and
        not is_valid_query(english_text)
    ):

        return "Please ask your question again."

    system_prompt = """
You are a professional bilingual voice assistant running on an ESP32.

Understand the user's intended language.

If the user speaks English:
answer in natural English.

If the user speaks Hindi:
answer in Hindi using Devanagari.

If the user speaks Hinglish:
answer naturally in Hinglish.

Compare Hindi and English recognition results and choose
the result that makes the most contextual sense.

Do not mention speech recognition.

Do not explain your language decision.

The answer will be spoken aloud.

Keep answers concise.

Usually 1 to 4 sentences.

Do not use markdown.

Do not use bullet points.

Do not use emojis.

Do not use headings.

Do not repeat the question.

Do not say "As an AI".
"""

    user_content = f"""
Hindi speech recognition:
{hindi_text if hindi_text else "No result"}

English speech recognition:
{english_text if english_text else "No result"}

Answer the user's question naturally.
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
                response.text[:1000]
            )

            return "AI response nahi mil saka."

        data = response.json()

        choices = data.get("choices")

        if not choices:

            return "AI response nahi mil saka."

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

        reply = str(reply).strip()

        reply = reply.replace(
            "```",
            ""
        )

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

            return "AI response nahi mil saka."

        print()
        print("==============================")
        print("AI REPLY")
        print("==============================")
        print(reply)
        print("==============================")

        return reply

    except requests.exceptions.Timeout:

        print("AI TIMEOUT")

        return "AI response nahi mil saka."

    except Exception as e:

        print(
            "AI ERROR:",
            str(e)
        )

        return "AI response nahi mil saka."


# =====================================================
# TTS LANGUAGE
# =====================================================

def detect_tts_language(
    text
):

    if not text:
        return "en"

    # Devanagari present
    for char in text:

        if "\u0900" <= char <= "\u097F":

            return "hi"

    # Otherwise English/Hinglish
    return "en"


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

    text = clean_text(text)

    if not text:

        return jsonify({
            "status": "error",
            "message": "No text"
        }), 400

    language = detect_tts_language(
        text
    )

    print()
    print("==============================")
    print("TTS REQUEST")
    print("==============================")
    print("TEXT:", text)
    print("LANG:", language)
    print("==============================")

    try:

        audio = tempfile.NamedTemporaryFile(
            suffix=".mp3",
            delete=False
        )

        filename = audio.name

        audio.close()

        tts = gTTS(
            text=text,
            lang=language,
            slow=False
        )

        tts.save(
            filename
        )

        with open(
            filename,
            "rb"
        ) as f:

            data = f.read()

        try:
            os.remove(filename)
        except:
            pass

        print(
            "TTS AUDIO BYTES:",
            len(data)
        )

        return Response(
            data,
            mimetype="audio/mpeg",
            headers={
                "Cache-Control": "no-cache",
                "Content-Length": str(len(data))
            }
        )

    except Exception as e:

        print()
        print("==============================")
        print("TTS ERROR")
        print("==============================")

        print(
            type(e).__name__
        )

        print(
            str(e)
        )

        print("==============================")

        return jsonify({
            "status": "error",
            "message": str(e)
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

        # -------------------------------------------------
        # WAV
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

        # =================================================
        # HINDI
        # =================================================

        print()
        print("HINDI SPEECH")

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

            hindi_text = None

        except sr.RequestError as e:

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
        print("ENGLISH SPEECH")

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

            english_text = None

        except sr.RequestError as e:

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
        # AI
        # =================================================

        ai_reply = get_ai_reply(
            hindi_text,
            english_text
        )

        # =================================================
        # TRANSCRIPTION
        # =================================================

        if is_valid_query(
            english_text
        ):

            transcription = english_text

        else:

            transcription = hindi_text

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
                ai_reply
        }

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

        print("==============================")

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

            except:

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

    print()
    print("==============================")
    print("ESP32 VOICE SERVER")
    print("==============================")

    print(
        "PORT:",
        port
    )

    print(
        "MODEL:",
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
        port=port,
        threaded=True
    )

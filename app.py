from flask import Flask, request, jsonify, Response
import os
import speech_recognition as sr
import requests
import re
import tempfile
import uuid
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
# TTS MEMORY STORAGE
# =====================================================

tts_files = {}

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
        "tts_engine": "gTTS",
        "model": AI_MODEL
    })


# =====================================================
# WAKE
#
# IMPORTANT:
# This is TEST MODE.
#
# Real wake detection later add kar sakte hain.
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
            "Audio bytes:",
            len(audio_data)
        )

        # ------------------------------------------------
        # TEMPORARY TEST
        # ------------------------------------------------
        #
        # Abhi har wake request ko false rakha gaya hai.
        #
        # Agar aap actual HELLO detection chahte hain,
        # uske liye separate speech recognition lagayenge.
        #

        response = {
            "status": "ok",
            "wake": False
        }

        print(
            "WAKE:",
            False
        )

        return jsonify(response)

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
# AI REPLY
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

Understand the user's actual intended language.

If the user speaks English:
answer completely in natural English.

If the user speaks Hindi:
answer completely in Hindi using Devanagari.

If the user speaks Hinglish:
answer naturally in Hinglish.

Compare both Hindi and English speech recognition results.

Choose the result that makes the most linguistic and contextual sense.

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

Do not say "Sure" unnecessarily.

Do not say "As an AI".

Always answer naturally.
"""

    user_content = f"""
Hindi speech recognition:
{hindi_text if hindi_text else "No result"}

English speech recognition:
{english_text if english_text else "No result"}

Determine the user's intended meaning and language.

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

        print("Hindi:", hindi_text)
        print("English:", english_text)

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
                response.text[:2000]
            )

            return "AI response nahi mil saka."

        try:

            data = response.json()

        except Exception:

            return "AI response nahi mil saka."

        choices = data.get(
            "choices"
        )

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

        reply = str(
            reply
        ).strip()

        reply = reply.replace(
            "```",
            ""
        )

        reply = reply.strip()

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

    except requests.exceptions.ConnectionError as e:

        print(
            "AI CONNECTION ERROR:",
            str(e)
        )

        return "AI response nahi mil saka."

    except Exception as e:

        print(
            "AI ERROR:",
            str(e)
        )

        return "AI response nahi mil saka."


# =====================================================
# CREATE TTS
# =====================================================

def create_tts(text):

    text = clean_text(text)

    if not text:

        return None

    try:

        filename = (
            str(uuid.uuid4())
            + ".mp3"
        )

        filepath = os.path.join(
            tempfile.gettempdir(),
            filename
        )

        # ------------------------------------------------
        # LANGUAGE DETECTION
        # ------------------------------------------------

        devanagari = re.search(
            r"[\u0900-\u097F]",
            text
        )

        if devanagari:

            language = "hi"

        else:

            language = "en"

        print()
        print("==============================")
        print("TTS")
        print("==============================")

        print(
            "Language:",
            language
        )

        print(
            "Text:",
            text
        )

        print(
            "Creating MP3..."
        )

        tts = gTTS(
            text=text,
            lang=language,
            slow=False
        )

        tts.save(
            filepath
        )

        if not os.path.exists(
            filepath
        ):

            print(
                "TTS FILE NOT CREATED"
            )

            return None

        filesize = os.path.getsize(
            filepath
        )

        print(
            "TTS MP3 bytes:",
            filesize
        )

        if filesize < 100:

            print(
                "TTS FILE TOO SMALL"
            )

            try:
                os.remove(filepath)
            except Exception:
                pass

            return None

        # ------------------------------------------------
        # Store
        # ------------------------------------------------

        tts_files[filename] = filepath

        print(
            "TTS READY:",
            filename
        )

        print("==============================")

        return filename

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

        return None


# =====================================================
# TTS DOWNLOAD
# =====================================================

@app.route(
    "/tts/<filename>",
    methods=["GET"]
)
def download_tts(filename):

    print()
    print("==============================")
    print("TTS DOWNLOAD REQUEST")
    print("==============================")

    print(
        "Filename:",
        filename
    )

    filepath = tts_files.get(
        filename
    )

    if not filepath:

        print(
            "TTS FILE NOT FOUND"
        )

        return "TTS file not found", 404

    if not os.path.exists(
        filepath
    ):

        print(
            "TTS FILE DELETED"
        )

        tts_files.pop(
            filename,
            None
        )

        return "TTS file not found", 404

    try:

        with open(
            filepath,
            "rb"
        ) as f:

            data = f.read()

        print(
            "Sending bytes:",
            len(data)
        )

        # ------------------------------------------------
        # Delete after reading
        # ------------------------------------------------

        try:

            os.remove(
                filepath
            )

        except Exception:

            pass

        tts_files.pop(
            filename,
            None
        )

        print(
            "TTS SENT"
        )

        return Response(

            data,

            mimetype="audio/mpeg",

            headers={
                "Content-Length":
                    str(len(data)),
                "Cache-Control":
                    "no-cache"
            }
        )

    except Exception as e:

        print(
            "TTS SEND ERROR:",
            str(e)
        )

        return "TTS error", 500


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

        # ------------------------------------------------
        # RECEIVE
        # ------------------------------------------------

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

        # ------------------------------------------------
        # TEMP WAV
        # ------------------------------------------------

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

        # ------------------------------------------------
        # SPEECH
        # ------------------------------------------------

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
                "Hindi not understood"
            )

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
                "English not understood"
            )

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

            print()
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
        # BEST TRANSCRIPTION
        # =================================================

        if is_valid_query(
            english_text
        ):

            transcription = english_text

        else:

            transcription = hindi_text

        # =================================================
        # TTS
        # =================================================

        tts_filename = create_tts(
            ai_reply
        )

        # =================================================
        # TTS URL
        # =================================================

        tts_url = None

        if tts_filename:

            # Render public host automatically
            host = request.host_url.rstrip("/")

            tts_url = (
                host
                + "/tts/"
                + tts_filename
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

            "tts_url":
                tts_url
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
            type(e).__name__
        )

        print(
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

            "tts_url":
                None

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

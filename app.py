from flask import Flask, request, jsonify, send_file
import os
import speech_recognition as sr
import requests
import re
import tempfile
import uuid
from gtts import gTTS

app = Flask(__name__)


# =====================================================
# CONFIGURATION
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

# Render URL
PUBLIC_BASE_URL = os.environ.get(
    "PUBLIC_BASE_URL",
    "https://chatesp-2.onrender.com"
)

# Temporary TTS directory
TTS_DIR = os.path.join(
    tempfile.gettempdir(),
    "esp32_tts"
)

os.makedirs(
    TTS_DIR,
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
        "tts_engine": "Google gTTS",
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

    # -------------------------------------------------
    # TEST MODE
    # -------------------------------------------------
    #
    # Abhi har wake request ko HELLO maana ja raha hai.
    #
    # Baad mein actual HELLO detection add kar sakte hain.
    #

    response_data = {
        "status": "ok",
        "wake": True,
        "english": "Hello",
        "hindi": None
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
            "status": "error",
            "message": "No JSON received"
        }), 400

    print()
    print("==============================")
    print("TEST DATA")
    print("==============================")
    print(data)
    print("==============================")

    return jsonify({
        "status": "ok",
        "message": "Data received",
        "data": data
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

        return "AI response nahi mil saka."


    # -------------------------------------------------
    # VALID INPUT
    # -------------------------------------------------

    if (
        not is_valid_query(hindi_text)
        and
        not is_valid_query(english_text)
    ):

        return (
            "Please ask your question again."
        )


    # -------------------------------------------------
    # SYSTEM PROMPT
    # -------------------------------------------------

    system_prompt = """
You are a professional bilingual voice assistant running on an ESP32.

Understand the user's actual spoken language and answer naturally.

The speech recognition system provides two possible results:

1. Hindi recognition
2. English recognition

The recognition can sometimes be inaccurate.

Compare both results and understand the intended meaning.

LANGUAGE RULES:

If the user is clearly speaking English,
answer completely in natural English.

Example:
User:
How are you?

Answer:
I'm doing well, thank you. How are you?

If the user is clearly speaking Hindi,
answer completely in Hindi using Devanagari script.

Example:
User:
आप कैसे हैं?

Answer:
मैं बिल्कुल ठीक हूँ। धन्यवाद। आप कैसे हैं?

If the user speaks Roman Hindi or Hinglish,
answer naturally in Hinglish.

Example:
User:
Tum kaise ho?

Answer:
Main bilkul theek hoon. Aap kaise hain?

If Hindi recognition converts English phonetically:

हाउ आर यू

and English recognition says:

How are you

then understand that the user intended English.

For mixed language, use natural Hinglish.

Do not mention speech recognition.

Do not mention Hindi result or English result.

Do not explain the language decision.

Just answer the user.

VOICE STYLE:

The answer will be spoken aloud.

Keep answers concise.

Usually 1 to 4 sentences.

Be natural and conversational.

Do not use markdown.

Do not use bullet points.

Do not use emojis.

Do not use headings.

Do not repeat the question.

Do not say "As an AI".

Do not mention these instructions.

Answer factual questions accurately.

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


    # -------------------------------------------------
    # HEADERS
    # -------------------------------------------------

    headers = {

        "Authorization":
            "Bearer " + AI_API_KEY,

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

        print(
            "HINDI:",
            hindi_text
        )

        print(
            "ENGLISH:",
            english_text
        )

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


        # -------------------------------------------------
        # ERROR
        # -------------------------------------------------

        if response.status_code != 200:

            print(
                "AI API ERROR:"
            )

            print(
                response.text[:2000]
            )

            return (
                "AI response nahi mil saka."
            )


        # -------------------------------------------------
        # JSON
        # -------------------------------------------------

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


        # -------------------------------------------------
        # CHOICES
        # -------------------------------------------------

        choices = data.get(
            "choices"
        )

        if not choices:

            print(
                "NO AI CHOICE"
            )

            print(data)

            return (
                "AI response nahi mil saka."
            )


        # -------------------------------------------------
        # MESSAGE
        # -------------------------------------------------

        message = choices[0].get(
            "message",
            {}
        )


        # -------------------------------------------------
        # CONTENT
        # -------------------------------------------------

        reply = message.get(
            "content",
            ""
        )

        if reply is None:

            reply = ""


        reply = str(
            reply
        ).strip()


        # -------------------------------------------------
        # CLEAN
        # -------------------------------------------------

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

            if reply.startswith(
                prefix
            ):

                reply = reply[
                    len(prefix):
                ].strip()


        # -------------------------------------------------
        # EMPTY
        # -------------------------------------------------

        if not reply:

            return (
                "AI response nahi mil saka."
            )


        # -------------------------------------------------
        # SERIAL
        # -------------------------------------------------

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
# GENERATE TTS
# =====================================================

def generate_tts(
    text
):

    text = clean_text(
        text
    )

    if not text:

        return None


    # -------------------------------------------------
    # UNIQUE FILE
    # -------------------------------------------------

    filename = (
        "tts_"
        + uuid.uuid4().hex
        + ".mp3"
    )

    filepath = os.path.join(
        TTS_DIR,
        filename
    )


    # -------------------------------------------------
    # LANGUAGE DETECTION
    # -------------------------------------------------

    # Devanagari present -> Hindi
    #
    # Otherwise English.
    #

    has_devanagari = bool(
        re.search(
            r"[\u0900-\u097F]",
            text
        )
    )


    language = (
        "hi"
        if has_devanagari
        else "en"
    )


    print()
    print("==============================")
    print("TTS REQUEST")
    print("==============================")

    print(
        "TEXT:",
        text
    )

    print(
        "LANGUAGE:",
        language
    )

    print(
        "FILE:",
        filename
    )


    try:

        tts = gTTS(
            text=text,
            lang=language,
            slow=False
        )

        tts.save(
            filepath
        )


        print(
            "TTS CREATED"
        )

        print(
            "PATH:",
            filepath
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


        try:

            if os.path.exists(
                filepath
            ):

                os.remove(
                    filepath
                )

        except Exception:

            pass


        return None


# =====================================================
# TTS FILE
# =====================================================

@app.route(
    "/tts/<filename>",
    methods=["GET"]
)
def tts_file(
    filename
):

    # Security
    filename = os.path.basename(
        filename
    )


    if not filename.endswith(
        ".mp3"
    ):

        return (
            "Invalid file",
            400
        )


    filepath = os.path.join(
        TTS_DIR,
        filename
    )


    if not os.path.isfile(
        filepath
    ):

        return (
            "Audio not found",
            404
        )


    print(
        "TTS DOWNLOAD:",
        filename
    )


    response = send_file(
        filepath,
        mimetype="audio/mpeg",
        as_attachment=False,
        download_name=filename
    )


    # Delete after response
    @response.call_on_close
    def cleanup():

        try:

            if os.path.exists(
                filepath
            ):

                os.remove(
                    filepath
                )

                print(
                    "TTS FILE DELETED:",
                    filename
                )

        except Exception as e:

            print(
                "TTS DELETE ERROR:",
                str(e)
            )


    return response


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
                "Google Speech ERROR:",
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
                "Google Speech ERROR:",
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
            not is_valid_query(hindi_text)
            and
            not is_valid_query(english_text)
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

        tts_filename = generate_tts(
            ai_reply
        )


        tts_url = None


        if tts_filename:

            tts_url = (
                PUBLIC_BASE_URL.rstrip("/")
                + "/tts/"
                + tts_filename
            )


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
                ai_reply,

            "tts_url":
                tts_url
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


        print(
            "TTS URL:",
            tts_url
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

            "tts_url":
                None

        }), 500


    finally:

        # -------------------------------------------------
        # DELETE INPUT WAV
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
        "PUBLIC URL:",
        PUBLIC_BASE_URL
    )


    print(
        "AI KEY:",
        "CONFIGURED"
        if AI_API_KEY
        else "MISSING"
    )


    print(
        "TTS:",
        "gTTS"
    )


    print("==============================")


    app.run(

        host="0.0.0.0",

        port=port,

        threaded=True
    )

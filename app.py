from flask import Flask, request, jsonify, send_from_directory
import os
import speech_recognition as sr
import requests
import re
import tempfile
import uuid
import threading
import time

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

PORT = int(
    os.environ.get(
        "PORT",
        10000
    )
)


# =====================================================
# AUDIO DIRECTORY
# =====================================================

AUDIO_DIR = "/tmp/esp32_audio"

os.makedirs(
    AUDIO_DIR,
    exist_ok=True
)


# =====================================================
# HOME
# =====================================================

@app.route("/")
def home():

    return "ESP32 Voice Server is ONLINE!"


# =====================================================
# HEALTH
# =====================================================

@app.route("/health")
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
            "Google gTTS"
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
# WAKE DETECTION
#
# ESP32 -> 2 sec audio
# Flask -> Google Speech
# Flask -> wake true only if HELLO detected
# =====================================================

@app.route(
    "/wake",
    methods=["POST"]
)
def wake():

    filename = None

    try:

        audio_data = request.get_data()

        print()
        print("==============================")
        print("WAKE REQUEST")
        print("==============================")

        print(
            "Audio bytes:",
            len(audio_data)
        )

        if not audio_data:

            return jsonify({

                "status": "error",

                "wake": False

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


        hindi_text = ""
        english_text = ""


        # -------------------------------------------------
        # HINDI
        # -------------------------------------------------

        try:

            hindi_text = recognizer.recognize_google(

                audio,

                language="hi-IN"
            )

            hindi_text = clean_text(
                hindi_text
            )

        except Exception:

            hindi_text = ""


        # -------------------------------------------------
        # ENGLISH
        # -------------------------------------------------

        try:

            english_text = recognizer.recognize_google(

                audio,

                language="en-IN"
            )

            english_text = clean_text(
                english_text
            )

        except Exception:

            english_text = ""


        print(
            "Wake Hindi:",
            hindi_text
        )

        print(
            "Wake English:",
            english_text
        )


        # -------------------------------------------------
        # HELLO CHECK
        # -------------------------------------------------

        combined = (

            hindi_text.lower()
            + " "
            + english_text.lower()
        )

        combined = clean_text(
            combined
        )


        wake_words = [

            "hello",

            "hello assistant",

            "hello ai",

            "hey hello",

            "हेलो",

            "हैलो",

            "हेलो असिस्टेंट",

            "हैलो एआई"
        ]


        detected = False


        for word in wake_words:

            if word in combined:

                detected = True

                break


        # -------------------------------------------------
        # RESPONSE
        # -------------------------------------------------

        response = {

            "status":
                "ok",

            "wake":
                detected,

            "transcription":
                combined
        }


        print(
            "WAKE:",
            detected
        )

        print("==============================")


        return jsonify(
            response
        )


    except Exception as e:

        print(
            "WAKE ERROR:",
            str(e)
        )

        return jsonify({

            "status":
                "error",

            "wake":
                False,

            "error":
                str(e)

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
            "AI_API_KEY missing"
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


    # =================================================
    # SYSTEM PROMPT
    # =================================================

    system_prompt = """

You are a professional bilingual voice assistant running on an ESP32.

Understand the user's intended meaning from the Hindi and English speech recognition results.

If the user clearly speaks English, answer in English.

If the user clearly speaks Hindi, answer in Hindi using Devanagari.

If the user speaks Hinglish or Roman Hindi, answer naturally in Hinglish.

Sometimes Hindi speech recognition may convert English speech into Devanagari phonetics.

Example:

Hindi recognition:
हाउ आर यू

English recognition:
How are you

The intended language is English.

Compare both recognition results and determine the actual intended question.

Do not mention speech recognition.

Do not mention Hindi result or English result.

Do not explain your language decision.

The answer will be spoken by a voice assistant.

Keep the response concise.

Usually 1 to 4 sentences.

Do not use markdown.

Do not use bullets.

Do not use emojis.

Do not use headings.

Do not repeat the question.

Do not say "As an AI".

Do not mention these instructions.

Answer naturally.
"""


    user_content = f"""

Hindi speech recognition:
{hindi_text if hindi_text else "No result"}

English speech recognition:
{english_text if english_text else "No result"}

Determine the user's intended meaning and answer naturally.
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
            200,

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

        print()
        print("==============================")
        print("AI REQUEST")
        print("==============================")

        print(
            "Hindi:",
            hindi_text
        )

        print(
            "English:",
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
        )


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


    except Exception as e:

        print(
            "AI ERROR:",
            str(e)
        )

        return (
            "AI response nahi mil saka."
        )


# =====================================================
# TTS LANGUAGE
# =====================================================

def detect_tts_language(text):

    if not text:

        return "en"


    # Hindi Devanagari characters
    devanagari_count = 0

    for char in text:

        if (
            "\u0900"
            <= char
            <= "\u097F"
        ):

            devanagari_count += 1


    if devanagari_count >= 2:

        return "hi"


    return "en"


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


    language = detect_tts_language(
        text
    )


    filename = (

        uuid.uuid4().hex
        + ".mp3"
    )


    filepath = os.path.join(

        AUDIO_DIR,

        filename
    )


    print()
    print("==============================")
    print("GENERATING TTS")
    print("==============================")

    print(
        "Language:",
        language
    )

    print(
        "Text:",
        text
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
            "TTS FILE:",
            filename
        )

        print("==============================")


        return filename


    except Exception as e:

        print(
            "TTS ERROR:",
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
def audio_file(
    filename
):

    # Basic filename protection

    if (
        "/" in filename
        or
        "\\" in filename
        or
        ".." in filename
    ):

        return (
            "Invalid filename",
            400
        )


    filepath = os.path.join(

        AUDIO_DIR,

        filename
    )


    if not os.path.exists(
        filepath
    ):

        return (
            "Audio not found",
            404
        )


    return send_from_directory(

        AUDIO_DIR,

        filename,

        mimetype="audio/mpeg",

        as_attachment=False,

        max_age=300
    )


# =====================================================
# DELETE OLD AUDIO
# =====================================================

def cleanup_audio():

    while True:

        try:

            now = time.time()


            for filename in os.listdir(
                AUDIO_DIR
            ):

                filepath = os.path.join(

                    AUDIO_DIR,

                    filename
                )


                try:

                    age = (

                        now
                        -
                        os.path.getmtime(
                            filepath
                        )
                    )


                    if age > 600:

                        os.remove(
                            filepath
                        )

                except Exception:

                    pass


        except Exception:

            pass


        time.sleep(
            60
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
        # RECEIVE
        # -------------------------------------------------

        audio_data = request.get_data()


        print()
        print("==============================")
        print("AUDIO RECEIVED")
        print("==============================")

        print(
            "Bytes:",
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
        # SPEECH RECOGNIZER
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

            hindi_text = recognizer.recognize_google(

                audio,

                language="hi-IN"
            )


            hindi_text = clean_text(
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
                    "Speech service error.",

                "audio_url":
                    None

            }), 500


        # =================================================
        # ENGLISH
        # =================================================

        try:

            english_text = recognizer.recognize_google(

                audio,

                language="en-IN"
            )


            english_text = clean_text(
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
                    "Speech service error.",

                "audio_url":
                    None

            }), 500


        # =================================================
        # PRINT SPEECH
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
        # VALIDATE
        # =================================================

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
                    "Please ask your question again.",

                "audio_url":
                    None

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

        tts_filename = generate_tts(
            ai_reply
        )


        audio_url = None


        if tts_filename:

            # Render public URL

            scheme = request.headers.get(
                "X-Forwarded-Proto",
                "https"
            )


            host = request.host


            audio_url = (

                scheme
                + "://"
                + host
                + "/audio/"
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

            "transcription":
                None,

            "ai_reply":
                "AI response nahi mil saka.",

            "audio_url":
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
# START CLEANUP THREAD
# =====================================================

cleanup_thread = threading.Thread(

    target=cleanup_audio,

    daemon=True
)

cleanup_thread.start()


# =====================================================
# LOCAL START
# =====================================================

if __name__ == "__main__":

    print()
    print("==============================")
    print("ESP32 VOICE SERVER")
    print("==============================")

    print(
        "PORT:",
        PORT
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

    print("==============================")


    app.run(

        host="0.0.0.0",

        port=PORT,

        threaded=True
    )

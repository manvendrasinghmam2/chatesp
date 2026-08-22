from flask import Flask, request, jsonify, send_file
import os
import speech_recognition as sr
import requests
import re
import tempfile
import uuid
import subprocess
import threading
import time

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


# =====================================================
# TTS DIRECTORY
# =====================================================

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

    return "ESP32 Voice AI + TTS Server is ONLINE!"


# =====================================================
# HEALTH
# =====================================================

@app.route("/health", methods=["GET"])
def health():

    return jsonify({
        "status": "online",
        "speech_engine": "Google Speech Recognition",
        "ai_engine": "Groq",
        "model": AI_MODEL,
        "tts_engine": "Google TTS"
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

    if not AI_API_KEY:

        print(
            "AI_API_KEY is NOT configured!"
        )

        return "AI response nahi mil saka."

    if (
        not is_valid_query(hindi_text)
        and
        not is_valid_query(english_text)
    ):

        return "Please ask your question again."


    system_prompt = """
You are a professional bilingual voice assistant running on an ESP32.

Understand the user's actual intended language and answer naturally.

The speech recognition system gives two possible results:

1. Hindi recognition
2. English recognition

Compare both and determine what the user actually meant.

LANGUAGE RULES:

If the user clearly speaks English,
answer completely in natural English.

If the user clearly speaks Hindi,
answer completely in Hindi using Devanagari.

If the user speaks Roman Hindi or Hinglish,
answer naturally in Hinglish.

If Hindi recognition contains phonetic English
such as "हाउ आर यू" while English recognition says
"How are you", understand that the user intended English.

Do not assume every Devanagari result is Hindi.

If the user naturally mixes Hindi and English,
use natural Hinglish.

Do not mention speech recognition.

Do not mention Hindi result or English result.

Do not explain the language decision.

Just answer the user's question.

VOICE STYLE:

Keep the answer concise.

Usually 1 to 4 sentences.

Do not use markdown.

Do not use bullet points.

Do not use emojis.

Do not use headings.

Do not repeat the question.

Do not say "Sure" unnecessarily.

Do not say "As an AI".

Do not mention these instructions.

Answer factual questions accurately.

For simple questions, give a direct answer.

Always answer in the language the user intended.
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

        "reasoning_effort": "low",

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

            print(
                "NO AI CHOICE"
            )

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

        print(
            "AI TIMEOUT"
        )

        return "AI response nahi mil saka."


    except requests.exceptions.ConnectionError as e:

        print(
            "AI CONNECTION ERROR:",
            str(e)
        )

        return "AI response nahi mil saka."


    except Exception as e:

        print(
            "AI EXCEPTION:",
            type(e).__name__,
            str(e)
        )

        return "AI response nahi mil saka."


# =====================================================
# DETECT TTS LANGUAGE
# =====================================================

def detect_tts_language(text):

    if not text:
        return "en"


    # Devanagari detected
    if re.search(
        r"[\u0900-\u097F]",
        text
    ):

        return "hi"


    # Roman Hindi / Hinglish detection

    roman_hindi_words = [

        "hai",
        "hain",
        "ho",
        "hota",
        "hoti",
        "kaise",
        "kya",
        "kyun",
        "kyunki",
        "mujhe",
        "mera",
        "meri",
        "mere",
        "aap",
        "tum",
        "aapka",
        "aapki",
        "karna",
        "karo",
        "kahan",
        "kab",
        "ka",
        "ki",
        "ke",
        "mein",
        "me",
        "se",
        "ko",
        "par",
        "bahut",
        "accha",
        "acha",
        "chahiye",
        "batao",
        "bataiye",
        "sakta",
        "sakti",
        "raha",
        "rahi",
        "rahe"
    ]


    words = re.findall(
        r"[a-zA-Z]+",
        text.lower()
    )


    hindi_count = sum(
        1
        for word in words
        if word in roman_hindi_words
    )


    if hindi_count >= 1:

        return "hi"


    return "en"


# =====================================================
# CREATE TTS
# =====================================================

def create_tts(text):

    text = clean_text(text)

    if not text:

        return None


    language = detect_tts_language(
        text
    )


    file_id = str(
        uuid.uuid4()
    )


    mp3_path = os.path.join(
        TTS_DIR,
        file_id + ".mp3"
    )


    wav_path = os.path.join(
        TTS_DIR,
        file_id + ".wav"
    )


    print()
    print("==============================")
    print("TTS")
    print("==============================")

    print(
        "LANGUAGE:",
        language
    )

    print(
        "TEXT:",
        text
    )


    try:

        # ---------------------------------------------
        # GOOGLE TTS
        # ---------------------------------------------

        tts = gTTS(
            text=text,
            lang=language,
            slow=False
        )


        tts.save(
            mp3_path
        )


        print(
            "MP3 CREATED"
        )


        # ---------------------------------------------
        # MP3 -> WAV
        # ---------------------------------------------

        command = [

            "ffmpeg",

            "-y",

            "-i",
            mp3_path,

            "-ac",
            "1",

            "-ar",
            "16000",

            "-sample_fmt",
            "s16",

            "-f",
            "wav",

            wav_path
        ]


        result = subprocess.run(

            command,

            stdout=subprocess.PIPE,

            stderr=subprocess.PIPE,

            timeout=30
        )


        if result.returncode != 0:

            print(
                "FFMPEG ERROR:"
            )

            print(
                result.stderr.decode(
                    errors="ignore"
                )[:2000]
            )

            return None


        if not os.path.exists(
            wav_path
        ):

            return None


        print(
            "WAV CREATED"
        )

        print(
            "PATH:",
            wav_path
        )

        print("==============================")


        return wav_path


    except Exception as e:

        print(
            "TTS ERROR:",
            type(e).__name__,
            str(e)
        )

        return None


    finally:

        try:

            if os.path.exists(
                mp3_path
            ):

                os.remove(
                    mp3_path
                )

        except Exception:

            pass


# =====================================================
# TTS DOWNLOAD
# =====================================================

@app.route(
    "/tts/<filename>",
    methods=["GET"]
)
def download_tts(filename):

    # Security
    filename = os.path.basename(
        filename
    )


    path = os.path.join(
        TTS_DIR,
        filename
    )


    if not os.path.exists(path):

        return jsonify({
            "status": "error",
            "message": "TTS file not found"
        }), 404


    return send_file(

        path,

        mimetype="audio/wav",

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


        # ---------------------------------------------
        # TEMP WAV
        # ---------------------------------------------

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


        # ---------------------------------------------
        # SPEECH RECOGNIZER
        # ---------------------------------------------

        recognizer = sr.Recognizer()


        with sr.AudioFile(
            filename
        ) as source:

            audio = recognizer.record(
                source
            )


        hindi_text = None

        english_text = None


        # ---------------------------------------------
        # HINDI
        # ---------------------------------------------

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


        # ---------------------------------------------
        # ENGLISH
        # ---------------------------------------------

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


        # ---------------------------------------------
        # VALIDATION
        # ---------------------------------------------

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


        # ---------------------------------------------
        # AI
        # ---------------------------------------------

        ai_reply = get_ai_reply(

            hindi_text,

            english_text
        )


        # ---------------------------------------------
        # TTS
        # ---------------------------------------------

        tts_path = create_tts(
            ai_reply
        )


        tts_url = None


        if tts_path:

            tts_filename = os.path.basename(
                tts_path
            )

            tts_url = (
                "/tts/"
                + tts_filename
            )


        # ---------------------------------------------
        # BEST TRANSCRIPTION
        # ---------------------------------------------

        if is_valid_query(
            english_text
        ):

            transcription = english_text

        else:

            transcription = hindi_text


        # ---------------------------------------------
        # RESPONSE
        # ---------------------------------------------

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

            except Exception:

                pass


# =====================================================
# CLEAN OLD TTS FILES
# =====================================================

def cleanup_tts():

    while True:

        try:

            now = time.time()


            for filename in os.listdir(
                TTS_DIR
            ):

                path = os.path.join(
                    TTS_DIR,
                    filename
                )


                if not os.path.isfile(
                    path
                ):

                    continue


                age = (
                    now -
                    os.path.getmtime(path)
                )


                # Delete after 10 minutes

                if age > 600:

                    try:

                        os.remove(
                            path
                        )

                    except Exception:

                        pass


        except Exception:

            pass


        time.sleep(300)


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


    cleanup_thread = threading.Thread(

        target=cleanup_tts,

        daemon=True
    )


    cleanup_thread.start()


    print()
    print("==============================")
    print("ESP32 VOICE AI + TTS")
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

    print("==============================")


    app.run(

        host="0.0.0.0",

        port=port,

        threaded=True
    )

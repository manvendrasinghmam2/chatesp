from flask import Flask, request, jsonify, send_file
import os
import speech_recognition as sr
import requests
import re
import tempfile
import subprocess
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

        "model":
            AI_MODEL,

        "tts":
            "Google gTTS"
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
    print("WAKE REQUEST")
    print("==============================")

    if request.method == "POST":

        audio_data = request.get_data()

        print(
            "Audio bytes:",
            len(audio_data)
        )

    # IMPORTANT
    #
    # Testing ke liye FALSE.
    #
    # Isse ESP32 automatically
    # HELLO DETECTED nahi karega.
    #
    # Actual wake word detection
    # baad mein add kar sakte hain.

    response = {

        "status":
            "ok",

        "wake":
            False
    }

    print(
        "Wake response:",
        response
    )

    return jsonify(
        response
    )


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
        print("AI_API_KEY is missing")
        print("==============================")

        return "AI response nahi mil saka."


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

        return "Please ask your question again."


    # -------------------------------------------------
    # SYSTEM PROMPT
    # -------------------------------------------------

    system_prompt = """
You are a professional bilingual voice assistant.

The user is speaking to an ESP32 voice assistant.

You receive two speech recognition results:

1. Hindi recognition
2. English recognition

The recognition can sometimes be inaccurate.

Understand the user's actual intended meaning.

LANGUAGE RULES:

If the user clearly speaks English,
answer completely in natural English.

Example:

User:
How are you?

Answer:
I'm doing well, thank you. How can I help you today?

If the user clearly speaks Hindi,
answer completely in Hindi using Devanagari.

Example:

User:
आप कैसे हैं?

Answer:
मैं बिल्कुल ठीक हूँ। धन्यवाद। आप कैसे हैं?

If the user speaks Hinglish,
answer naturally in Hinglish.

Example:

User:
Tum kaise ho?

Answer:
Main bilkul theek hoon. Aap kaise hain?

Compare both recognition results.

Choose the interpretation that makes the most contextual sense.

Do not mention speech recognition.

Do not mention Hindi recognition.

Do not mention English recognition.

Do not explain your language decision.

The response will be converted into speech.

Keep answers concise.

Usually 1 to 4 sentences.

Do not use markdown.

Do not use bullet points.

Do not use emojis.

Do not use headings.

Do not repeat the question.

Do not say "As an AI".

Do not say "Sure" unnecessarily.

Answer naturally.
"""


    # -------------------------------------------------
    # USER CONTENT
    # -------------------------------------------------

    user_content = f"""
Hindi speech recognition:
{hindi_text if hindi_text else "No result"}

English speech recognition:
{english_text if english_text else "No result"}

Determine the user's intended meaning and answer naturally.
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
            "Model:",
            AI_MODEL
        )

        print(
            "Hindi:",
            hindi_text
        )

        print(
            "English:",
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
        print("AI HTTP STATUS")
        print("==============================")

        print(
            response.status_code
        )


        # -------------------------------------------------
        # API ERROR
        # -------------------------------------------------

        if response.status_code != 200:

            print(
                response.text[:2000]
            )

            return "AI response nahi mil saka."


        # -------------------------------------------------
        # JSON
        # -------------------------------------------------

        data = response.json()


        choices = data.get(
            "choices"
        )


        if not choices:

            print(
                "No choices in AI response"
            )

            print(
                data
            )

            return "AI response nahi mil saka."


        # -------------------------------------------------
        # MESSAGE
        # -------------------------------------------------

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


        # -------------------------------------------------
        # CLEAN AI RESPONSE
        # -------------------------------------------------

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

            return "AI response nahi mil saka."


        # -------------------------------------------------
        # PRINT AI
        # -------------------------------------------------

        print()
        print("==============================")
        print("AI REPLY")
        print("==============================")
        print(reply)
        print("==============================")


        return reply


    except requests.exceptions.Timeout:

        print(
            "AI timeout"
        )

        return "AI response nahi mil saka."


    except requests.exceptions.ConnectionError as e:

        print(
            "AI connection error:",
            str(e)
        )

        return "AI response nahi mil saka."


    except Exception as e:

        print(
            "AI exception:",
            type(e).__name__,
            str(e)
        )

        return "AI response nahi mil saka."


# =====================================================
# CREATE TTS MP3
# =====================================================

def create_tts_mp3(
    text,
    filename,
    language="en"
):

    text = clean_text(
        text
    )

    if not text:

        return False


    try:

        tts = gTTS(

            text=text,

            lang=language,

            slow=False
        )


        tts.save(
            filename
        )


        return os.path.exists(
            filename
        )


    except Exception as e:

        print()
        print("==============================")
        print("gTTS ERROR")
        print("==============================")

        print(
            type(e).__name__
        )

        print(
            str(e)
        )

        print("==============================")


        return False


# =====================================================
# MP3 -> WAV
# =====================================================

def convert_mp3_to_wav(
    mp3_file,
    wav_file
):

    try:

        command = [

            "ffmpeg",

            "-y",

            "-i",
            mp3_file,

            "-ac",
            "1",

            "-ar",
            "16000",

            "-sample_fmt",
            "s16",

            wav_file
        ]


        result = subprocess.run(

            command,

            stdout=subprocess.PIPE,

            stderr=subprocess.PIPE,

            timeout=60
        )


        if result.returncode != 0:

            print()
            print("==============================")
            print("FFMPEG ERROR")
            print("==============================")

            print(
                result.stderr.decode(
                    errors="ignore"
                )[-3000:]
            )

            print("==============================")


            return False


        return os.path.exists(
            wav_file
        )


    except FileNotFoundError:

        print()
        print("==============================")
        print("FFMPEG NOT FOUND")
        print("==============================")

        print(
            "FFmpeg is not installed on server."
        )

        print("==============================")


        return False


    except Exception as e:

        print(
            "FFmpeg exception:",
            str(e)
        )

        return False


# =====================================================
# TTS WAV
# =====================================================

@app.route(
    "/tts",
    methods=["POST"]
)
def tts():

    mp3_file = None

    wav_file = None


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


        text = data.get(
            "text",
            ""
        )


        text = clean_text(
            text
        )


        if not text:

            return jsonify({

                "status":
                    "error",

                "message":
                    "No text received"

            }), 400


        language = data.get(
            "language",
            "en"
        )


        language = str(
            language
        )


        if language not in [
            "en",
            "hi"
        ]:

            language = "en"


        mp3_file = tempfile.mktemp(
            suffix=".mp3"
        )


        wav_file = tempfile.mktemp(
            suffix=".wav"
        )


        print()
        print("==============================")
        print("TTS")
        print("==============================")

        print(
            "Text:",
            text
        )

        print(
            "Language:",
            language
        )


        # -------------------------------------------------
        # gTTS
        # -------------------------------------------------

        ok = create_tts_mp3(

            text,

            mp3_file,

            language
        )


        if not ok:

            return jsonify({

                "status":
                    "error",

                "message":
                    "TTS generation failed"

            }), 500


        # -------------------------------------------------
        # MP3 -> WAV
        # -------------------------------------------------

        ok = convert_mp3_to_wav(

            mp3_file,

            wav_file
        )


        if not ok:

            return jsonify({

                "status":
                    "error",

                "message":
                    "MP3 to WAV conversion failed"

            }), 500


        print(
            "TTS WAV ready"
        )

        print("==============================")


        return send_file(

            wav_file,

            mimetype=
                "audio/wav",

            as_attachment=False,

            download_name=
                "reply.wav"
        )


    except Exception as e:

        print(
            "TTS endpoint error:",
            str(e)
        )


        return jsonify({

            "status":
                "error",

            "message":
                str(e)

        }), 500


    finally:

        # Files ko immediately delete nahi karenge
        # because send_file ko file chahiye hoti hai.
        #
        # Temporary files OS cleanup ke liye chhod diye ja rahe hain.


        pass


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

                "transcription":
                    None,

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
        # SAVE WAV
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
                    "Speech service error"

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
                    "Speech service error"

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

            print(
                "Speech not understood."
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
        # USER PRINT
        # =================================================

        print()
        print("==============================")
        print("USER:")
        print("==============================")

        print(
            transcription
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
        print("FINAL")
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


    print("==============================")


    app.run(

        host="0.0.0.0",

        port=port,

        threaded=True
    )

from flask import Flask, request, jsonify, Response
import os
import speech_recognition as sr
import requests
import re
import tempfile
import subprocess

from gtts import gTTS
import imageio_ffmpeg


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
# TTS SETTINGS
# =====================================================

TTS_SAMPLE_RATE = 22050


# =====================================================
# TEMP STORAGE
# =====================================================

LAST_AI_REPLY = ""

LAST_TTS_LANGUAGE = "en"


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
        "model": AI_MODEL,
        "tts": "Google gTTS",
        "tts_format": "WAV 22050Hz mono 16-bit"
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
# HINDI / ENGLISH DETECTION
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
# WAKE
# =====================================================

@app.route(
    "/wake",
    methods=["POST"]
)
def wake():

    print()
    print("================================")
    print("WAKE REQUEST")
    print("================================")

    audio_data = request.get_data()

    print(
        "Audio bytes:",
        len(audio_data)
    )

    if not audio_data:

        return jsonify({
            "status": "error",
            "wake": False
        }), 400

    filename = None

    try:

        fd, filename = tempfile.mkstemp(
            suffix=".wav"
        )

        os.close(fd)

        with open(
            filename,
            "wb"
        ) as f:

            f.write(audio_data)

        recognizer = sr.Recognizer()

        with sr.AudioFile(
            filename
        ) as source:

            audio = recognizer.record(
                source
            )

        # =================================================
        # ENGLISH HELLO
        # =================================================

        english = None

        try:

            english = recognizer.recognize_google(
                audio,
                language="en-IN"
            )

        except Exception:
            english = None

        print(
            "Wake English:",
            english
        )

        # =================================================
        # HINDI
        # =================================================

        hindi = None

        try:

            hindi = recognizer.recognize_google(
                audio,
                language="hi-IN"
            )

        except Exception:
            hindi = None

        print(
            "Wake Hindi:",
            hindi
        )

        # =================================================
        # CHECK HELLO
        # =================================================

        wake_detected = False

        candidates = [
            english,
            hindi
        ]

        wake_words = [
            "hello",
            "helo",
            "hallo",
            "hellow",
            "हेलो",
            "हैलो"
        ]

        for text in candidates:

            if not text:
                continue

            normalized = (
                text
                .lower()
                .strip()
            )

            for word in wake_words:

                if word in normalized:

                    wake_detected = True
                    break

            if wake_detected:
                break

        print(
            "WAKE:",
            wake_detected
        )

        print(
            "================================"
        )

        return jsonify({

            "status":
                "ok",

            "wake":
                wake_detected,

            "english":
                english,

            "hindi":
                hindi

        })

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

            "message":
                str(e)

        }), 500

    finally:

        if filename:

            try:

                if os.path.exists(filename):
                    os.remove(filename)

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

Understand the user's intended language and answer naturally.

LANGUAGE RULES:

If the user clearly speaks English,
answer completely in natural English.

If the user clearly speaks Hindi,
answer completely in Hindi using Devanagari script.

If the user speaks Roman Hindi or Hinglish,
answer in natural Hinglish using Roman script.

If English speech was incorrectly recognized as
phonetic Hindi, understand the intended English
meaning and answer in English.

Compare Hindi and English recognition results
and choose the interpretation that makes the most
linguistic and contextual sense.

Do not mention speech recognition.

Do not explain your language decision.

VOICE STYLE:

The response will be spoken aloud.

Keep it concise.

Usually 1 to 4 sentences.

Do not use markdown.

Do not use bullet points.

Do not use emojis.

Do not use headings.

Do not repeat the question.

Do not say "Sure" unnecessarily.

Do not say "As an AI".

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
        print("================================")
        print("AI REQUEST")
        print("================================")

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
                "AI ERROR:",
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

        print()
        print("AI REPLY:")
        print(reply)

        print(
            "================================"
        )

        return reply

    except requests.exceptions.Timeout:

        print("AI TIMEOUT")

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

    global LAST_AI_REPLY
    global LAST_TTS_LANGUAGE

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
        print("================================")
        print("AUDIO RECEIVED")
        print("================================")

        print(
            "Audio bytes:",
            len(audio_data)
        )

        # =================================================
        # SAVE WAV
        # =================================================

        fd, filename = tempfile.mkstemp(
            suffix=".wav"
        )

        os.close(fd)

        with open(
            filename,
            "wb"
        ) as f:

            f.write(audio_data)

        # =================================================
        # SPEECH RECOGNITION
        # =================================================

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
                    "Speech service error."

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
                    "Speech service error."

            }), 500

        # =================================================
        # PRINT SPEECH
        # =================================================

        print()
        print("================================")
        print("SPEECH RESULTS")
        print("================================")

        print(
            "Hindi:",
            hindi_text
        )

        print(
            "English:",
            english_text
        )

        print(
            "================================"
        )

        # =================================================
        # VALIDATION
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
                    "Please ask your question again."

            }), 400

        # =================================================
        # AI
        # =================================================

        ai_reply = get_ai_reply(

            hindi_text,

            english_text
        )

        LAST_AI_REPLY = ai_reply

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
        # TTS LANGUAGE
        # =================================================

        if contains_devanagari(
            ai_reply
        ):

            LAST_TTS_LANGUAGE = "hi"

        else:

            LAST_TTS_LANGUAGE = "en"

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
        print("================================")
        print("FINAL RESPONSE")
        print("================================")

        print(
            "USER:",
            transcription
        )

        print(
            "AI:",
            ai_reply
        )

        print(
            "TTS LANGUAGE:",
            LAST_TTS_LANGUAGE
        )

        print(
            "================================"
        )

        return jsonify(
            response_data
        )

    except Exception as e:

        print()
        print("================================")
        print("SERVER ERROR")
        print("================================")

        print(
            type(e).__name__
        )

        print(
            str(e)
        )

        print(
            "================================"
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
# TTS
#
# ESP32 POST:
#
# {
#   "text": "Hello"
# }
#
# Server returns:
#
# WAV
# 22050 Hz
# mono
# 16-bit PCM
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
                "status": "error",
                "message": "No JSON"
            }), 400

        text = clean_text(
            data.get("text")
        )

        if not text:

            return jsonify({
                "status": "error",
                "message": "No text"
            }), 400

        print()
        print("================================")
        print("TTS REQUEST")
        print("================================")

        print(
            "Text:",
            text
        )

        # =================================================
        # LANGUAGE
        # =================================================

        if contains_devanagari(text):

            language = "hi"

        else:

            language = "en"

        print(
            "Language:",
            language
        )

        # =================================================
        # FILES
        # =================================================

        mp3_fd, mp3_file = tempfile.mkstemp(
            suffix=".mp3"
        )

        os.close(mp3_fd)

        wav_fd, wav_file = tempfile.mkstemp(
            suffix=".wav"
        )

        os.close(wav_fd)

        # =================================================
        # gTTS
        # =================================================

        tts = gTTS(

            text=text,

            lang=language,

            slow=False
        )

        tts.save(
            mp3_file
        )

        print(
            "gTTS generated."
        )

        # =================================================
        # FFMPEG
        # =================================================

        ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()

        command = [

            ffmpeg,

            "-y",

            "-i",
            mp3_file,

            "-ac",
            "1",

            "-ar",
            str(TTS_SAMPLE_RATE),

            "-sample_fmt",
            "s16",

            "-f",
            "wav",

            wav_file
        ]

        print(
            "Converting MP3 -> WAV..."
        )

        result = subprocess.run(

            command,

            stdout=subprocess.PIPE,

            stderr=subprocess.PIPE,

            timeout=60
        )

        if result.returncode != 0:

            print(
                result.stderr.decode(
                    errors="ignore"
                )[-2000:]
            )

            return jsonify({

                "status":
                    "error",

                "message":
                    "FFmpeg conversion failed"

            }), 500

        print(
            "WAV generated."
        )

        # =================================================
        # READ WAV
        # =================================================

        with open(
            wav_file,
            "rb"
        ) as f:

            wav_data = f.read()

        print(
            "WAV bytes:",
            len(wav_data)
        )

        print(
            "================================"
        )

        return Response(

            wav_data,

            status=200,

            mimetype="audio/wav",

            headers={

                "Content-Length":
                    str(len(wav_data)),

                "Cache-Control":
                    "no-cache",

                "Connection":
                    "close"
            }
        )

    except Exception as e:

        print()
        print(
            "TTS ERROR:",
            type(e).__name__,
            str(e)
        )

        return jsonify({

            "status":
                "error",

            "message":
                str(e)

        }), 500

    finally:

        for filename in [
            mp3_file,
            wav_file
        ]:

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
    print("================================")
    print("ESP32 VOICE SERVER")
    print("================================")

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
        "TTS:",
        "gTTS + FFmpeg"
    )

    print(
        "================================"
    )

    app.run(
        host="0.0.0.0",
        port=port,
        threaded=True
    )

from flask import Flask, request, jsonify, Response
import os
import re
import tempfile
import io
import wave

import speech_recognition as sr
import requests

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
        "model": AI_MODEL,
        "tts": "gTTS"
    })


# =====================================================
# WAKE
#
# IMPORTANT:
#
# Pehle tumhare code me wake=True hard-coded tha.
#
# Isliye ESP32:
#
# Listening for HELLO...
# HELLO DETECTED!
#
# har baar kar raha tha.
#
# Abhi testing ke liye actual speech recognition
# use ki ja rahi hai.
# =====================================================

@app.route("/wake", methods=["POST"])
def wake():

    print()
    print("==============================")
    print("WAKE REQUEST")
    print("==============================")

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

            f.write(audio_data)

        # -------------------------------------------------
        # RECOGNIZER
        # -------------------------------------------------

        recognizer = sr.Recognizer()

        with sr.AudioFile(filename) as source:

            audio = recognizer.record(source)

        text = None

        # -------------------------------------------------
        # ENGLISH
        # -------------------------------------------------

        try:

            text = recognizer.recognize_google(
                audio,
                language="en-IN"
            )

        except sr.UnknownValueError:

            text = None

        except sr.RequestError as e:

            print(
                "Wake speech error:",
                str(e)
            )

            return jsonify({
                "status": "error",
                "wake": False
            }), 500

        # -------------------------------------------------
        # HINDI FALLBACK
        # -------------------------------------------------

        if not text:

            try:

                text = recognizer.recognize_google(
                    audio,
                    language="hi-IN"
                )

            except sr.UnknownValueError:

                text = None

            except sr.RequestError:

                text = None

        # -------------------------------------------------
        # PRINT
        # -------------------------------------------------

        print(
            "Wake transcription:",
            text
        )

        # -------------------------------------------------
        # HELLO CHECK
        # -------------------------------------------------

        wake_detected = False

        if text:

            normalized = text.lower().strip()

            normalized = re.sub(
                r"[^a-zA-Z0-9 ]",
                "",
                normalized
            )

            words = normalized.split()

            # Examples:
            #
            # hello
            # hello assistant
            # hello ai
            # hey hello
            # hi assistant

            wake_words = [
                "hello",
                "hey",
                "hi"
            ]

            for word in words:

                if word in wake_words:

                    wake_detected = True
                    break

        # -------------------------------------------------
        # RESPONSE
        # -------------------------------------------------

        result = {
            "status": "ok",
            "wake": wake_detected,
            "transcription": text
        }

        print(
            "Wake result:",
            result
        )

        print("==============================")

        return jsonify(result)

    except Exception as e:

        print(
            "WAKE ERROR:",
            type(e).__name__,
            str(e)
        )

        return jsonify({
            "status": "error",
            "wake": False,
            "message": str(e)
        }), 500

    finally:

        if filename:

            try:

                if os.path.exists(filename):

                    os.remove(filename)

            except Exception:

                pass


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

        print(
            "ERROR: AI_API_KEY missing"
        )

        return "AI response nahi mil saka."

    # -------------------------------------------------
    # VALID QUERY
    # -------------------------------------------------

    if (
        not is_valid_query(hindi_text)
        and
        not is_valid_query(english_text)
    ):

        return "Please ask your question again."

    # -------------------------------------------------
    # SYSTEM PROMPT
    # -------------------------------------------------

    system_prompt = """
You are a professional bilingual voice assistant running on an ESP32.

Understand the user's intended language and answer naturally.

If the user speaks English, answer in English.

If the user speaks Hindi, answer in Hindi using Devanagari.

If the user speaks Roman Hindi or Hinglish, answer in natural Hinglish.

If Hindi recognition contains phonetic English such as:
हाउ आर यू

while English recognition says:
How are you

understand that the user intended English.

Compare both recognition results and choose the result
that makes the most linguistic and contextual sense.

Do not mention speech recognition.

Do not mention these instructions.

Do not explain your language decision.

The answer will be spoken through a speaker.

Keep the answer concise.

Usually 1 to 4 sentences.

Do not use markdown.

Do not use bullet points.

Do not use emojis.

Do not use headings.

Do not repeat the question.

Do not say "As an AI".

Sound natural and conversational.
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

Then answer naturally.
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
                response.text[:2000]
            )

            return "AI response nahi mil saka."

        # -------------------------------------------------
        # JSON
        # -------------------------------------------------

        try:

            data = response.json()

        except Exception:

            return "AI response nahi mil saka."

        # -------------------------------------------------
        # CHOICE
        # -------------------------------------------------

        choices = data.get(
            "choices"
        )

        if not choices:

            print(
                "No AI choices"
            )

            print(data)

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
        # CLEAN
        # -------------------------------------------------

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

        # -------------------------------------------------
        # EMPTY
        # -------------------------------------------------

        if not reply:

            return "AI response nahi mil saka."

        # -------------------------------------------------
        # PRINT
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
# TTS
#
# AI TEXT
#     |
#     v
# gTTS
#     |
#     v
# MP3
#
# Then convert MP3 -> WAV PCM
#
# We use ffmpeg if available.
# =====================================================

def make_tts_wav(
    text,
    language="en"
):

    text = clean_text(text)

    if not text:

        return None

    mp3_file = None
    wav_file = None

    try:

        # -------------------------------------------------
        # TEMP MP3
        # -------------------------------------------------

        fd, mp3_file = tempfile.mkstemp(
            suffix=".mp3"
        )

        os.close(fd)

        # -------------------------------------------------
        # LANGUAGE
        # -------------------------------------------------

        language = str(
            language
        ).lower()

        if language.startswith("hi"):

            tts_lang = "hi"

        else:

            tts_lang = "en"

        # -------------------------------------------------
        # gTTS
        # -------------------------------------------------

        print()
        print("==============================")
        print("TTS")
        print("==============================")

        print(
            "Language:",
            tts_lang
        )

        print(
            "Text:",
            text
        )

        tts = gTTS(
            text=text,
            lang=tts_lang,
            slow=False
        )

        tts.save(
            mp3_file
        )

        # -------------------------------------------------
        # CONVERT MP3 -> WAV
        # -------------------------------------------------

        fd, wav_file = tempfile.mkstemp(
            suffix=".wav"
        )

        os.close(fd)

        # Use ffmpeg installed on Render
        #
        # 16 kHz
        # mono
        # signed 16-bit PCM

        command = (
            "ffmpeg "
            "-y "
            "-loglevel error "
            "-i "
            f'"{mp3_file}" '
            "-ar 16000 "
            "-ac 1 "
            "-sample_fmt s16 "
            f'"{wav_file}"'
        )

        exit_code = os.system(
            command
        )

        if exit_code != 0:

            print(
                "FFMPEG failed"
            )

            return None

        # -------------------------------------------------
        # READ WAV
        # -------------------------------------------------

        with open(
            wav_file,
            "rb"
        ) as f:

            wav_data = f.read()

        print(
            "WAV bytes:",
            len(wav_data)
        )

        print("==============================")

        return wav_data

    except Exception as e:

        print()
        print("==============================")
        print("TTS ERROR")
        print("==============================")

        print(
            type(e).__name__,
            str(e)
        )

        print("==============================")

        return None

    finally:

        if mp3_file:

            try:

                if os.path.exists(mp3_file):

                    os.remove(mp3_file)

            except Exception:

                pass

        if wav_file:

            try:

                if os.path.exists(wav_file):

                    os.remove(wav_file)

            except Exception:

                pass


# =====================================================
# DETECT LANGUAGE
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

    # Prefer English when valid English
    # recognition exists.

    if is_valid_query(
        english_text
    ):

        return "en"

    if is_valid_query(
        hindi_text
    ):

        # If Hindi result contains Devanagari,
        # use Hindi voice.

        if re.search(
            r"[\u0900-\u097F]",
            hindi_text
        ):

            return "hi"

        # Roman Hindi / Hinglish
        # gTTS Hindi is usually better.

        return "hi"

    return "en"


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

            f.write(audio_data)

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

            hindi_text = None

            print(
                "Hindi not understood."
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

            english_text = None

            print(
                "English not understood."
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

            print(
                "Speech not understood"
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
                    "Please ask your question again.",

                "tts_available":
                    False

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
        # TTS LANGUAGE
        # =================================================

        tts_language = detect_tts_language(

            hindi_text,

            english_text
        )

        # =================================================
        # TTS WAV
        # =================================================

        tts_wav = make_tts_wav(

            ai_reply,

            tts_language
        )

        # =================================================
        # RESULT
        # =================================================

        if tts_wav:

            tts_available = True

        else:

            tts_available = False

        print()
        print("==============================")
        print("FINAL")
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
            "TTS:",
            tts_available
        )

        print("==============================")

        # =================================================
        # JSON
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

            "tts_available":
                tts_available,

            "tts_language":
                tts_language
        }

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

            "tts_available":
                False

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
# TTS TEST
#
# Browser / ESP32 can request:
#
# /tts?text=Hello
# =====================================================

@app.route(
    "/tts",
    methods=["GET"]
)
def tts_endpoint():

    text = request.args.get(
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
                "No text"

        }), 400

    language = request.args.get(
        "lang",
        "en"
    )

    wav_data = make_tts_wav(
        text,
        language
    )

    if not wav_data:

        return jsonify({

            "status":
                "error",

            "message":
                "TTS failed"

        }), 500

    return Response(

        wav_data,

        mimetype="audio/wav",

        headers={
            "Content-Length":
                str(len(wav_data)),

            "Cache-Control":
                "no-cache"
        }
    )


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

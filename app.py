from flask import Flask, request, jsonify, Response
import os
import speech_recognition as sr
import requests
import re
import tempfile
import traceback
import wave
import time


app = Flask(__name__)


# ============================================================
# CONFIG
# ============================================================

AI_API_KEY = os.environ.get("AI_API_KEY")

AI_URL = os.environ.get(
    "AI_URL",
    "https://api.groq.com/openai/v1/chat/completions"
)

AI_MODEL = os.environ.get(
    "AI_MODEL",
    "openai/gpt-oss-20b"
)


# ============================================================
# TTS CONFIG
# ============================================================

TTS_URL = os.environ.get(
    "TTS_URL",
    "https://api.groq.com/openai/v1/audio/speech"
)

TTS_MODEL = os.environ.get(
    "TTS_MODEL",
    "canopylabs/orpheus-v1-english"
)

# Hannah voice
TTS_VOICE = os.environ.get(
    "TTS_VOICE",
    "hannah"
)

# Groq Orpheus input limit
TTS_MAX_CHARS = 200


# ============================================================
# DEBUG CONFIG
# ============================================================

DEBUG_MODE = True

AI_TIMEOUT = 35
TTS_TIMEOUT = 60
SPEECH_TIMEOUT = 20


# ============================================================
# GLOBAL STATS
# ============================================================

REQUEST_COUNT = 0
AI_COUNT = 0
TTS_COUNT = 0
SPEECH_COUNT = 0


# ============================================================
# HOME
# ============================================================

@app.route("/", methods=["GET"])
def home():

    return "ESP32 Voice Server is ONLINE!"


# ============================================================
# HEALTH
# ============================================================

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

        "tts_engine":
            "Groq Orpheus",

        "tts_model":
            TTS_MODEL,

        "tts_voice":
            TTS_VOICE,

        "ai_key":
            "configured" if AI_API_KEY else "missing",

        "debug":
            DEBUG_MODE
    })


# ============================================================
# DEBUG PRINT
# ============================================================

def debug_print(*args):

    if DEBUG_MODE:
        print(*args, flush=True)


# ============================================================
# CLEAN TEXT
# ============================================================

def clean_text(text):

    if text is None:
        return ""

    text = str(text)

    text = text.strip()

    text = text.replace(
        "```",
        ""
    )

    text = re.sub(
        r"[\r\n]+",
        " ",
        text
    )

    text = re.sub(
        r"\s+",
        " ",
        text
    )

    return text.strip()


# ============================================================
# TTS TEXT CLEANING
# ============================================================

def clean_tts_text(text):

    text = clean_text(text)

    if not text:
        return ""

    prefixes = [
        "AI:",
        "Answer:",
        "Response:",
        "Assistant:"
    ]

    for prefix in prefixes:

        if text.lower().startswith(
            prefix.lower()
        ):

            text = text[
                len(prefix):
            ].strip()

    # Markdown remove
    text = text.replace(
        "**",
        ""
    )

    text = text.replace(
        "__",
        ""
    )

    text = text.replace(
        "*",
        ""
    )

    # Remove non ASCII
    # Orpheus English model ke liye
    text = re.sub(
        r"[^\x00-\x7F]+",
        " ",
        text
    )

    text = re.sub(
        r"\s+",
        " ",
        text
    )

    text = text.strip()

    # ========================================================
    # MAX 200 CHARACTERS
    # ========================================================

    if len(text) > TTS_MAX_CHARS:

        debug_print(
            "TTS TEXT TOO LONG:",
            len(text)
        )

        text = text[
            :TTS_MAX_CHARS
        ]

        positions = [

            text.rfind("."),

            text.rfind("?"),

            text.rfind("!"),

            text.rfind(",")

        ]

        best = max(
            positions
        )

        if best >= 40:

            text = text[
                :best + 1
            ]

    return text.strip()


# ============================================================
# VALID QUERY
# ============================================================

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


# ============================================================
# WAV DEBUG
# ============================================================

def inspect_wav(filename):

    debug_print("")
    debug_print("========================================")
    debug_print("WAV DEBUG INSPECTION")
    debug_print("========================================")

    try:

        file_size = os.path.getsize(
            filename
        )

        debug_print(
            "FILE SIZE:",
            file_size,
            "bytes"
        )

        with wave.open(
            filename,
            "rb"
        ) as wav:

            channels = wav.getnchannels()

            sample_width = wav.getsampwidth()

            sample_rate = wav.getframerate()

            frames = wav.getnframes()

            duration = (
                frames / sample_rate
                if sample_rate > 0
                else 0
            )

            compression = wav.getcomptype()

            compression_name = wav.getcompname()

            debug_print(
                "WAV CHANNELS:",
                channels
            )

            debug_print(
                "WAV SAMPLE WIDTH:",
                sample_width,
                "bytes"
            )

            debug_print(
                "WAV SAMPLE RATE:",
                sample_rate,
                "Hz"
            )

            debug_print(
                "WAV FRAMES:",
                frames
            )

            debug_print(
                "WAV DURATION:",
                round(duration, 3),
                "seconds"
            )

            debug_print(
                "WAV COMPRESSION:",
                compression
            )

            debug_print(
                "WAV COMPRESSION NAME:",
                compression_name
            )

            if (
                channels == 1
                and
                sample_width == 2
                and
                sample_rate in [
                    8000,
                    16000,
                    22050,
                    24000,
                    44100,
                    48000
                ]
                and
                compression == "NONE"
            ):

                debug_print(
                    "WAV FORMAT CHECK: OK"
                )

            else:

                debug_print(
                    "WAV FORMAT CHECK: CHECK REQUIRED"
                )

    except Exception as e:

        debug_print(
            "WAV INSPECTION ERROR:",
            type(e).__name__,
            str(e)
        )

    debug_print(
        "========================================"
    )


# ============================================================
# WAV AUDIO CONTENT DEBUG
# ============================================================

def inspect_audio_energy(filename):

    debug_print("")
    debug_print(
        "AUDIO CONTENT DEBUG"
    )

    try:

        with wave.open(
            filename,
            "rb"
        ) as wav:

            frames = wav.readframes(
                wav.getnframes()
            )

            if not frames:

                debug_print(
                    "AUDIO DATA: EMPTY"
                )

                return

            # Basic byte variation check
            unique_sample_bytes = len(
                set(frames[:10000])
            )

            debug_print(
                "AUDIO RAW BYTES:",
                len(frames)
            )

            debug_print(
                "AUDIO BYTE VARIATION:",
                unique_sample_bytes
            )

            if unique_sample_bytes <= 2:

                debug_print(
                    "WARNING: AUDIO MAY BE SILENCE"
                )

            else:

                debug_print(
                    "AUDIO CONTENT: DATA PRESENT"
                )

    except Exception as e:

        debug_print(
            "AUDIO ENERGY ERROR:",
            type(e).__name__,
            str(e)
        )


# ============================================================
# WAKE
# ============================================================

@app.route(
    "/wake",
    methods=["POST", "GET"]
)
def wake():

    debug_print("")
    debug_print(
        "========================================"
    )
    debug_print(
        "WAKE REQUEST RECEIVED"
    )
    debug_print(
        "========================================"
    )

    try:

        audio_data = request.get_data()

        debug_print(
            "WAKE AUDIO BYTES:",
            len(audio_data)
        )

        response_data = {

            "status":
                "ok",

            "wake":
                True,

            "english":
                "Hello",

            "hindi":
                None
        }

        return jsonify(
            response_data
        )

    except Exception as e:

        debug_print(
            "WAKE ERROR:",
            type(e).__name__,
            str(e)
        )

        return jsonify({

            "status":
                "error",

            "message":
                str(e)

        }), 500


# ============================================================
# TEST
# ============================================================

@app.route(
    "/test",
    methods=["POST"]
)
def test():

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

        return jsonify({

            "status":
                "ok",

            "message":
                "Data received",

            "data":
                data

        })

    except Exception as e:

        return jsonify({

            "status":
                "error",

            "message":
                str(e)

        }), 500


# ============================================================
# AI
# ============================================================

def get_ai_reply(
    hindi_text,
    english_text
):

    global AI_COUNT

    AI_COUNT += 1

    hindi_text = clean_text(
        hindi_text
    )

    english_text = clean_text(
        english_text
    )

    debug_print("")
    debug_print(
        "========================================"
    )
    debug_print(
        "AI REQUEST #",
        AI_COUNT
    )
    debug_print(
        "========================================"
    )

    debug_print(
        "AI HINDI INPUT:",
        hindi_text
    )

    debug_print(
        "AI ENGLISH INPUT:",
        english_text
    )

    if not AI_API_KEY:

        debug_print(
            "AI ERROR: AI_API_KEY MISSING"
        )

        return (
            "No AI response. Try again."
        )

    if (
        not is_valid_query(hindi_text)
        and
        not is_valid_query(english_text)
    ):

        debug_print(
            "AI ERROR: INVALID QUERY"
        )

        return (
            "Please ask your question again."
        )

    # ========================================================
    # SYSTEM PROMPT
    # ========================================================

    system_prompt = """
You are Hannah, a concise bilingual voice assistant.

Your main knowledge/help area is:

STEM education
Artificial Intelligence
AI
Robotics
Electronics
Embedded systems
Microcontrollers
ESP32
Arduino
Sensors
Automation
Programming
Aerospace
Avitron Aerospace Pvt Ltd
Noida
STEM education projects

You may also answer simple normal conversation such as:

Hello
Hi
How are you?
What is your name?
Who are you?
What can you do?
Thank you
Good morning
Good night

For unrelated questions, politely say:

Sorry, I can only help with STEM education, AI, robotics,
electronics, embedded systems, aerospace, and related topics.
Please ask me something related to these areas.

LANGUAGE RULES:

VERY IMPORTANT.

If the user's actual spoken query is English,
answer ONLY in natural English.

Example:

User:
How are you?

Correct:
I am doing great. How can I help you?

Incorrect:
Main theek hoon.

If the user's actual spoken query is Hindi,
answer in natural Roman Hindi.

Example:

User:
तुम कैसे हो?

Correct:
Main bilkul theek hoon. Aap kaise hain?

If the user speaks Hinglish,
answer in natural Hinglish.

Example:

User:
Aap robotics ke baare mein kya bata sakte ho?

Correct:
Robotics mein main sensors, motors, controllers aur AI ke baare mein help kar sakti hoon.

DO NOT use Devanagari Hindi in the answer.

Hindi must be written using English/Roman letters.

IMPORTANT:
Do not decide language from the translated recognition result alone.
Look at the user's original speech recognition results and determine
whether the user intended English, Hindi, or Hinglish.

Keep responses suitable for voice.

Usually 1 to 3 short sentences.

Maximum around 350 characters.

No markdown.
No bullet points.
No emojis.
No headings.
No unnecessary explanation.
Do not repeat the question.

Return ONLY the answer.

Your name is Hannah.
"""

    user_content = f"""
Hindi speech recognition:
{hindi_text if hindi_text else "No result"}

English speech recognition:
{english_text if english_text else "No result"}

Determine the user's intended language and meaning.

If English was spoken, answer in English.

If Hindi was spoken, answer in Roman Hindi.

If Hinglish was spoken, answer in Hinglish.

Return only the final voice response.
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
            300,

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

    start_time = time.time()

    try:

        debug_print(
            "AI URL:",
            AI_URL
        )

        debug_print(
            "AI MODEL:",
            AI_MODEL
        )

        debug_print(
            "SENDING AI REQUEST..."
        )

        response = requests.post(

            AI_URL,

            headers=headers,

            json=payload,

            timeout=AI_TIMEOUT
        )

        elapsed = round(
            time.time() - start_time,
            2
        )

        debug_print(
            "AI HTTP:",
            response.status_code
        )

        debug_print(
            "AI TIME:",
            elapsed,
            "seconds"
        )

        debug_print(
            "AI RESPONSE CONTENT TYPE:",
            response.headers.get(
                "Content-Type"
            )
        )

        if response.status_code != 200:

            debug_print(
                "========================================"
            )

            debug_print(
                "AI SERVER ERROR BODY:"
            )

            debug_print(
                response.text[:5000]
            )

            debug_print(
                "========================================"
            )

            return (
                "No AI response. Try again."
            )

        try:

            data = response.json()

        except Exception as e:

            debug_print(
                "AI JSON PARSE ERROR:",
                type(e).__name__,
                str(e)
            )

            debug_print(
                "RAW RESPONSE:",
                response.text[:3000]
            )

            return (
                "No AI response. Try again."
            )

        debug_print(
            "AI JSON RECEIVED"
        )

        choices = data.get(
            "choices"
        )

        if not choices:

            debug_print(
                "AI ERROR: choices missing"
            )

            debug_print(
                "AI DATA:",
                data
            )

            return (
                "No AI response. Try again."
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

        reply = clean_text(
            reply
        )

        prefixes = [

            "AI:",

            "Answer:",

            "Response:",

            "Assistant:"

        ]

        for prefix in prefixes:

            if reply.lower().startswith(
                prefix.lower()
            ):

                reply = reply[
                    len(prefix):
                ].strip()

        if not reply:

            debug_print(
                "AI ERROR: EMPTY REPLY"
            )

            return (
                "No AI response. Try again."
            )

        debug_print("")
        debug_print(
            "AI FINAL REPLY:"
        )
        debug_print(
            reply
        )

        debug_print(
            "========================================"
        )

        return reply

    except requests.exceptions.Timeout:

        debug_print(
            "AI TIMEOUT after",
            AI_TIMEOUT,
            "seconds"
        )

        return (
            "No AI response. Try again."
        )

    except requests.exceptions.ConnectionError as e:

        debug_print(
            "AI CONNECTION ERROR:",
            str(e)
        )

        return (
            "No AI response. Try again."
        )

    except Exception as e:

        debug_print(
            "AI EXCEPTION:",
            type(e).__name__,
            str(e)
        )

        traceback.print_exc()

        return (
            "No AI response. Try again."
        )


# ============================================================
# TTS
# ============================================================

def generate_tts(text):

    global TTS_COUNT

    TTS_COUNT += 1

    text = clean_tts_text(
        text
    )

    debug_print("")
    debug_print(
        "========================================"
    )
    debug_print(
        "TTS REQUEST #",
        TTS_COUNT
    )
    debug_print(
        "========================================"
    )

    debug_print(
        "TTS TEXT:",
        text
    )

    debug_print(
        "TTS TEXT LENGTH:",
        len(text)
    )

    debug_print(
        "TTS MODEL:",
        TTS_MODEL
    )

    debug_print(
        "TTS VOICE:",
        TTS_VOICE
    )

    debug_print(
        "TTS URL:",
        TTS_URL
    )

    if not text:

        debug_print(
            "TTS ERROR: EMPTY TEXT"
        )

        return None

    if not AI_API_KEY:

        debug_print(
            "TTS ERROR: AI_API_KEY MISSING"
        )

        return None

    payload = {

        "model":
            TTS_MODEL,

        "input":
            text,

        "voice":
            TTS_VOICE,

        "response_format":
            "wav"
    }

    headers = {

        "Authorization":
            "Bearer " + AI_API_KEY,

        "Content-Type":
            "application/json",

        "Accept":
            "audio/wav"
    }

    start_time = time.time()

    try:

        debug_print(
            "SENDING TTS REQUEST..."
        )

        response = requests.post(

            TTS_URL,

            headers=headers,

            json=payload,

            timeout=TTS_TIMEOUT
        )

        elapsed = round(
            time.time() - start_time,
            2
        )

        debug_print(
            "TTS HTTP:",
            response.status_code
        )

        debug_print(
            "TTS TIME:",
            elapsed,
            "seconds"
        )

        debug_print(
            "TTS CONTENT TYPE:",
            response.headers.get(
                "Content-Type"
            )
        )

        debug_print(
            "TTS CONTENT LENGTH:",
            response.headers.get(
                "Content-Length",
                "-1"
            )
        )

        if response.status_code == 200:

            audio_data = response.content

            debug_print(
                "TTS AUDIO BYTES:",
                len(audio_data)
            )

            if not audio_data:

                debug_print(
                    "TTS ERROR: EMPTY AUDIO"
                )

                return None

            # Check WAV header
            if audio_data[:4] == b"RIFF":

                debug_print(
                    "TTS WAV HEADER: VALID RIFF"
                )

            else:

                debug_print(
                    "TTS WARNING: RIFF HEADER NOT FOUND"
                )

            debug_print(
                "TTS SUCCESS"
            )

            debug_print(
                "========================================"
            )

            return audio_data

        # ====================================================
        # IMPORTANT ERROR DEBUG
        # ====================================================

        debug_print("")
        debug_print(
            "========================================"
        )

        debug_print(
            "TTS SERVER ERROR"
        )

        debug_print(
            "HTTP CODE:",
            response.status_code
        )

        debug_print(
            "CONTENT TYPE:",
            response.headers.get(
                "Content-Type"
            )
        )

        debug_print(
            "ERROR BODY:"
        )

        try:

            debug_print(
                response.text[:8000]
            )

        except Exception as e:

            debug_print(
                "ERROR READING BODY:",
                str(e)
            )

        debug_print(
            "========================================"
        )

        return None

    except requests.exceptions.Timeout:

        debug_print(
            "TTS TIMEOUT after",
            TTS_TIMEOUT,
            "seconds"
        )

        return None

    except requests.exceptions.ConnectionError as e:

        debug_print(
            "TTS CONNECTION ERROR:",
            str(e)
        )

        return None

    except Exception as e:

        debug_print(
            "TTS EXCEPTION:",
            type(e).__name__,
            str(e)
        )

        traceback.print_exc()

        return None


# ============================================================
# TTS ENDPOINT
# ============================================================

@app.route(
    "/tts",
    methods=["POST"]
)
def tts():

    debug_print("")
    debug_print(
        "========================================"
    )
    debug_print(
        "TTS ENDPOINT"
    )
    debug_print(
        "========================================"
    )

    try:

        data = request.get_json(
            silent=True
        )

        debug_print(
            "TTS JSON:",
            data
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

        audio_data = generate_tts(
            text
        )

        if audio_data is None:

            return jsonify({

                "status":
                    "error",

                "message":
                    "TTS generation failed"

            }), 500

        return Response(

            audio_data,

            status=200,

            mimetype="audio/wav",

            headers={

                "Cache-Control":
                    "no-cache",

                "Content-Disposition":
                    "inline; filename=speech.wav"

            }

        )

    except Exception as e:

        debug_print(
            "TTS ENDPOINT EXCEPTION:",
            type(e).__name__,
            str(e)
        )

        traceback.print_exc()

        return jsonify({

            "status":
                "error",

            "message":
                str(e)

        }), 500


# ============================================================
# UPLOAD AUDIO
# ============================================================

@app.route(
    "/uploadAudio",
    methods=["POST"]
)
def upload_audio():

    global REQUEST_COUNT
    global SPEECH_COUNT

    REQUEST_COUNT += 1
    SPEECH_COUNT += 1

    filename = None

    debug_print("")
    debug_print(
        "########################################"
    )
    debug_print(
        "UPLOAD AUDIO REQUEST #",
        REQUEST_COUNT
    )
    debug_print(
        "########################################"
    )

    try:

        # ====================================================
        # REQUEST INFO
        # ====================================================

        audio_data = request.get_data()

        debug_print(
            "CONTENT TYPE:",
            request.content_type
        )

        debug_print(
            "CONTENT LENGTH HEADER:",
            request.content_length
        )

        debug_print(
            "ACTUAL AUDIO BYTES:",
            len(audio_data)
        )

        debug_print(
            "USER AGENT:",
            request.headers.get(
                "User-Agent"
            )
        )

        debug_print(
            "########################################"
        )

        # ====================================================
        # NO AUDIO
        # ====================================================

        if not audio_data:

            debug_print(
                "ERROR: NO AUDIO RECEIVED"
            )

            return jsonify({

                "status":
                    "error",

                "message":
                    "No audio received",

                "transcription":
                    None,

                "hindi_transcription":
                    None,

                "english_transcription":
                    None,

                "ai_reply":
                    "Please ask your question again."

            }), 400

        # ====================================================
        # WAV HEADER QUICK CHECK
        # ====================================================

        debug_print(
            "FIRST 16 BYTES:",
            audio_data[:16]
        )

        if audio_data[:4] == b"RIFF":

            debug_print(
                "UPLOAD FILE: RIFF WAV detected"
            )

        else:

            debug_print(
                "WARNING: FILE DOES NOT START WITH RIFF"
            )

        # ====================================================
        # SAVE FILE
        # ====================================================

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

        debug_print(
            "WAV FILE:",
            filename
        )

        debug_print(
            "WAV SAVED SIZE:",
            os.path.getsize(filename)
        )

        # ====================================================
        # WAV INSPECTION
        # ====================================================

        inspect_wav(
            filename
        )

        inspect_audio_energy(
            filename
        )

        # ====================================================
        # SPEECH RECOGNIZER
        # ====================================================

        debug_print("")
        debug_print(
            "========================================"
        )
        debug_print(
            "SPEECH RECOGNITION START"
        )
        debug_print(
            "========================================"
        )

        recognizer = sr.Recognizer()

        # Better recognition settings
        recognizer.energy_threshold = 250

        recognizer.dynamic_energy_threshold = True

        recognizer.pause_threshold = 0.8

        recognizer.phrase_threshold = 0.2

        recognizer.non_speaking_duration = 0.5

        # ====================================================
        # READ AUDIO
        # ====================================================

        try:

            with sr.AudioFile(
                filename
            ) as source:

                debug_print(
                    "SR SAMPLE RATE:",
                    source.SAMPLE_RATE
                )

                debug_print(
                    "SR SAMPLE WIDTH:",
                    source.SAMPLE_WIDTH
                )

                debug_print(
                    "SR CHANNELS:",
                    source.CHANNELS
                )

                debug_print(
                    "SR DURATION:",
                    source.DURATION
                )

                audio = recognizer.record(
                    source
                )

                debug_print(
                    "AUDIO RECORD SUCCESS"
                )

        except Exception as e:

            debug_print(
                "AUDIO FILE READ ERROR:",
                type(e).__name__,
                str(e)
            )

            traceback.print_exc()

            return jsonify({

                "status":
                    "error",

                "message":
                    "Invalid WAV audio",

                "details":
                    str(e),

                "ai_reply":
                    "Please try speaking again."

            }), 400

        hindi_text = None
        english_text = None

        # ====================================================
        # HINDI
        # ====================================================

        debug_print("")
        debug_print(
            "----------------------------------------"
        )
        debug_print(
            "HINDI SPEECH RECOGNITION"
        )
        debug_print(
            "----------------------------------------"
        )

        hindi_start = time.time()

        try:

            hindi_text = recognizer.recognize_google(

                audio,

                language="hi-IN"
            )

            hindi_text = clean_text(
                hindi_text
            )

            debug_print(
                "HINDI SUCCESS:"
            )

            debug_print(
                hindi_text
            )

            debug_print(
                "HINDI TIME:",
                round(
                    time.time() - hindi_start,
                    2
                ),
                "seconds"
            )

        except sr.UnknownValueError:

            debug_print(
                "HINDI UNKNOWN VALUE"
            )

            debug_print(
                "Google could not understand Hindi audio."
            )

        except sr.RequestError as e:

            debug_print(
                "HINDI GOOGLE REQUEST ERROR:"
            )

            debug_print(
                type(e).__name__,
                str(e)
            )

        except Exception as e:

            debug_print(
                "HINDI UNEXPECTED ERROR:"
            )

            debug_print(
                type(e).__name__,
                str(e)
            )

            traceback.print_exc()

        # ====================================================
        # ENGLISH
        # ====================================================

        debug_print("")
        debug_print(
            "----------------------------------------"
        )
        debug_print(
            "ENGLISH SPEECH RECOGNITION"
        )
        debug_print(
            "----------------------------------------"
        )

        english_start = time.time()

        try:

            english_text = recognizer.recognize_google(

                audio,

                language="en-IN"
            )

            english_text = clean_text(
                english_text
            )

            debug_print(
                "ENGLISH SUCCESS:"
            )

            debug_print(
                english_text
            )

            debug_print(
                "ENGLISH TIME:",
                round(
                    time.time() - english_start,
                    2
                ),
                "seconds"
            )

        except sr.UnknownValueError:

            debug_print(
                "ENGLISH UNKNOWN VALUE"
            )

            debug_print(
                "Google could not understand English audio."
            )

        except sr.RequestError as e:

            debug_print(
                "ENGLISH GOOGLE REQUEST ERROR:"
            )

            debug_print(
                type(e).__name__,
                str(e)
            )

        except Exception as e:

            debug_print(
                "ENGLISH UNEXPECTED ERROR:"
            )

            debug_print(
                type(e).__name__,
                str(e)
            )

            traceback.print_exc()

        # ====================================================
        # FINAL SPEECH DEBUG
        # ====================================================

        debug_print("")
        debug_print(
            "========================================"
        )
        debug_print(
            "SPEECH RECOGNITION RESULT"
        )
        debug_print(
            "========================================"
        )

        debug_print(
            "Hindi:",
            hindi_text
        )

        debug_print(
            "English:",
            english_text
        )

        # ====================================================
        # VALIDATION
        # ====================================================

        hindi_valid = is_valid_query(
            hindi_text
        )

        english_valid = is_valid_query(
            english_text
        )

        debug_print(
            "Hindi valid:",
            hindi_valid
        )

        debug_print(
            "English valid:",
            english_valid
        )

        # ====================================================
        # BOTH FAILED
        # ====================================================

        if (
            not hindi_valid
            and
            not english_valid
        ):

            debug_print("")
            debug_print(
                "########################################"
            )

            debug_print(
                "SPEECH NOT UNDERSTOOD"
            )

            debug_print(
                "AI REQUEST WILL NOT BE SENT"
            )

            debug_print(
                "TTS REQUEST WILL NOT BE SENT"
            )

            debug_print(
                "########################################"
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

                "debug": {

                    "audio_bytes":
                        len(audio_data),

                    "wav_file":
                        filename,

                    "hindi_valid":
                        hindi_valid,

                    "english_valid":
                        english_valid

                },

                "ai_reply":
                    "Please speak again."

            }), 400

        # ====================================================
        # AI
        # ====================================================

        debug_print("")
        debug_print(
            "========================================"
        )
        debug_print(
            "SENDING QUERY TO AI"
        )
        debug_print(
            "========================================"
        )

        ai_reply = get_ai_reply(

            hindi_text,

            english_text
        )

        # ====================================================
        # BEST TRANSCRIPTION
        # ====================================================

        if english_valid:

            transcription = (
                english_text
            )

        elif hindi_valid:

            transcription = (
                hindi_text
            )

        else:

            transcription = None

        # ====================================================
        # FINAL RESPONSE
        # ====================================================

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

        debug_print("")
        debug_print(
            "========================================"
        )
        debug_print(
            "FINAL SERVER RESPONSE"
        )
        debug_print(
            "========================================"
        )

        debug_print(
            "TRANSCRIPTION:",
            transcription
        )

        debug_print(
            "AI REPLY:",
            ai_reply
        )

        debug_print(
            "========================================"
        )

        return jsonify(
            response_data
        )

    except Exception as e:

        debug_print("")
        debug_print(
            "########################################"
        )

        debug_print(
            "UPLOAD AUDIO SERVER EXCEPTION"
        )

        debug_print(
            type(e).__name__,
            str(e)
        )

        traceback.print_exc()

        debug_print(
            "########################################"
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
                "Please try again."

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

                    debug_print(
                        "TEMP WAV DELETED"
                    )

            except Exception as e:

                debug_print(
                    "TEMP FILE DELETE ERROR:",
                    str(e)
                )


# ============================================================
# DIRECT TTS TEST
# ============================================================

@app.route(
    "/test-tts",
    methods=["GET"]
)
def test_tts():

    debug_print("")
    debug_print(
        "========================================"
    )
    debug_print(
        "DIRECT TTS TEST"
    )
    debug_print(
        "========================================"
    )

    test_text = (
        "Hello, I am Hannah. "
        "How can I help you?"
    )

    audio_data = generate_tts(
        test_text
    )

    if audio_data is None:

        return jsonify({

            "status":
                "error",

            "message":
                "TTS test failed"

        }), 500

    return Response(

        audio_data,

        status=200,

        mimetype="audio/wav",

        headers={

            "Cache-Control":
                "no-cache",

            "Content-Disposition":
                "inline; filename=hannah-test.wav"

        }

    )


# ============================================================
# SIMPLE AI TEST
# ============================================================

@app.route(
    "/test-ai",
    methods=["GET"]
)
def test_ai():

    debug_print(
        "DIRECT AI TEST"
    )

    reply = get_ai_reply(
        "",
        "Hello, how are you?"
    )

    return jsonify({

        "status":
            "ok",

        "ai_reply":
            reply

    })


# ============================================================
# SERVER STATUS
# ============================================================

@app.route(
    "/stats",
    methods=["GET"]
)
def stats():

    return jsonify({

        "requests":
            REQUEST_COUNT,

        "speech_requests":
            SPEECH_COUNT,

        "ai_requests":
            AI_COUNT,

        "tts_requests":
            TTS_COUNT,

        "debug":
            DEBUG_MODE

    })


# ============================================================
# START
# ============================================================

if __name__ == "__main__":

    port = int(
        os.environ.get(
            "PORT",
            10000
        )
    )

    print("")
    print("========================================")
    print("ESP32 VOICE SERVER")
    print("========================================")

    print(
        "PORT:",
        port
    )

    print(
        "AI MODEL:",
        AI_MODEL
    )

    print(
        "TTS MODEL:",
        TTS_MODEL
    )

    print(
        "TTS VOICE:",
        TTS_VOICE
    )

    print(
        "AI KEY:",
        "CONFIGURED"
        if AI_API_KEY
        else "MISSING"
    )

    print(
        "DEBUG:",
        DEBUG_MODE
    )

    print("========================================")
    print("SERVER READY")
    print("========================================")
    print("")

    app.run(

        host="0.0.0.0",

        port=port,

        threaded=True

    )

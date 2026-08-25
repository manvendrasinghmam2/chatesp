from flask import Flask, request, jsonify
import os
import speech_recognition as sr
import requests
import re
import tempfile
import traceback
import time
import subprocess


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
# PIPER TTS CONFIG
# ============================================================

PIPER_MODEL = os.environ.get(
    "PIPER_MODEL",
    "voices/en_US-lessac-medium.onnx"
)

TTS_MAX_CHARS = 180


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

    piper_exists = os.path.exists(PIPER_MODEL)

    return jsonify({

        "status": "online",

        "speech_engine":
            "Google Speech Recognition",

        "ai_engine":
            "Groq",

        "model":
            AI_MODEL,

        "tts_engine":
            "Piper",

        "tts_model":
            PIPER_MODEL,

        "tts_available":
            piper_exists
    })


# ============================================================
# WAKE
# ============================================================

@app.route(
    "/wake",
    methods=["POST", "GET"]
)
def wake():

    print()
    print("========================================")
    print("WAKE REQUEST RECEIVED")
    print("========================================")

    try:

        audio_data = request.get_data()

        print(
            "AUDIO BYTES:",
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

        print(
            "WAKE RESPONSE:",
            response_data
        )

        return jsonify(
            response_data
        )

    except Exception as e:

        print(
            "WAKE ERROR:",
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

    # Markdown

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

    # Remove Devanagari

    text = re.sub(
        r"[\u0900-\u097F]+",
        " ",
        text
    )

    text = re.sub(
        r"\s+",
        " ",
        text
    )

    text = text.strip()

    if not re.search(
        r"[A-Za-z0-9]",
        text
    ):

        return ""

    # Maximum length

    if len(text) > TTS_MAX_CHARS:

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

    if not re.search(
        r"[A-Za-z0-9\u0900-\u097F]",
        text
    ):

        return False

    return True


# ============================================================
# AI
# ============================================================

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

    # ========================================================
    # KEY
    # ========================================================

    if not AI_API_KEY:

        print(
            "AI ERROR: AI_API_KEY missing"
        )

        return None


    # ========================================================
    # QUERY VALIDATION
    # ========================================================

    if (
        not is_valid_query(hindi_text)
        and
        not is_valid_query(english_text)
    ):

        print(
            "AI: INVALID QUERY"
        )

        return None


    # ========================================================
    # SYSTEM PROMPT
    # ========================================================

    system_prompt = """
You are Diana, a concise bilingual voice assistant running
on an ESP32.

The user speech may be:
English, Hindi, Hinglish, or Roman Hindi.

Understand the intended meaning from both recognition results.

LANGUAGE RULES:

If the user speaks English:
answer in natural English.

If the user speaks Hindi:
answer in natural Roman Hindi / Hinglish.

If the user speaks Hinglish:
answer in natural Hinglish.

IMPORTANT:
Never answer using Devanagari Hindi script.

Hindi answers MUST use English/Roman letters.

VOICE RULES:

Keep the answer very short.

Usually one or two sentences.

Maximum about 150 characters when possible.

No markdown.

No bullet points.

No emojis.

No headings.

Do not repeat the question.

Do not say "As an AI".

Sound natural and conversational.

Return ONLY the answer.
"""


    user_content = f"""
Hindi speech recognition:
{hindi_text if hindi_text else "No result"}

English speech recognition:
{english_text if english_text else "No result"}

Determine the intended meaning and answer naturally.
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
        print("========================================")
        print("AI REQUEST")
        print("========================================")

        print(
            "ENGLISH INPUT:",
            english_text
        )

        print(
            "HINDI INPUT:",
            hindi_text
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
                "AI SERVER ERROR:"
            )

            print(
                response.text[:3000]
            )

            return None


        try:

            data = response.json()

        except Exception as e:

            print(
                "AI JSON ERROR:",
                str(e)
            )

            return None


        choices = data.get(
            "choices"
        )

        if not choices:

            print(
                "AI ERROR: choices missing"
            )

            print(
                data
            )

            return None


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

            print(
                "AI ERROR: EMPTY REPLY"
            )

            return None


        if reply.lower() in [

            "no ai response. try again.",

            "no ai response",

            "try again."
        ]:

            print(
                "AI ERROR REPLY RECEIVED"
            )

            return None


        print()
        print("AI REPLY:")
        print(reply)

        print("========================================")

        return reply


    except requests.exceptions.Timeout:

        print(
            "AI TIMEOUT"
        )

        return None


    except requests.exceptions.ConnectionError:

        print(
            "AI CONNECTION ERROR"
        )

        return None


    except Exception as e:

        print(
            "AI ERROR:",
            type(e).__name__,
            str(e)
        )

        return None


# ============================================================
# PIPER TTS
# ============================================================

def generate_tts(text):

    original_text = text

    text = clean_tts_text(
        text
    )


    print()
    print("========================================")
    print("PIPER TTS")
    print("========================================")

    print(
        "ORIGINAL TEXT:",
        original_text
    )

    print(
        "FINAL TTS TEXT:",
        text
    )

    print(
        "PIPER MODEL:",
        PIPER_MODEL
    )


    # ========================================================
    # EMPTY
    # ========================================================

    if not text:

        print(
            "TTS ERROR: EMPTY TEXT"
        )

        return None, "empty_text"


    # ========================================================
    # MODEL CHECK
    # ========================================================

    if not os.path.exists(
        PIPER_MODEL
    ):

        print(
            "PIPER MODEL NOT FOUND:",
            PIPER_MODEL
        )

        return None, "piper_model_missing"


    # ========================================================
    # TEMP WAV
    # ========================================================

    output_file = None

    try:

        fd, output_file = tempfile.mkstemp(
            suffix=".wav"
        )

        os.close(fd)


        print(
            "GENERATING AUDIO..."
        )


        # Piper reads text from stdin
        # and writes WAV to output file

        process = subprocess.run(

            [
                "python",
                "-m",
                "piper",
                "--model",
                PIPER_MODEL,
                "--output_file",
                output_file
            ],

            input=text,

            text=True,

            capture_output=True,

            timeout=60
        )


        print(
            "PIPER RETURN CODE:",
            process.returncode
        )


        if process.stdout:

            print(
                "PIPER STDOUT:",
                process.stdout[:1000]
            )


        if process.stderr:

            print(
                "PIPER STDERR:",
                process.stderr[:3000]
            )


        if process.returncode != 0:

            print(
                "PIPER ERROR"
            )

            return None, "piper_error"


        if not os.path.exists(
            output_file
        ):

            print(
                "PIPER OUTPUT FILE MISSING"
            )

            return None, "empty_audio"


        with open(
            output_file,
            "rb"
        ) as f:

            audio_data = f.read()


        if not audio_data:

            print(
                "PIPER AUDIO EMPTY"
            )

            return None, "empty_audio"


        print(
            "PIPER AUDIO BYTES:",
            len(audio_data)
        )

        print(
            "PIPER SUCCESS"
        )

        print("========================================")


        return audio_data, None


    except subprocess.TimeoutExpired:

        print(
            "PIPER TIMEOUT"
        )

        return None, "timeout"


    except Exception as e:

        print(
            "PIPER EXCEPTION:",
            type(e).__name__,
            str(e)
        )

        traceback.print_exc()

        return None, "exception"


    finally:

        if output_file:

            try:

                if os.path.exists(
                    output_file
                ):

                    os.remove(
                        output_file
                    )

            except Exception:

                pass


# ============================================================
# TTS ENDPOINT
# ============================================================

@app.route(
    "/tts",
    methods=["POST"]
)
def tts():

    print()
    print("========================================")
    print("TTS ENDPOINT")
    print("========================================")


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
            "text"
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


        audio_data, error_code = generate_tts(
            text
        )


        if audio_data is None:

            return jsonify({

                "status":
                    "error",

                "message":
                    "TTS generation failed",

                "code":
                    error_code

            }), 500


        return Response(

            audio_data,

            status=200,

            mimetype="audio/wav",

            headers={

                "Content-Type":
                    "audio/wav",

                "Content-Length":
                    str(len(audio_data)),

                "Cache-Control":
                    "no-cache",

                "Content-Disposition":
                    "inline; filename=speech.wav"
            }
        )


    except Exception as e:

        print(
            "TTS SERVER EXCEPTION:",
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

    filename = None


    try:

        print()
        print("========================================")
        print("AUDIO REQUEST RECEIVED")
        print("========================================")


        audio_data = request.get_data()


        print(
            "CONTENT TYPE:",
            request.content_type
        )

        print(
            "CONTENT LENGTH:",
            request.content_length
        )

        print(
            "AUDIO BYTES:",
            len(audio_data)
        )


        # ====================================================
        # NO AUDIO
        # ====================================================

        if not audio_data:

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
                    None

            }), 400


        # ====================================================
        # SAVE WAV
        # ====================================================

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


        print(
            "WAV FILE:",
            filename
        )


        # ====================================================
        # SPEECH RECOGNITION
        # ====================================================

        recognizer = sr.Recognizer()


        with sr.AudioFile(
            filename
        ) as source:

            audio = recognizer.record(
                source
            )


        hindi_text = None

        english_text = None


        # ====================================================
        # HINDI
        # ====================================================

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

                "details":
                    str(e)

            }), 500


        # ====================================================
        # ENGLISH
        # ====================================================

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

                "details":
                    str(e),

                "hindi_transcription":
                    hindi_text,

                "english_transcription":
                    None

            }), 500


        # ====================================================
        # VALIDATION
        # ====================================================

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
                    None

            }), 400


        # ====================================================
        # AI
        # ====================================================

        ai_reply = get_ai_reply(

            hindi_text,

            english_text
        )


        # ====================================================
        # AI FAILURE
        # ====================================================

        if not ai_reply:

            print(
                "AI FAILED"
            )


            return jsonify({

                "status":
                    "error",

                "message":
                    "AI response unavailable",

                "transcription":
                    english_text
                    if is_valid_query(
                        english_text
                    )
                    else hindi_text,

                "hindi_transcription":
                    hindi_text,

                "english_transcription":
                    english_text,

                "ai_reply":
                    None

            }), 503


        # ====================================================
        # BEST TRANSCRIPTION
        # ====================================================

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


        # ====================================================
        # GENERATE TTS FROM AI REPLY
        # ====================================================

        print()
        print("========================================")
        print("GENERATING TTS FROM AI REPLY")
        print("========================================")

        audio_data, tts_error = generate_tts(
            ai_reply
        )


        # ====================================================
        # FINAL JSON
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
                ai_reply,

            "tts":
                True if audio_data else False,

            "tts_error":
                tts_error
        }


        print()
        print("========================================")
        print("FINAL RESPONSE")
        print("========================================")

        print(
            response_data
        )

        print("========================================")


        # ====================================================
        # IMPORTANT
        #
        # JSON response me WAV bhejna nahi hai.
        #
        # ESP32 ko AI reply mil jayega.
        #
        # ESP32 /tts endpoint ko AI reply bhejkar
        # WAV receive kar sakta hai.
        # ====================================================

        return jsonify(
            response_data
        )


    except Exception as e:

        print()
        print("========================================")
        print("SERVER ERROR")
        print("========================================")


        print(
            type(e).__name__,
            str(e)
        )


        traceback.print_exc()


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


# ============================================================
# DIRECT TTS TEST
# ============================================================

@app.route(
    "/test-tts",
    methods=["GET"]
)
def test_tts():

    print()
    print("========================================")
    print("DIRECT PIPER TTS TEST")
    print("========================================")


    test_text = (
        "Hello, I am Diana. "
        "How can I help you?"
    )


    audio_data, error_code = generate_tts(
        test_text
    )


    if audio_data is None:

        return jsonify({

            "status":
                "error",

            "message":
                "TTS test failed",

            "code":
                error_code

        }), 500


    return Response(

        audio_data,

        status=200,

        mimetype="audio/wav",

        headers={

            "Content-Type":
                "audio/wav",

            "Content-Length":
                str(len(audio_data)),

            "Cache-Control":
                "no-cache",

            "Content-Disposition":
                "inline; filename=diana-test.wav"
        }
    )


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


    print()
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
        "PIPER MODEL:",
        PIPER_MODEL
    )

    print(
        "AI KEY:",
        "CONFIGURED"
        if AI_API_KEY
        else "MISSING"
    )


    print("========================================")


    app.run(

        host="0.0.0.0",

        port=port,

        threaded=True
    )

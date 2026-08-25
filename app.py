from flask import Flask, request, jsonify, Response
import os
import speech_recognition as sr
import requests
import re
import tempfile
import traceback
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
# GROQ TTS
# ============================================================

TTS_URL = os.environ.get(
    "TTS_URL",
    "https://api.groq.com/openai/v1/audio/speech"
)

TTS_MODEL = os.environ.get(
    "TTS_MODEL",
    "canopylabs/orpheus-v1-english"
)

TTS_VOICE = os.environ.get(
    "TTS_VOICE",
    "hannah"
)

TTS_MAX_CHARS = 180


# ============================================================
# TTS STATE
# ============================================================

# If Groq says quota is exhausted, don't keep hammering
# the API on every ESP32 request.
tts_rate_limited_until = 0


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

    now = int(time.time())

    tts_available = (
        now >= tts_rate_limited_until
    )

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

        "tts_available":
            tts_available
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

        print("========================================")

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

    text = clean_text(
        text
    )

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

    # --------------------------------------------------------
    # IMPORTANT:
    # Orpheus English should not receive Devanagari.
    # Convert non-ASCII characters to spaces.
    # --------------------------------------------------------

    text = re.sub(
        r"[^\x00-\x7F]+",
        " ",
        text
    )

    # Remove excessive spaces
    text = re.sub(
        r"\s+",
        " ",
        text
    )

    text = text.strip()

    # --------------------------------------------------------
    # Must contain at least one letter or digit.
    # This prevents:
    # "."
    # "..."
    # "!"
    # etc.
    # --------------------------------------------------------

    if not re.search(
        r"[A-Za-z0-9]",
        text
    ):

        return ""

    # --------------------------------------------------------
    # Maximum length
    # --------------------------------------------------------

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

    # Must contain a letter or digit
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

Examples:

User:
Aap kaise ho?

Good:
Main bilkul theek hoon. Aap kaise hain?

User:
Mujhe time batao.

Good:
Bilkul, main aapko time bata deta hoon.

User:
What is the capital of India?

Good:
The capital of India is New Delhi.

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


        # Remove prefixes
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


        # ----------------------------------------------------
        # Do not allow fake error text to reach TTS
        # ----------------------------------------------------

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
# TTS
# ============================================================

def generate_tts(text):

    global tts_rate_limited_until

    # --------------------------------------------------------
    # Clean
    # --------------------------------------------------------

    original_text = text

    text = clean_tts_text(
        text
    )


    print()
    print("========================================")
    print("TTS REQUEST")
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
        "TTS MODEL:",
        TTS_MODEL
    )

    print(
        "TTS VOICE:",
        TTS_VOICE
    )


    # --------------------------------------------------------
    # Empty
    # --------------------------------------------------------

    if not text:

        print(
            "TTS ERROR: TEXT HAS NO LETTER/DIGIT"
        )

        return None, "empty_text"


    # --------------------------------------------------------
    # API key
    # --------------------------------------------------------

    if not AI_API_KEY:

        print(
            "TTS ERROR: AI_API_KEY missing"
        )

        return None, "missing_api_key"


    # --------------------------------------------------------
    # Local rate-limit protection
    # --------------------------------------------------------

    now = int(
        time.time()
    )

    if now < tts_rate_limited_until:

        remaining = (
            tts_rate_limited_until -
            now
        )

        print(
            "TTS RATE LIMITED LOCALLY"
        )

        print(
            "RETRY AFTER:",
            remaining,
            "seconds"
        )

        return None, "rate_limited"


    # --------------------------------------------------------
    # PAYLOAD
    # --------------------------------------------------------

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


    try:

        print(
            "TTS CHARACTERS:",
            len(text)
        )

        print(
            "SENDING TTS REQUEST..."
        )


        response = requests.post(

            TTS_URL,

            headers=headers,

            json=payload,

            timeout=60
        )


        print(
            "TTS HTTP:",
            response.status_code
        )

        print(
            "TTS CONTENT TYPE:",
            response.headers.get(
                "Content-Type"
            )
        )

        print(
            "TTS CONTENT LENGTH:",
            response.headers.get(
                "Content-Length",
                "-1"
            )
        )


        # ====================================================
        # SUCCESS
        # ====================================================

        if response.status_code == 200:

            audio_data = response.content


            if not audio_data:

                print(
                    "TTS ERROR: EMPTY AUDIO"
                )

                return None, "empty_audio"


            print(
                "TTS AUDIO BYTES:",
                len(audio_data)
            )

            print(
                "TTS SUCCESS"
            )

            print("========================================")

            return audio_data, None


        # ====================================================
        # RATE LIMIT
        # ====================================================

        if response.status_code == 429:

            retry_after = response.headers.get(
                "Retry-After"
            )

            try:

                retry_seconds = int(
                    retry_after
                )

            except Exception:

                retry_seconds = 60


            # Don't hammer API
            tts_rate_limited_until = (
                int(time.time()) +
                retry_seconds
            )


            print()
            print("========================================")
            print("TTS RATE LIMIT")
            print("========================================")

            print(
                "RETRY AFTER:",
                retry_seconds,
                "seconds"
            )


            try:

                error_json = response.json()

                print(
                    "ERROR BODY:",
                    error_json
                )

            except Exception:

                print(
                    "ERROR BODY:",
                    response.text[:3000]
                )


            print("========================================")


            return None, "rate_limited"


        # ====================================================
        # OTHER ERROR
        # ====================================================

        print()
        print("========================================")
        print("TTS SERVER ERROR")
        print("========================================")

        print(
            "HTTP CODE:",
            response.status_code
        )

        try:

            print(
                "ERROR BODY:",
                response.text[:5000]
            )

        except Exception:

            pass

        print("========================================")


        return None, "server_error"


    except requests.exceptions.Timeout:

        print(
            "TTS TIMEOUT"
        )

        return None, "timeout"


    except requests.exceptions.ConnectionError as e:

        print(
            "TTS CONNECTION ERROR:",
            str(e)
        )

        return None, "connection_error"


    except Exception as e:

        print(
            "TTS EXCEPTION:",
            type(e).__name__,
            str(e)
        )

        return None, "exception"


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

            print(
                "TTS: NO JSON RECEIVED"
            )

            return jsonify({

                "status":
                    "error",

                "message":
                    "No JSON received"

            }), 400


        print(
            "TTS JSON:",
            data
        )


        text = data.get(
            "text"
        )


        text = clean_text(
            text
        )


        if not text:

            print(
                "TTS: EMPTY TEXT"
            )

            return jsonify({

                "status":
                    "error",

                "message":
                    "No text received"

            }), 400


        audio_data, error_code = generate_tts(
            text
        )


        # ====================================================
        # TTS FAILED
        # ====================================================

        if audio_data is None:

            if error_code == "rate_limited":

                return jsonify({

                    "status":
                        "error",

                    "message":
                        "TTS rate limit reached",

                    "code":
                        "rate_limited"

                }), 429


            if error_code == "empty_text":

                return jsonify({

                    "status":
                        "error",

                    "message":
                        "TTS text contains no usable letters or digits",

                    "code":
                        "empty_text"

                }), 400


            return jsonify({

                "status":
                    "error",

                "message":
                    "TTS generation failed",

                "code":
                    error_code

            }), 500


        # ====================================================
        # RETURN WAV
        # ====================================================

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


        print("========================================")


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
                "AI FAILED - NOT CALLING TTS"
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


        print()
        print("========================================")
        print("FINAL RESPONSE")
        print("========================================")


        print(
            response_data
        )


        print("========================================")


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


        print("========================================")


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
    print("DIRECT TTS TEST")
    print("========================================")


    test_text = (
        "Hello, I am Diana. "
        "How can I help you?"
    )


    audio_data, error_code = generate_tts(
        test_text
    )


    if audio_data is None:

        if error_code == "rate_limited":

            return jsonify({

                "status":
                    "error",

                "message":
                    "TTS rate limit reached. Wait for Groq quota reset.",

                "code":
                    "rate_limited"

            }), 429


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


    print("========================================")


    app.run(

        host="0.0.0.0",

        port=port,

        threaded=True
    )

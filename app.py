from flask import Flask, request, jsonify, Response
import os
import re
import tempfile
import traceback
import requests
import speech_recognition as sr


# ============================================================
# FLASK APP
# ============================================================

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

TTS_VOICE = os.environ.get(
    "TTS_VOICE",
    "hannah"
)

# Groq Orpheus maximum input
TTS_MAX_CHARS = 200


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

        "api_key":
            "configured"
            if AI_API_KEY
            else "missing"
    })


# ============================================================
# WAKE
# ============================================================

@app.route("/wake", methods=["POST", "GET"])
def wake():

    print()
    print("========================================")
    print("WAKE REQUEST")
    print("========================================")

    try:

        audio_data = request.get_data()

        print(
            "WAKE AUDIO BYTES:",
            len(audio_data)
        )

        return jsonify({
            "status": "ok",
            "wake": True,
            "english": "Hello",
            "hindi": None
        })

    except Exception as e:

        print(
            "WAKE ERROR:",
            type(e).__name__,
            str(e)
        )

        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


# ============================================================
# TEST
# ============================================================

@app.route("/test", methods=["POST"])
def test():

    try:

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

    except Exception as e:

        return jsonify({
            "status": "error",
            "message": str(e)
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
# TTS CLEAN
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

    # Remove Devanagari / non ASCII
    # because Orpheus English is being used
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
    # MAX TTS LENGTH
    # ========================================================

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

        best = max(positions)

        if best >= 40:

            text = text[
                :best + 1
            ]

    return text.strip()


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

    print()
    print("========================================")
    print("AI FUNCTION")
    print("========================================")

    print(
        "Hindi:",
        hindi_text
    )

    print(
        "English:",
        english_text
    )

    # ========================================================
    # API KEY
    # ========================================================

    if not AI_API_KEY:

        print(
            "AI ERROR: API KEY MISSING"
        )

        return (
            "No AI response. Try again."
        )

    # ========================================================
    # VALIDATION
    # ========================================================

    if (
        not is_valid_query(hindi_text)
        and
        not is_valid_query(english_text)
    ):

        return (
            "Please ask your question again."
        )

    # ========================================================
    # SYSTEM PROMPT
    # ========================================================

    system_prompt = """

You are Hannah, a friendly voice assistant.

You are designed mainly for:

STEM education
AI
Robotics
Electronics
Embedded systems
Arduino
ESP32
Sensors
Automation
Programming
Aerospace
Avionics
Aviontron Aerospace Pvt. Ltd.
Noida
STEM education

You can also answer simple conversation questions such as:

Hello
Hi
How are you?
Who are you?
What is your name?
Good morning
Thank you
What can you do?

IMPORTANT TOPIC RULE:

If the user asks about STEM, AI, robotics, electronics,
embedded systems, programming, automation, aerospace,
avionics or related education, answer normally.

If the user asks something completely unrelated to these
topics, politely say that you mainly help with STEM education,
AI, robotics, electronics, embedded systems and aerospace.

Do not provide unrelated detailed answers.

LANGUAGE RULES:

If the user speaks English,
answer in natural English.

If the user speaks Hindi,
answer in natural Roman Hindi.

Do NOT use Devanagari Hindi.

If the user speaks Hinglish,
answer naturally in Hinglish.

IMPORTANT:

Detect the actual language of the user's question.

Examples:

User:
How are you?

Correct:
I am doing great. How can I help you?

User:
Tum kaise ho?

Correct:
Main bilkul theek hoon. Aap kaise ho?

User:
आप कैसे हो?

Correct:
Main bilkul theek hoon. Aap kaise ho?

User:
What is robotics?

Correct:
Robotics is the field of designing and building robots.

User:
Robotics kya hai?

Correct:
Robotics robots ko design aur control karne ki field hai.

User:
hello

Correct:
Hello! How can I help you?

User:
what is your name

Correct:
My name is Hannah.

VOICE RULES:

Keep answers concise.

Usually one or two sentences.

Maximum about 180 characters when possible.

No markdown.

No bullet points.

No emojis.

No headings.

Do not repeat the question.

Do not say "As an AI".

Sound natural and conversational.

Return ONLY the answer.
"""

    # ========================================================
    # USER CONTENT
    # ========================================================

    user_content = f"""

Hindi speech recognition:
{hindi_text if hindi_text else "No result"}

English speech recognition:
{english_text if english_text else "No result"}

Use the speech recognition results together.

Determine what the user actually meant.

IMPORTANT:
Answer in the SAME language style as the user's actual query.

English question = English answer.

Hindi question = Roman Hindi answer.

Hinglish question = Hinglish answer.

Return only the final answer.
"""

    # ========================================================
    # PAYLOAD
    # ========================================================

    payload = {

        "model":
            AI_MODEL,

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

    # ========================================================
    # REQUEST
    # ========================================================

    try:

        print(
            "SENDING AI REQUEST..."
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

        # ====================================================
        # ERROR
        # ====================================================

        if response.status_code != 200:

            print()
            print("========================================")
            print("AI SERVER ERROR")
            print("========================================")

            print(
                response.text[:10000]
            )

            print("========================================")

            return (
                "No AI response. Try again."
            )

        # ====================================================
        # JSON
        # ====================================================

        try:

            data = response.json()

        except Exception as e:

            print(
                "AI JSON ERROR:",
                str(e)
            )

            print(
                response.text[:5000]
            )

            return (
                "No AI response. Try again."
            )

        # ====================================================
        # CHOICES
        # ====================================================

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

            return (
                "No AI response. Try again."
            )

        # ====================================================
        # REPLY
        # ====================================================

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

            return (
                "No AI response. Try again."
            )

        print()
        print("AI REPLY:")
        print(reply)

        print("========================================")

        return reply

    except requests.exceptions.Timeout:

        print(
            "AI TIMEOUT"
        )

        return (
            "No AI response. Try again."
        )

    except requests.exceptions.ConnectionError as e:

        print(
            "AI CONNECTION ERROR:",
            str(e)
        )

        return (
            "No AI response. Try again."
        )

    except Exception as e:

        print(
            "AI EXCEPTION:",
            type(e).__name__,
            str(e)
        )

        traceback.print_exc()

        return (
            "No AI response. Try again."
        )


# ============================================================
# GENERATE TTS
# ============================================================

def generate_tts(text):

    print()
    print("========================================")
    print("TTS FUNCTION")
    print("========================================")

    text = clean_tts_text(
        text
    )

    print(
        "TTS TEXT:",
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

    print(
        "TTS TEXT LENGTH:",
        len(text)
    )

    # ========================================================
    # EMPTY
    # ========================================================

    if not text:

        print(
            "TTS ERROR: EMPTY TEXT"
        )

        return None

    # ========================================================
    # API KEY
    # ========================================================

    if not AI_API_KEY:

        print(
            "TTS ERROR: API KEY MISSING"
        )

        return None

    # ========================================================
    # PAYLOAD
    # ========================================================

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

    print()
    print("TTS PAYLOAD:")
    print(payload)

    print()
    print("SENDING TTS REQUEST...")

    # ========================================================
    # REQUEST
    # ========================================================

    try:

        response = requests.post(

            TTS_URL,

            headers=headers,

            json=payload,

            timeout=60
        )

        print()
        print("========================================")
        print("TTS RESPONSE")
        print("========================================")

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

        print(
            "TTS TRANSFER ENCODING:",
            response.headers.get(
                "Transfer-Encoding",
                "none"
            )
        )

        # ====================================================
        # SUCCESS
        # ====================================================

        if response.status_code == 200:

            audio_data = response.content

            print(
                "TTS AUDIO BYTES:",
                len(audio_data)
            )

            if not audio_data:

                print(
                    "TTS ERROR: EMPTY AUDIO"
                )

                return None

            # Check WAV header
            if audio_data[:4] == b"RIFF":

                print(
                    "TTS WAV HEADER: VALID"
                )

            else:

                print(
                    "TTS WARNING: WAV HEADER NOT FOUND"
                )

            print(
                "TTS SUCCESS"
            )

            print("========================================")

            return audio_data

        # ====================================================
        # SERVER ERROR
        # ====================================================

        print()
        print("========================================")
        print("TTS SERVER ERROR")
        print("========================================")

        print(
            "HTTP CODE:",
            response.status_code
        )

        print()
        print("ERROR BODY:")

        try:

            print(
                response.text[:10000]
            )

        except Exception:

            print(
                "Could not read error body."
            )

        print()
        print("RESPONSE HEADERS:")

        print(
            dict(response.headers)
        )

        print("========================================")

        return None

    # ========================================================
    # TIMEOUT
    # ========================================================

    except requests.exceptions.Timeout:

        print()
        print(
            "TTS TIMEOUT"
        )

        return None

    # ========================================================
    # CONNECTION
    # ========================================================

    except requests.exceptions.ConnectionError as e:

        print()
        print(
            "TTS CONNECTION ERROR:"
        )

        print(
            str(e)
        )

        return None

    # ========================================================
    # OTHER
    # ========================================================

    except Exception as e:

        print()
        print(
            "TTS EXCEPTION:",
            type(e).__name__,
            str(e)
        )

        traceback.print_exc()

        return None


# ============================================================
# TTS ENDPOINT
# ============================================================

@app.route("/tts", methods=["POST"])
def tts():

    print()
    print("========================================")
    print("/tts REQUEST")
    print("========================================")

    try:

        data = request.get_json(
            silent=True
        )

        print(
            "TTS JSON:",
            data
        )

        if not data:

            return jsonify({
                "status": "error",
                "message": "No JSON received"
            }), 400

        text = clean_text(
            data.get("text")
        )

        if not text:

            return jsonify({
                "status": "error",
                "message": "No text received"
            }), 400

        audio_data = generate_tts(
            text
        )

        if audio_data is None:

            return jsonify({
                "status": "error",
                "message": "TTS generation failed"
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

        print(
            "TTS ENDPOINT ERROR:",
            type(e).__name__,
            str(e)
        )

        traceback.print_exc()

        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


# ============================================================
# DIRECT TTS TEST
# ============================================================

@app.route("/test-tts", methods=["GET"])
def test_tts():

    print()
    print("========================================")
    print("DIRECT TTS TEST")
    print("========================================")

    test_text = (
        "Hello, I am Hannah. "
        "How can I help you?"
    )

    print(
        "TEST TEXT:",
        test_text
    )

    audio_data = generate_tts(
        test_text
    )

    if audio_data is None:

        print(
            "DIRECT TTS TEST FAILED"
        )

        return jsonify({

            "status":
                "error",

            "message":
                "TTS test failed",

            "voice":
                TTS_VOICE,

            "model":
                TTS_MODEL

        }), 500

    print(
        "DIRECT TTS TEST SUCCESS"
    )

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
# UPLOAD AUDIO
# ============================================================

@app.route("/uploadAudio", methods=["POST"])
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
                    "Please ask your question again."

            }), 400

        # ====================================================
        # SAVE WAV
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
                    "Please ask your question again."

            }), 400

        # ====================================================
        # AI
        # ====================================================

        ai_reply = get_ai_reply(

            hindi_text,

            english_text
        )

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
                "No AI response. Try again."

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

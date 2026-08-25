
from flask import Flask, request, jsonify, Response
import os
import speech_recognition as sr
import requests
import re
import tempfile
import traceback


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
# GROQ TTS CONFIG
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

TTS_MAX_CHARS = 200


# ============================================================
# STANDARD AI ERROR MESSAGE
# ============================================================

AI_ERROR_MESSAGE = "No AI response. Try again."


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

        "status":
            "online",

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

        "assistant":
            "Diana",

        "company":
            "Avitron Aerospace Pvt. Ltd.",

        "domain":
            "STEM Education, Robotics, AI, Electronics, Aerospace"

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

    # Remove markdown code blocks
    text = text.replace(
        "```",
        ""
    )

    # Remove newlines
    text = re.sub(
        r"[\r\n]+",
        " ",
        text
    )

    # Remove multiple spaces
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
        "Assistant:",
        "Diana:"
    ]

    for prefix in prefixes:

        if text.lower().startswith(
            prefix.lower()
        ):

            text = text[
                len(prefix):
            ].strip()

    # Remove markdown
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

    # Remove emojis / unusual symbols
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

    # Limit TTS length
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
    # API KEY CHECK
    # ========================================================

    if not AI_API_KEY:

        print(
            "AI ERROR: AI_API_KEY missing"
        )

        return AI_ERROR_MESSAGE

    # ========================================================
    # QUERY CHECK
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
    # DIANA SYSTEM PROMPT
    # ========================================================

    system_prompt = """
You are Diana, a friendly and concise voice assistant for
Avitron Aerospace Pvt. Ltd.

Your primary purpose is to help users with questions related to:

Avitron Aerospace Pvt. Ltd.
STEM education.
Robotics.
Artificial Intelligence.
AI projects.
Electronics.
Embedded systems.
ESP32.
Arduino.
Microcontrollers.
Sensors and actuators.
Robotics projects.
AI and machine learning education.
Electronics projects.
Programming related to robotics, AI and electronics.
STEM learning.
Science and technology education.
Aerospace and educational aerospace technology.

DOMAIN RULE:

If the user's question is related to any of the topics above,
answer the question helpfully and naturally.

You can answer educational questions, technical questions,
project questions, beginner questions and practical questions
about STEM, robotics, AI, electronics, embedded systems,
microcontrollers and aerospace technology.

If the question is NOT related to STEM education, robotics,
AI, electronics, embedded systems, aerospace or Avitron
Aerospace Pvt. Ltd., do NOT answer the unrelated question.

Instead politely explain that you specialize in these topics
and ask the user to ask something related to them.

LANGUAGE RULES:

The user may speak:

English.
Hindi.
Hinglish.
Roman Hindi.

Understand the intended meaning from both speech recognition
results.

If the user speaks English:
answer in natural English.

If the user speaks Hindi:
answer in natural Roman Hindi or Hinglish.

If the user speaks Hinglish:
answer in natural Hinglish.

IMPORTANT:

Never use Devanagari Hindi script.

Hindi answers MUST always use English/Roman letters.

Examples:

User:
Robotics kya hoti hai?

Good:
Robotics ek technology field hai jisme robots ko design,
build aur program kiya jata hai.

User:
What is AI?

Good:
AI means Artificial Intelligence. It helps computers learn,
understand information and make decisions.

User:
ESP32 kya hai?

Good:
ESP32 ek powerful microcontroller hai jo Wi-Fi aur Bluetooth
ke saath robotics aur IoT projects mein use hota hai.

User:
Arduino se robot kaise banaye?

Good:
Arduino, motors, motor driver aur sensors ka use karke basic
robot banaya ja sakta hai. Main aapko step by step guide kar
sakti hoon.

User:
Electronics kya hai?

Good:
Electronics mein circuits aur electronic components ka use
karke devices aur systems banaye jate hain.

User:
What can you help me with?

Good:
I can help with STEM education, AI, robotics, electronics,
embedded systems and aerospace technology.

UNRELATED QUESTION EXAMPLE:

User:
Who is the Prime Minister of India?

Good:
I can help with STEM education, AI, robotics, electronics and
related technology. What would you like to learn?

Hindi/Hinglish version:

Main STEM education, AI, robotics, electronics aur related
technology mein help kar sakti hoon. Aap kya poochna chahenge?

Another example:

User:
Mujhe ek joke sunao.

Good:
Main STEM education, AI, robotics aur electronics se related
questions mein help kar sakti hoon. Main aapki kya sahayata
kar sakti hoon?

AVITRON AEROSPACE RULE:

If the user asks specifically about Avitron Aerospace Pvt. Ltd.,
only provide information that is actually available in the
conversation or provided knowledge.

Never invent company facts.

Never invent courses.

Never invent products.

Never invent facilities.

Never invent employees.

Never invent addresses.

Never invent achievements.

Never invent programs.

Never claim that Avitron provides a service unless the
information is actually known.

If you do not know a specific Avitron fact, say:

"Is information ke baare mein mere paas abhi exact details
nahi hain. Aap Avitron Aerospace Pvt. Ltd. ke STEM,
robotics, AI, electronics ya aerospace programs ke baare mein
pooch sakte hain."

TECHNICAL ANSWER RULE:

For technical questions, explain clearly and simply.

For beginner questions, use beginner-friendly language.

For advanced questions, provide technically accurate answers.

If the user asks how to build something, explain the required
components and basic steps when appropriate.

Do not unnecessarily make answers complicated.

VOICE RULES:

Keep answers short and easy to speak.

Usually one or two short sentences.

For technical questions, use up to three short sentences when
necessary.

Maximum about 180 characters when possible.

No markdown.

No bullet points.

No emojis.

No headings.

Do not repeat the user's question.

Do not say "As an AI".

Sound friendly, natural and conversational.

If the user asks an unrelated question, keep the refusal
friendly and short.

For unrelated questions, use a response similar to:

"Main sirf STEM education, AI, robotics, electronics aur
related technology questions mein help kar sakti hoon.
Aap kya poochna chahenge?"

Return ONLY the final answer.
"""

    # ========================================================
    # USER CONTENT
    # ========================================================

    user_content = f"""
Hindi speech recognition:
{hindi_text if hindi_text else "No result"}

English speech recognition:
{english_text if english_text else "No result"}

Determine the user's intended meaning from the available
speech recognition results.

Answer according to your STEM, AI, robotics, electronics,
embedded systems and aerospace specialization.

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
            250,

        "stream":
            False
    }

    # ========================================================
    # HEADERS
    # ========================================================

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

        print()
        print("========================================")
        print("AI REQUEST")
        print("========================================")

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

        # ====================================================
        # SERVER ERROR
        # ====================================================

        if response.status_code != 200:

            print(
                "AI SERVER ERROR:"
            )

            print(
                response.text[:3000]
            )

            return AI_ERROR_MESSAGE

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

            return AI_ERROR_MESSAGE

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

            return AI_ERROR_MESSAGE

        # ====================================================
        # MESSAGE
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

        reply = str(
            reply
        ).strip()

        reply = clean_text(
            reply
        )

        # ====================================================
        # REMOVE PREFIX
        # ====================================================

        prefixes = [

            "AI:",

            "Answer:",

            "Response:",

            "Assistant:",

            "Diana:"
        ]

        for prefix in prefixes:

            if reply.lower().startswith(
                prefix.lower()
            ):

                reply = reply[
                    len(prefix):
                ].strip()

        # ====================================================
        # EMPTY RESPONSE
        # ====================================================

        if not reply:

            print(
                "AI ERROR: Empty response"
            )

            return AI_ERROR_MESSAGE

        print()
        print("AI REPLY:")
        print(reply)

        print("========================================")

        return reply

    # ========================================================
    # TIMEOUT
    # ========================================================

    except requests.exceptions.Timeout:

        print(
            "AI TIMEOUT"
        )

        return AI_ERROR_MESSAGE

    # ========================================================
    # CONNECTION
    # ========================================================

    except requests.exceptions.ConnectionError as e:

        print(
            "AI CONNECTION ERROR:",
            str(e)
        )

        return AI_ERROR_MESSAGE

    # ========================================================
    # OTHER
    # ========================================================

    except Exception as e:

        print(
            "AI ERROR:",
            type(e).__name__,
            str(e)
        )

        traceback.print_exc()

        return AI_ERROR_MESSAGE


# ============================================================
# TTS
# ============================================================

def generate_tts(text):

    text = clean_tts_text(
        text
    )

    print()
    print("========================================")
    print("TTS REQUEST")
    print("========================================")

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

    if not text:

        print(
            "TTS ERROR: empty text"
        )

        return None

    if not AI_API_KEY:

        print(
            "TTS ERROR: AI_API_KEY missing"
        )

        return None

    # ========================================================
    # TTS PAYLOAD
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

    try:

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
                    "TTS ERROR: empty audio"
                )

                return None

            print(
                "TTS AUDIO BYTES:",
                len(audio_data)
            )

            print(
                "TTS SUCCESS"
            )

            print("========================================")

            return audio_data

        # ====================================================
        # ERROR
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

            print(
                "Could not read error body."
            )

        print("========================================")

        return None

    except requests.exceptions.Timeout:

        print(
            "TTS TIMEOUT"
        )

        return None

    except requests.exceptions.ConnectionError as e:

        print(
            "TTS CONNECTION ERROR:",
            str(e)
        )

        return None

    except Exception as e:

        print(
            "TTS EXCEPTION:",
            type(e).__name__,
            str(e)
        )

        return None


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
                "TTS: No JSON received"
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
                    "Please ask your question again."

            }), 400

        # ====================================================
        # SAVE AUDIO
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
                AI_ERROR_MESSAGE

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
        "How can I help you with STEM, robotics, AI or electronics?"
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

    print(
        "ASSISTANT:",
        "Diana"
    )

    print(
        "COMPANY:",
        "Avitron Aerospace Pvt. Ltd."
    )

    print(
        "DOMAIN:",
        "STEM | AI | Robotics | Electronics | Aerospace"
    )

    print("========================================")

    app.run(

        host="0.0.0.0",

        port=port,

        threaded=True
    )


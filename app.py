from flask import Flask, request, jsonify, Response
import os
import speech_recognition as sr
import requests
import re
import tempfile
import traceback
import threading


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

# HANNAH VOICE
TTS_VOICE = os.environ.get(
    "TTS_VOICE",
    "hannah"
)

# Do NOT use 200 character hard limit.
# Keep enough room for normal voice answers.
TTS_MAX_CHARS = 500


# ============================================================
# CONVERSATION MEMORY
# ============================================================

MAX_MEMORY_MESSAGES = 12

conversation_memory = []

memory_lock = threading.Lock()


def add_memory(role, content):

    if not content:
        return

    with memory_lock:

        conversation_memory.append({
            "role": role,
            "content": content
        })

        while len(conversation_memory) > MAX_MEMORY_MESSAGES:
            conversation_memory.pop(0)


def get_memory():

    with memory_lock:

        return list(conversation_memory)


def clear_memory():

    with memory_lock:

        conversation_memory.clear()


# ============================================================
# HOME
# ============================================================

@app.route("/", methods=["GET"])
def home():

    return "ESP32 Hannah Voice Server is ONLINE!"


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

        "memory":
            True

    })


# ============================================================
# CLEAR MEMORY
# ============================================================

@app.route("/clear-memory", methods=["GET", "POST"])
def clear_memory_route():

    clear_memory()

    return jsonify({

        "status": "ok",

        "message":
            "Conversation memory cleared"

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

        return jsonify({

            "status":
                "ok",

            "wake":
                True,

            "english":
                "Hello",

            "hindi":
                None

        })

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
# CLEAN TTS TEXT
# ============================================================

def clean_tts_text(text):

    text = clean_text(text)

    if not text:
        return ""

    prefixes = [

        "AI:",
        "Answer:",
        "Response:",
        "Assistant:",
        "Hannah:"

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

    # Remove unusual symbols/emojis
    # Keep normal ASCII English/Roman Hindi

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
    # LONG TEXT PROTECTION
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

        best = max(
            positions
        )

        if best >= 100:

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
# DOMAIN PROMPT
# ============================================================

SYSTEM_PROMPT = """

You are Hannah, a friendly female voice assistant.

You are running on an ESP32 voice device.

Your primary purpose is to help with:

- Avitron Aerospace Pvt. Ltd.
- Noida
- STEM education
- STEM learning
- Artificial Intelligence
- AI
- Robotics
- Electronics
- Embedded systems
- Microcontrollers
- ESP32
- Arduino
- Sensors
- Automation
- Programming related to robotics/electronics
- Aerospace technology
- Drones
- Educational robotics
- STEM projects

============================================================
LANGUAGE RULES
============================================================

You must detect the language of the user's actual question.

If the user asks in English:
ANSWER IN ENGLISH.

Example:

User:
How are you?

Answer:
I am doing great. How can I help you?

User:
What is your name?

Answer:
My name is Hannah. How can I help you?

IMPORTANT:
Do NOT translate an English question into Hindi.

------------------------------------------------------------

If the user asks in Hindi:
ANSWER IN ROMAN HINDI.

Do NOT use Devanagari script.

Example:

User:
तुम कैसे हो?

Answer:
Main bilkul theek hoon. Aap kaise hain?

------------------------------------------------------------

If the user speaks Hinglish:
ANSWER IN NATURAL HINGLISH.

Example:

User:
Robotics kya hoti hai?

Answer:
Robotics mein robots ko design, build aur program kiya jata hai.

============================================================
BASIC CONVERSATION
============================================================

You may answer normal basic conversational questions such as:

Hello
Hi
Hey
How are you?
What is your name?
Who are you?
Good morning
Good evening
Thank you
Thanks
Bye

Keep these answers short and natural.

============================================================
DOMAIN RESTRICTION
============================================================

For questions related to the following topics, provide useful
answers:

STEM education
AI
Artificial Intelligence
Robotics
Electronics
Embedded systems
ESP32
Arduino
Sensors
Automation
Aerospace
Drones
Avitron Aerospace Pvt. Ltd.
Noida
STEM projects
Robotics projects
AI projects
Electronics projects

============================================================
UNRELATED QUESTIONS
============================================================

If the question is unrelated to STEM education, AI, robotics,
electronics, embedded systems, aerospace, Avitron Aerospace,
Noida, or basic conversation, politely say that you cannot
help with that topic.

Use the SAME language as the user.

English:

I can help with STEM education, AI, robotics, electronics and
aerospace. What can I help you with?

Roman Hindi:

Main STEM education, AI, robotics, electronics aur aerospace
se related sawalon mein madad kar sakti hoon. Main aapki kya
sahayata kar sakti hoon?

============================================================
AVITRON
============================================================

If asked about Avitron Aerospace Pvt. Ltd., answer only with
information that is actually available from the conversation
or supplied context.

Do not invent company facts.

============================================================
CONVERSATION MEMORY
============================================================

Use previous conversation context when it is available.

If the user asks:

"What did I ask before?"

or

"Uske baad kya?"

use the conversation history.

Keep continuity natural.

============================================================
VOICE STYLE
============================================================

You are speaking through a physical speaker.

Keep responses conversational.

Normally use 1-3 sentences.

Do not use markdown.

Do not use bullet points.

Do not use headings.

Do not use emojis.

Do not say "As an AI".

Do not repeat the user's question unnecessarily.

Return ONLY the answer.

"""


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
    # API KEY
    # ========================================================

    if not AI_API_KEY:

        print(
            "AI ERROR: AI_API_KEY missing"
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
    # MEMORY
    # ========================================================

    memory = get_memory()

    messages = [

        {
            "role":
                "system",

            "content":
                SYSTEM_PROMPT

        }

    ]

    # Add previous conversation

    for item in memory:

        messages.append({

            "role":
                item["role"],

            "content":
                item["content"]

        })

    # ========================================================
    # USER CONTENT
    # ========================================================

    user_content = f"""

Hindi speech recognition:
{hindi_text if hindi_text else "No result"}

English speech recognition:
{english_text if english_text else "No result"}

Important:

Determine which recognition result best represents what
the user actually said.

If English recognition clearly contains an English sentence,
treat it as English.

If Hindi recognition contains Hindi speech, answer in Roman
Hindi.

If both contain useful information, understand the intended
meaning from both.

Return only the final spoken answer.
"""

    messages.append({

        "role":
            "user",

        "content":
            user_content

    })

    # ========================================================
    # PAYLOAD
    # ========================================================

    payload = {

        "model":
            AI_MODEL,

        "messages":
            messages,

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

    try:

        print()
        print("========================================")
        print("AI REQUEST")
        print("========================================")

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

            print(
                "AI SERVER ERROR:"
            )

            print(
                response.text[:3000]
            )

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

        reply = str(
            reply
        ).strip()

        reply = clean_text(
            reply
        )

        # ====================================================
        # PREFIX
        # ====================================================

        prefixes = [

            "AI:",
            "Answer:",
            "Response:",
            "Assistant:",
            "Hannah:"

        ]

        for prefix in prefixes:

            if reply.lower().startswith(
                prefix.lower()
            ):

                reply = reply[
                    len(prefix):
                ].strip()

        # ====================================================
        # EMPTY
        # ====================================================

        if not reply:

            return (
                "No AI response. Try again."
            )

        # ====================================================
        # MEMORY SAVE
        # ========================================================

        # Save user message
        detected_query = (
            english_text
            if is_valid_query(
                english_text
            )
            else hindi_text
        )

        if detected_query:

            add_memory(
                "user",
                detected_query
            )

        # Save assistant reply

        add_memory(
            "assistant",
            reply
        )

        print()
        print("AI REPLY:")
        print(reply)

        print(
            "MEMORY MESSAGES:",
            len(get_memory())
        )

        print(
            "========================================"
        )

        return reply

    # ========================================================
    # TIMEOUT
    # ========================================================

    except requests.exceptions.Timeout:

        print(
            "AI TIMEOUT"
        )

        return (
            "No AI response. Try again."
        )

    # ========================================================
    # CONNECTION
    # ========================================================

    except requests.exceptions.ConnectionError as e:

        print(
            "AI CONNECTION ERROR:",
            str(e)
        )

        return (
            "No AI response. Try again."
        )

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

        return (
            "No AI response. Try again."
        )


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

    print(
        "TTS TEXT LENGTH:",
        len(text)
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
    # GROQ PAYLOAD
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

            print(
                "========================================"
            )

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

            pass

        print(
            "========================================"
        )

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
                    "inline; filename=hannah.wav"

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

        print(
            "========================================"
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

        print(
            "========================================"
        )

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

        print(
            "========================================"
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
# DIRECT TTS TEST
# ============================================================

@app.route(
    "/test-tts",
    methods=["GET"]
)
def test_tts():

    print()
    print("========================================")
    print("DIRECT HANNAH TTS TEST")
    print("========================================")

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
    print("ESP32 HANNAH VOICE SERVER")
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
        "TTS MAX CHARS:",
        TTS_MAX_CHARS
    )

    print(
        "MEMORY:",
        "ENABLED"
    )

    print(
        "AI KEY:",
        "CONFIGURED"
        if AI_API_KEY
        else "MISSING"
    )

    print(
        "========================================"
    )

    app.run(

        host="0.0.0.0",

        port=port,

        threaded=True

    )

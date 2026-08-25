from flask import Flask, request, jsonify, Response
import os
import speech_recognition as sr
import requests
import re
import tempfile
import traceback
import threading
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
# GROQ ORPHEUS TTS
# ============================================================

TTS_URL = os.environ.get(
    "TTS_URL",
    "https://api.groq.com/openai/v1/audio/speech"
)

TTS_MODEL = os.environ.get(
    "TTS_MODEL",
    "canopylabs/orpheus-v1-english"
)

# HANNAH FEMALE VOICE
TTS_VOICE = os.environ.get(
    "TTS_VOICE",
    "hannah"
)

# IMPORTANT:
# Groq Orpheus input maximum = 200 characters
TTS_MAX_CHARS = 200


# ============================================================
# MEMORY
# ============================================================

MAX_MEMORY_MESSAGES = 12

MEMORY_TIMEOUT = 1800

conversation_memory = {}

memory_lock = threading.Lock()


# ============================================================
# GENERAL
# ============================================================

AI_ERROR_MESSAGE = "No AI response. Try again."


# ============================================================
# HOME
# ============================================================

@app.route("/", methods=["GET"])
def home():

    return "Hannah Voice Server is ONLINE!"


# ============================================================
# HEALTH
# ============================================================

@app.route("/health", methods=["GET"])
def health():

    return jsonify({

        "status": "online",

        "assistant": "Hannah",

        "ai_model": AI_MODEL,

        "tts_model": TTS_MODEL,

        "tts_voice": TTS_VOICE,

        "tts_max_chars": TTS_MAX_CHARS,

        "memory": True,

        "language_detection": True

    })


# ============================================================
# CLEAN TEXT
# ============================================================

def clean_text(text):

    if text is None:

        return ""

    text = str(text).strip()

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
# SESSION ID
# ============================================================

def get_session_id():

    session_id = request.headers.get(
        "X-Session-ID"
    )

    if session_id:

        return clean_session_id(
            session_id
        )


    try:

        data = request.get_json(
            silent=True
        )

        if data:

            session_id = data.get(
                "session_id"
            )

            if session_id:

                return clean_session_id(
                    session_id
                )

    except Exception:

        pass


    return "default"


def clean_session_id(session_id):

    if not session_id:

        return "default"

    session_id = str(
        session_id
    ).strip()

    session_id = re.sub(
        r"[^a-zA-Z0-9_\-]",
        "_",
        session_id
    )

    return session_id[:100] or "default"


# ============================================================
# MEMORY CLEANUP
# ============================================================

def cleanup_memory():

    current_time = time.time()

    with memory_lock:

        expired = []

        for session_id, data in conversation_memory.items():

            last_activity = data.get(
                "last_activity",
                0
            )

            if (
                current_time - last_activity
                >
                MEMORY_TIMEOUT
            ):

                expired.append(
                    session_id
                )


        for session_id in expired:

            del conversation_memory[
                session_id
            ]


# ============================================================
# GET MEMORY
# ============================================================

def get_memory(session_id):

    cleanup_memory()

    with memory_lock:

        data = conversation_memory.get(
            session_id
        )

        if not data:

            return []

        return list(
            data.get(
                "messages",
                []
            )
        )


# ============================================================
# ADD MEMORY
# ============================================================

def add_memory(
    session_id,
    role,
    content
):

    content = clean_text(
        content
    )

    if not content:

        return

    with memory_lock:

        if session_id not in conversation_memory:

            conversation_memory[
                session_id
            ] = {

                "messages": [],

                "last_activity":
                    time.time()

            }


        messages = conversation_memory[
            session_id
        ]["messages"]


        messages.append({

            "role":
                role,

            "content":
                content

        })


        if len(messages) > MAX_MEMORY_MESSAGES:

            conversation_memory[
                session_id
            ]["messages"] = messages[
                -MAX_MEMORY_MESSAGES:
            ]


        conversation_memory[
            session_id
        ]["last_activity"] = time.time()


# ============================================================
# CLEAR MEMORY
# ============================================================

@app.route(
    "/clear-memory",
    methods=["GET", "POST"]
)
def clear_memory():

    session_id = get_session_id()

    with memory_lock:

        existed = (
            session_id
            in conversation_memory
        )

        if existed:

            del conversation_memory[
                session_id
            ]


    return jsonify({

        "status": "ok",

        "session_id":
            session_id,

        "memory_cleared":
            existed

    })


# ============================================================
# LANGUAGE DETECTION
# ============================================================

def detect_user_language(
    hindi_text,
    english_text
):

    hindi_text = clean_text(
        hindi_text
    ).lower()

    english_text = clean_text(
        english_text
    ).lower()


    # ========================================================
    # DEVANAGARI ENGLISH PHRASES
    # ========================================================

    english_devanagari = [

        "हाउ आर यू",
        "हाउ आरयू",
        "व्हाट इज योर नेम",
        "व्हाट्स योर नेम",
        "व्हाट इज योर",
        "व्हेयर आर यू",
        "व्हाट कैन यू डू",
        "हाउ डू यू डू",
        "गुड मॉर्निंग",
        "गुड आफ्टरनून",
        "गुड इवनिंग",
        "गुड नाइट",
        "थैंक यू",
        "थैंक्यू",
        "आई एम फाइन",
        "आई एम गुड",
        "आई एम ओके",
        "सी यू",
        "हैलो",
        "हेलो",
        "हाय",
        "टेल मी",
        "व्हाट इज",
        "व्हाट आर",
        "व्हाई",
        "व्हेन",
        "व्हेयर",
        "हू आर",
        "कैन यू",
        "कुड यू",
        "प्लीज",
        "एक्सप्लेन"

    ]


    for phrase in english_devanagari:

        if phrase in hindi_text:

            return "english"


    # ========================================================
    # NORMAL ENGLISH
    # ========================================================

    english_words = {

        "how",
        "are",
        "you",
        "what",
        "is",
        "your",
        "name",
        "who",
        "where",
        "why",
        "when",
        "can",
        "could",
        "would",
        "tell",
        "about",
        "explain",
        "please",
        "hello",
        "hi",
        "hey",
        "good",
        "morning",
        "evening",
        "night",
        "thank",
        "thanks",
        "robotics",
        "robot",
        "electronics",
        "artificial",
        "intelligence",
        "aerospace",
        "technology",
        "stem",
        "education",
        "work",
        "working",
        "help"

    }


    english_count = 0

    for word in english_text.split():

        word = re.sub(
            r"[^a-zA-Z]",
            "",
            word
        )

        if word in english_words:

            english_count += 1


    # ========================================================
    # ROMAN HINDI
    # ========================================================

    roman_hindi_words = {

        "kya",
        "kaise",
        "kaisa",
        "kaisi",
        "aap",
        "aapko",
        "mujhe",
        "mujhko",
        "mera",
        "meri",
        "mere",
        "hamara",
        "humara",
        "batao",
        "bataiye",
        "hai",
        "hain",
        "hoon",
        "hun",
        "mein",
        "me",
        "ka",
        "ki",
        "ke",
        "ko",
        "se",
        "par",
        "kyun",
        "kyon",
        "kab",
        "kahan",
        "kar",
        "karo",
        "karna",
        "karta",
        "karte",
        "karti",
        "bata",
        "chahiye",
        "chahta",
        "chahti",
        "ye",
        "yah",
        "woh",
        "vo",
        "iska",
        "iske",
        "uska",
        "uske",
        "aapka",
        "aapki",
        "aapke"

    }


    roman_count = 0

    for word in hindi_text.split():

        word = re.sub(
            r"[^a-zA-Z]",
            "",
            word
        )

        if word in roman_hindi_words:

            roman_count += 1


    # Hinglish
    if roman_count >= 1 and english_count >= 1:

        return "hinglish"


    # English
    if english_count >= 1:

        return "english"


    # Roman Hindi
    if roman_count >= 1:

        return "hindi"


    # Devanagari Hindi
    if hindi_text:

        return "hindi"


    if english_text:

        return "english"


    return "unknown"


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
        "Hannah:"

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


    # Remove TTS directions if any
    # We do not need them for normal conversation.
    text = re.sub(
        r"\[[^\]]*\]",
        "",
        text
    )


    # IMPORTANT:
    # Hannah is English Orpheus.
    # Remove Devanagari so TTS does not receive
    # unsupported Hindi script.

    text = re.sub(
        r"[\u0900-\u097F]+",
        " ",
        text
    )


    # Remove unusual Unicode
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
    # HARD 200 CHARACTER LIMIT
    # ========================================================

    if len(text) > TTS_MAX_CHARS:

        text = text[
            :TTS_MAX_CHARS
        ]


        # End at last complete word
        last_space = text.rfind(
            " "
        )

        if last_space > 80:

            text = text[
                :last_space
            ]


        # Try punctuation
        punctuation_positions = [

            text.rfind("."),

            text.rfind("?"),

            text.rfind("!"),

            text.rfind(",")

        ]


        best = max(
            punctuation_positions
        )


        if best >= 60:

            text = text[
                :best + 1
            ]


    return text.strip()


# ============================================================
# AI
# ============================================================

def get_ai_reply(
    hindi_text,
    english_text,
    session_id
):

    hindi_text = clean_text(
        hindi_text
    )

    english_text = clean_text(
        english_text
    )


    if not AI_API_KEY:

        print(
            "AI_API_KEY MISSING"
        )

        return AI_ERROR_MESSAGE


    if (
        not is_valid_query(hindi_text)
        and
        not is_valid_query(english_text)
    ):

        return (
            "Please ask your question again."
        )


    detected_language = detect_user_language(

        hindi_text,

        english_text

    )


    print(
        "DETECTED LANGUAGE:",
        detected_language
    )


    # ========================================================
    # SYSTEM PROMPT
    # ========================================================

    system_prompt = """

You are Hannah, a friendly female voice assistant for
Avitron Aerospace Pvt. Ltd.

Your main areas are:

STEM education,
Artificial Intelligence,
AI,
Robotics,
Electronics,
Embedded systems,
ESP32,
Arduino,
Microcontrollers,
Sensors,
Programming,
Science,
Technology,
Aerospace,
Educational technology.

You may also answer simple basic conversation questions.

Examples:

How are you?
I am doing great. How can I help you?

What is your name?
My name is Hannah.

Who are you?
I am Hannah, a voice assistant for Avitron Aerospace.

============================================================
LANGUAGE
============================================================

The CURRENT USER QUERY language is provided separately.

If language is ENGLISH:
Answer ONLY in English.

If language is HINDI:
Answer in natural Hindi using Roman English letters.

If language is HINGLISH:
Answer in natural Hinglish.

NEVER use Devanagari script in your answer.

============================================================
IMPORTANT DEVANAGARI ENGLISH
============================================================

Speech recognition can write English words using
Devanagari.

For example:

हाउ आर यू

means:

How are you?

Therefore:

हाउ आर यू

MUST receive:

I am doing great. How can I help you?

NOT:

Main theek hoon.

Another example:

व्हाट इज योर नेम

Answer:

My name is Hannah.

NOT:

Mera naam Hannah hai.

============================================================
REAL HINDI
============================================================

आप कैसे हो

Answer:

Main bilkul theek hoon. Aap kaise hain?

रोबोटिक्स क्या है

Answer in Roman Hindi.

============================================================
HINGLISH
============================================================

Robotics kya hai?

Answer naturally in Hinglish.

AI kya hota hai and how does it work?

Answer naturally in Hinglish.

============================================================
DOMAIN
============================================================

Focus mainly on:

STEM education
AI
Robotics
Electronics
Embedded systems
ESP32
Arduino
Sensors
Programming
Science
Technology
Aerospace

============================================================
UNRELATED
============================================================

If the question is completely unrelated:

English:
I can help with STEM education, AI, robotics, electronics and related technology. What would you like to ask?

Hindi:
Main STEM education, AI, robotics, electronics aur related technology mein help kar sakti hoon. Aap kya poochna chahenge?

============================================================
MEMORY
============================================================

Use previous conversation context.

If the user says:

Tell me more.
Explain that.
What about this?
How does it work?
Iske baare mein batao.
Ye kaise kaam karta hai?

Use the previous conversation.

Do not unnecessarily ask the user to repeat themselves.

============================================================
VOICE
============================================================

Be friendly and natural.

Basic questions:
Keep answers short.

Technical questions:
Give useful answers.

No markdown.
No bullet points.
No headings.
No emojis.
Do not repeat the question.
Do not say "As an AI".

Return ONLY the answer.
"""


    # ========================================================
    # MEMORY
    # ========================================================

    previous_messages = get_memory(
        session_id
    )


    messages = [

        {

            "role":
                "system",

            "content":
                system_prompt

        }

    ]


    for item in previous_messages:

        messages.append({

            "role":
                item["role"],

            "content":
                item["content"]

        })


    # ========================================================
    # CURRENT QUERY
    # ========================================================

    user_content = f"""

CURRENT USER QUERY:

Hindi speech recognition:
{hindi_text if hindi_text else "No result"}

English speech recognition:
{english_text if english_text else "No result"}

DETECTED LANGUAGE:
{detected_language}

IMPORTANT:

If detected language is english:
answer in English.

If detected language is hindi:
answer in Roman Hindi.

If detected language is hinglish:
answer in Hinglish.

Remember that Devanagari may contain English phonetic
speech.

Example:

हाउ आर यू

must be treated as English.

Answer ONLY the current question.
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
            500,

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
            "SESSION:",
            session_id
        )

        print(
            "LANGUAGE:",
            detected_language
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
                response.text[:5000]
            )

            return AI_ERROR_MESSAGE


        try:

            data = response.json()

        except Exception:

            print(
                "AI JSON ERROR"
            )

            return AI_ERROR_MESSAGE


        choices = data.get(
            "choices"
        )


        if not choices:

            print(
                "AI CHOICES MISSING"
            )

            print(
                data
            )

            return AI_ERROR_MESSAGE


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


        for prefix in [

            "AI:",
            "Answer:",
            "Response:",
            "Assistant:",
            "Hannah:"

        ]:

            if reply.lower().startswith(
                prefix.lower()
            ):

                reply = reply[
                    len(prefix):
                ].strip()


        if not reply:

            return AI_ERROR_MESSAGE


        # ====================================================
        # SAVE MEMORY
        # ====================================================

        if detected_language == "english":

            user_memory = (

                english_text

                if is_valid_query(
                    english_text
                )

                else hindi_text

            )

        else:

            user_memory = (

                hindi_text

                if is_valid_query(
                    hindi_text
                )

                else english_text

            )


        if user_memory:

            add_memory(

                session_id,

                "user",

                user_memory

            )


        add_memory(

            session_id,

            "assistant",

            reply

        )


        print()
        print("AI REPLY:")
        print(reply)

        print(
            "AI REPLY LENGTH:",
            len(reply)
        )

        print("========================================")


        return reply


    except requests.exceptions.Timeout:

        print(
            "AI TIMEOUT"
        )

        return AI_ERROR_MESSAGE


    except requests.exceptions.ConnectionError as e:

        print(
            "AI CONNECTION ERROR:",
            str(e)
        )

        return AI_ERROR_MESSAGE


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

    print()
    print("========================================")
    print("TTS REQUEST")
    print("========================================")


    # Clean and enforce 200 character limit
    text = clean_tts_text(
        text
    )


    print(
        "TTS TEXT:",
        text
    )

    print(
        "TTS TEXT LENGTH:",
        len(text)
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
            "TTS ERROR: EMPTY TEXT"
        )

        return None


    if not AI_API_KEY:

        print(
            "TTS ERROR: AI_API_KEY MISSING"
        )

        return None


    # ========================================================
    # GROQ DOCUMENTED PAYLOAD
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
            "SENDING GROQ TTS..."
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

        print(
            "TTS TRANSFER:",
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


            if not audio_data:

                print(
                    "TTS ERROR: EMPTY AUDIO"
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
        # IMPORTANT ERROR DEBUG
        # ====================================================

        print()
        print("========================================")
        print("TTS SERVER ERROR")
        print("========================================")

        print(
            "HTTP CODE:",
            response.status_code
        )

        print(
            "RESPONSE HEADERS:"
        )

        print(
            dict(response.headers)
        )

        print(
            "ERROR BODY:"
        )

        try:

            print(
                response.text[:10000]
            )

        except Exception as e:

            print(
                "Could not read response:",
                str(e)
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

            print(
                "TTS: NO JSON"
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
            data.get(
                "text"
            )
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
                    "TTS generation failed",

                "voice":
                    TTS_VOICE,

                "model":
                    TTS_MODEL

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
            "TTS ENDPOINT ERROR:",
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
# TEST TTS
# ============================================================

@app.route(
    "/test-tts",
    methods=["GET"]
)
def test_tts():

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
                "TTS test failed",

            "voice":
                TTS_VOICE,

            "model":
                TTS_MODEL

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
# MEMORY STATUS
# ============================================================

@app.route(
    "/memory-status",
    methods=["GET", "POST"]
)
def memory_status():

    session_id = get_session_id()

    memory = get_memory(
        session_id
    )


    return jsonify({

        "status":
            "ok",

        "session_id":
            session_id,

        "messages":
            len(memory),

        "conversation":
            memory

    })


# ============================================================
# WAKE
# ============================================================

@app.route(
    "/wake",
    methods=["POST", "GET"]
)
def wake():

    try:

        audio_data = request.get_data()


        print(
            "WAKE AUDIO BYTES:",
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

        return jsonify({

            "status":
                "error",

            "message":
                str(e)

        }), 500


# ============================================================
# TEST JSON
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


        session_id = get_session_id()


        print(
            "SESSION:",
            session_id
        )


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


        if not audio_data:

            return jsonify({

                "status":
                    "error",

                "message":
                    "No audio received",

                "ai_reply":
                    "Please ask your question again."

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
        # HINDI RECOGNITION
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
        # ENGLISH RECOGNITION
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
        # LANGUAGE
        # ====================================================

        detected_language = detect_user_language(

            hindi_text,

            english_text

        )


        print(
            "FINAL LANGUAGE:",
            detected_language
        )


        # ====================================================
        # AI
        # ====================================================

        ai_reply = get_ai_reply(

            hindi_text,

            english_text,

            session_id

        )


        # ====================================================
        # TRANSCRIPTION
        # ====================================================

        if detected_language == "english":

            transcription = (

                english_text

                if is_valid_query(
                    english_text
                )

                else hindi_text

            )

        else:

            transcription = (

                hindi_text

                if is_valid_query(
                    hindi_text
                )

                else english_text

            )


        # ====================================================
        # FINAL JSON
        # ====================================================

        response_data = {

            "status":
                "ok",

            "session_id":
                session_id,

            "language":
                detected_language,

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
    print("HANNAH ESP32 VOICE SERVER")
    print("========================================")

    print(
        "PORT:",
        port
    )

    print(
        "ASSISTANT:",
        "Hannah"
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
        "TTS MAX:",
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

    print("========================================")


    app.run(

        host="0.0.0.0",

        port=port,

        threaded=True

    )

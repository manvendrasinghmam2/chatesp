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
# HANNAH TTS
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

# Increased so long answers are not cut too early
TTS_MAX_CHARS = 1500


# ============================================================
# ERROR
# ============================================================

AI_ERROR_MESSAGE = "No AI response. Try again."


# ============================================================
# MEMORY
# ============================================================

MAX_MEMORY_MESSAGES = 12
MEMORY_TIMEOUT = 1800

conversation_memory = {}
memory_lock = threading.Lock()


# ============================================================
# SESSION ID
# ============================================================

def get_session_id():

    try:

        data = request.get_json(
            silent=True
        )

        if data:

            session_id = data.get(
                "session_id"
            )

            if session_id:

                return str(
                    session_id
                ).strip()

    except Exception:

        pass


    session_id = request.headers.get(
        "X-Session-ID"
    )

    if session_id:

        return str(
            session_id
        ).strip()


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
# CLEAN TEXT
# ============================================================

def clean_text(text):

    if text is None:

        return ""

    text = str(
        text
    ).strip()

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
# TTS CLEAN
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

    # TTS is English/Roman-Hindi.
    # Remove Devanagari and unusual Unicode.
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

    # Do not cut in middle of word/sentence
    if len(text) > TTS_MAX_CHARS:

        text = text[
            :TTS_MAX_CHARS
        ]

        last_space = text.rfind(
            " "
        )

        if last_space > 100:

            text = text[
                :last_space
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
    # ENGLISH PHRASES WRITTEN IN DEVANAGARI
    #
    # Example:
    # हाउ आर यू = How are you
    # ========================================================

    english_devanagari_phrases = [

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
        "बाय",
        "हैलो",
        "हेलो",
        "हाय",
        "टेल मी",
        "टेल मी अबाउट",
        "व्हाट इज",
        "व्हाट आर",
        "व्हाई",
        "व्हेन",
        "व्हेयर",
        "हू आर",
        "कैन यू",
        "कुड यू",
        "प्लीज",
        "एक्सप्लेन",
        "रोबोटिक्स",
        "इलेक्ट्रॉनिक्स",
        "आर्टिफिशियल इंटेलिजेंस",
        "एआई",
        "एयरोस्पेस"
    ]


    for phrase in english_devanagari_phrases:

        if phrase in hindi_text:

            return "english"


    # ========================================================
    # ENGLISH RECOGNITION CHECK
    # ========================================================

    english_words = {

        "how",
        "are",
        "you",
        "what",
        "is",
        "your",
        "name",
        "where",
        "why",
        "when",
        "who",
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
        "education"
    }


    english_words_list = (
        english_text.split()
    )


    english_count = 0


    for word in english_words_list:

        word = re.sub(
            r"[^a-zA-Z]",
            "",
            word
        )

        if word in english_words:

            english_count += 1


    # Clear English result
    if english_count >= 1:

        # If Hindi result contains strong Hindi words,
        # check for Hinglish below.
        hindi_roman_words = [

            "kya",
            "kaise",
            "kaisa",
            "kaisi",
            "aap",
            "mujhe",
            "mera",
            "meri",
            "batao",
            "bataiye",
            "hai",
            "hain",
            "hoon",
            "mein",
            "me",
            "ka",
            "ki",
            "ke",
            "ko",
            "se",
            "par",
            "kyun",
            "kab",
            "kahan",
            "ye",
            "yah",
            "woh",
            "vo",
            "iska",
            "iske",
            "uska",
            "uske",
            "karna",
            "karo"
        ]

        roman_hindi_count = 0

        for word in hindi_text.split():

            if word in hindi_roman_words:

                roman_hindi_count += 1


        if roman_hindi_count >= 2:

            return "hinglish"

        return "english"


    # ========================================================
    # ROMAN HINDI / HINGLISH
    # ========================================================

    roman_hindi_words = [

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
        "kaise",
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
        "mujhe",
        "aapka",
        "aapki",
        "aapke"
    ]


    roman_count = 0

    for word in hindi_text.split():

        word = re.sub(
            r"[^a-zA-Z]",
            "",
            word
        )

        if word in roman_hindi_words:

            roman_count += 1


    if roman_count >= 1:

        # If English words are also present
        english_in_hindi = 0

        for word in hindi_text.split():

            word = re.sub(
                r"[^a-zA-Z]",
                "",
                word
            )

            if word in english_words:

                english_in_hindi += 1


        if (
            english_in_hindi >= 1
            and
            roman_count >= 1
        ):

            return "hinglish"

        return "hindi"


    # ========================================================
    # PURE DEVANAGARI
    #
    # Default Hindi unless it matched English phrases above.
    # ========================================================

    if hindi_text:

        return "hindi"


    if english_text:

        return "english"


    return "unknown"


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

            print(
                "MEMORY EXPIRED:",
                session_id
            )


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

def clear_memory(session_id):

    with memory_lock:

        if session_id in conversation_memory:

            del conversation_memory[
                session_id
            ]

            return True

    return False


# ============================================================
# PRINT MEMORY
# ============================================================

def print_memory(session_id):

    memory = get_memory(
        session_id
    )

    print()
    print("========================================")
    print("MEMORY")
    print("SESSION:", session_id)
    print("MESSAGES:", len(memory))

    for item in memory:

        print(
            item["role"].upper(),
            ":",
            item["content"]
        )

    print("========================================")


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
            "AI ERROR: AI_API_KEY missing"
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


    # ========================================================
    # DETECT LANGUAGE
    # ========================================================

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

You can also answer basic conversation questions.

============================================================
BASIC QUESTIONS
============================================================

You can answer:

Hello
Hi
Hey
How are you?
What is your name?
Who are you?
What can you do?
Thank you
Thanks
Goodbye
Bye

Examples:

How are you?
I am doing great. How can I help you?

What is your name?
My name is Hannah.

Who are you?
I am Hannah, a voice assistant for Avitron Aerospace.

============================================================
LANGUAGE RULE
============================================================

The CURRENT USER QUERY has priority.

The detected language will be provided.

If detected language is ENGLISH:
Answer ONLY in English.

If detected language is HINDI:
Answer in natural Hindi using ONLY Roman letters.

If detected language is HINGLISH:
Answer naturally in Hinglish.

NEVER use Devanagari Hindi in the answer.

============================================================
VERY IMPORTANT
============================================================

Hindi speech recognition may incorrectly write English
sentences using Devanagari.

For example:

हाउ आर यू

means:

How are you?

Therefore:

हाउ आर यू
must receive an English answer.

Example:

User:
हाउ आर यू

Correct:
I am doing great. How can I help you?

NOT:
Main theek hoon.

Another example:

User:
व्हाट इज योर नेम

Correct:
My name is Hannah.

NOT:
Mera naam Hannah hai.

============================================================
REAL HINDI
============================================================

If the user actually speaks Hindi:

आप कैसे हैं

Answer:

Main bilkul theek hoon. Aap kaise hain?

रोबोटिक्स क्या है

Answer:

Robotics mein robots ko design, build aur program kiya jata hai.

============================================================
HINGLISH
============================================================

If the user mixes Hindi and English:

Robotics kya hai?

Answer:

Robotics mein robots ko design, build aur program kiya jata hai.

AI kya hota hai and how does it work?

Answer naturally in Hinglish.

============================================================
MEMORY
============================================================

Use previous conversation to continue natural interaction.

If user says:

Tell me more.
Explain that.
What about this?
How does it work?
Iske baare mein batao.
Ye kaise kaam karta hai?

Use previous conversation context.

Do not ask them to repeat information unnecessarily.

============================================================
DOMAIN
============================================================

You should help with:

STEM education
AI
Robotics
Electronics
Embedded systems
ESP32
Arduino
Sensors
Actuators
Programming
Science
Technology
Aerospace
Avitron Aerospace related topics.

============================================================
UNRELATED QUESTIONS
============================================================

If the question is completely unrelated to STEM,
education, AI, robotics, electronics, science,
technology or aerospace, politely redirect.

For English:

I can help with STEM education, AI, robotics, electronics
and related technology. What would you like to ask?

For Hindi:

Main STEM education, AI, robotics, electronics aur related
technology mein help kar sakti hoon. Aap kya poochna chahenge?

============================================================
AVITRON AEROSPACE
============================================================

Do not invent company information.

If exact company information is not known,
say that you do not have the exact details.

============================================================
VOICE STYLE
============================================================

Be friendly and natural.

Keep normal answers concise.

Technical questions can have longer answers.

No markdown.

No bullet points.

No emojis.

No headings.

Do not repeat the question.

Do not say "As an AI".

Return ONLY the final answer.
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

Follow the detected language strictly.

If detected language = english:
answer in English.

If detected language = hindi:
answer in Roman Hindi.

If detected language = hinglish:
answer in Hinglish.

IMPORTANT:
The Hindi recognition result may contain English words
written in Devanagari. Do not treat Devanagari as Hindi
automatically.

Example:

हाउ आर यू
is English.

Answer:
I am doing great. How can I help you?

Answer only the current question.
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


    # ========================================================
    # REQUEST
    # ========================================================

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
            "HINDI:",
            hindi_text
        )

        print(
            "ENGLISH:",
            english_text
        )

        print(
            "LANGUAGE:",
            detected_language
        )

        print(
            "MEMORY:",
            len(previous_messages)
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

        except Exception as e:

            print(
                "AI JSON ERROR:",
                str(e)
            )

            return AI_ERROR_MESSAGE


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


        if not reply:

            return AI_ERROR_MESSAGE


        # ====================================================
        # SAVE USER QUERY
        # ====================================================

        if detected_language == "english":

            memory_query = (
                english_text
                if is_valid_query(english_text)
                else hindi_text
            )

        else:

            memory_query = (
                hindi_text
                if is_valid_query(hindi_text)
                else english_text
            )


        if memory_query:

            add_memory(

                session_id,

                "user",

                memory_query
            )


        add_memory(

            session_id,

            "assistant",

            reply
        )


        print_memory(
            session_id
        )


        print()
        print("AI REPLY:")
        print(reply)

        print(
            "REPLY LENGTH:",
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
        "TTS LENGTH:",
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
            "TTS ERROR: EMPTY"
        )

        return None


    if not AI_API_KEY:

        print(
            "TTS ERROR: AI KEY MISSING"
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


    try:

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


        if response.status_code == 200:

            audio_data = response.content


            if not audio_data:

                print(
                    "TTS EMPTY AUDIO"
                )

                return None


            print(
                "TTS AUDIO BYTES:",
                len(audio_data)
            )


            print(
                "TTS SUCCESS"
            )


            return audio_data


        print(
            "TTS SERVER ERROR"
        )


        print(
            response.text[:5000]
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
            "TTS ERROR:",
            type(e).__name__,
            str(e)
        )

        traceback.print_exc()

        return None


# ============================================================
# HOME
# ============================================================

@app.route(
    "/",
    methods=["GET"]
)
def home():

    return "Hannah Voice Server is ONLINE!"


# ============================================================
# HEALTH
# ============================================================

@app.route(
    "/health",
    methods=["GET"]
)
def health():

    return jsonify({

        "status":
            "online",

        "assistant":
            "Hannah",

        "ai_model":
            AI_MODEL,

        "tts_model":
            TTS_MODEL,

        "tts_voice":
            TTS_VOICE,

        "memory":
            True,

        "language_detection":
            True

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
            "WAKE AUDIO:",
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
# TTS ENDPOINT
# ============================================================

@app.route(
    "/tts",
    methods=["POST"]
)
def tts():

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

        traceback.print_exc()


        return jsonify({

            "status":
                "error",

            "message":
                str(e)

        }), 500


# ============================================================
# CLEAR MEMORY
# ============================================================

@app.route(
    "/clear-memory",
    methods=["GET", "POST"]
)
def clear_memory_endpoint():

    try:

        session_id = clean_session_id(
            get_session_id()
        )


        cleared = clear_memory(
            session_id
        )


        return jsonify({

            "status":
                "ok",

            "session_id":
                session_id,

            "memory_cleared":
                cleared

        })


    except Exception as e:

        return jsonify({

            "status":
                "error",

            "message":
                str(e)

        }), 500


# ============================================================
# MEMORY STATUS
# ============================================================

@app.route(
    "/memory-status",
    methods=["GET", "POST"]
)
def memory_status():

    try:

        session_id = clean_session_id(
            get_session_id()
        )


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
        print("AUDIO REQUEST")
        print("========================================")


        session_id = clean_session_id(
            get_session_id()
        )


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


        # ====================================================
        # SPEECH
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
                "Hindi not understood"
            )


        except sr.RequestError as e:

            print(
                "Google Speech Error:",
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
                "English not understood"
            )


        except sr.RequestError as e:

            print(
                "Google Speech Error:",
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
        # VALIDATION
        # ====================================================

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


        # ====================================================
        # DETECT LANGUAGE
        # ====================================================

        detected_language = detect_user_language(

            hindi_text,

            english_text

        )


        print(
            "FINAL DETECTED LANGUAGE:",
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
        # RESPONSE
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


        return jsonify(
            response_data
        )


    except Exception as e:

        print()
        print("SERVER ERROR")


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
# TEST TTS
# ============================================================

@app.route(
    "/test-tts",
    methods=["GET"]
)
def test_tts():

    test_text = (

        "Hello, I am Hannah. "

        "I can help you with STEM education, "

        "artificial intelligence, robotics, "

        "electronics and aerospace technology."

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
        "MEMORY:",
        "ENABLED"
    )

    print(
        "LANGUAGE DETECTION:",
        "ENABLED"
    )

    print(
        "TTS MAX CHARS:",
        TTS_MAX_CHARS
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

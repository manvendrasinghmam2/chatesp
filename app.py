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

# ============================================================
# HANNAH VOICE
# ============================================================

TTS_VOICE = os.environ.get(
    "TTS_VOICE",
    "hannah"
)


# ============================================================
# TTS TEXT LIMIT
# ============================================================

# Pehle 200 chars tha.
# Ab answer ko unnecessarily chhota nahi karenge.
TTS_MAX_CHARS = 1500


# ============================================================
# AI ERROR MESSAGE
# ============================================================

AI_ERROR_MESSAGE = (
    "No AI response. Try again."
)


# ============================================================
# MEMORY CONFIG
# ============================================================

# 12 messages = approximately 6 user/assistant exchanges
MAX_MEMORY_MESSAGES = 12

# 30 minutes inactivity ke baad memory expire
MEMORY_TIMEOUT = 1800


# ============================================================
# GLOBAL CONVERSATION MEMORY
# ============================================================

conversation_memory = {}

memory_lock = threading.Lock()


# ============================================================
# GET SESSION ID
# ============================================================

def get_session_id():

    # --------------------------------------------------------
    # JSON
    # --------------------------------------------------------

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


    # --------------------------------------------------------
    # HTTP HEADER
    # --------------------------------------------------------

    session_id = request.headers.get(
        "X-Session-ID"
    )

    if session_id:

        return str(
            session_id
        ).strip()


    # --------------------------------------------------------
    # DEFAULT
    # --------------------------------------------------------

    return "default"


# ============================================================
# CLEAN SESSION ID
# ============================================================

def clean_session_id(session_id):

    if not session_id:

        return "default"

    session_id = str(
        session_id
    ).strip()

    if len(session_id) > 100:

        session_id = session_id[:100]

    session_id = re.sub(
        r"[^a-zA-Z0-9_\-]",
        "_",
        session_id
    )

    return session_id or "default"


# ============================================================
# CLEAN TEXT
# ============================================================

def clean_text(text):

    if text is None:

        return ""

    text = str(
        text
    )

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


    # --------------------------------------------------------
    # Remove prefixes
    # --------------------------------------------------------

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


    # --------------------------------------------------------
    # Remove markdown
    # --------------------------------------------------------

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
    # Remove unsupported Unicode
    #
    # Hindi Devanagari remove hogi.
    # Roman Hindi/Hinglish rahega.
    # --------------------------------------------------------

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


    # --------------------------------------------------------
    # MAX LENGTH
    # --------------------------------------------------------

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
# CLEAN EXPIRED MEMORY
# ============================================================

def cleanup_memory():

    current_time = time.time()

    with memory_lock:

        expired_sessions = []

        for session_id, session_data in conversation_memory.items():

            last_activity = session_data.get(
                "last_activity",
                0
            )

            if (
                current_time - last_activity
                >
                MEMORY_TIMEOUT
            ):

                expired_sessions.append(
                    session_id
                )


        for session_id in expired_sessions:

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

        session_data = conversation_memory.get(
            session_id
        )

        if not session_data:

            return []

        return list(
            session_data.get(
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

    if not content:

        return

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
        ][
            "messages"
        ]


        messages.append({

            "role":
                role,

            "content":
                content

        })


        # ----------------------------------------------------
        # Keep latest messages only
        # ----------------------------------------------------

        if len(messages) > MAX_MEMORY_MESSAGES:

            conversation_memory[
                session_id
            ][
                "messages"
            ] = messages[
                -MAX_MEMORY_MESSAGES:
            ]


        conversation_memory[
            session_id
        ][
            "last_activity"
        ] = time.time()


# ============================================================
# CLEAR MEMORY
# ============================================================

def clear_memory(session_id):

    with memory_lock:

        if session_id in conversation_memory:

            del conversation_memory[
                session_id
            ]

            print(
                "MEMORY CLEARED:",
                session_id
            )

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
    print("CURRENT MEMORY")
    print("SESSION:", session_id)
    print("MESSAGES:", len(memory))
    print("========================================")


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


    # ========================================================
    # API KEY
    # ========================================================

    if not AI_API_KEY:

        print(
            "AI ERROR: AI_API_KEY missing"
        )

        return AI_ERROR_MESSAGE


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

You are Hannah, a friendly female voice assistant for
Avitron Aerospace Pvt. Ltd.

Your main knowledge areas are:

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
Actuators,
Programming,
Science,
Technology,
Aerospace,
Educational technology,
and Avitron Aerospace Pvt. Ltd.

You can also answer basic conversational questions.

============================================================
BASIC CONVERSATION
============================================================

You may answer:

Hello
Hi
Hey
How are you?
How are you doing?
What is your name?
Who are you?
What can you do?
Who made you?
Thank you
Thanks
Goodbye
Bye
Nice to meet you

Examples:

User:
Hello

Answer:
Hello! How can I help you today?

User:
How are you?

Answer:
I am doing great. How can I help you?

User:
What is your name?

Answer:
My name is Hannah.

User:
Who are you?

Answer:
I am Hannah, a voice assistant for Avitron Aerospace.

User:
What can you do?

Answer:
I can help with STEM education, AI, robotics, electronics
and related technology.


============================================================
IMPORTANT LANGUAGE RULE
============================================================

You MUST detect the language of the CURRENT user query.

There are three response modes.


============================================================
MODE 1: HINDI
============================================================

If the user speaks Hindi:

Answer in Hindi.

BUT write Hindi using ONLY Roman/English letters.

NEVER use Devanagari Hindi script.

Example:

User:
Delhi jaane ke liye kya hai?

Correct:
Delhi jaane ke liye aap train, bus, flight ya car se ja sakte hain.

Wrong:
दिल्ली जाने के लिए आप ट्रेन, बस, फ्लाइट या कार से जा सकते हैं।


Example:

User:
Aap kaise ho?

Correct:
Main bilkul theek hoon. Aap kaise hain?


Example:

User:
Robotics kya hoti hai?

Correct:
Robotics mein robots ko design, build aur program kiya jata hai.


============================================================
MODE 2: ENGLISH
============================================================

If the user speaks English:

Answer completely in natural English.

Example:

User:
How can I go to Delhi?

Correct:
You can go to Delhi by train, bus, flight, or car.

Do NOT translate the answer into Hindi.


============================================================
MODE 3: HINGLISH
============================================================

If the user mixes Hindi and English:

Answer naturally in Hinglish.

Example:

User:
Delhi kaise go kar sakte hain?

Correct:
Aap Delhi train, bus, flight ya car se ja sakte hain.


Example:

User:
Robotics kya hoti hai and how does it work?

Correct:
Robotics mein robots ko design aur program kiya jata hai.
They use sensors, controllers and motors to perform tasks.


============================================================
VERY IMPORTANT LANGUAGE DETECTION
============================================================

You will receive two speech recognition results:

Hindi speech recognition:
{hindi_text}

English speech recognition:
{english_text}

DO NOT automatically choose English just because
an English recognition result exists.

Speech recognition can produce incorrect translations.

Determine the language based on the user's actual wording.

If the user's wording is clearly Hindi:
use Roman Hindi.

If clearly English:
use English.

If mixed:
use Hinglish.

The CURRENT query language has priority over previous
conversation language.


============================================================
CONVERSATION MEMORY
============================================================

Previous conversation messages are provided to you.

Use them to maintain natural chat-style communication.

If the user says:

Tell me more.
Explain that.
How does it work?
What about this?
Iske baare mein batao.
Ye kaise kaam karta hai?

Use the previous conversation to understand what
"that", "this", "it", "iske", or "ye" refers to.

Do not ask the user to repeat information that already
exists in the conversation history.


============================================================
DOMAIN
============================================================

Help with:

STEM education
AI
Artificial Intelligence
Robotics
Electronics
Embedded systems
ESP32
Arduino
Microcontrollers
Sensors
Actuators
Programming
Science
Technology
Aerospace
Educational technology
Avitron Aerospace Pvt. Ltd.


============================================================
UNRELATED QUESTIONS
============================================================

If the question is completely unrelated to STEM,
education, AI, robotics, electronics, embedded systems,
science, technology, aerospace or Avitron Aerospace,
and it is NOT a basic conversational question:

For Hindi/Hinglish say:

Main STEM education, AI, robotics, electronics aur related
technology mein help kar sakti hoon. Aap kya poochna chahenge?

For English say:

I can help with STEM education, AI, robotics, electronics
and related technology. What would you like to ask?


============================================================
AVITRON AEROSPACE
============================================================

If asked about Avitron Aerospace Pvt. Ltd.:

Never invent company information.

Do not invent:

courses,
products,
employees,
addresses,
facilities,
achievements,
certifications,
partnerships,
programs,
or other facts.

Only provide information that you actually know.

If exact information is unavailable:

Is information ke baare mein mere paas abhi exact details
nahi hain. Aap STEM, robotics, AI, electronics ya aerospace
se related kuch pooch sakte hain.


============================================================
VOICE STYLE
============================================================

You are a voice assistant.

Sound natural.

Sound friendly.

Sound conversational.

Do not use markdown.

Do not use bullet points.

Do not use emojis.

Do not use headings.

Do not repeat the user's question.

Do not say "As an AI".

Do not unnecessarily shorten technical answers.

Do not stop a sentence in the middle.

Normal answers should usually be concise.

Technical answers may be longer when needed.

The answer must be suitable for voice playback.


============================================================
TTS LANGUAGE
============================================================

The TTS voice is an English voice.

Therefore:

English = normal English.

Hindi = Roman Hindi.

Hinglish = Roman Hindi + English.

NEVER output Devanagari Hindi.

============================================================

Return ONLY the final answer.
"""


    # ========================================================
    # MEMORY
    # ========================================================

    previous_messages = get_memory(
        session_id
    )


    # ========================================================
    # MESSAGE ARRAY
    # ========================================================

    messages = [

        {
            "role":
                "system",

            "content":
                system_prompt
        }

    ]


    # --------------------------------------------------------
    # Add previous conversation
    # --------------------------------------------------------

    for item in previous_messages:

        messages.append({

            "role":
                item["role"],

            "content":
                item["content"]

        })


    # ========================================================
    # CURRENT USER CONTENT
    # ========================================================

    user_content = f"""

CURRENT USER QUERY

Hindi speech recognition:
{hindi_text if hindi_text else "No result"}

English speech recognition:
{english_text if english_text else "No result"}


IMPORTANT:

First determine the language of the CURRENT query.

If Hindi:
answer in Roman Hindi.

If English:
answer in English.

If Hinglish:
answer in Hinglish.

Do not choose English merely because an English
speech recognition result exists.

Use previous conversation only for context.

Answer ONLY the current user's question.
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
    # AI REQUEST
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


        # ====================================================
        # ERROR
        # ====================================================

        if response.status_code != 200:

            print(
                "AI SERVER ERROR:"
            )

            print(
                response.text[:5000]
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
        # EMPTY RESPONSE
        # ====================================================

        if not reply:

            print(
                "AI ERROR: EMPTY RESPONSE"
            )

            return AI_ERROR_MESSAGE


        # ====================================================
        # SAVE USER QUERY
        # ====================================================

        user_message_for_memory = None


        if is_valid_query(
            hindi_text
        ) and not is_valid_query(
            english_text
        ):

            user_message_for_memory = (
                hindi_text
            )

        elif is_valid_query(
            english_text
        ) and not is_valid_query(
            hindi_text
        ):

            user_message_for_memory = (
                english_text
            )

        elif is_valid_query(
            hindi_text
        ):

            # Hindi preferred if both are valid
            user_message_for_memory = (
                hindi_text
            )

        elif is_valid_query(
            english_text
        ):

            user_message_for_memory = (
                english_text
            )


        # ====================================================
        # MEMORY SAVE
        # ====================================================

        if user_message_for_memory:

            add_memory(

                session_id,

                "user",

                user_message_for_memory
            )


        add_memory(

            session_id,

            "assistant",

            reply
        )


        # ====================================================
        # DEBUG
        # ====================================================

        print_memory(
            session_id
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
            "TTS ERROR: EMPTY TEXT"
        )

        return None


    if not AI_API_KEY:

        print(
            "TTS ERROR: AI_API_KEY MISSING"
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


            print(
                "========================================"
            )


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


        try:

            print(
                "ERROR BODY:",
                response.text[:5000]
            )

        except Exception:

            print(
                "Could not read error body."
            )


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
# HOME
# ============================================================

@app.route(
    "/",
    methods=["GET"]
)
def home():

    return (
        "Hannah Voice Server is ONLINE!"
    )


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
            True,

        "memory_messages":
            MAX_MEMORY_MESSAGES

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


        print(
            "========================================"
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
# CLEAR MEMORY
# ============================================================

@app.route(
    "/clear-memory",
    methods=["POST", "GET"]
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

            "max_messages":
                MAX_MEMORY_MESSAGES,

            "timeout":
                MEMORY_TIMEOUT,

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
        print("AUDIO REQUEST RECEIVED")
        print("========================================")


        # ====================================================
        # SESSION
        # ====================================================

        session_id = clean_session_id(
            get_session_id()
        )


        print(
            "SESSION ID:",
            session_id
        )


        # ====================================================
        # AUDIO
        # ====================================================

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
        # EMPTY AUDIO
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
        # SPEECH RECOGNIZER
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
        # HINDI SPEECH
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
        # ENGLISH SPEECH
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

            english_text,

            session_id

        )


        # ====================================================
        # BEST TRANSCRIPTION
        # ====================================================

        if is_valid_query(
            hindi_text
        ):

            transcription = (
                hindi_text
            )

        elif is_valid_query(
            english_text
        ):

            transcription = (
                english_text
            )

        else:

            transcription = None


        # ====================================================
        # FINAL JSON
        # ====================================================

        response_data = {

            "status":
                "ok",

            "session_id":
                session_id,

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
    print("HANNAH TTS TEST")
    print("========================================")


    test_text = (

        "Hello, I am Hannah. "

        "I can help you with STEM education, "

        "artificial intelligence, robotics, "

        "electronics, embedded systems "

        "and aerospace technology."

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
# START SERVER
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
        "TTS MAX CHARS:",
        TTS_MAX_CHARS
    )


    print(
        "MEMORY MESSAGES:",
        MAX_MEMORY_MESSAGES
    )


    print(
        "MEMORY TIMEOUT:",
        MEMORY_TIMEOUT,
        "seconds"
    )


    print(
        "AI KEY:",
        "CONFIGURED"
        if AI_API_KEY
        else "MISSING"
    )


    print(
        "DOMAIN:",
        "STEM | AI | Robotics | Electronics | Aerospace"
    )


    print(
        "========================================"
    )


    app.run(

        host="0.0.0.0",

        port=port,

        threaded=True

    )

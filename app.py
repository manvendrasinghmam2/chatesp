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


# ============================================================
# HANNAH VOICE
# ============================================================

TTS_VOICE = os.environ.get(
    "TTS_VOICE",
    "hannah"
)


# ============================================================
# TTS MAXIMUM TEXT
# ============================================================

TTS_MAX_CHARS = 1500


# ============================================================
# AI ERROR MESSAGE
# ============================================================

AI_ERROR_MESSAGE = (
    "No AI response. Try again."
)


# ============================================================
# CONVERSATION MEMORY
# ============================================================

# Maximum number of previous user/assistant messages
# stored for one session.
#
# 12 messages means approximately:
#
# User
# Diana
# User
# Diana
# ...
#
# up to 6 conversation exchanges.
#
# Increase if required.
# ============================================================

MAX_MEMORY_MESSAGES = 12


# ============================================================
# MEMORY EXPIRATION
# ============================================================

# Memory will automatically expire after this many seconds
# if no new conversation happens.
#
# 30 minutes = 1800 seconds
# ============================================================

MEMORY_TIMEOUT = 1800


# ============================================================
# GLOBAL MEMORY
# ============================================================

conversation_memory = {}

memory_lock = threading.Lock()


# ============================================================
# MEMORY STRUCTURE
# ============================================================

"""
conversation_memory = {

    "default": {

        "messages": [
            {
                "role": "user",
                "content": "Hello"
            },
            {
                "role": "assistant",
                "content": "Hello! How can I help you?"
            }
        ],

        "last_activity": 1234567890
    }

}
"""


# ============================================================
# GET SESSION ID
# ============================================================

def get_session_id():

    # --------------------------------------------------------
    # First try JSON
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
    # Then try HTTP header
    # --------------------------------------------------------

    session_id = request.headers.get(
        "X-Session-ID"
    )

    if session_id:

        return str(
            session_id
        ).strip()


    # --------------------------------------------------------
    # Default session
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

    # Prevent extremely large session IDs

    if len(session_id) > 100:

        session_id = session_id[:100]

    # Only safe characters

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

    # Multiple spaces

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
    # Remove common AI prefixes
    # --------------------------------------------------------

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
    # Hannah/Orpheus English voice ke liye
    # Roman Hindi/Hinglish use karna better hai.
    # --------------------------------------------------------

    text = re.sub(
        r"[^\x00-\x7F]+",
        " ",
        text
    )


    # Multiple spaces

    text = re.sub(
        r"\s+",
        " ",
        text
    )

    text = text.strip()


    # --------------------------------------------------------
    # TTS LENGTH
    # --------------------------------------------------------

    if len(text) > TTS_MAX_CHARS:

        print(
            "TTS TEXT TOO LONG:",
            len(text)
        )

        text = text[
            :TTS_MAX_CHARS
        ]

        # Avoid cutting middle of a word

        last_space = text.rfind(
            " "
        )

        if last_space > 100:

            text = text[
                :last_space
            ]


    print(
        "FINAL TTS TEXT LENGTH:",
        len(text)
    )

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
# CLEAN OLD MEMORY
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
        # Keep only latest messages
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
# MEMORY DEBUG
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
    # QUERY VALIDATION
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

You are Diana, a friendly female voice assistant for
Avitron Aerospace Pvt. Ltd.

You are designed for natural continuous voice conversation.

============================================================
MAIN KNOWLEDGE AREAS
============================================================

Your main areas are:

STEM education.

Robotics.

Artificial Intelligence.

AI projects.

Machine learning education.

Electronics.

Embedded systems.

ESP32.

Arduino.

Microcontrollers.

Sensors.

Actuators.

Robotics projects.

Programming related to robotics.

Programming related to AI.

Programming related to electronics.

Science and technology education.

Aerospace technology.

Educational aerospace technology.

Avitron Aerospace Pvt. Ltd.

============================================================
CONTINUOUS CONVERSATION
============================================================

You have access to previous conversation messages.

Use previous messages to understand context.

If the user says:

"Tell me more."

"Explain that."

"What about this?"

"How does it work?"

"Why?"

"Give me an example."

understand what "that", "this", or "it" refers to
from the previous conversation.

Do NOT ask the user to repeat information that is already
available in the conversation history.

Maintain a natural chat-like interaction.

============================================================
BASIC CONVERSATION
============================================================

Basic conversation is ALWAYS allowed.

You can answer:

Hello.

Hi.

Hey.

Good morning.

Good afternoon.

Good evening.

How are you?

How are you doing?

What is your name?

Who are you?

What can you do?

Who made you?

Where are you from?

Thank you.

Thanks.

Goodbye.

Bye.

Nice to meet you.

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
My name is Diana.

User:
Who are you?

Answer:
I am Diana, a voice assistant for Avitron Aerospace.

User:
What can you do?

Answer:
I can help with STEM education, AI, robotics, electronics
and related technology.

============================================================
DOMAIN RULE
============================================================

If the question is related to:

STEM,
education,
AI,
Artificial Intelligence,
robotics,
electronics,
embedded systems,
ESP32,
Arduino,
microcontrollers,
sensors,
programming,
science,
technology,
aerospace,
educational technology,
or Avitron Aerospace,

answer helpfully.

Basic conversational questions are also allowed.

============================================================
UNRELATED QUESTIONS
============================================================

If the question is completely unrelated to:

STEM,
education,
AI,
robotics,
electronics,
embedded systems,
science,
technology,
aerospace,
Avitron Aerospace,

and it is NOT a basic conversational question,

do not answer the unrelated topic.

Instead say:

I can help with STEM education, AI, robotics, electronics
and related technology. What would you like to learn?

For Hindi/Hinglish:

Main STEM education, AI, robotics, electronics aur related
technology mein help kar sakti hoon. Aap kya poochna chahenge?

============================================================
AVITRON AEROSPACE
============================================================

If the user asks about Avitron Aerospace Pvt. Ltd.:

Only provide information you actually know.

Never invent:

Company facts.

Courses.

Products.

Facilities.

Employees.

Addresses.

Achievements.

Partnerships.

Certifications.

Programs.

If exact information is not available, say:

Is information ke baare mein mere paas abhi exact details
nahi hain. Aap Avitron ke STEM, robotics, AI, electronics
ya aerospace programs ke baare mein pooch sakte hain.

============================================================
LANGUAGE
============================================================

The user may speak:

English.

Hindi.

Hinglish.

Roman Hindi.

Understand the intended meaning.

If user speaks English:
answer in natural English.

If user speaks Hindi:
answer in natural Roman Hindi or Hinglish.

If user speaks Hinglish:
answer in natural Hinglish.

IMPORTANT:

NEVER use Devanagari Hindi script.

Hindi must ALWAYS be written using English/Roman letters.

Examples:

User:
Aap kaise ho?

Answer:
Main bilkul theek hoon. Aap kaise hain?

User:
Aapka naam kya hai?

Answer:
Mera naam Diana hai.

User:
Aap kya kar sakti ho?

Answer:
Main STEM education, AI, robotics aur electronics mein
aapki madad kar sakti hoon.

User:
Robotics kya hoti hai?

Answer:
Robotics ek technology field hai jisme robots ko design,
build aur program kiya jata hai.

============================================================
VOICE ANSWER RULE
============================================================

You are speaking through a voice assistant.

Make answers natural and easy to speak.

Usually answer in one or two sentences.

Technical questions can use three or more short sentences
when necessary.

Do NOT unnecessarily shorten a useful answer.

Do NOT stop an answer in the middle of a sentence.

Do NOT cut important information just to make the answer
short.

Try to keep normal answers below 400 characters.

Technical answers may be longer when necessary.

No markdown.

No bullet points.

No emojis.

No headings.

Do not repeat the user's question.

Do not say "As an AI".

Sound friendly.

Sound natural.

Sound conversational.

============================================================
TTS
============================================================

The response will be spoken by an English voice.

Never use Devanagari.

Use English or Roman Hindi.

Do not include unnecessary special characters.

============================================================

Return ONLY the final answer.
"""


    # ========================================================
    # PREVIOUS MEMORY
    # ========================================================

    previous_messages = get_memory(
        session_id
    )


    # ========================================================
    # BUILD MESSAGE LIST
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
    # CURRENT USER MESSAGE
    # ========================================================

    user_content = f"""

Hindi speech recognition:

{hindi_text if hindi_text else "No result"}

English speech recognition:

{english_text if english_text else "No result"}

Understand the intended meaning of the current user request.

Use previous conversation context when relevant.

Return only the final answer.
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
            "MEMORY MESSAGES:",
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
        # AI SERVER ERROR
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
        # EMPTY
        # ====================================================

        if not reply:

            print(
                "AI ERROR: Empty response"
            )

            return AI_ERROR_MESSAGE


        # ====================================================
        # SAVE CONVERSATION
        # ====================================================

        # IMPORTANT:
        # Save only recognized/current query.
        #
        # Prefer English transcription if available.
        # Otherwise Hindi transcription.
        # ====================================================

        user_message_for_memory = None


        if is_valid_query(
            english_text
        ):

            user_message_for_memory = (
                english_text
            )

        elif is_valid_query(
            hindi_text
        ):

            user_message_for_memory = (
                hindi_text
            )


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
        # DEBUG MEMORY
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
            "TTS ERROR: empty text"
        )

        return None


    if not AI_API_KEY:

        print(
            "TTS ERROR: AI_API_KEY missing"
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


        was_cleared = clear_memory(
            session_id
        )


        return jsonify({

            "status":
                "ok",

            "session_id":
                session_id,

            "memory_cleared":
                was_cleared

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

            "memory_timeout":
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

            english_text,

            session_id
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
    print("DIRECT TTS TEST")
    print("========================================")


    test_text = (

        "Hello, I am Diana. "

        "I can help you with STEM education, "

        "artificial intelligence, "

        "robotics, electronics, "

        "embedded systems and aerospace technology."

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


    print(
        "========================================"
    )


    app.run(

        host="0.0.0.0",

        port=port,

        threaded=True
    )

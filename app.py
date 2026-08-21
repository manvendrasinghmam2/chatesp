from flask import Flask, request, jsonify
import os
import speech_recognition as sr
import requests
import re
import threading
import time
from collections import deque


# =========================================================
# APP
# =========================================================

app = Flask(__name__)


# =========================================================
# CONFIG
# =========================================================

AI_API_KEY = os.environ.get("AI_API_KEY", "").strip()

AI_URL = os.environ.get(
    "AI_URL",
    "https://api.groq.com/openai/v1/chat/completions"
).strip()

AI_MODEL = os.environ.get(
    "AI_MODEL",
    "llama-3.1-8b-instant"
).strip()


# =========================================================
# MEMORY SETTINGS
# =========================================================

# Number of previous conversation turns.
# 6 turns = 12 messages.
#
# This keeps the prompt small and fast.
MAX_MEMORY_TURNS = 6

# Delete memory after this much inactivity.
MEMORY_TIMEOUT = 30 * 60

# In-memory conversation store.
#
# Since your ESP32 is currently one assistant device,
# one global memory is enough.
conversation_memory = deque(
    maxlen=MAX_MEMORY_TURNS * 2
)

memory_lock = threading.Lock()

last_memory_time = 0


# =========================================================
# LOCK FOR AI REQUESTS
# =========================================================

ai_lock = threading.Lock()


# =========================================================
# HOME
# =========================================================

@app.route("/", methods=["GET"])
def home():

    return "ESP32 Voice Server is ONLINE!"


# =========================================================
# HEALTH
# =========================================================

@app.route("/health", methods=["GET"])
def health():

    return jsonify({
        "status": "online",
        "speech_engine": "Google Speech Recognition",
        "ai_engine": "Groq",
        "model": AI_MODEL,
        "memory": "enabled",
        "memory_turns": MAX_MEMORY_TURNS
    })


# =========================================================
# WAKE
# =========================================================

@app.route("/wake", methods=["POST", "GET"])
def wake():

    return jsonify({
        "status": "ok",
        "wake": True,
        "english": "Hello",
        "hindi": None
    })


# =========================================================
# TEXT CLEANING
# =========================================================

def clean_text(text):

    if text is None:
        return ""

    text = str(text)

    # Remove null characters
    text = text.replace("\x00", "")

    # Remove excessive spaces
    text = re.sub(r"\s+", " ", text)

    return text.strip()


# =========================================================
# VALID QUERY
# =========================================================

def is_valid_query(text):

    text = clean_text(text)

    if not text:
        return False

    if len(text) < 2:
        return False

    bad_values = {
        "unknown",
        "none",
        "null",
        "no response",
        "no valid query",
        "speech not understood",
        "could not understand",
        "please say that again"
    }

    if text.lower() in bad_values:
        return False

    return True


# =========================================================
# MEMORY CLEAR
# =========================================================

def clear_memory():

    global last_memory_time

    with memory_lock:

        conversation_memory.clear()

        last_memory_time = time.time()


# =========================================================
# MEMORY CLEANUP
# =========================================================

def cleanup_memory():

    global last_memory_time

    now = time.time()

    with memory_lock:

        if (
            conversation_memory
            and last_memory_time > 0
            and now - last_memory_time > MEMORY_TIMEOUT
        ):

            conversation_memory.clear()

        last_memory_time = now


# =========================================================
# ADD USER MESSAGE
# =========================================================

def add_user_memory(text):

    global last_memory_time

    text = clean_text(text)

    if not text:
        return

    cleanup_memory()

    with memory_lock:

        conversation_memory.append({
            "role": "user",
            "content": text
        })

        last_memory_time = time.time()


# =========================================================
# ADD AI MESSAGE
# =========================================================

def add_ai_memory(text):

    global last_memory_time

    text = clean_text(text)

    if not text:
        return

    with memory_lock:

        conversation_memory.append({
            "role": "assistant",
            "content": text
        })

        last_memory_time = time.time()


# =========================================================
# GET MEMORY
# =========================================================

def get_memory():

    cleanup_memory()

    with memory_lock:

        return list(conversation_memory)


# =========================================================
# BEST TRANSCRIPTION
# =========================================================

def choose_transcription(
    hindi_text,
    english_text
):

    hindi_text = clean_text(hindi_text)
    english_text = clean_text(english_text)

    hindi_valid = is_valid_query(hindi_text)
    english_valid = is_valid_query(english_text)

    # -----------------------------------------------------
    # Only English
    # -----------------------------------------------------

    if english_valid and not hindi_valid:

        return english_text


    # -----------------------------------------------------
    # Only Hindi
    # -----------------------------------------------------

    if hindi_valid and not english_valid:

        return hindi_text


    # -----------------------------------------------------
    # Both available
    #
    # For AI we send BOTH.
    #
    # For displayed transcription, choose English if
    # available because Google often gives better English
    # text for English/Hinglish.
    # -----------------------------------------------------

    if english_valid:

        return english_text

    return hindi_text


# =========================================================
# SYSTEM PROMPT
# =========================================================

SYSTEM_PROMPT = r"""
You are a fast, natural voice assistant similar to Alexa.

You are running on an ESP32 voice device.

Your personality:
- calm
- friendly
- intelligent
- concise
- natural
- conversational

The user speaks through a microphone.

Speech recognition can produce:
1. Hindi transcription
2. English transcription

Both can be inaccurate.

Your job is to understand the user's intended meaning using:
- current speech
- both transcriptions
- previous conversation memory
- context

IMPORTANT:
Never talk about transcription.
Never talk about memory.
Never say you are reading Hindi/English transcription.
Never explain your internal reasoning.

==================================================
LANGUAGE
==================================================

If user speaks English:
Answer in English.

If user speaks Hindi:
Answer in Hindi using Devanagari.

If user speaks Hinglish:
Answer in natural Roman Hinglish.

Do not unnecessarily switch language.

==================================================
CONTEXT
==================================================

Use previous conversation naturally.

Example:

User:
How about the weather today?

Assistant:
I can help with that. Which city?

User:
Noida City

Correct behavior:
Understand that "Noida City" is the answer to the previous city question.

Do NOT respond:
"Could you please ask a complete question?"

Instead understand the context.

Example:

User:
What is the capital of India?

Assistant:
New Delhi.

User:
Population?

Correct behavior:
Understand that the user is asking about the population of India.

Example:

User:
Who is Elon Musk?

Assistant:
...

User:
How old is he?

Correct behavior:
Understand "he" refers to Elon Musk.

==================================================
SHORT FOLLOW-UP QUESTIONS
==================================================

Users may say incomplete phrases such as:

"about it"
"population"
"where"
"today"
"Noida"
"Google"
"iske baare mein batao"
"इसके बारे में बताओ"

Use previous conversation to determine what they mean.

Do NOT treat a short follow-up as an error.

==================================================
WEATHER
==================================================

You do NOT have guaranteed live weather data.

Never invent current weather.

If the user asks for current weather and no live weather data
has been supplied, say briefly:

"I don't have live weather data right now."

If a city is supplied after a weather question, remember the city
for the conversation.

Do not pretend that you fetched Google weather.

==================================================
GENERAL QUESTIONS
==================================================

Answer simple questions directly.

Do not over-explain.

Voice answers should normally be:
1 to 3 sentences.

==================================================
VOICE STYLE
==================================================

Speak naturally.

Do not use:
- markdown
- bullet points
- headings
- emojis
- code
- long explanations
- unnecessary greetings
- "As an AI"
- "According to the transcription"

Do not repeat the user's question.

Do not say "Sure" unless it sounds natural.

==================================================
IMPORTANT MEMORY RULE
==================================================

Previous messages are conversation context.

Use them when the current user message is incomplete.

Do not blindly repeat old answers.

Answer the CURRENT question.

==================================================
EMPTY ANSWER
==================================================

Always produce a useful answer.

Never return an empty response.

If the question is genuinely unclear, ask one short clarification.

==================================================
EXAMPLES
==================================================

User:
How are you?

Answer:
I'm doing well. How can I help?

User:
Tum kaise ho?

Answer:
Main bilkul theek hoon. Aap kaise hain?

User:
Noida kahan hai?

Answer:
Noida Uttar Pradesh mein hai aur Delhi NCR ka hissa hai.

User:
भारत की राजधानी क्या है?

Answer:
भारत की राजधानी नई दिल्ली है।

User:
How about the weather today?

Answer:
Which city should I check?

User:
Noida City

Answer:
I don't have live weather data right now.

User:
What is the capital of India?

Assistant:
New Delhi.

User:
Population?

Answer:
India has a population of over 1.4 billion people.

==================================================
FINAL RULE
==================================================

Understand intent first.

Then give the shortest useful natural answer.
"""


# =========================================================
# BUILD USER MESSAGE
# =========================================================

def build_user_content(
    hindi_text,
    english_text
):

    hindi_text = clean_text(hindi_text)
    english_text = clean_text(english_text)

    if not hindi_text:
        hindi_text = "No Hindi result"

    if not english_text:
        english_text = "No English result"

    return f"""
Current user speech:

Hindi recognition:
{hindi_text}

English recognition:
{english_text}

Understand the user's intended meaning using the conversation
history and answer naturally.

If this is a short follow-up, connect it to the previous turn.
"""


# =========================================================
# REMOVE BAD AI PREFIX
# =========================================================

def clean_ai_reply(reply):

    if reply is None:
        return ""

    reply = str(reply)

    reply = reply.replace("```", "")

    reply = re.sub(
        r"^\s*(AI|Assistant|Answer|Response)\s*:\s*",
        "",
        reply,
        flags=re.IGNORECASE
    )

    reply = re.sub(
        r"\s+",
        " ",
        reply
    )

    return reply.strip()


# =========================================================
# GROQ REQUEST
# =========================================================

def call_groq(
    hindi_text,
    english_text
):

    if not AI_API_KEY:

        print("ERROR: AI_API_KEY is missing")

        return ""


    # -----------------------------------------------------
    # Memory
    # -----------------------------------------------------

    memory = get_memory()


    # -----------------------------------------------------
    # Current user
    # -----------------------------------------------------

    current_user = build_user_content(
        hindi_text,
        english_text
    )


    # -----------------------------------------------------
    # Messages
    # -----------------------------------------------------

    messages = [

        {
            "role": "system",
            "content": SYSTEM_PROMPT
        }

    ]


    # -----------------------------------------------------
    # Add memory
    # -----------------------------------------------------

    for item in memory:

        role = item.get("role")
        content = clean_text(
            item.get("content", "")
        )

        if (
            role in ("user", "assistant")
            and content
        ):

            messages.append({
                "role": role,
                "content": content
            })


    # -----------------------------------------------------
    # Current user message
    # -----------------------------------------------------

    messages.append({
        "role": "user",
        "content": current_user
    })


    # -----------------------------------------------------
    # Payload
    # -----------------------------------------------------

    payload = {

        "model": AI_MODEL,

        "messages": messages,

        "temperature": 0.2,

        "max_completion_tokens": 180,

        "stream": False
    }


    headers = {

        "Authorization":
            "Bearer " + AI_API_KEY,

        "Content-Type":
            "application/json",

        "User-Agent":
            "ESP32-Voice-Assistant/1.0"
    }


    # -----------------------------------------------------
    # Request
    # -----------------------------------------------------

    try:

        print()
        print("==============================")
        print("GROQ REQUEST")
        print("==============================")

        print("MODEL:", AI_MODEL)

        print("MEMORY MESSAGES:", len(memory))

        print("==============================")


        response = requests.post(

            AI_URL,

            headers=headers,

            json=payload,

            timeout=35
        )


        print()
        print("==============================")
        print("GROQ RESPONSE")
        print("==============================")

        print(
            "HTTP:",
            response.status_code
        )

        print("==============================")


        # -------------------------------------------------
        # API error
        # -------------------------------------------------

        if response.status_code != 200:

            print("GROQ ERROR:")
            print(response.text[:3000])

            return ""


        # -------------------------------------------------
        # JSON
        # -------------------------------------------------

        try:

            data = response.json()

        except Exception as e:

            print("JSON ERROR:", str(e))

            return ""


        # -------------------------------------------------
        # Choices
        # -------------------------------------------------

        choices = data.get(
            "choices",
            []
        )

        if not choices:

            print("NO CHOICES")

            print(data)

            return ""


        # -------------------------------------------------
        # Message
        # -------------------------------------------------

        message = choices[0].get(
            "message",
            {}
        )


        reply = message.get(
            "content",
            ""
        )


        reply = clean_ai_reply(
            reply
        )


        if not reply:

            print("EMPTY AI CONTENT")

            print(data)

            return ""


        print()
        print("==============================")
        print("AI REPLY")
        print("==============================")

        print(reply)

        print("==============================")


        return reply


    except requests.exceptions.Timeout:

        print("GROQ TIMEOUT")

        return ""


    except requests.exceptions.ConnectionError as e:

        print(
            "GROQ CONNECTION ERROR:",
            str(e)
        )

        return ""


    except Exception as e:

        print(
            "GROQ EXCEPTION:",
            type(e).__name__,
            str(e)
        )

        return ""


# =========================================================
# AI REPLY WITH RETRY
# =========================================================

def get_ai_reply(
    hindi_text,
    english_text
):

    # -----------------------------------------------------
    # Only one AI request at a time.
    # -----------------------------------------------------

    with ai_lock:

        # First attempt
        reply = call_groq(
            hindi_text,
            english_text
        )

        if reply:

            return reply


        # -------------------------------------------------
        # Retry with a smaller context.
        #
        # This helps if the first request had an issue.
        # -------------------------------------------------

        print()
        print("AI RETRY...")
        print()


        time.sleep(0.25)


        reply = call_groq(
            hindi_text,
            english_text
        )

        if reply:

            return reply


        return (
            "I couldn't get a response right now."
        )


# =========================================================
# SAVE SUCCESSFUL CONVERSATION
# =========================================================

def save_conversation(
    user_text,
    ai_reply
):

    user_text = clean_text(
        user_text
    )

    ai_reply = clean_text(
        ai_reply
    )

    if not user_text:
        return

    # Don't save server error messages.
    if ai_reply in (
        "I couldn't get a response right now.",
        "AI response nahi mil saka."
    ):
        return


    add_user_memory(
        user_text
    )

    add_ai_memory(
        ai_reply
    )


# =========================================================
# AUDIO ENDPOINT
# =========================================================

@app.route(
    "/uploadAudio",
    methods=["POST"]
)
def upload_audio():

    try:

        # -------------------------------------------------
        # AUDIO
        # -------------------------------------------------

        audio_data = request.get_data()


        if not audio_data:

            return jsonify({

                "status": "error",

                "message":
                    "No audio received",

                "ai_reply":
                    "Please ask your question again."

            }), 400


        print()
        print("==============================")
        print("AUDIO RECEIVED")
        print("==============================")

        print(
            "Audio bytes:",
            len(audio_data)
        )

        print("==============================")


        # -------------------------------------------------
        # Save WAV
        # -------------------------------------------------

        filename = "/tmp/esp32_audio.wav"


        with open(
            filename,
            "wb"
        ) as f:

            f.write(
                audio_data
            )


        # -------------------------------------------------
        # Speech recognizer
        # -------------------------------------------------

        recognizer = sr.Recognizer()


        # Better handling of ESP32 audio.
        recognizer.energy_threshold = 250
        recognizer.dynamic_energy_threshold = True
        recognizer.pause_threshold = 0.8
        recognizer.phrase_threshold = 0.2
        recognizer.non_speaking_duration = 0.4


        with sr.AudioFile(
            filename
        ) as source:

            audio = recognizer.record(
                source
            )


        hindi_text = ""
        english_text = ""


        # =================================================
        # HINDI
        # =================================================

        print()
        print("==============================")
        print("HINDI RECOGNITION")
        print("==============================")


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
                "Hindi: not understood"
            )

            hindi_text = ""


        except sr.RequestError as e:

            print(
                "Hindi Google error:",
                str(e)
            )

            hindi_text = ""


        # =================================================
        # ENGLISH
        # =================================================

        print()
        print("==============================")
        print("ENGLISH RECOGNITION")
        print("==============================")


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
                "English: not understood"
            )

            english_text = ""


        except sr.RequestError as e:

            print(
                "English Google error:",
                str(e)
            )

            english_text = ""


        # =================================================
        # VALIDATION
        # =================================================

        if (
            not is_valid_query(hindi_text)
            and
            not is_valid_query(english_text)
        ):

            print()
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

            }), 200


        # =================================================
        # TRANSCRIPTION
        # =================================================

        transcription = choose_transcription(

            hindi_text,

            english_text
        )


        # =================================================
        # AI
        # =================================================

        ai_reply = get_ai_reply(

            hindi_text,

            english_text
        )


        # =================================================
        # SAVE MEMORY
        # =================================================

        if ai_reply:

            save_conversation(

                transcription,

                ai_reply
            )


        # =================================================
        # FINAL
        # =================================================

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
        print("==============================")
        print("FINAL RESPONSE")
        print("==============================")

        print(
            "USER:",
            transcription
        )

        print(
            "AI:",
            ai_reply
        )

        print("==============================")


        return jsonify(
            response_data
        )


    # =====================================================
    # SERVER ERROR
    # =====================================================

    except Exception as e:

        print()
        print("==============================")
        print("SERVER ERROR")
        print("==============================")

        print(
            "TYPE:",
            type(e).__name__
        )

        print(
            "ERROR:",
            str(e)
        )

        print("==============================")


        return jsonify({

            "status":
                "error",

            "message":
                "Server error",

            "ai_reply":
                "I couldn't process that right now."

        }), 500


# =========================================================
# TEXT TEST ENDPOINT
#
# Isse ESP32 ke bina memory test kar sakte ho.
# =========================================================

@app.route(
    "/chat",
    methods=["POST"]
)
def chat():

    try:

        data = request.get_json(
            silent=True
        ) or {}


        text = clean_text(
            data.get("text", "")
        )


        if not text:

            return jsonify({

                "status":
                    "error",

                "message":
                    "Text is required"

            }), 400


        # Text ko English slot mein rakhte hain.
        # AI dono context samajh sakta hai.

        ai_reply = get_ai_reply(

            "",

            text
        )


        save_conversation(

            text,

            ai_reply
        )


        return jsonify({

            "status":
                "ok",

            "transcription":
                text,

            "ai_reply":
                ai_reply

        })


    except Exception as e:

        return jsonify({

            "status":
                "error",

            "message":
                str(e)

        }), 500


# =========================================================
# MEMORY VIEW
# =========================================================

@app.route(
    "/memory",
    methods=["GET"]
)
def memory_view():

    return jsonify({

        "status":
            "ok",

        "messages":
            get_memory()

    })


# =========================================================
# CLEAR MEMORY
# =========================================================

@app.route(
    "/memory/clear",
    methods=["POST", "GET"]
)
def memory_clear():

    clear_memory()

    return jsonify({

        "status":
            "ok",

        "message":
            "Memory cleared"

    })


# =========================================================
# TEST
# =========================================================

@app.route(
    "/test",
    methods=["POST"]
)
def test():

    data = request.get_json(
        silent=True
    )


    return jsonify({

        "status":
            "ok",

        "received":
            data

    })


# =========================================================
# START
# =========================================================

if __name__ == "__main__":

    port = int(

        os.environ.get(
            "PORT",
            "10000"
        )
    )


    print()
    print("==============================")
    print("ESP32 VOICE AI SERVER")
    print("==============================")

    print(
        "PORT:",
        port
    )

    print(
        "AI URL:",
        AI_URL
    )

    print(
        "AI MODEL:",
        AI_MODEL
    )

    print(
        "AI KEY:",
        "CONFIGURED"
        if AI_API_KEY
        else "MISSING"
    )

    print(
        "MEMORY:",
        "ENABLED"
    )

    print(
        "MEMORY TURNS:",
        MAX_MEMORY_TURNS
    )

    print("==============================")


    app.run(

        host="0.0.0.0",

        port=port,

        threaded=True
    )

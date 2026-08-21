from flask import Flask, request, jsonify
import os
import speech_recognition as sr
import requests
import re
import threading
import time

app = Flask(__name__)


# =====================================================
# CONFIGURATION
# =====================================================

AI_API_KEY = os.environ.get("AI_API_KEY")

AI_URL = os.environ.get(
    "AI_URL",
    "https://api.groq.com/openai/v1/chat/completions"
)

AI_MODEL = os.environ.get(
    "AI_MODEL",
    "llama-3.1-8b-instant"
)


# =====================================================
# MEMORY SETTINGS
# =====================================================

# Number of previous user/assistant messages to remember.
#
# Example:
#
# User 1
# AI 1
# User 2
# AI 2
# ...
#
# 20 messages = approximately 10 conversation turns.
#
MAX_MEMORY_MESSAGES = 20


# =====================================================
# CONVERSATION MEMORY
# =====================================================

conversation_history = []

memory_lock = threading.Lock()


# =====================================================
# MEMORY FUNCTIONS
# =====================================================

def add_to_memory(role, content):

    if not content:
        return

    content = str(content).strip()

    if not content:
        return

    with memory_lock:

        conversation_history.append({
            "role": role,
            "content": content
        })

        # Keep only latest messages
        if len(conversation_history) > MAX_MEMORY_MESSAGES:

            del conversation_history[
                0:
                len(conversation_history) - MAX_MEMORY_MESSAGES
            ]


def get_memory():

    with memory_lock:

        return list(conversation_history)


def clear_memory():

    with memory_lock:

        conversation_history.clear()


# =====================================================
# HOME
# =====================================================

@app.route("/", methods=["GET"])
def home():

    return "ESP32 Voice Server is ONLINE!"


# =====================================================
# HEALTH
# =====================================================

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

        "memory_messages":
            len(get_memory()),

        "memory_limit":
            MAX_MEMORY_MESSAGES
    })


# =====================================================
# MEMORY VIEW
#
# Browser:
#
# /memory
#
# =====================================================

@app.route("/memory", methods=["GET"])
def memory():

    return jsonify({

        "status": "ok",

        "messages":
            get_memory(),

        "count":
            len(get_memory())
    })


# =====================================================
# RESET MEMORY
#
# Browser:
#
# /reset
#
# =====================================================

@app.route("/reset", methods=["GET", "POST"])
def reset():

    clear_memory()

    print()
    print("==============================")
    print("MEMORY CLEARED")
    print("==============================")

    return jsonify({

        "status":
            "ok",

        "message":
            "Conversation memory cleared."
    })


# =====================================================
# WAKE ENDPOINT
# =====================================================

@app.route("/wake", methods=["POST", "GET"])
def wake():

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


# =====================================================
# TEST
# =====================================================

@app.route("/test", methods=["POST"])
def test():

    data = request.get_json(silent=True)

    if not data:

        return jsonify({

            "status":
                "error",

            "message":
                "No JSON received"

        }), 400

    print()
    print("==============================")
    print("TEST DATA")
    print("==============================")

    print(data)

    print("==============================")

    return jsonify({

        "status":
            "ok",

        "message":
            "Data received",

        "data":
            data
    })


# =====================================================
# CLEAN TEXT
# =====================================================

def clean_text(text):

    if not text:

        return ""

    text = str(text).strip()

    text = re.sub(
        r"\s+",
        " ",
        text
    )

    return text


# =====================================================
# VALID QUERY
# =====================================================

def is_valid_query(text):

    if not text:

        return False

    text = text.strip()

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


# =====================================================
# SYSTEM PROMPT
# =====================================================

SYSTEM_PROMPT = """
You are a professional bilingual voice assistant running on an ESP32.

You are having a continuous conversation with the user.

IMPORTANT:
You have access to previous conversation messages.

Use the previous conversation to understand short follow-up questions.

For example:

User:
How about the weather today?

Assistant:
Which city are you in?

User:
Noida City

The last user message "Noida City" is NOT a new unrelated question.

It is the answer to the previous question.

Therefore understand it as:

"Tell me about today's weather in Noida."

Use conversation context naturally.


==================================================
LANGUAGE
==================================================

If the user speaks English:

Answer in natural English.

If the user speaks Hindi:

Answer in Hindi using Devanagari.

If the user speaks Roman Hindi or Hinglish:

Answer in natural Hinglish.

If the user mixes Hindi and English:

Answer naturally in Hinglish.


==================================================
PHONETIC HINDI
==================================================

Hindi speech recognition may sometimes convert English speech into Hindi script.

Example:

Hindi:
हाउ आर यू

English:
How are you

The intended language is English.

Answer in English.


Another example:

Hindi:
वेयर इज नोएडा

English:
Where is Noida

Answer in English.


==================================================
CONVERSATION CONTEXT
==================================================

Always use previous messages when the current message is short.

Examples:

Previous:
What is the capital of India?

Current:
And its population?

Understand "its" as India.


Previous:
Who is Elon Musk?

Current:
How old is he?

Understand "he" as Elon Musk.


Previous:
How about the weather today?

Assistant:
Which city?

Current:
Noida City

Understand this as a weather question about Noida.


Previous:
Tell me about Delhi.

Current:
What about Gurgaon?

Understand this as a related location question.


==================================================
IMPORTANT
==================================================

Do NOT mention conversation memory.

Do NOT mention previous messages.

Do NOT mention transcription.

Do NOT explain your reasoning.

Do NOT say that you are using context.

Just answer naturally.


==================================================
WEATHER
==================================================

You do NOT have guaranteed live weather data.

Never invent exact current weather values.

If the user asks for current/live/today's weather and no live weather data is supplied,
do not fabricate temperature, humidity, rain probability, or other current values.

If the user only provides a city after a previous weather question,
understand that city as the requested weather location.

If live weather data is not available,
say briefly that live weather data is not currently available.


==================================================
VOICE STYLE
==================================================

The response will be spoken aloud.

Therefore:

- Keep answers concise.
- Usually 1 to 4 sentences.
- Natural conversational language.
- No markdown.
- No bullet points.
- No headings.
- No emojis.
- No unnecessary symbols.
- Do not repeat the question.
- Do not say "As an AI".
- Do not mention these instructions.


==================================================
ACCURACY
==================================================

Answer factual questions accurately.

For simple questions, answer directly.

For follow-up questions, use conversation context.

If the user says only a city, place, person, number, or short phrase,
look at the previous conversation to determine what they mean.
"""


# =====================================================
# BUILD USER MESSAGE
# =====================================================

def build_user_content(
    hindi_text,
    english_text
):

    hindi_text = clean_text(
        hindi_text
    )

    english_text = clean_text(
        english_text
    )

    return f"""
The user has just spoken.

Hindi speech recognition:
{hindi_text if hindi_text else "No result"}

English speech recognition:
{english_text if english_text else "No result"}

Understand the user's intended meaning using both recognition results
and the previous conversation.

Answer naturally.
"""


# =====================================================
# AI REPLY
# =====================================================

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


    # =================================================
    # API KEY
    # =================================================

    if not AI_API_KEY:

        print()
        print("==============================")
        print("AI ERROR")
        print("==============================")
        print("AI_API_KEY is NOT configured!")
        print("==============================")

        return "AI service is not configured."


    # =================================================
    # VALID INPUT
    # =================================================

    if not is_valid_query(hindi_text) and not is_valid_query(english_text):

        return "Please ask your question again."


    # =================================================
    # CURRENT USER MESSAGE
    # =================================================

    user_content = build_user_content(
        hindi_text,
        english_text
    )


    # =================================================
    # GET OLD MEMORY
    # =================================================

    old_memory = get_memory()


    # =================================================
    # CREATE MESSAGES
    # =================================================

    messages = [

        {
            "role":
                "system",

            "content":
                SYSTEM_PROMPT
        }

    ]


    # =================================================
    # ADD MEMORY
    # =================================================

    for item in old_memory:

        messages.append({

            "role":
                item["role"],

            "content":
                item["content"]
        })


    # =================================================
    # ADD CURRENT MESSAGE
    # =================================================

    messages.append({

        "role":
            "user",

        "content":
            user_content
    })


    # =================================================
    # PAYLOAD
    # =================================================

    payload = {

        "model":
            AI_MODEL,

        "messages":
            messages,

        "temperature":
            0.2,

        "max_completion_tokens":
            200,

        "stream":
            False
    }


    # =================================================
    # HEADERS
    # =================================================

    headers = {

        "Authorization":
            "Bearer " + AI_API_KEY,

        "Content-Type":
            "application/json"
    }


    # =================================================
    # DEBUG
    # =================================================

    print()
    print("==============================")
    print("AI REQUEST")
    print("==============================")

    print(
        "MODEL:",
        AI_MODEL
    )

    print(
        "MEMORY MESSAGES:",
        len(old_memory)
    )

    print()
    print("HINDI:")
    print(hindi_text)

    print()
    print("ENGLISH:")
    print(english_text)

    print()
    print("CONVERSATION MEMORY:")

    for item in old_memory:

        print(
            item["role"].upper() + ":",
            item["content"]
        )

    print("==============================")


    # =================================================
    # API REQUEST
    # =================================================

    try:

        response = requests.post(

            AI_URL,

            headers=headers,

            json=payload,

            timeout=35
        )


        # =================================================
        # RESPONSE STATUS
        # =================================================

        print()
        print("==============================")
        print("AI RESPONSE")
        print("==============================")

        print(
            "HTTP:",
            response.status_code
        )

        print("==============================")


        # =================================================
        # API ERROR
        # =================================================

        if response.status_code != 200:

            print()
            print("==============================")
            print("AI API ERROR")
            print("==============================")

            print(
                "STATUS:",
                response.status_code
            )

            print()
            print(
                "BODY:"
            )

            print(
                response.text[:3000]
            )

            print("==============================")


            return (
                "AI service error "
                + str(response.status_code)
            )


        # =================================================
        # JSON
        # =================================================

        try:

            data = response.json()

        except Exception as e:

            print()
            print(
                "JSON ERROR:",
                str(e)
            )

            return "AI returned an invalid response."


        # =================================================
        # CHOICES
        # =================================================

        choices = data.get(
            "choices"
        )


        if not choices:

            print()
            print("==============================")
            print("NO AI CHOICE")
            print("==============================")

            print(data)

            print("==============================")


            return "AI returned no answer."


        # =================================================
        # MESSAGE
        # =================================================

        message = choices[0].get(

            "message",

            {}
        )


        # =================================================
        # CONTENT
        # =================================================

        reply = message.get(

            "content",

            ""
        )


        if reply is None:

            reply = ""


        reply = str(
            reply
        ).strip()


        # =================================================
        # CLEAN
        # =================================================

        reply = reply.replace(
            "```",
            ""
        )

        reply = reply.strip()


        prefixes = [

            "AI:",

            "Answer:",

            "Response:"
        ]


        for prefix in prefixes:

            if reply.startswith(
                prefix
            ):

                reply = reply[
                    len(prefix):
                ].strip()


        # =================================================
        # EMPTY
        # =================================================

        if not reply:

            print()
            print("==============================")
            print("EMPTY AI RESPONSE")
            print("==============================")

            print(data)

            print("==============================")


            return "AI returned an empty answer."


        # =================================================
        # SAVE USER TO MEMORY
        # =================================================

        add_to_memory(

            "user",

            user_content
        )


        # =================================================
        # SAVE AI TO MEMORY
        # =================================================

        add_to_memory(

            "assistant",

            reply
        )


        # =================================================
        # SUCCESS
        # =================================================

        print()
        print("==============================")
        print("AI REPLY")
        print("==============================")

        print(reply)

        print("==============================")


        return reply


    # =================================================
    # TIMEOUT
    # =================================================

    except requests.exceptions.Timeout:

        print()
        print("==============================")
        print("AI TIMEOUT")
        print("==============================")

        return "AI service timed out."


    # =================================================
    # CONNECTION
    # =================================================

    except requests.exceptions.ConnectionError as e:

        print()
        print("==============================")
        print("AI CONNECTION ERROR")
        print("==============================")

        print(
            str(e)
        )

        print("==============================")


        return "AI service connection failed."


    # =================================================
    # GENERAL
    # =================================================

    except Exception as e:

        print()
        print("==============================")
        print("AI EXCEPTION")
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


        return "AI service error."


# =====================================================
# UPLOAD AUDIO
# =====================================================

@app.route(
    "/uploadAudio",
    methods=["POST"]
)
def upload_audio():

    try:

        # =================================================
        # RECEIVE AUDIO
        # =================================================

        audio_data = request.get_data()


        if not audio_data:

            print(
                "ERROR: No audio received"
            )

            return jsonify({

                "status":
                    "error",

                "message":
                    "No audio received",

                "ai_reply":
                    "No audio received."

            }), 400


        # =================================================
        # AUDIO INFO
        # =================================================

        print()
        print("==============================")
        print("AUDIO RECEIVED")
        print("==============================")

        print(
            "Audio bytes:",
            len(audio_data)
        )

        print("==============================")


        # =================================================
        # SAVE WAV
        # =================================================

        filename = "/tmp/audio.wav"


        with open(
            filename,
            "wb"
        ) as f:

            f.write(
                audio_data
            )


        # =================================================
        # SPEECH RECOGNIZER
        # =================================================

        recognizer = sr.Recognizer()


        with sr.AudioFile(
            filename
        ) as source:

            audio = recognizer.record(
                source
            )


        hindi_text = None

        english_text = None


        # =================================================
        # HINDI SPEECH
        # =================================================

        print()
        print("==============================")
        print("HINDI SPEECH")
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
                "Hindi not understood."
            )

            hindi_text = None


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

                "ai_reply":
                    "Speech service error."

            }), 500


        # =================================================
        # ENGLISH SPEECH
        # =================================================

        print()
        print("==============================")
        print("ENGLISH SPEECH")
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
                "English not understood."
            )

            english_text = None


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

                "ai_reply":
                    "Speech service error."

            }), 500


        # =================================================
        # VALIDATION
        # =================================================

        if not is_valid_query(
            hindi_text
        ) and not is_valid_query(
            english_text
        ):

            print()
            print("==============================")
            print("SPEECH NOT UNDERSTOOD")
            print("==============================")


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


        # =================================================
        # SHOW RESULTS
        # =================================================

        print()
        print("==============================")
        print("SPEECH RESULTS")
        print("==============================")

        print()
        print(
            "Hindi transcription:"
        )

        print(
            hindi_text
        )

        print()
        print(
            "English transcription:"
        )

        print(
            english_text
        )

        print("==============================")


        # =================================================
        # AI
        # =================================================

        ai_reply = get_ai_reply(

            hindi_text,

            english_text
        )


        # =================================================
        # BEST TRANSCRIPTION
        # =================================================

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


        # =================================================
        # FINAL RESPONSE
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
                ai_reply,

            "memory_messages":
                len(get_memory())
        }


        # =================================================
        # PRINT FINAL
        # =================================================

        print()
        print("==============================")
        print("FINAL RESPONSE")
        print("==============================")

        print(
            response_data
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
                str(e),

            "ai_reply":
                "Server error."

        }), 500


# =====================================================
# START SERVER
# =====================================================

if __name__ == "__main__":

    port = int(

        os.environ.get(
            "PORT",
            10000
        )
    )


    print()
    print("==============================")
    print("ESP32 VOICE SERVER")
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
        "MEMORY LIMIT:",
        MAX_MEMORY_MESSAGES
    )


    print("==============================")


    app.run(

        host="0.0.0.0",

        port=port
    )

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


# ============================================================
# MEMORY
# ============================================================

MAX_MEMORY_MESSAGES = 12

conversation_memory = []


def add_memory(role, content):

    global conversation_memory

    content = clean_text(content)

    if not content:
        return

    conversation_memory.append({
        "role": role,
        "content": content
    })

    if len(conversation_memory) > MAX_MEMORY_MESSAGES:
        conversation_memory = conversation_memory[
            -MAX_MEMORY_MESSAGES:
        ]


def clear_memory():

    global conversation_memory

    conversation_memory = []


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

        "ai_model": AI_MODEL,

        "tts_model": TTS_MODEL,

        "tts_voice": TTS_VOICE,

        "memory_messages":
            len(conversation_memory),

        "api_key":
            "configured"
            if AI_API_KEY
            else "missing"
    })


# ============================================================
# CLEAR MEMORY
# ============================================================

@app.route("/clear-memory", methods=["GET", "POST"])
def clear_memory_route():

    clear_memory()

    return jsonify({
        "status": "ok",
        "message": "Conversation memory cleared."
    })


# ============================================================
# CLEAN TEXT
# ============================================================

def clean_text(text):

    if text is None:
        return ""

    text = str(text)

    text = text.replace("```", "")

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
        "Assistant:"
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

    # Remove Devanagari for English Orpheus.
    # Roman Hindi remains untouched.
    text = re.sub(
        r"[\u0900-\u097F]+",
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
# AI SYSTEM PROMPT
# ============================================================

SYSTEM_PROMPT = """
You are Hannah, a friendly female voice assistant for
Avitron Aerospace Pvt. Ltd., Noida.

Your main knowledge and assistance area is:

STEM education
AI
Robotics
Electronics
Embedded systems
Arduino
ESP32
Sensors
Microcontrollers
Programming
Automation
Aerospace technology
Engineering education
Robotics projects
AI projects
Electronics projects

You can also answer simple normal conversation questions
such as:

Hello
Hi
How are you?
What is your name?
Who are you?
What can you do?
Good morning
Thank you
Goodbye

IMPORTANT TOPIC RULE:

If the user asks about something unrelated to:
AI, robotics, electronics, STEM education, embedded systems,
Arduino, ESP32, automation, aerospace, engineering education,
or basic conversation,

politely say that you mainly help with STEM education, AI,
robotics, electronics and aerospace-related topics, and ask
what assistance they need in those areas.

Do NOT provide long unrelated answers.

============================================================
LANGUAGE RULE
============================================================

VERY IMPORTANT.

Detect the language of the USER'S ACTUAL SPOKEN QUESTION.

If the user speaks English:
ANSWER ONLY IN NATURAL ENGLISH.

If the user speaks Hindi:
ANSWER IN NATURAL ROMAN HINDI.

Do NOT use Devanagari Hindi.

If the user speaks Hinglish:
ANSWER IN NATURAL HINGLISH.

If the user mixes Hindi and English:
you may naturally mix Hindi and English.

Examples:

User:
How are you?

Correct:
I am doing great. How can I help you?

Wrong:
Main theek hoon. Aap kaise hain?

User:
तुम कैसे हो?

Correct:
Main bilkul theek hoon. Aap kaise ho?

User:
Tum kaise ho Hannah?

Correct:
Main bilkul theek hoon. Aap kaise ho?

User:
What is AI?

Correct:
AI means Artificial Intelligence. It helps machines learn,
reason and perform tasks.

User:
AI kya hai?

Correct:
AI ka matlab Artificial Intelligence hai. Ye machines ko
learning aur intelligent tasks karne mein help karta hai.

User:
ESP32 kya hai?

Correct:
ESP32 ek powerful microcontroller hai jo Wi-Fi aur Bluetooth
ke saath IoT aur robotics projects mein kaam aata hai.

============================================================
CONVERSATION
============================================================

Use previous conversation context when useful.

If the user says:
"haan"
"yes"
"iske baare mein batao"
"aur batao"
"how?"
"why?"

understand it using the previous conversation.

Do not unnecessarily repeat previous answers.

============================================================
VOICE RULES
============================================================

Keep answers concise.

Usually 1 to 3 sentences.

Aim for about 200 characters or less when possible,
but do NOT cut an answer in the middle.

No markdown.

No bullet points.

No headings.

No emojis.

Do not repeat the question.

Do not say "As an AI".

Sound natural and conversational.

Return ONLY the answer.
"""


# ============================================================
# AI REPLY
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

    # --------------------------------------------------------
    # API KEY
    # --------------------------------------------------------

    if not AI_API_KEY:

        print("AI ERROR: AI_API_KEY missing")

        return "Please try again."


    # --------------------------------------------------------
    # QUERY VALIDATION
    # --------------------------------------------------------

    if (
        not is_valid_query(hindi_text)
        and
        not is_valid_query(english_text)
    ):

        return "Please ask your question again."


    # --------------------------------------------------------
    # CHOOSE BEST RECOGNITION
    # --------------------------------------------------------

    # Send both recognition results to AI.
    user_content = f"""
Current user speech:

Hindi recognition:
{hindi_text if hindi_text else "No result"}

English recognition:
{english_text if english_text else "No result"}

Use the recognition results to understand what the user
actually said.

IMPORTANT:
Determine the language of the user's actual question.
Do not choose the answer language merely because an English
recognition result exists.

Answer naturally.
"""


    # --------------------------------------------------------
    # BUILD MESSAGES
    # --------------------------------------------------------

    messages = [

        {
            "role": "system",
            "content": SYSTEM_PROMPT
        }
    ]


    # Add previous memory
    messages.extend(
        conversation_memory
    )


    # Current user message
    messages.append({

        "role": "user",

        "content": user_content
    })


    # --------------------------------------------------------
    # PAYLOAD
    # --------------------------------------------------------

    payload = {

        "model":
            AI_MODEL,

        "messages":
            messages,

        "temperature":
            0.2,

        "max_completion_tokens":
            250,

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


    # --------------------------------------------------------
    # REQUEST
    # --------------------------------------------------------

    try:

        print()
        print("========================================")
        print("AI REQUEST")
        print("========================================")

        response = requests.post(

            AI_URL,

            headers=headers,

            json=payload,

            timeout=45
        )


        print(
            "AI HTTP:",
            response.status_code
        )


        # ----------------------------------------------------
        # ERROR
        # ----------------------------------------------------

        if response.status_code != 200:

            print("AI SERVER ERROR")

            print(
                response.text[:10000]
            )

            return "Please try again."


        # ----------------------------------------------------
        # JSON
        # ----------------------------------------------------

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

            return "Please try again."


        # ----------------------------------------------------
        # CHOICES
        # ----------------------------------------------------

        choices = data.get(
            "choices"
        )

        if not choices:

            print(
                "AI ERROR: choices missing"
            )

            print(data)

            return "Please try again."


        # ----------------------------------------------------
        # MESSAGE
        # ----------------------------------------------------

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


        # ----------------------------------------------------
        # REMOVE PREFIX
        # ----------------------------------------------------

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


        # ----------------------------------------------------
        # EMPTY
        # ----------------------------------------------------

        if not reply:

            print(
                "AI ERROR: empty reply"
            )

            return "Please try again."


        # ----------------------------------------------------
        # MEMORY
        # ----------------------------------------------------

        # Save a clean user representation.
        if is_valid_query(english_text):

            user_memory_text = english_text

        else:

            user_memory_text = hindi_text


        add_memory(
            "user",
            user_memory_text
        )

        add_memory(
            "assistant",
            reply
        )


        print()
        print("AI REPLY:")
        print(reply)

        print(
            "MEMORY:",
            len(conversation_memory),
            "messages"
        )

        print("========================================")


        return reply


    # --------------------------------------------------------
    # TIMEOUT
    # --------------------------------------------------------

    except requests.exceptions.Timeout:

        print(
            "AI TIMEOUT"
        )

        return "Please try again."


    # --------------------------------------------------------
    # CONNECTION
    # --------------------------------------------------------

    except requests.exceptions.ConnectionError as e:

        print(
            "AI CONNECTION ERROR:",
            str(e)
        )

        return "Please try again."


    # --------------------------------------------------------
    # OTHER
    # --------------------------------------------------------

    except Exception as e:

        print(
            "AI EXCEPTION:",
            type(e).__name__,
            str(e)
        )

        traceback.print_exc()

        return "Please try again."


# ============================================================
# TTS GENERATION
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


    # --------------------------------------------------------
    # EMPTY
    # --------------------------------------------------------

    if not text:

        print(
            "TTS ERROR: empty text"
        )

        return None


    # --------------------------------------------------------
    # KEY
    # --------------------------------------------------------

    if not AI_API_KEY:

        print(
            "TTS ERROR: AI_API_KEY missing"
        )

        return None


    # --------------------------------------------------------
    # GROQ PAYLOAD
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
            "SENDING TTS REQUEST..."
        )


        response = requests.post(

            TTS_URL,

            headers=headers,

            json=payload,

            timeout=90
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
            "TTS TRANSFER ENCODING:",
            response.headers.get(
                "Transfer-Encoding",
                "none"
            )
        )

        print(
            "TTS RESPONSE BYTES:",
            len(response.content)
        )


        # ----------------------------------------------------
        # SUCCESS
        # ----------------------------------------------------

        if response.status_code == 200:

            audio_data = response.content


            if not audio_data:

                print(
                    "TTS ERROR: EMPTY AUDIO"
                )

                return None


            # Check WAV header
            if len(audio_data) >= 12:

                header = audio_data[:4]

                print(
                    "TTS HEADER:",
                    header
                )


            print(
                "TTS AUDIO BYTES:",
                len(audio_data)
            )

            print(
                "TTS SUCCESS"
            )

            print("========================================")


            return audio_data


        # ----------------------------------------------------
        # ERROR
        # ----------------------------------------------------

        print()
        print("========================================")
        print("TTS SERVER ERROR")
        print("========================================")

        print(
            "HTTP CODE:",
            response.status_code
        )

        print(
            "CONTENT TYPE:",
            response.headers.get(
                "Content-Type"
            )
        )

        print(
            "CONTENT LENGTH:",
            response.headers.get(
                "Content-Length",
                "-1"
            )
        )

        print(
            "TRANSFER ENCODING:",
            response.headers.get(
                "Transfer-Encoding",
                "none"
            )
        )


        try:

            error_body = response.text

            print(
                "ERROR BODY:"
            )

            print(
                error_body[:10000]
            )

        except Exception as e:

            print(
                "ERROR BODY READ FAILED:",
                str(e)
            )


        print("========================================")


        return None


    # --------------------------------------------------------
    # TIMEOUT
    # --------------------------------------------------------

    except requests.exceptions.Timeout:

        print(
            "TTS TIMEOUT"
        )

        return None


    # --------------------------------------------------------
    # CONNECTION
    # --------------------------------------------------------

    except requests.exceptions.ConnectionError as e:

        print(
            "TTS CONNECTION ERROR:",
            str(e)
        )

        return None


    # --------------------------------------------------------
    # OTHER
    # --------------------------------------------------------

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
            "TTS ENDPOINT ERROR:",
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
                "TTS test failed. Check Render logs."

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
# WAKE
# ============================================================

@app.route(
    "/wake",
    methods=["GET", "POST"]
)
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


# ============================================================
# AUDIO UPLOAD
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


        # ----------------------------------------------------
        # NO AUDIO
        # ----------------------------------------------------

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


        # ----------------------------------------------------
        # SAVE WAV
        # ----------------------------------------------------

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


        # ----------------------------------------------------
        # SPEECH RECOGNITION
        # ----------------------------------------------------

        recognizer = sr.Recognizer()


        with sr.AudioFile(
            filename
        ) as source:

            audio = recognizer.record(
                source
            )


        hindi_text = None
        english_text = None


        # ----------------------------------------------------
        # HINDI
        # ----------------------------------------------------

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


        # ----------------------------------------------------
        # ENGLISH
        # ----------------------------------------------------

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


        # ----------------------------------------------------
        # VALIDATION
        # ----------------------------------------------------

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


        # ----------------------------------------------------
        # AI
        # ----------------------------------------------------

        ai_reply = get_ai_reply(

            hindi_text,

            english_text
        )


        # ----------------------------------------------------
        # TRANSCRIPTION
        # ----------------------------------------------------

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


        # ----------------------------------------------------
        # RESPONSE
        # ----------------------------------------------------

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
                "Please try again."

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

    print(
        "MEMORY:",
        MAX_MEMORY_MESSAGES,
        "messages"
    )

    print("========================================")


    app.run(

        host="0.0.0.0",

        port=port,

        threaded=True
    )

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


# ============================================================
# HANNAH VOICE
# ============================================================

TTS_VOICE = os.environ.get(
    "TTS_VOICE",
    "hannah"
)


# ============================================================
# IMPORTANT
# ============================================================
# Earlier this was 200.
#
# Now increased so complete answers can be spoken.
#
# This is a SERVER-SIDE limit.
# Actual TTS model/API limits can still apply.
# ============================================================

TTS_MAX_CHARS = 1500


# ============================================================
# AI ERROR MESSAGE
# ============================================================

AI_ERROR_MESSAGE = (
    "No AI response. Try again."
)


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
    # IMPORTANT
    #
    # Orpheus English voice is being used.
    #
    # Remove Devanagari / unsupported Unicode.
    #
    # AI prompt already tells the model to use
    # Roman Hindi / Hinglish.
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
    #
    # DO NOT cut at 200 characters anymore.
    #
    # Maximum is now 1500.
    #
    # We do NOT cut at punctuation because that can still
    # remove the rest of a valid answer.
    # --------------------------------------------------------

    if len(text) > TTS_MAX_CHARS:

        print(
            "TTS TEXT TOO LONG:",
            len(text),
            "characters"
        )

        print(
            "TTS LIMIT:",
            TTS_MAX_CHARS
        )

        text = text[
            :TTS_MAX_CHARS
        ]

        # Try to avoid cutting in the middle
        # of a word.

        last_space = text.rfind(" ")

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

You are Diana, a friendly female voice assistant for
Avitron Aerospace Pvt. Ltd.

You are designed for voice interaction.

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

User:
Thank you.

Answer:
You're welcome!

User:
Goodbye.

Answer:
Goodbye! Have a great day.

============================================================
DOMAIN RULE
============================================================

If the question is related to:

STEM education,
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
or Avitron Aerospace Pvt. Ltd.

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
AVITRON AEROSPACE RULE
============================================================

If the user asks about Avitron Aerospace Pvt. Ltd.:

Only provide information that you actually know.

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

The user can speak:

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

User:
ESP32 kya hai?

Answer:
ESP32 ek powerful microcontroller hai jo robotics aur
IoT projects mein kaafi useful hai.

============================================================
VOICE ANSWER RULE
============================================================

You are speaking through a voice assistant.

Make answers natural and easy to speak.

Usually answer in one or two sentences.

For technical questions, use up to three short sentences
when necessary.

DO NOT unnecessarily shorten a useful answer.

DO NOT stop an answer in the middle of a sentence.

DO NOT cut important information just to make the answer
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
IMPORTANT TTS RULE
============================================================

The response will be spoken by an English voice.

Therefore:

Do not use Devanagari.

Use English or Roman Hindi.

Do not include unnecessary special characters.

============================================================

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


Understand the user's intended meaning.

Answer according to Diana's rules.

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

    # ========================================================
    # CLEAN TTS TEXT
    # ========================================================

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

    print(
        "TTS MAX CHARS:",
        TTS_MAX_CHARS
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

    # ========================================================
    # TTS REQUEST
    # ========================================================

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
        "I can help you with STEM education, "
        "artificial intelligence, robotics, "
        "electronics, embedded systems and aerospace technology."
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

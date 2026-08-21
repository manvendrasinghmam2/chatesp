from flask import Flask, request, jsonify
import os
import speech_recognition as sr
import requests
import re
import time
import threading

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
# LISTENING CONFIGURATION
# =====================================================

LISTEN_TIME = 120          # 2 minutes
WAKE_WORD = "hello"

# Assistant state
assistant_active = False
last_activity_time = 0

state_lock = threading.Lock()


# =====================================================
# STATE FUNCTIONS
# =====================================================

def activate_assistant():
    global assistant_active
    global last_activity_time

    with state_lock:
        assistant_active = True
        last_activity_time = time.time()

    print()
    print("==============================")
    print("ASSISTANT ACTIVE")
    print("Listening for 2 minutes")
    print("==============================")


def reset_timer():
    global last_activity_time

    with state_lock:
        last_activity_time = time.time()

    print("2-minute listening timer RESET")


def deactivate_assistant():
    global assistant_active

    with state_lock:
        assistant_active = False

    print()
    print("==============================")
    print("ASSISTANT SLEEP / IDLE")
    print("==============================")


def is_assistant_active():

    global assistant_active
    global last_activity_time

    with state_lock:

        if not assistant_active:
            return False

        elapsed = time.time() - last_activity_time

        if elapsed >= LISTEN_TIME:

            assistant_active = False

            print()
            print("==============================")
            print("2 MINUTES COMPLETED")
            print("ASSISTANT GOING TO SLEEP")
            print("==============================")

            return False

        return True


def get_remaining_time():

    with state_lock:

        if not assistant_active:
            return 0

        elapsed = time.time() - last_activity_time

        remaining = LISTEN_TIME - elapsed

        if remaining < 0:
            return 0

        return int(remaining)


# =====================================================
# BACKGROUND SLEEP MONITOR
# =====================================================

def sleep_monitor():

    while True:

        time.sleep(1)

        if is_assistant_active():

            remaining = get_remaining_time()

            if remaining % 10 == 0:

                print(
                    "Listening remaining:",
                    remaining,
                    "seconds"
                )


sleep_thread = threading.Thread(
    target=sleep_monitor,
    daemon=True
)

sleep_thread.start()


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

        "wake_word":
            WAKE_WORD,

        "wake_endpoint":
            "/wake",

        "audio_endpoint":
            "/uploadAudio",

        "status_endpoint":
            "/status",

        "listen_time_seconds":
            LISTEN_TIME
    })


# =====================================================
# STATUS
# =====================================================

@app.route("/status", methods=["GET"])
def status():

    active = is_assistant_active()

    remaining = get_remaining_time()

    return jsonify({

        "status": "ok",

        "assistant_active":
            active,

        "listening":
            active,

        "sleep":
            not active,

        "remaining_seconds":
            remaining,

        "wake_word":
            WAKE_WORD

    })


# =====================================================
# TEST
# =====================================================

@app.route("/test", methods=["POST"])
def test():

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
# HELLO / WAKE WORD CHECK
# =====================================================

def is_hello(text):

    if not text:
        return False

    text = str(
        text
    ).lower().strip()

    print(
        "Checking wake text:",
        text
    )

    # =================================================
    # ENGLISH
    # =================================================

    wake_words = [

        "hello",
        "helo",
        "hallo",
        "hellow",
        "hello hello",
        "hey hello",
        "hey",
        "helo hello"

    ]

    for word in wake_words:

        if word in text:
            return True

    # =================================================
    # HINDI
    # =================================================

    hindi_wake_words = [

        "हेलो",
        "हैलो",
        "हेल्लो",
        "हलो",
        "हेलो हेलो"

    ]

    for word in hindi_wake_words:

        if word in text:
            return True

    # =================================================
    # NORMALIZE
    # =================================================

    normalized = re.sub(
        r"[^a-zA-Z0-9\s]",
        "",
        text
    )

    normalized = normalized.strip()

    if normalized in [

        "hello",
        "helo",
        "hallo",
        "hellow"

    ]:

        return True

    return False


# =====================================================
# WAKE WORD ENDPOINT
# =====================================================

@app.route(
    "/wake",
    methods=["POST"]
)
def wake():

    try:

        print()
        print("==============================")
        print("WAKE REQUEST RECEIVED")
        print("==============================")

        # =================================================
        # RECEIVE AUDIO
        # =================================================

        audio_data = request.get_data()

        if not audio_data:

            print(
                "ERROR: No wake audio received"
            )

            return jsonify({

                "status":
                    "error",

                "wake":
                    False,

                "message":
                    "No audio received"

            }), 400

        print(
            "Wake audio bytes:",
            len(audio_data)
        )

        # =================================================
        # SAVE AUDIO
        # =================================================

        filename = "/tmp/wake.wav"

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

        english_text = None
        hindi_text = None

        # =================================================
        # ENGLISH
        # =================================================

        print(
            "Trying English wake recognition..."
        )

        try:

            english_text = recognizer.recognize_google(

                audio,

                language="en-IN"

            )

            print(
                "English:",
                english_text
            )

        except sr.UnknownValueError:

            english_text = None

        except sr.RequestError as e:

            print(
                "Google English API error:",
                str(e)
            )

        # =================================================
        # HINDI
        # =================================================

        print(
            "Trying Hindi wake recognition..."
        )

        try:

            hindi_text = recognizer.recognize_google(

                audio,

                language="hi-IN"

            )

            print(
                "Hindi:",
                hindi_text
            )

        except sr.UnknownValueError:

            hindi_text = None

        except sr.RequestError as e:

            print(
                "Google Hindi API error:",
                str(e)
            )

        # =================================================
        # CHECK HELLO
        # =================================================

        english_wake = is_hello(
            english_text
        )

        hindi_wake = is_hello(
            hindi_text
        )

        hello_detected = (

            english_wake
            or
            hindi_wake

        )

        # =================================================
        # HELLO DETECTED
        # =================================================

        if hello_detected:

            activate_assistant()

            return jsonify({

                "status":
                    "ok",

                "wake":
                    True,

                "word":
                    "hello",

                "message":
                    "Wake word detected",

                "listening":
                    True,

                "assistant_active":
                    True,

                "sleep":
                    False,

                "listen_time":
                    LISTEN_TIME,

                "remaining_seconds":
                    LISTEN_TIME,

                "english":
                    english_text,

                "hindi":
                    hindi_text

            })

        # =================================================
        # NO HELLO
        # =================================================

        return jsonify({

            "status":
                "ok",

            "wake":
                False,

            "listening":
                False,

            "assistant_active":
                False,

            "sleep":
                True,

            "english":
                english_text,

            "hindi":
                hindi_text

        })

    except Exception as e:

        print()
        print("==============================")
        print("WAKE SERVER ERROR")
        print("==============================")

        print(
            type(e).__name__,
            str(e)
        )

        print("==============================")

        return jsonify({

            "status":
                "error",

            "wake":
                False,

            "message":
                str(e)

        }), 500


# =====================================================
# AI REPLY
# =====================================================

def get_ai_reply(
    hindi_text,
    english_text
):

    if not AI_API_KEY:

        print(
            "AI_API_KEY is NOT configured!"
        )

        return "AI response nahi mil saka."

    # =================================================
    # SYSTEM PROMPT
    # =================================================

    system_prompt = """

You are a smart voice assistant running on an ESP32.

The user may speak English, Hindi, or Hinglish.

You will receive two speech recognition results.

Determine the language the user intended to speak.

If the user intended English, reply in English.

If the user intended Hindi, reply in Hindi using Devanagari.

If the user speaks Hinglish or Roman Hindi,
reply naturally in Hinglish.

Speech recognition may be inaccurate.

If Hindi recognition contains phonetic English
such as:

हाउ आर यू

while English recognition says:

How are you

then treat it as English.

Keep responses short because the response
will be spoken through an ESP32.

Do not use markdown.

Do not use emojis.

Do not use bullet points.

Do not explain language detection.

Answer naturally.

"""

    # =================================================
    # USER CONTENT
    # =================================================

    user_content = f"""

Hindi speech recognition result:

{hindi_text if hindi_text else "No Hindi result"}

English speech recognition result:

{english_text if english_text else "No English result"}

Determine what the user intended to say.

Then answer naturally.

"""

    # =================================================
    # PAYLOAD
    # =================================================

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
            150,

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
    # REQUEST
    # =================================================

    try:

        print()
        print("==============================")
        print("GROQ REQUEST")
        print("==============================")

        response = requests.post(

            AI_URL,

            headers=headers,

            json=payload,

            timeout=30

        )

        print(
            "HTTP STATUS:",
            response.status_code
        )

        print(
            "RAW RESPONSE:",
            response.text
        )

        # =================================================
        # ERROR
        # =================================================

        if response.status_code != 200:

            print(
                "GROQ ERROR:",
                response.text
            )

            return "AI response nahi mil saka."

        # =================================================
        # JSON
        # =================================================

        try:

            data = response.json()

        except Exception:

            return "AI response nahi mil saka."

        # =================================================
        # CHOICES
        # =================================================

        choices = data.get(
            "choices"
        )

        if not choices:

            return "AI response nahi mil saka."

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

        if not reply:

            return "AI response nahi mil saka."

        print()
        print("==============================")
        print("AI REPLY")
        print("==============================")

        print(reply)

        print("==============================")

        return reply

    except requests.exceptions.Timeout:

        print(
            "GROQ TIMEOUT"
        )

        return "AI response nahi mil saka."

    except requests.exceptions.ConnectionError:

        print(
            "GROQ CONNECTION ERROR"
        )

        return "AI response nahi mil saka."

    except Exception as e:

        print(
            "GROQ ERROR:",
            type(e).__name__,
            str(e)
        )

        return "AI response nahi mil saka."


# =====================================================
# UPLOAD AUDIO / COMMAND
# =====================================================

@app.route(
    "/uploadAudio",
    methods=["POST"]
)
def upload_audio():

    try:

        # =================================================
        # CHECK ACTIVE MODE
        # =================================================

        if not is_assistant_active():

            print()
            print("==============================")
            print("COMMAND REJECTED")
            print("ASSISTANT IS SLEEPING")
            print("==============================")

            return jsonify({

                "status":
                    "sleep",

                "message":
                    "Say hello first",

                "assistant_active":
                    False,

                "listening":
                    False,

                "sleep":
                    True,

                "wake_required":
                    True

            }), 403

        # =================================================
        # RECEIVE AUDIO
        # =================================================

        audio_data = request.get_data()

        if not audio_data:

            return jsonify({

                "status":
                    "error",

                "message":
                    "No audio received"

            }), 400

        print()
        print("==============================")
        print("COMMAND AUDIO RECEIVED")
        print("==============================")

        print(
            "Audio bytes:",
            len(audio_data)
        )

        # =================================================
        # RESET TIMER
        # =================================================

        reset_timer()

        # =================================================
        # SAVE AUDIO
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
        # RECOGNIZER
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
        # HINDI
        # =================================================

        print()
        print("TRYING HINDI RECOGNITION")

        try:

            hindi_text = recognizer.recognize_google(

                audio,

                language="hi-IN"

            )

            print(
                "Hindi:",
                hindi_text
            )

        except sr.UnknownValueError:

            hindi_text = None

        except sr.RequestError as e:

            print(
                "Hindi Speech API error:",
                str(e)
            )

        # =================================================
        # ENGLISH
        # =================================================

        print()
        print("TRYING ENGLISH RECOGNITION")

        try:

            english_text = recognizer.recognize_google(

                audio,

                language="en-IN"

            )

            print(
                "English:",
                english_text
            )

        except sr.UnknownValueError:

            english_text = None

        except sr.RequestError as e:

            print(
                "English Speech API error:",
                str(e)
            )

        # =================================================
        # CHECK SPEECH
        # =================================================

        if not hindi_text and not english_text:

            return jsonify({

                "status":
                    "error",

                "message":
                    "Speech not understood",

                "assistant_active":
                    is_assistant_active(),

                "remaining_seconds":
                    get_remaining_time()

            }), 400

        # =================================================
        # AI
        # =================================================

        ai_reply = get_ai_reply(

            hindi_text,

            english_text

        )

        # =================================================
        # TIMER RESET AFTER QUERY
        # =================================================

        reset_timer()

        # =================================================
        # FINAL RESPONSE
        # =================================================

        remaining = get_remaining_time()

        response_data = {

            "status":
                "ok",

            "transcription":
                english_text
                if english_text
                else hindi_text,

            "hindi_transcription":
                hindi_text,

            "english_transcription":
                english_text,

            "ai_reply":
                ai_reply,

            "assistant_active":
                True,

            "listening":
                True,

            "sleep":
                False,

            "remaining_seconds":
                remaining

        }

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

    except Exception as e:

        print()
        print("==============================")
        print("SERVER ERROR")
        print("==============================")

        print(
            type(e).__name__,
            str(e)
        )

        print("==============================")

        return jsonify({

            "status":
                "error",

            "message":
                str(e)

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
        "WAKE WORD:",
        WAKE_WORD
    )

    print(
        "LISTEN TIME:",
        LISTEN_TIME,
        "seconds"
    )

    print(
        "STATE:",
        "SLEEP / WAITING FOR HELLO"
    )

    print("==============================")

    app.run(

        host="0.0.0.0",

        port=port,

        threaded=True

    )

from flask import Flask, request, jsonify
import os
import speech_recognition as sr
import requests
import time
import re

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
# WAKE CONFIGURATION
# =====================================================

ACTIVE_TIME = 120

last_wake_time = 0


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

        "wake":
            "enabled",

        "active_time":
            ACTIVE_TIME
    })


# =====================================================
# WAKE WORD CHECK
# =====================================================

def check_wake_word(text):

    if not text:
        return False

    text = str(text).lower().strip()

    text = re.sub(
        r"[^a-zA-Z0-9\u0900-\u097F\s]",
        " ",
        text
    )

    text = " ".join(
        text.split()
    )

    wake_words = [

        "hello",
        "helo",
        "hellow",
        "halo",
        "हेलो",
        "हैलो",
        "हेल्लो"

    ]

    for word in wake_words:

        if word in text:
            return True

    return False


# =====================================================
# WAKE AUDIO
# =====================================================

def process_wake_audio(audio_data):

    global last_wake_time

    filename = "/tmp/wake.wav"

    try:

        with open(
            filename,
            "wb"
        ) as f:

            f.write(
                audio_data
            )


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

        try:

            english_text = recognizer.recognize_google(

                audio,

                language="en-IN"

            )

        except sr.UnknownValueError:

            english_text = None

        except sr.RequestError as e:

            print(
                "Wake English API error:",
                str(e)
            )


        # =================================================
        # HINDI
        # =================================================

        try:

            hindi_text = recognizer.recognize_google(

                audio,

                language="hi-IN"

            )

        except sr.UnknownValueError:

            hindi_text = None

        except sr.RequestError as e:

            print(
                "Wake Hindi API error:",
                str(e)
            )


        print()
        print("==============================")
        print("WAKE RECOGNITION")
        print("==============================")

        print(
            "English:",
            english_text
        )

        print(
            "Hindi:",
            hindi_text
        )

        print("==============================")


        detected = False


        if check_wake_word(
            english_text
        ):

            detected = True


        if check_wake_word(
            hindi_text
        ):

            detected = True


        if detected:

            last_wake_time = time.time()

            print()
            print("==============================")
            print("HELLO DETECTED!")
            print("==============================")


            return {

                "status":
                    "ok",

                "wake":
                    True,

                "english":
                    english_text,

                "hindi":
                    hindi_text
            }


        return {

            "status":
                "ok",

            "wake":
                False,

            "english":
                english_text,

            "hindi":
                hindi_text
        }


    except Exception as e:

        print()
        print("==============================")
        print("WAKE ERROR")
        print("==============================")

        print(
            type(e).__name__
        )

        print(
            str(e)
        )

        print("==============================")


        return {

            "status":
                "error",

            "wake":
                False,

            "message":
                str(e)
        }


# =====================================================
# WAKE
# =====================================================

@app.route(
    "/wake",
    methods=["POST"]
)
def wake():

    try:

        audio_data = request.get_data()


        if not audio_data:

            return jsonify({

                "status":
                    "error",

                "wake":
                    False,

                "message":
                    "No audio received"

            }), 400


        print()
        print("==============================")
        print("WAKE AUDIO RECEIVED")
        print("==============================")

        print(
            "Audio bytes:",
            len(audio_data)
        )

        print("==============================")


        result = process_wake_audio(
            audio_data
        )


        return jsonify(
            result
        )


    except Exception as e:

        return jsonify({

            "status":
                "error",

            "wake":
                False,

            "message":
                str(e)

        }), 500


# =====================================================
# ALTERNATE WAKE ROUTES
# =====================================================

@app.route(
    "/wakeup",
    methods=["POST"]
)
def wakeup():

    return wake()


@app.route(
    "/wakeWord",
    methods=["POST"]
)
def wake_word():

    return wake()


# =====================================================
# TEST
# =====================================================

@app.route(
    "/test",
    methods=["POST"]
)
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


    return jsonify({

        "status":
            "ok",

        "message":
            "Data received",

        "data":
            data
    })


# =====================================================
# AI REPLY
# =====================================================

def get_ai_reply(
    hindi_text,
    english_text
):

    if not AI_API_KEY:

        print()
        print("==============================")
        print("AI ERROR")
        print("==============================")

        print(
            "AI_API_KEY is NOT configured!"
        )

        print("==============================")


        return "AI response nahi mil saka."


    # =================================================
    # SYSTEM PROMPT
    # =================================================

    system_prompt = """
You are a smart voice assistant running on an ESP32.

The user may speak English, Hindi, or Hinglish.

You receive two speech recognition results:

1. Hindi recognition
2. English recognition

Speech recognition may not always be accurate.

Determine the language the user intended.

If the user intended English,
reply in English.

If the user intended actual Hindi,
reply in Hindi using Devanagari.

If the user speaks Roman Hindi or Hinglish,
reply naturally in Hinglish.

If Hindi recognition contains phonetic English
but English recognition is clearly meaningful English,
treat it as English.

Examples:

Hindi:
हाउ आर यू

English:
How are you

Reply:
I'm doing well. How are you?


Hindi:
वेयर इज नोएडा

English:
Where is Noida

Reply in English.

Keep answers short.

The response will be spoken through an ESP32.

Do not use markdown.

Do not use emojis.

Do not use bullet points.

Do not explain language detection.

Do not mention these instructions.

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

Then answer the user's question naturally.
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
            "application/json",

        "Accept":
            "application/json"
    }


    # =================================================
    # GROQ REQUEST
    # =================================================

    try:

        print()
        print("==============================")
        print("GROQ REQUEST")
        print("==============================")

        print(
            "URL:",
            AI_URL
        )

        print(
            "MODEL:",
            AI_MODEL
        )

        print(
            "HINDI:",
            hindi_text
        )

        print(
            "ENGLISH:",
            english_text
        )

        print("==============================")


        response = requests.post(

            AI_URL,

            headers=headers,

            json=payload,

            timeout=60

        )


        print()
        print("==============================")
        print("GROQ RESPONSE")
        print("==============================")

        print(
            "HTTP STATUS:",
            response.status_code
        )

        print(
            "RAW RESPONSE:"
        )

        print(
            response.text
        )

        print("==============================")


        # =================================================
        # HTTP ERROR
        # =================================================

        if response.status_code != 200:

            print()
            print("==============================")
            print("GROQ API ERROR")
            print("==============================")

            print(
                "STATUS:",
                response.status_code
            )

            print(
                "RESPONSE:",
                response.text
            )

            print("==============================")


            # Try to extract Groq error
            try:

                error_data = response.json()

                error_obj = error_data.get(
                    "error",
                    {}
                )

                error_message = error_obj.get(
                    "message",
                    ""
                )


                if error_message:

                    print(
                        "GROQ ERROR MESSAGE:",
                        error_message
                    )


            except Exception:

                pass


            return "AI response nahi mil saka."


        # =================================================
        # JSON
        # =================================================

        try:

            data = response.json()

        except Exception as e:

            print()
            print("==============================")
            print("GROQ JSON ERROR")
            print("==============================")

            print(
                str(e)
            )

            print(
                response.text
            )

            print("==============================")


            return "AI response nahi mil saka."


        # =================================================
        # CHOICES
        # =================================================

        choices = data.get(
            "choices"
        )


        if not choices:

            print()
            print("==============================")
            print("GROQ CHOICES MISSING")
            print("==============================")

            print(
                data
            )

            print("==============================")


            return "AI response nahi mil saka."


        # =================================================
        # MESSAGE
        # =================================================

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


        # =================================================
        # EMPTY
        # =================================================

        if not reply:

            print()
            print("==============================")
            print("EMPTY AI RESPONSE")
            print("==============================")

            print(
                data
            )

            print("==============================")


            return "AI response nahi mil saka."


        # =================================================
        # SUCCESS
        # =================================================

        print()
        print("==============================")
        print("AI REPLY")
        print("==============================")

        print(
            reply
        )

        print("==============================")


        return reply


    # =================================================
    # TIMEOUT
    # =================================================

    except requests.exceptions.Timeout as e:

        print()
        print("==============================")
        print("GROQ TIMEOUT")
        print("==============================")

        print(
            str(e)
        )

        print("==============================")


        return "AI response nahi mil saka."


    # =================================================
    # CONNECTION
    # =================================================

    except requests.exceptions.ConnectionError as e:

        print()
        print("==============================")
        print("GROQ CONNECTION ERROR")
        print("==============================")

        print(
            str(e)
        )

        print("==============================")


        return "AI response nahi mil saka."


    # =================================================
    # GENERAL
    # =================================================

    except Exception as e:

        print()
        print("==============================")
        print("GROQ EXCEPTION")
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


        return "AI response nahi mil saka."


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
                    "No audio received"

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


        print(
            "Audio saved:",
            filename
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
        # HINDI RECOGNITION
        # =================================================

        print()
        print("==============================")
        print("TRYING HINDI RECOGNITION")
        print("==============================")


        try:

            hindi_text = recognizer.recognize_google(

                audio,

                language="hi-IN"

            )


            print(
                "Hindi result:"
            )

            print(
                hindi_text
            )


        except sr.UnknownValueError:

            print(
                "Hindi speech not understood."
            )

            hindi_text = None


        except sr.RequestError as e:

            print(
                "Google Speech API error:"
            )

            print(
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


        # =================================================
        # ENGLISH RECOGNITION
        # =================================================

        print()
        print("==============================")
        print("TRYING ENGLISH RECOGNITION")
        print("==============================")


        try:

            english_text = recognizer.recognize_google(

                audio,

                language="en-IN"

            )


            print(
                "English result:"
            )

            print(
                english_text
            )


        except sr.UnknownValueError:

            print(
                "English speech not understood."
            )

            english_text = None


        except sr.RequestError as e:

            print(
                "Google Speech API error:"
            )

            print(
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


        # =================================================
        # NO SPEECH
        # =================================================

        if not hindi_text and not english_text:

            print()
            print("==============================")
            print("SPEECH NOT UNDERSTOOD")
            print("==============================")


            return jsonify({

                "status":
                    "error",

                "message":
                    "Speech not understood"

            }), 400


        # =================================================
        # SHOW RESULTS
        # =================================================

        print()
        print("==============================")
        print("SPEECH RESULTS")
        print("==============================")

        print(
            "Hindi transcription:",
            hindi_text
        )

        print(
            "English transcription:",
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
        # FINAL RESPONSE
        # =================================================

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
                ai_reply
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


    # =================================================
    # SERVER ERROR
    # =================================================

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
        "WAKE ENDPOINTS:"
    )

    print(
        "/wake"
    )

    print(
        "/wakeup"
    )

    print(
        "/wakeWord"
    )

    print(
        "ACTIVE TIME:",
        ACTIVE_TIME,
        "seconds"
    )

    print("==============================")


    app.run(

        host="0.0.0.0",

        port=port

    )

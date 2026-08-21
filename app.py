from flask import Flask, request, jsonify
import os
import speech_recognition as sr
import requests
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
            AI_MODEL
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

            "status": "error",

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

        "status": "ok",

        "message":
            "Data received",

        "data":
            data
    })


# =====================================================
# WAKE WORD DETECTION
# =====================================================

def is_hello(text):

    if not text:
        return False

    text = text.lower().strip()

    print(
        "Wake recognition:",
        text
    )

    # English
    english_words = [
        "hello",
        "helo",
        "hallo",
        "hellow",
        "hey hello",
        "hello hello"
    ]

    for word in english_words:

        if word in text:
            return True

    # Hindi / phonetic recognition
    hindi_words = [
        "हेलो",
        "हैलो",
        "हेल्लो",
        "हलो",
        "हेलो हेलो"
    ]

    for word in hindi_words:

        if word in text:
            return True

    # Roman Hindi / common ASR variations
    normalized = re.sub(
        r"[^a-zA-Z0-9\s]",
        "",
        text
    )

    normalized = normalized.lower()

    if normalized in [
        "hello",
        "helo",
        "hallo",
        "hellow"
    ]:

        return True

    return False


# =====================================================
# WAKE ENDPOINT
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


        filename = "/tmp/wake.wav"

        with open(
            filename,
            "wb"
        ) as f:

            f.write(audio_data)


        recognizer = sr.Recognizer()


        with sr.AudioFile(
            filename
        ) as source:

            audio = recognizer.record(
                source
            )


        # =================================================
        # TRY ENGLISH
        # =================================================

        english_text = None

        try:

            english_text = recognizer.recognize_google(

                audio,

                language="en-IN"
            )

        except sr.UnknownValueError:

            english_text = None

        except sr.RequestError as e:

            print(
                "Wake Google error:",
                str(e)
            )

            return jsonify({

                "status":
                    "error",

                "wake":
                    False,

                "message":
                    "Speech service error"

            }), 500


        # =================================================
        # TRY HINDI
        # =================================================

        hindi_text = None

        try:

            hindi_text = recognizer.recognize_google(

                audio,

                language="hi-IN"
            )

        except sr.UnknownValueError:

            hindi_text = None

        except sr.RequestError:

            hindi_text = None


        print()
        print("==============================")
        print("WAKE WORD CHECK")
        print("==============================")

        print(
            "English:",
            english_text
        )

        print(
            "Hindi:",
            hindi_text
        )


        # =================================================
        # CHECK HELLO
        # =================================================

        detected = (

            is_hello(
                english_text
            )

            or

            is_hello(
                hindi_text
            )
        )


        if detected:

            print(
                "WAKE WORD: HELLO DETECTED"
            )

            print("==============================")

            return jsonify({

                "status":
                    "ok",

                "wake":
                    True,

                "word":
                    "hello",

                "message":
                    "Wake word detected"

            })


        print(
            "WAKE WORD: NOT DETECTED"
        )

        print("==============================")


        return jsonify({

            "status":
                "ok",

            "wake":
                False
        })


    except Exception as e:

        print()
        print("==============================")
        print("WAKE SERVER ERROR")
        print("==============================")

        print(
            type(e).__name__
        )

        print(
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


    system_prompt = """
You are a smart voice assistant running on an ESP32.

The user may speak English, Hindi, or Hinglish.

You will receive two possible speech recognition results:

1. Hindi recognition result
2. English recognition result

Determine the language the user intended.

If English was intended, reply in English.

If actual Hindi was intended, reply in Hindi using Devanagari.

If Roman Hindi or Hinglish was intended, reply naturally in Hinglish.

Google Speech Recognition may convert English speech into Hindi
phonetic Devanagari.

For example:

Hindi recognition:
हाउ आर यू

English recognition:
How are you

The intended language is English.

Do not simply choose language based on script.

Keep responses short because the response will be spoken
through an ESP32 voice assistant.

Do not use markdown.

Do not use emojis.

Do not use bullet points.

Do not explain language detection.

Answer naturally.
"""


    user_content = f"""
Hindi speech recognition result:

{hindi_text if hindi_text else "No Hindi result"}


English speech recognition result:

{english_text if english_text else "No English result"}


Determine what the user intended to say.

Then answer naturally.
"""


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


    headers = {

        "Authorization":
            "Bearer " + AI_API_KEY,

        "Content-Type":
            "application/json"
    }


    try:

        response = requests.post(

            AI_URL,

            headers=headers,

            json=payload,

            timeout=30
        )


        print()
        print("==============================")
        print("GROQ RESPONSE")
        print("==============================")

        print(
            response.status_code
        )

        print(
            response.text
        )

        print("==============================")


        if response.status_code != 200:

            return "AI response nahi mil saka."


        try:

            data = response.json()

        except Exception:

            return "AI response nahi mil saka."


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


        print(
            "AI:",
            reply
        )


        return reply


    except requests.exceptions.Timeout:

        return "AI response nahi mil saka."


    except requests.exceptions.ConnectionError:

        return "AI response nahi mil saka."


    except Exception as e:

        print(
            "Groq error:",
            str(e)
        )

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


        filename = "/tmp/audio.wav"


        with open(
            filename,
            "wb"
        ) as f:

            f.write(audio_data)


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

        try:

            hindi_text = recognizer.recognize_google(

                audio,

                language="hi-IN"
            )

        except sr.UnknownValueError:

            hindi_text = None

        except sr.RequestError as e:

            print(
                "Google Speech error:",
                str(e)
            )


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
                "Google Speech error:",
                str(e)
            )


        print()
        print("==============================")
        print("SPEECH RESULTS")
        print("==============================")

        print(
            "Hindi:",
            hindi_text
        )

        print(
            "English:",
            english_text
        )

        print("==============================")


        if not hindi_text and not english_text:

            return jsonify({

                "status":
                    "error",

                "message":
                    "Speech not understood"

            }), 400


        # =================================================
        # AI
        # =================================================

        ai_reply = get_ai_reply(

            hindi_text,

            english_text

        )


        # =================================================
        # RESPONSE
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


    except Exception as e:

        print()
        print("==============================")
        print("SERVER ERROR")
        print("==============================")

        print(
            type(e).__name__
        )

        print(
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

    print("==============================")


    app.run(

        host="0.0.0.0",

        port=port
    )

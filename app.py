from flask import Flask, request, jsonify
import os
import speech_recognition as sr
import requests


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
    "openai/gpt-oss-20b"
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
# RECOGNIZE SPEECH
# =====================================================

def recognize_audio(audio):

    recognizer = sr.Recognizer()

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

        print(
            "Hindi result:",
            hindi_text
        )

    except sr.UnknownValueError:

        hindi_text = None

    except sr.RequestError as e:

        print(
            "Google Speech API error:",
            str(e)
        )

        raise e

    # =================================================
    # ENGLISH
    # =================================================

    try:

        english_text = recognizer.recognize_google(
            audio,
            language="en-IN"
        )

        print(
            "English result:",
            english_text
        )

    except sr.UnknownValueError:

        english_text = None

    except sr.RequestError as e:

        print(
            "Google Speech API error:",
            str(e)
        )

        raise e

    return hindi_text, english_text


# =====================================================
# HELLO DETECTION
# =====================================================

def detect_hello(hindi_text, english_text):

    texts = []

    if hindi_text:
        texts.append(hindi_text.lower().strip())

    if english_text:
        texts.append(english_text.lower().strip())

    for text in texts:

        # Normal English
        if "hello" in text:
            return True

        # Common recognition variations
        if text in [
            "helo",
            "hallo",
            "hellow",
            "hey hello",
            "hello ji",
            "hello g"
        ]:
            return True

        # Hindi phonetic recognition
        if any(word in text for word in [
            "हेलो",
            "हैलो",
            "हेल्लो",
            "हेलो जी",
            "हैलो जी"
        ]):
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

        print()
        print("==============================")
        print("WAKE AUDIO")
        print("==============================")

        print(
            "Audio bytes:",
            len(audio_data)
        )

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

        hindi_text, english_text = recognize_audio(
            audio
        )

        is_hello = detect_hello(
            hindi_text,
            english_text
        )

        print()
        print(
            "Wake Hindi:",
            hindi_text
        )

        print(
            "Wake English:",
            english_text
        )

        print(
            "HELLO:",
            is_hello
        )

        print("==============================")

        return jsonify({

            "status":
                "ok",

            "wake":
                is_hello,

            "english":
                english_text,

            "hindi":
                hindi_text
        })

    except Exception as e:

        print()
        print("==============================")
        print("WAKE ERROR")
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

You receive two possible speech recognition results:

1. Hindi recognition result
2. English recognition result

Speech recognition may be inaccurate.

Determine the language the user actually intended.

If the user intended English, reply in English.

If the user intended actual Hindi, reply in Hindi using Devanagari.

If the user speaks Roman Hindi or Hinglish, reply naturally in Hinglish.

Important:

Hindi recognition can sometimes convert English pronunciation
into Devanagari.

Example:

Hindi recognition:
हाउ आर यू

English recognition:
How are you

This is English.

Reply:
I'm doing well. How are you?

Do not treat every Devanagari result as Hindi.

Actual Hindi example:

आप कैसे हैं?

Reply:
मैं ठीक हूँ। धन्यवाद, आप कैसे हैं?

Roman Hindi example:

tum kaise ho

Reply:
Main bilkul theek hoon.

Keep answers short because the answer will be spoken
through an ESP32 voice assistant.

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

Then answer naturally in the intended language.
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
            False,

        "include_reasoning":
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
            "HTTP:",
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


        if not reply:

            return "AI response nahi mil saka."


        reply = str(
            reply
        ).strip()


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


    except requests.exceptions.ConnectionError as e:

        print(
            "GROQ CONNECTION ERROR:",
            str(e)
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
        print("AI AUDIO RECEIVED")
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


        # =================================================
        # SPEECH RECOGNITION
        # =================================================

        try:

            hindi_text, english_text = recognize_audio(
                audio
            )

        except sr.RequestError as e:

            return jsonify({

                "status":
                    "error",

                "message":
                    "Speech service error",

                "details":
                    str(e)

            }), 500


        # =================================================
        # NOTHING UNDERSTOOD
        # =================================================

        if not hindi_text and not english_text:

            print(
                "Speech not understood."
            )

            return jsonify({

                "status":
                    "error",

                "message":
                    "Speech not understood"

            }), 400


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


        # =================================================
        # AI
        # =================================================

        ai_reply = get_ai_reply(

            hindi_text,

            english_text
        )


        # =================================================
        # TRANSCRIPTION
        # =================================================

        transcription = (
            english_text
            if english_text
            else hindi_text
        )


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

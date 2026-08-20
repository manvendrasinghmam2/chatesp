from flask import Flask, request, jsonify
import os
import speech_recognition as sr
import requests

app = Flask(__name__)

# =====================================================
# AI CONFIG
# =====================================================

AI_API_KEY = os.environ.get("AI_API_KEY")

# Apne currently working AI endpoint/model ke according
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

@app.route("/")
def home():

    return "ESP32 Voice Server is ONLINE!"


# =====================================================
# HEALTH
# =====================================================

@app.route("/health")
def health():

    return jsonify({
        "status": "online",
        "speech_engine": "Google Speech Recognition",
        "ai_engine": "Hosted AI"
    })


# =====================================================
# TEST
# =====================================================

@app.route("/test", methods=["POST"])
def test():

    data = request.get_json(silent=True)

    if not data:

        return jsonify({
            "status": "error",
            "message": "No JSON received"
        }), 400

    print("ESP32 DATA:", data)

    return jsonify({
        "status": "ok",
        "message": "Data received"
    })


# =====================================================
# AI REPLY
# =====================================================

def get_ai_reply(text):

    if not AI_API_KEY:

        print("AI_API_KEY not configured")

        return "AI response nahi mil saka."


    # -------------------------------------------------
    # LANGUAGE PRESERVATION
    # -------------------------------------------------

    system_prompt = """
You are a helpful voice assistant.

IMPORTANT LANGUAGE RULES:

1. If the user speaks Hindi, reply in Hindi.
2. If the user speaks English, reply in English.
3. If the user speaks Hinglish, reply in Hinglish.
4. Do not unnecessarily translate the user's language.
5. Keep the response short and natural.
6. The response will be spoken aloud by a voice assistant.
7. Do not use markdown.
8. Do not use emojis unless necessary.
"""


    payload = {

        "model": AI_MODEL,

        "messages": [

            {
                "role": "system",
                "content": system_prompt
            },

            {
                "role": "user",
                "content": text
            }

        ],

        "temperature": 0.4,

        "max_tokens": 150
    }


    headers = {

        "Authorization":
            f"Bearer {AI_API_KEY}",

        "Content-Type":
            "application/json"
    }


    try:

        print()
        print("==============================")
        print("AI REQUEST")
        print("==============================")

        print("Input:", text)

        response = requests.post(

            AI_URL,

            headers=headers,

            json=payload,

            timeout=30
        )


        print("AI HTTP:", response.status_code)


        # -------------------------------------------------
        # ERROR
        # -------------------------------------------------

        if response.status_code != 200:

            print()
            print("==============================")
            print("AI ERROR")
            print("==============================")

            print(response.text)

            return "AI response nahi mil saka."


        # -------------------------------------------------
        # JSON
        # -------------------------------------------------

        data = response.json()


        # -------------------------------------------------
        # RESPONSE TEXT
        # -------------------------------------------------

        reply = (

            data
            .get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
        )


        reply = reply.strip()


        print()
        print("==============================")
        print("AI REPLY")
        print("==============================")

        print(reply)

        print("==============================")


        if not reply:

            return "AI response nahi mil saka."


        return reply


    except Exception as e:

        print()
        print("==============================")
        print("AI EXCEPTION")
        print("==============================")

        print(str(e))

        return "AI response nahi mil saka."


# =====================================================
# UPLOAD AUDIO
# =====================================================

@app.route("/uploadAudio", methods=["POST"])
def upload_audio():

    try:

        audio_data = request.get_data()


        # -------------------------------------------------
        # CHECK AUDIO
        # -------------------------------------------------

        if not audio_data:

            return jsonify({
                "status": "error",
                "message": "No audio received"
            }), 400


        print()
        print("==============================")
        print("AUDIO RECEIVED")
        print("==============================")

        print(
            "Bytes:",
            len(audio_data)
        )


        # -------------------------------------------------
        # SAVE WAV
        # -------------------------------------------------

        filename = "/tmp/audio.wav"


        with open(
            filename,
            "wb"
        ) as f:

            f.write(audio_data)


        # -------------------------------------------------
        # SPEECH RECOGNITION
        # -------------------------------------------------

        recognizer = sr.Recognizer()


        with sr.AudioFile(filename) as source:

            audio = recognizer.record(source)


        text = None


        # =================================================
        # FIRST TRY HINDI
        # =================================================

        try:

            text = recognizer.recognize_google(

                audio,

                language="hi-IN"
            )


            print()
            print("HINDI RESULT:")
            print(text)


        except sr.UnknownValueError:

            text = None


        except sr.RequestError as e:

            return jsonify({

                "status": "error",

                "message":
                    "Speech service error",

                "details":
                    str(e)

            }), 500


        # =================================================
        # ENGLISH
        # =================================================

        if not text:

            try:

                text = recognizer.recognize_google(

                    audio,

                    language="en-IN"
                )


                print()
                print("ENGLISH RESULT:")
                print(text)


            except sr.UnknownValueError:

                return jsonify({

                    "status": "error",

                    "message":
                        "Speech not understood"

                }), 400


            except sr.RequestError as e:

                return jsonify({

                    "status": "error",

                    "message":
                        "Speech service error",

                    "details":
                        str(e)

                }), 500


        # =================================================
        # TRANSCRIPTION
        # =================================================

        print()
        print("==============================")
        print("TRANSCRIPTION")
        print("==============================")

        print(text)

        print("==============================")


        # =================================================
        # AI
        # =================================================

        ai_reply = get_ai_reply(text)


        # =================================================
        # FINAL RESPONSE
        # =================================================

        response_data = {

            "status": "ok",

            "transcription": text,

            "ai_reply": ai_reply
        }


        return jsonify(
            response_data
        )


    # =====================================================
    # ERRORS
    # =====================================================

    except Exception as e:

        print()
        print("==============================")
        print("ERROR")
        print("==============================")

        print(str(e))

        print("==============================")


        return jsonify({

            "status": "error",

            "message":
                str(e)

        }), 500


# =====================================================
# START
# =====================================================

if __name__ == "__main__":

    port = int(

        os.environ.get(

            "PORT",

            10000
        )
    )


    app.run(

        host="0.0.0.0",

        port=port
    )

from flask import Flask, request, jsonify
import os
import speech_recognition as sr
import json
import urllib.request
import urllib.error

app = Flask(__name__)

# =====================================================
# AI CONFIG
# =====================================================

AI_API_KEY = os.environ.get("AI_API_KEY")

AI_URL = "https://api.groq.com/openai/v1/chat/completions"

# Current supported Groq model
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
        "ai_engine": "Groq Hosted AI"
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

        print("AI_API_KEY NOT CONFIGURED")

        return "AI response nahi mil saka."


    # -------------------------------------------------
    # LANGUAGE RULE
    # -------------------------------------------------

    system_prompt = """
You are a short and natural voice assistant.

IMPORTANT LANGUAGE RULES:

1. If the user's actual language is Hindi, reply in Hindi using Devanagari script.
2. If the user's actual language is English, reply in English.
3. If the user speaks Hinglish, reply in Hinglish.
4. If speech recognition writes English words using Hindi/Devanagari phonetic spelling,
   such as "हाउ आर यू", understand that it means English "How are you"
   and reply in English.
5. Do not unnecessarily translate the user's language.
6. Keep answers short because the answer will be spoken by an ESP32 voice assistant.
7. Do not use markdown.
8. Do not use emojis.
9. Answer the user's question directly.
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

        "temperature": 0.3,

        "max_tokens": 150
    }


    data = json.dumps(payload).encode("utf-8")


    headers = {

        "Authorization":
            "Bearer " + AI_API_KEY,

        "Content-Type":
            "application/json"
    }


    try:

        print()
        print("==============================")
        print("AI REQUEST")
        print("==============================")

        print("Input:", text)
        print("Model:", AI_MODEL)


        req = urllib.request.Request(
            AI_URL,
            data=data,
            headers=headers,
            method="POST"
        )


        with urllib.request.urlopen(
            req,
            timeout=30
        ) as response:

            response_data = response.read()

            status_code = response.status


        print("AI HTTP:", status_code)


        if status_code != 200:

            print("AI ERROR:")
            print(
                response_data.decode(
                    "utf-8",
                    errors="replace"
                )
            )

            return "AI response nahi mil saka."


        result = json.loads(
            response_data.decode(
                "utf-8"
            )
        )


        reply = (
            result
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


    except urllib.error.HTTPError as e:

        error_body = e.read().decode(
            "utf-8",
            errors="replace"
        )

        print()
        print("==============================")
        print("AI HTTP ERROR")
        print("==============================")

        print("Code:", e.code)
        print(error_body)

        return "AI response nahi mil saka."


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
        # AUDIO CHECK
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
        # FIRST TRY ENGLISH
        # =================================================

        try:

            text = recognizer.recognize_google(
                audio,
                language="en-IN"
            )

            print()
            print("ENGLISH RESULT:")
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
        # THEN TRY HINDI
        # =================================================

        if not text:

            try:

                text = recognizer.recognize_google(
                    audio,
                    language="hi-IN"
                )

                print()
                print("HINDI RESULT:")
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
        # FINAL JSON
        # =================================================

        return jsonify({

            "status": "ok",

            "transcription": text,

            "ai_reply": ai_reply

        })


    # =====================================================
    # ERROR
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

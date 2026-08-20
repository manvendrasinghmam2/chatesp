from flask import Flask, request, jsonify
import os
import speech_recognition as sr
from groq import Groq

app = Flask(__name__)


# =====================================================
# GROQ AI
# =====================================================

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

if GROQ_API_KEY:
    groq_client = Groq(
        api_key=GROQ_API_KEY
    )
    print("================================")
    print("GROQ AI: READY")
    print("================================")
else:
    groq_client = None

    print("================================")
    print("GROQ AI: API KEY NOT FOUND")
    print("================================")


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
        "ai_engine": "Groq"
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

    if not groq_client:

        print("GROQ_API_KEY NOT FOUND")

        return "AI key nahi mili."


    try:

        print()
        print("==============================")
        print("GROQ AI REQUEST")
        print("==============================")
        print("Question:", text)


        response = groq_client.chat.completions.create(

            # Current Groq model
            model="openai/gpt-oss-20b",

            messages=[

                {
                    "role": "system",
                    "content": (
                        "You are a helpful voice assistant for an ESP32. "

                        "The user may speak Hindi, English, "
                        "or Hinglish. "

                        "If the user speaks Hindi, reply in Hindi. "

                        "If the user speaks English, reply in English. "

                        "If the user speaks Hinglish, reply in Hinglish. "

                        "Keep replies short, natural and useful. "

                        "Do not give very long answers."
                    )
                },

                {
                    "role": "user",
                    "content": text
                }

            ],

            temperature=0.5,

            max_completion_tokens=150
        )


        reply = response.choices[0].message.content.strip()


        print()
        print("==============================")
        print("GROQ SUCCESS")
        print("==============================")
        print("AI REPLY:")
        print(reply)
        print("==============================")


        return reply


    except Exception as e:

        print()
        print("==============================")
        print("GROQ ERROR")
        print("==============================")
        print("ERROR TYPE:")
        print(type(e).__name__)
        print()
        print("ERROR:")
        print(str(e))
        print("==============================")


        return "AI response nahi mil saka."


# =====================================================
# UPLOAD AUDIO
# =====================================================

@app.route("/uploadAudio", methods=["POST"])
def upload_audio():

    try:

        # =================================================
        # RECEIVE AUDIO
        # =================================================

        audio_data = request.get_data()

        if not audio_data:

            return jsonify({
                "status": "error",
                "message": "No audio received"
            }), 400


        print()
        print("==============================")
        print("AUDIO RECEIVED")
        print("==============================")
        print("Bytes:", len(audio_data))


        # =================================================
        # SAVE WAV
        # =================================================

        filename = "/tmp/audio.wav"

        with open(filename, "wb") as f:

            f.write(audio_data)


        # =================================================
        # SPEECH RECOGNIZER
        # =================================================

        recognizer = sr.Recognizer()


        # =================================================
        # READ WAV
        # =================================================

        with sr.AudioFile(filename) as source:

            audio = recognizer.record(source)


        # =================================================
        # HINDI
        # =================================================

        hindi_text = None

        try:

            hindi_text = recognizer.recognize_google(
                audio,
                language="hi-IN"
            )

            print()
            print("HINDI RESULT:")
            print(hindi_text)

        except sr.UnknownValueError:

            print("Hindi speech not recognized.")

        except sr.RequestError as e:

            print("Google Speech Error:", str(e))

            return jsonify({
                "status": "error",
                "message": "Speech service error",
                "details": str(e)
            }), 500


        # =================================================
        # ENGLISH
        # =================================================

        english_text = None

        try:

            english_text = recognizer.recognize_google(
                audio,
                language="en-IN"
            )

            print()
            print("ENGLISH RESULT:")
            print(english_text)

        except sr.UnknownValueError:

            print("English speech not recognized.")

        except sr.RequestError as e:

            print("Google Speech Error:", str(e))

            return jsonify({
                "status": "error",
                "message": "Speech service error",
                "details": str(e)
            }), 500


        # =================================================
        # SELECT TRANSCRIPTION
        # =================================================

        if hindi_text:

            text = hindi_text

        elif english_text:

            text = english_text

        else:

            return jsonify({
                "status": "error",
                "message": "Speech not understood"
            }), 400


        # =================================================
        # TRANSCRIPTION RESULT
        # =================================================

        print()
        print("==============================")
        print("TRANSCRIPTION")
        print("==============================")
        print(text)
        print("==============================")


        # =================================================
        # SEND TO AI
        # =================================================

        ai_reply = get_ai_reply(text)


        # =================================================
        # FINAL RESPONSE
        # =================================================

        print()
        print("==============================")
        print("FINAL RESPONSE")
        print("==============================")
        print("Text:", text)
        print("AI:", ai_reply)
        print("==============================")


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
        print("SERVER ERROR")
        print("==============================")
        print(type(e).__name__)
        print(str(e))
        print("==============================")


        return jsonify({

            "status": "error",

            "message": str(e)

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

    app.run(
        host="0.0.0.0",
        port=port
    )

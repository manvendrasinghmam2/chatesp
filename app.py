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
    groq_client = Groq(api_key=GROQ_API_KEY)
    print("Groq AI: READY")
else:
    groq_client = None
    print("Groq AI: API KEY NOT FOUND")


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

        return "AI key is not configured on the server."


    try:

        print()
        print("==============================")
        print("ASKING AI")
        print("==============================")
        print(text)


        response = groq_client.chat.completions.create(

            model="llama-3.1-8b-instant",

            messages=[

                {
                    "role": "system",
                    "content": (
                        "You are a helpful voice assistant for an ESP32. "
                        "Reply naturally and briefly. "
                        "The user may speak Hindi, English, or Hinglish. "
                        "Reply in the same language/style as the user. "
                        "If the user speaks Hindi, answer in Hindi. "
                        "If the user speaks English, answer in English. "
                        "If the user uses Hinglish, answer in Hinglish. "
                        "Keep answers short because they will be shown "
                        "on a small voice device."
                    )
                },

                {
                    "role": "user",
                    "content": text
                }

            ],

            temperature=0.5,

            max_tokens=150
        )


        reply = response.choices[0].message.content.strip()


        print()
        print("==============================")
        print("AI REPLY")
        print("==============================")
        print(reply)
        print("==============================")


        return reply


    except Exception as e:

        print()
        print("==============================")
        print("AI ERROR")
        print("==============================")
        print(str(e))
        print("==============================")


        return "AI response nahi mil saka."


# =====================================================
# UPLOAD AUDIO
# =====================================================

@app.route("/uploadAudio", methods=["POST"])
def upload_audio():

    try:

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


        recognizer = sr.Recognizer()


        # =================================================
        # READ AUDIO
        # =================================================

        with sr.AudioFile(filename) as source:

            audio = recognizer.record(source)


        # =================================================
        # HINDI TRY
        # =================================================

        hindi_text = None

        try:

            hindi_text = recognizer.recognize_google(
                audio,
                language="hi-IN"
            )

            print("Hindi:", hindi_text)

        except sr.UnknownValueError:

            pass

        except sr.RequestError as e:

            return jsonify({
                "status": "error",
                "message": "Speech service error",
                "details": str(e)
            }), 500


        # =================================================
        # ENGLISH TRY
        # =================================================

        english_text = None

        try:

            english_text = recognizer.recognize_google(
                audio,
                language="en-IN"
            )

            print("English:", english_text)

        except sr.UnknownValueError:

            pass

        except sr.RequestError as e:

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

        return jsonify({

            "status": "ok",

            "transcription": text,

            "ai_reply": ai_reply

        })


    # =====================================================
    # ERRORS
    # =====================================================

    except Exception as e:

        print()
        print("==============================")
        print("SERVER ERROR")
        print("==============================")
        print(str(e))
        print("==============================")


        return jsonify({

            "status": "error",

            "message": str(e)

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

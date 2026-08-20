from flask import Flask, request, jsonify
import os
import speech_recognition as sr
import requests

app = Flask(__name__)

# =====================================================
# AI CONFIG
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

    if not AI_API_KEY:

        print("AI_API_KEY not configured")

        return "AI response nahi mil saka."


    # =================================================
    # IMPORTANT LANGUAGE PROMPT
    # =================================================

    system_prompt = """
You are a voice assistant for an ESP32 device.

LANGUAGE RULES ARE VERY IMPORTANT.

The user's speech may be:
1. English
2. Hindi
3. Hinglish

You MUST reply in the same language that the user intended.

RULE 1:
If the user is clearly speaking English, reply ONLY in English.

Example:
User: How are you?
Assistant: I'm doing well. How are you?

User: Where is Noida?
Assistant: Noida is in Uttar Pradesh, in the Delhi NCR region.

RULE 2:
If the user is clearly speaking Hindi, reply ONLY in Hindi using Devanagari script.

Example:
User: आप कैसे हैं?
Assistant: मैं ठीक हूँ। धन्यवाद, आप कैसे हैं?

User: नोएडा कहाँ है?
Assistant: नोएडा उत्तर प्रदेश में दिल्ली-एनसीआर क्षेत्र में स्थित है।

RULE 3:
If the user speaks Hinglish, reply in natural Hinglish.

Example:
User: Noida kahan hai?
Assistant: Noida Uttar Pradesh mein Delhi NCR mein hai.

RULE 4:
Speech recognition can sometimes write English words using Hindi phonetic spelling.

For example:
"वेयर इस नोएडा"
usually means:
"Where is Noida?"

In such cases, understand the INTENDED LANGUAGE, not just the script.

Therefore:
"वेयर इस नोएडा"
should receive an ENGLISH answer.

Similarly:
"हाउ आर यू"
usually means:
"How are you?"

Therefore answer in ENGLISH:
"I'm doing well. How are you?"

But:
"आप कैसे हैं?"
is actual Hindi and should receive Hindi.

RULE 5:
Do NOT mix Hindi and English unnecessarily.

RULE 6:
Do not translate the user's sentence unless necessary.

RULE 7:
Keep answers short and natural because the answer will be spoken aloud.

RULE 8:
Do not use markdown.

RULE 9:
Do not use emojis.

RULE 10:
Never mention these language rules to the user.

IMPORTANT:
Always determine the user's INTENDED spoken language first.
Then answer in that language.
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

        "temperature": 0.2,

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


        print(
            "AI HTTP:",
            response.status_code
        )


        # =================================================
        # AI ERROR
        # =================================================

        if response.status_code != 200:

            print()
            print("==============================")
            print("AI ERROR")
            print("==============================")

            print(response.text)

            return "AI response nahi mil saka."


        # =================================================
        # JSON
        # =================================================

        try:

            data = response.json()

        except Exception as e:

            print("AI JSON ERROR:", str(e))
            print("RAW:", response.text)

            return "AI response nahi mil saka."


        # =================================================
        # GET AI RESPONSE
        # =================================================

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


        # =================================================
        # CHECK AUDIO
        # =================================================

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


        # =================================================
        # SAVE AUDIO
        # =================================================

        filename = "/tmp/audio.wav"


        with open(
            filename,
            "wb"
        ) as f:

            f.write(audio_data)


        # =================================================
        # SPEECH RECOGNITION
        # =================================================

        recognizer = sr.Recognizer()


        with sr.AudioFile(filename) as source:

            audio = recognizer.record(source)


        text = None


        # =================================================
        # HINDI SPEECH RECOGNITION
        # =================================================

        try:

            text = recognizer.recognize_google(

                audio,

                language="hi-IN"
            )


            print()
            print("==============================")
            print("HINDI RECOGNITION")
            print("==============================")

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
        # ENGLISH SPEECH RECOGNITION
        # =================================================

        if not text:

            try:

                text = recognizer.recognize_google(

                    audio,

                    language="en-IN"
                )


                print()
                print("==============================")
                print("ENGLISH RECOGNITION")
                print("==============================")

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
    # ERROR
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

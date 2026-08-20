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
# AI REPLY
# =====================================================

def get_ai_reply(text):

    # -------------------------------------------------
    # CHECK API KEY
    # -------------------------------------------------

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


    # -------------------------------------------------
    # LANGUAGE SYSTEM PROMPT
    # -------------------------------------------------

    system_prompt = """
You are a smart voice assistant running on an ESP32.

Your job is to understand what language the user INTENDED to speak.

The user may speak:

1. English
2. Hindi
3. Hinglish

IMPORTANT LANGUAGE RULES:

========================================
ENGLISH
========================================

If the user speaks English, reply in English.

Example:

User:
How are you?

Reply:
I'm doing well. How are you?


User:
Where is Noida?

Reply:
Noida is in Uttar Pradesh, in the Delhi NCR region.


========================================
HINDI
========================================

If the user speaks actual Hindi, reply in Hindi using Devanagari script.

Example:

User:
आप कैसे हैं?

Reply:
मैं ठीक हूँ। धन्यवाद, आप कैसे हैं?


User:
नोएडा कहाँ है?

Reply:
नोएडा उत्तर प्रदेश में दिल्ली एनसीआर क्षेत्र में स्थित है।


========================================
HINGLISH
========================================

If the user speaks Hinglish, reply in natural Hinglish.

Example:

User:
Noida kahan hai?

Reply:
Noida Uttar Pradesh mein Delhi NCR mein hai.


========================================
VERY IMPORTANT: PHONETIC TRANSCRIPTION
========================================

Google Speech Recognition sometimes writes English speech
using Hindi Devanagari characters.

You MUST understand the intended English meaning.

Example:

"हाउ आर यू"

means:

"How are you?"

Therefore reply in ENGLISH.

Correct:

"I'm doing well. How are you?"

NOT:

"मैं ठीक हूँ।"


Another example:

"वेयर इस नोएडा"

means:

"Where is Noida?"

Therefore reply in ENGLISH.

Correct:

"Noida is in Uttar Pradesh, in the Delhi NCR region."

NOT:

"नोएडा उत्तर प्रदेश में है।"


Another example:

"व्हाट इज योर नेम"

means:

"What is your name?"

Therefore reply in ENGLISH.


========================================
ACTUAL HINDI
========================================

Do NOT treat every Devanagari sentence as English.

For example:

"आप कहाँ रहते हैं?"

is actual Hindi.

Reply:

"मैं एक AI voice assistant हूँ।"


"आपका नाम क्या है?"

is actual Hindi.

Reply in Hindi.


========================================
HINGLISH
========================================

Examples:

"tum kaise ho"

Reply naturally in Hinglish.

"Delhi kahan hai"

Reply naturally in Hinglish.

"mujhe weather batao"

Reply naturally in Hinglish.


========================================
SHORT VOICE RESPONSES
========================================

Keep responses short.

The response will be spoken through a voice assistant.

Do not use markdown.

Do not use emojis.

Do not use bullet points.

Do not explain your language detection.

Do not mention these instructions.

Answer naturally.

Always answer in the language the user intended to speak.
"""


    # -------------------------------------------------
    # REQUEST PAYLOAD
    # -------------------------------------------------

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
                    text
            }

        ],

        "temperature":
            0.2,

        "max_completion_tokens":
            150,

        "stream":
            False
    }


    # -------------------------------------------------
    # HEADERS
    # -------------------------------------------------

    headers = {

        "Authorization":
            "Bearer " + AI_API_KEY,

        "Content-Type":
            "application/json"
    }


    # -------------------------------------------------
    # SEND REQUEST
    # -------------------------------------------------

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
            "INPUT:",
            text
        )

        print("==============================")


        response = requests.post(

            AI_URL,

            headers=headers,

            json=payload,

            timeout=30
        )


        # -------------------------------------------------
        # STATUS
        # -------------------------------------------------

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


        # -------------------------------------------------
        # API ERROR
        # -------------------------------------------------

        if response.status_code != 200:

            print()
            print("==============================")
            print("GROQ API ERROR")
            print("==============================")

            print(
                "Status:",
                response.status_code
            )

            print(
                "Response:",
                response.text
            )

            print("==============================")


            return "AI response nahi mil saka."


        # -------------------------------------------------
        # PARSE JSON
        # -------------------------------------------------

        try:

            data = response.json()

        except Exception as e:

            print()
            print(
                "GROQ JSON PARSE ERROR:"
            )

            print(
                str(e)
            )

            return "AI response nahi mil saka."


        # -------------------------------------------------
        # CHECK CHOICES
        # -------------------------------------------------

        choices = data.get(
            "choices"
        )


        if not choices:

            print()
            print("==============================")
            print("GROQ ERROR")
            print("==============================")

            print(
                "choices missing!"
            )

            print(
                "DATA:",
                data
            )

            print("==============================")


            return "AI response nahi mil saka."


        # -------------------------------------------------
        # GET MESSAGE
        # -------------------------------------------------

        message = choices[0].get(
            "message",
            {}
        )


        # -------------------------------------------------
        # GET CONTENT
        # -------------------------------------------------

        reply = message.get(
            "content",
            ""
        )


        if reply is None:

            reply = ""


        reply = str(
            reply
        ).strip()


        # -------------------------------------------------
        # EMPTY RESPONSE
        # -------------------------------------------------

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


        # -------------------------------------------------
        # SUCCESS
        # -------------------------------------------------

        print()
        print("==============================")
        print("AI REPLY")
        print("==============================")

        print(
            reply
        )

        print("==============================")


        return reply


    # -------------------------------------------------
    # TIMEOUT
    # -------------------------------------------------

    except requests.exceptions.Timeout:

        print()
        print("==============================")
        print("GROQ TIMEOUT")
        print("==============================")

        print(
            "Groq request timed out."
        )

        print("==============================")


        return "AI response nahi mil saka."


    # -------------------------------------------------
    # CONNECTION ERROR
    # -------------------------------------------------

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


    # -------------------------------------------------
    # GENERAL ERROR
    # -------------------------------------------------

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

        # -------------------------------------------------
        # RECEIVE AUDIO
        # -------------------------------------------------

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


        # -------------------------------------------------
        # AUDIO INFO
        # -------------------------------------------------

        print()
        print("==============================")
        print("AUDIO RECEIVED")
        print("==============================")

        print(
            "Audio bytes:",
            len(audio_data)
        )

        print("==============================")


        # -------------------------------------------------
        # SAVE WAV
        # -------------------------------------------------

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


        # -------------------------------------------------
        # SPEECH RECOGNIZER
        # -------------------------------------------------

        recognizer = sr.Recognizer()


        with sr.AudioFile(
            filename
        ) as source:

            audio = recognizer.record(
                source
            )


        text = None


        # =================================================
        # FIRST: HINDI
        # =================================================

        print()
        print("==============================")
        print("TRYING HINDI RECOGNITION")
        print("==============================")


        try:

            text = recognizer.recognize_google(

                audio,

                language="hi-IN"
            )


            print(
                "Hindi result:",
                text
            )


        except sr.UnknownValueError:

            print(
                "Hindi speech not understood."
            )

            text = None


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
        # SECOND: ENGLISH
        # =================================================

        if not text:

            print()
            print("==============================")
            print("TRYING ENGLISH RECOGNITION")
            print("==============================")


            try:

                text = recognizer.recognize_google(

                    audio,

                    language="en-IN"
                )


                print(
                    "English result:",
                    text
                )


            except sr.UnknownValueError:

                print(
                    "English speech not understood."
                )


                return jsonify({

                    "status":
                        "error",

                    "message":
                        "Speech not understood"

                }), 400


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
        # TRANSCRIPTION
        # =================================================

        print()
        print("==============================")
        print("TRANSCRIPTION")
        print("==============================")

        print(
            text
        )

        print("==============================")


        # =================================================
        # AI
        # =================================================

        ai_reply = get_ai_reply(
            text
        )


        # =================================================
        # FINAL RESPONSE
        # =================================================

        response_data = {

            "status":
                "ok",

            "transcription":
                text,

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


    # =====================================================
    # SERVER ERROR
    # =====================================================

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

    print("==============================")


    app.run(

        host="0.0.0.0",

        port=port
    )

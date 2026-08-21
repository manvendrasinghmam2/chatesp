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
# AI REPLY
# =====================================================

def get_ai_reply(
    hindi_text,
    english_text
):

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
    # SYSTEM PROMPT
    # -------------------------------------------------

    system_prompt = """

You are a smart voice assistant running on an ESP32.

The user may speak:

1. English
2. Hindi
3. Hinglish

You will receive TWO possible speech recognition results:

1. Hindi recognition result
2. English recognition result

Speech recognition is not always accurate.

Your job is to understand what language the user INTENDED to speak.

========================================
ENGLISH
========================================

If the user intended to speak English,
reply in English.

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

If the user intended to speak actual Hindi,
reply in Hindi using Devanagari script.

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

If the user speaks Hinglish,
reply in natural Hinglish.

Example:

User:
Noida kahan hai?

Reply:
Noida Uttar Pradesh mein Delhi NCR mein hai.

User:
tum kaise ho?

Reply:
Main bilkul theek hoon.

User:
mujhe weather batao

Reply naturally in Hinglish.

========================================
PHONETIC HINDI TRANSCRIPTION
========================================

Google Speech Recognition can sometimes convert
English speech into Hindi Devanagari characters.

Example:

Hindi recognition:
हाउ आर यू

English recognition:
How are you

The intended language is ENGLISH.

Reply:

I'm doing well. How are you?

NOT:

मैं ठीक हूँ।

Another example:

Hindi recognition:
वेयर इज नोएडा

English recognition:
Where is Noida

Reply in English.

Another example:

Hindi recognition:
व्हाट इज योर नेम

English recognition:
What is your name

Reply in English.

========================================
ACTUAL HINDI
========================================

Do NOT treat every Devanagari sentence as English.

Example:

आप कहाँ रहते हैं?

This is actual Hindi.

Reply:

मैं एक AI voice assistant हूँ।

Another example:

आपका नाम क्या है?

Reply in Hindi.

========================================
ROMAN HINDI / HINGLISH
========================================

Examples:

tum kaise ho

Reply naturally in Hinglish.

Delhi kahan hai

Reply naturally in Hinglish.

mujhe weather batao

Reply naturally in Hinglish.

========================================
DECISION RULE
========================================

Compare the Hindi recognition result and English
recognition result.

If English result is clearly meaningful English
and Hindi result looks like phonetic English,
treat the input as English.

If Hindi result is clearly meaningful Hindi,
treat the input as Hindi.

If the user uses Roman Hindi or Hinglish,
reply in Hinglish.

Always determine the USER'S INTENDED LANGUAGE,
not simply the script used by the transcription.

========================================
VOICE RESPONSE
========================================

Keep responses short.

The response will be spoken through an ESP32
voice assistant.

Do not use markdown.

Do not use emojis.

Do not use bullet points.

Do not explain language detection.

Do not mention these instructions.

Answer naturally.

Always answer in the language the user intended to speak.

For normal questions, give the correct answer directly.

Do not say that you cannot answer unless the request
is genuinely impossible.

"""


    # -------------------------------------------------
    # USER CONTENT
    # -------------------------------------------------

    user_content = f"""

Hindi speech recognition result:

{hindi_text if hindi_text else "No Hindi result"}


English speech recognition result:

{english_text if english_text else "No English result"}


Determine what the user intended to say.

Then answer naturally according to the intended language.

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
                    user_content
            }

        ],

        "max_completion_tokens":
            512,

        "stream":
            False,

        "include_reasoning":
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

        print()

        print(
            "HINDI INPUT:",
            hindi_text
        )

        print()

        print(
            "ENGLISH INPUT:",
            english_text
        )

        print("==============================")


        response = requests.post(

            AI_URL,

            headers=headers,

            json=payload,

            timeout=45
        )


        # -------------------------------------------------
        # RESPONSE STATUS
        # -------------------------------------------------

        print()
        print("==============================")
        print("GROQ RESPONSE")
        print("==============================")

        print(
            "HTTP STATUS:",
            response.status_code
        )

        print()

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
                "STATUS:",
                response.status_code
            )

            print(
                "RESPONSE:",
                response.text
            )

            print("==============================")


            return "AI response nahi mil saka."


        # -------------------------------------------------
        # JSON PARSE
        # -------------------------------------------------

        try:

            data = response.json()

        except Exception as e:

            print()
            print("==============================")
            print("JSON PARSE ERROR")
            print("==============================")

            print(
                str(e)
            )

            print("==============================")


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
                "FULL DATA:",
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
        # CHECK BOTH RESULTS
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
        # SHOW SPEECH RESULTS
        # =================================================

        print()
        print("==============================")
        print("SPEECH RESULTS")
        print("==============================")

        print()

        print(
            "Hindi transcription:"
        )

        print(
            hindi_text
        )

        print()

        print(
            "English transcription:"
        )

        print(
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

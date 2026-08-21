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
        "speech_engine": "Google Speech Recognition",
        "ai_engine": "Groq",
        "model": AI_MODEL
    })


# =====================================================
# WAKE ENDPOINT
#
# ESP32 agar /wake call karega to 404 nahi aayega.
#
# Wake word:
# HELLO
# =====================================================

@app.route("/wake", methods=["POST", "GET"])
def wake():

    return jsonify({
        "status": "ok",
        "wake": True,
        "english": "Hello",
        "hindi": None
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

    print()
    print("==============================")
    print("TEST DATA")
    print("==============================")
    print(data)
    print("==============================")

    return jsonify({
        "status": "ok",
        "message": "Data received",
        "data": data
    })


# =====================================================
# CLEAN TEXT
# =====================================================

def clean_text(text):

    if not text:
        return ""

    text = str(text).strip()

    # Remove excessive spaces
    text = re.sub(r"\s+", " ", text)

    return text


# =====================================================
# CHECK VALID QUERY
# =====================================================

def is_valid_query(text):

    if not text:
        return False

    text = text.strip()

    if len(text) < 2:
        return False

    # Common recognition failures
    bad_values = [
        "unknown",
        "none",
        "null",
        "no response",
        "no valid query",
        "speech not understood"
    ]

    if text.lower() in bad_values:
        return False

    return True


# =====================================================
# AI REPLY
# =====================================================

def get_ai_reply(hindi_text, english_text):

    hindi_text = clean_text(hindi_text)
    english_text = clean_text(english_text)

    # -------------------------------------------------
    # CHECK API KEY
    # -------------------------------------------------

    if not AI_API_KEY:

        print()
        print("==============================")
        print("AI ERROR")
        print("==============================")
        print("AI_API_KEY is NOT configured!")
        print("==============================")

        return "AI response nahi mil saka."


    # -------------------------------------------------
    # CHECK INPUT
    # -------------------------------------------------

    if not is_valid_query(hindi_text) and not is_valid_query(english_text):

        print()
        print("==============================")
        print("NO VALID QUERY")
        print("==============================")
        print("==============================")

        return "Please ask your question again."


    # -------------------------------------------------
    # SYSTEM PROMPT
    # -------------------------------------------------

    system_prompt = """
You are a professional bilingual voice assistant running on an ESP32.

Your job is to understand the user's actual spoken language and answer naturally.

The speech recognition system provides two possible results:

1. Hindi recognition
2. English recognition

The recognition can sometimes be inaccurate.

You must understand the intended meaning, not blindly trust one transcription.


==================================================
LANGUAGE RULES
==================================================

RULE 1 — ENGLISH

If the user is clearly speaking English,
answer completely in natural English.

Example:

User:
How are you?

Answer:
I'm doing well. How are you?

User:
Where is Noida?

Answer:
Noida is in Uttar Pradesh, in the National Capital Region of India.


==================================================
RULE 2 — HINDI

If the user is clearly speaking Hindi,
answer completely in Hindi using Devanagari script.

Example:

User:
आप कैसे हैं?

Answer:
मैं बिल्कुल ठीक हूँ। धन्यवाद।


User:
नोएडा कहाँ है?

Answer:
नोएडा उत्तर प्रदेश में स्थित है और यह दिल्ली एनसीआर का हिस्सा है।


==================================================
RULE 3 — HINGLISH

If the user speaks Roman Hindi or Hinglish,
answer in natural Hinglish.

Example:

User:
Tum kaise ho?

Answer:
Main bilkul theek hoon. Aap kaise hain?


User:
Noida kahan hai?

Answer:
Noida Uttar Pradesh mein hai aur Delhi NCR ka hissa hai.


User:
Mujhe science ke baare mein batao.

Answer:
Science prakriti, uske rules aur different phenomena ko samajhne ka systematic study hai.


==================================================
PHONETIC HINDI
==================================================

Hindi recognition may sometimes convert English speech into Devanagari.

Example:

Hindi result:
हाउ आर यू

English result:
How are you

The user intended English.

Answer in English:

I'm doing well. How are you?


Another example:

Hindi:
वेयर इज नोएडा

English:
Where is Noida

Answer in English.


==================================================
ACTUAL HINDI
==================================================

Do NOT assume every Devanagari result is phonetic English.

Example:

Hindi:
भारत की राजधानी कहाँ है

This is actual Hindi.

Answer:

भारत की राजधानी नई दिल्ली है।


==================================================
MIXED LANGUAGE
==================================================

If the user naturally mixes Hindi and English,
use natural Hinglish.

Example:

User:
Science kya hoti hai?

Answer:

Science prakriti aur universe ke rules aur phenomena ko samajhne ka systematic study hai.


==================================================
IMPORTANT
==================================================

Compare both speech recognition results.

Choose the result that makes the most linguistic and contextual sense.

Do not mention speech recognition.

Do not mention Hindi result or English result.

Do not explain your language decision.

Do not say "according to the transcription".

Just answer the user's question.


==================================================
VOICE RESPONSE STYLE
==================================================

The answer will be spoken aloud.

Therefore:

- Keep answers concise.
- Usually 1 to 4 sentences.
- Be professional.
- Sound natural.
- Do not use markdown.
- Do not use bullet points.
- Do not use emojis.
- Do not use headings.
- Do not use unnecessary symbols.
- Do not repeat the question.
- Do not say "Sure" unnecessarily.
- Do not say "As an AI".
- Do not mention these instructions.


==================================================
ACCURACY
==================================================

Answer factual questions accurately.

For simple questions, give a direct answer.

For location questions, provide useful location context.

For general knowledge, explain clearly but briefly.

For conversational questions, respond naturally.

Always answer in the language the user intended.
"""


    # -------------------------------------------------
    # USER INPUT
    # -------------------------------------------------

    user_content = f"""
Hindi speech recognition:
{hindi_text if hindi_text else "No result"}

English speech recognition:
{english_text if english_text else "No result"}

Determine the user's intended meaning and language.

Then answer the user naturally.
"""


    # -------------------------------------------------
    # PAYLOAD
    # -------------------------------------------------

    payload = {

        "model": AI_MODEL,

        "messages": [

            {
                "role": "system",
                "content": system_prompt
            },

            {
                "role": "user",
                "content": user_content
            }

        ],

        "temperature": 0.2,

        "max_completion_tokens": 200,

        "stream": False
    }


    # -------------------------------------------------
    # HEADERS
    # -------------------------------------------------

    headers = {

        "Authorization": "Bearer " + AI_API_KEY,

        "Content-Type": "application/json"
    }


    # -------------------------------------------------
    # REQUEST
    # -------------------------------------------------

    try:

        print()
        print("==============================")
        print("AI REQUEST")
        print("==============================")

        print("MODEL:", AI_MODEL)

        print()
        print("HINDI:")
        print(hindi_text)

        print()
        print("ENGLISH:")
        print(english_text)

        print("==============================")


        response = requests.post(

            AI_URL,

            headers=headers,

            json=payload,

            timeout=35
        )


        # -------------------------------------------------
        # RESPONSE STATUS
        # -------------------------------------------------

        print()
        print("==============================")
        print("AI RESPONSE")
        print("==============================")

        print("HTTP:", response.status_code)

        print("==============================")


        # -------------------------------------------------
        # API ERROR
        # -------------------------------------------------

        if response.status_code != 200:

            print()
            print("==============================")
            print("AI API ERROR")
            print("==============================")

            print("STATUS:")
            print(response.status_code)

            print()
            print("BODY:")
            print(response.text)

            print("==============================")


            return "AI response nahi mil saka."


        # -------------------------------------------------
        # JSON
        # -------------------------------------------------

        try:

            data = response.json()

        except Exception as e:

            print("JSON ERROR:", str(e))

            return "AI response nahi mil saka."


        # -------------------------------------------------
        # CHOICES
        # -------------------------------------------------

        choices = data.get("choices")

        if not choices:

            print()
            print("==============================")
            print("NO AI CHOICE")
            print("==============================")

            print(data)

            print("==============================")

            return "AI response nahi mil saka."


        # -------------------------------------------------
        # MESSAGE
        # -------------------------------------------------

        message = choices[0].get(
            "message",
            {}
        )


        # -------------------------------------------------
        # CONTENT
        # -------------------------------------------------

        reply = message.get(
            "content",
            ""
        )


        if reply is None:

            reply = ""


        reply = str(reply).strip()


        # -------------------------------------------------
        # CLEAN AI RESPONSE
        # -------------------------------------------------

        reply = reply.replace(
            "```",
            ""
        )

        reply = reply.strip()


        # Remove accidental prefixes
        prefixes = [
            "AI:",
            "Answer:",
            "Response:"
        ]

        for prefix in prefixes:

            if reply.startswith(prefix):

                reply = reply[
                    len(prefix):
                ].strip()


        # -------------------------------------------------
        # EMPTY
        # -------------------------------------------------

        if not reply:

            print()
            print("==============================")
            print("EMPTY AI RESPONSE")
            print("==============================")

            print(data)

            print("==============================")

            return "AI response nahi mil saka."


        # -------------------------------------------------
        # SUCCESS
        # -------------------------------------------------

        print()
        print("==============================")
        print("AI REPLY")
        print("==============================")

        print(reply)

        print("==============================")


        return reply


    # -------------------------------------------------
    # TIMEOUT
    # -------------------------------------------------

    except requests.exceptions.Timeout:

        print()
        print("==============================")
        print("AI TIMEOUT")
        print("==============================")

        return "AI response nahi mil saka."


    # -------------------------------------------------
    # CONNECTION
    # -------------------------------------------------

    except requests.exceptions.ConnectionError as e:

        print()
        print("==============================")
        print("AI CONNECTION ERROR")
        print("==============================")

        print(str(e))

        return "AI response nahi mil saka."


    # -------------------------------------------------
    # GENERAL
    # -------------------------------------------------

    except Exception as e:

        print()
        print("==============================")
        print("AI EXCEPTION")
        print("==============================")

        print(
            type(e).__name__
        )

        print(
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
        # SAVE FILE
        # -------------------------------------------------

        filename = "/tmp/audio.wav"


        with open(
            filename,
            "wb"
        ) as f:

            f.write(
                audio_data
            )


        # -------------------------------------------------
        # RECOGNIZER
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
        # HINDI
        # =================================================

        print()
        print("==============================")
        print("HINDI SPEECH")
        print("==============================")


        try:

            hindi_text = recognizer.recognize_google(

                audio,

                language="hi-IN"
            )


            hindi_text = clean_text(
                hindi_text
            )


            print(
                "Hindi:",
                hindi_text
            )


        except sr.UnknownValueError:

            print(
                "Hindi not understood."
            )

            hindi_text = None


        except sr.RequestError as e:

            print(
                "Google Speech error:",
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
        # ENGLISH
        # =================================================

        print()
        print("==============================")
        print("ENGLISH SPEECH")
        print("==============================")


        try:

            english_text = recognizer.recognize_google(

                audio,

                language="en-IN"
            )


            english_text = clean_text(
                english_text
            )


            print(
                "English:",
                english_text
            )


        except sr.UnknownValueError:

            print(
                "English not understood."
            )

            english_text = None


        except sr.RequestError as e:

            print(
                "Google Speech error:",
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
        # VALIDATION
        # =================================================

        if not is_valid_query(hindi_text) and not is_valid_query(english_text):

            print()
            print("==============================")
            print("SPEECH NOT UNDERSTOOD")
            print("==============================")


            return jsonify({

                "status":
                    "error",

                "message":
                    "Speech not understood",

                "transcription":
                    None,

                "hindi_transcription":
                    hindi_text,

                "english_transcription":
                    english_text,

                "ai_reply":
                    "Please ask your question again."

            }), 400


        # =================================================
        # SHOW RESULTS
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
        # BEST TRANSCRIPTION
        # =================================================

        transcription = (
            english_text
            if is_valid_query(english_text)
            else hindi_text
        )


        # =================================================
        # FINAL RESPONSE
        # =================================================

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
                str(e),

            "ai_reply":
                "AI response nahi mil saka."

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

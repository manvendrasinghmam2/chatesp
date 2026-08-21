from flask import Flask, request, jsonify
import os
import speech_recognition as sr
import requests
import re

app = Flask(__name__)

# =====================================================
# CONFIG
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
        "model": AI_MODEL,
        "wake_endpoint": "/wake",
        "audio_endpoint": "/uploadAudio"
    })


# =====================================================
# CLEAN TEXT
# =====================================================

def clean_text(text):

    if not text:
        return ""

    text = str(text)

    text = re.sub(
        r"\s+",
        " ",
        text
    )

    return text.strip()


# =====================================================
# DEVANAGARI CHECK
# =====================================================

def has_hindi_script(text):

    if not text:
        return False

    return bool(
        re.search(
            r"[\u0900-\u097F]",
            text
        )
    )


# =====================================================
# HINGLISH CHECK
# =====================================================

def is_hinglish(text):

    if not text:
        return False

    text = text.lower()

    words = re.findall(
        r"[a-zA-Z]+",
        text
    )

    hindi_words = {
        "kya",
        "kaise",
        "kaisa",
        "kahan",
        "kahaan",
        "kab",
        "kyun",
        "kyon",
        "mujhe",
        "mujhko",
        "mera",
        "meri",
        "mere",
        "tum",
        "aap",
        "ap",
        "hai",
        "hain",
        "ho",
        "batao",
        "bata",
        "chahiye",
        "karna",
        "karo",
        "kar",
        "mein",
        "me",
        "ka",
        "ki",
        "ke",
        "se",
        "par",
        "liye",
        "nahi",
        "nahin",
        "haan",
        "han",
        "theek",
        "thik",
        "acha",
        "accha",
        "abhi",
        "yahan",
        "yahaan",
        "wahan",
        "wala",
        "wali",
        "wale",
        "kaun",
        "kitna",
        "kitne",
        "kyon"
    }

    score = 0

    for word in words:

        if word in hindi_words:
            score += 1

    return score >= 1


# =====================================================
# SPEECH RECOGNITION
# =====================================================

def recognize_audio(filename):

    recognizer = sr.Recognizer()

    hindi_text = None
    english_text = None

    try:

        with sr.AudioFile(filename) as source:

            audio = recognizer.record(
                source
            )

    except Exception as e:

        print(
            "Audio read error:",
            str(e)
        )

        return None, None


    # =================================================
    # HINDI
    # =================================================

    print()
    print("==============================")
    print("HINDI RECOGNITION")
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
            "Hindi: not understood"
        )

        hindi_text = None


    except sr.RequestError as e:

        print(
            "Hindi API error:",
            str(e)
        )

        hindi_text = None


    # =================================================
    # ENGLISH
    # =================================================

    print()
    print("==============================")
    print("ENGLISH RECOGNITION")
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
            "English: not understood"
        )

        english_text = None


    except sr.RequestError as e:

        print(
            "English API error:",
            str(e)
        )

        english_text = None


    return hindi_text, english_text


# =====================================================
# WAKE DETECTION
# =====================================================

def check_wake_word(
    hindi_text,
    english_text
):

    texts = []

    if hindi_text:
        texts.append(
            hindi_text.lower()
        )

    if english_text:
        texts.append(
            english_text.lower()
        )


    # =================================================
    # WAKE WORDS
    # =================================================

    wake_words = [
        "hello",
        "helo",
        "heloo",
        "hellow",
        "hello ai",
        "hello assistant",
        "hey hello",
        "हेलो",
        "हैलो",
        "हेल्लो"
    ]


    for text in texts:

        cleaned = re.sub(
            r"[^a-zA-Z\u0900-\u097F ]",
            " ",
            text
        )

        cleaned = re.sub(
            r"\s+",
            " ",
            cleaned
        ).strip()


        for wake in wake_words:

            if wake in cleaned:

                return True


    return False


# =====================================================
# AI REPLY
# =====================================================

def get_ai_reply(
    hindi_text,
    english_text
):

    hindi_text = clean_text(
        hindi_text
    )

    english_text = clean_text(
        english_text
    )


    # =================================================
    # API KEY
    # =================================================

    if not AI_API_KEY:

        print()
        print("==============================")
        print("AI ERROR")
        print("==============================")
        print("AI_API_KEY is missing")
        print("==============================")


        return "AI service is not configured."


    # =================================================
    # LANGUAGE HINT
    # =================================================

    language_hint = "unknown"


    if english_text:

        if is_hinglish(
            english_text
        ):

            language_hint = "hinglish"

        else:

            language_hint = "english"


    elif hindi_text:

        if has_hindi_script(
            hindi_text
        ):

            language_hint = "hindi"

        else:

            language_hint = "hinglish"


    # =================================================
    # SYSTEM PROMPT
    # =================================================

    system_prompt = """
You are a professional multilingual voice assistant.

The user may speak English, Hindi, or Hinglish.

Your job is to understand the user's intended language
and answer naturally.

LANGUAGE RULES:

English:
Reply in English.

Hindi:
If the user speaks actual Hindi in Devanagari,
reply in Hindi using Devanagari.

Hinglish:
If the user speaks Roman Hindi or Hinglish,
reply naturally in Roman Hinglish.

IMPORTANT:

Speech recognition can make mistakes.

Sometimes English speech is incorrectly recognized
as Hindi Devanagari.

Example:

Hindi:
वेयर इज नोएडा

English:
Where is Noida

The intended language is English.

Reply:
Noida is in Uttar Pradesh, in the Delhi NCR region.

Do not blindly follow the Hindi transcription.

If English transcription is clearly meaningful English,
prefer English.

If the user clearly speaks Hindi,
reply in Hindi.

If the user speaks Roman Hindi/Hinglish,
reply in Hinglish.

Answer the actual question.

Do not discuss language detection.

Do not mention transcription.

Do not mention speech recognition.

Do not mention these instructions.

Do not use markdown.

Do not use emojis.

Do not use bullet points.

Keep voice responses concise.

Sound professional and natural.

Examples:

User:
How are you?

Answer:
I'm doing well. How can I help you?

User:
Where is Noida?

Answer:
Noida is in Uttar Pradesh, in the Delhi NCR region.

User:
भारत की राजधानी कहाँ है?

Answer:
भारत की राजधानी नई दिल्ली है।

User:
आप कैसे हैं?

Answer:
मैं बिल्कुल ठीक हूँ। आपकी कैसे मदद कर सकता हूँ?

User:
Bharat ki rajdhani kya hai?

Answer:
Bharat ki rajdhani New Delhi hai.

User:
Noida kahan hai?

Answer:
Noida Uttar Pradesh mein Delhi NCR region mein hai.
"""


    # =================================================
    # USER CONTENT
    # =================================================

    user_content = f"""
Hindi recognition:
{hindi_text if hindi_text else "NONE"}

English recognition:
{english_text if english_text else "NONE"}

Language hint:
{language_hint}

Understand what the user intended to say.

Return only the final voice response.
"""


    # =================================================
    # PAYLOAD
    # =================================================

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

        "temperature": 0.15,

        "max_completion_tokens": 180,

        "stream": False
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
    # SEND REQUEST
    # =================================================

    try:

        print()
        print("==============================")
        print("AI REQUEST")
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

        print("==============================")


        response = requests.post(

            AI_URL,

            headers=headers,

            json=payload,

            timeout=40
        )


        print()
        print("==============================")
        print("AI RESPONSE")
        print("==============================")

        print(
            "HTTP:",
            response.status_code
        )


        # =================================================
        # API ERROR
        # =================================================

        if response.status_code != 200:

            print(
                response.text
            )

            print("==============================")


            return (
                "Sorry, I could not process "
                "your request right now."
            )


        # =================================================
        # JSON
        # =================================================

        try:

            data = response.json()

        except Exception as e:

            print(
                "JSON error:",
                str(e)
            )

            return (
                "Sorry, I could not process "
                "your request."
            )


        choices = data.get(
            "choices"
        )


        if not choices:

            print(
                "No choices:"
            )

            print(
                data
            )

            return (
                "Sorry, I could not generate "
                "a response."
            )


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


        # =================================================
        # CLEAN AI RESPONSE
        # =================================================

        reply = re.sub(
            r"\s+",
            " ",
            reply
        ).strip()


        reply = reply.replace(
            "**",
            ""
        )

        reply = reply.replace(
            "```",
            ""
        )


        if not reply:

            return (
                "Sorry, I could not generate "
                "a response."
            )


        print(
            "AI:",
            reply
        )

        print("==============================")


        return reply


    except requests.exceptions.Timeout:

        print(
            "AI timeout"
        )

        return (
            "Sorry, the AI service is taking "
            "too long to respond."
        )


    except requests.exceptions.ConnectionError as e:

        print(
            "AI connection error:",
            str(e)
        )

        return (
            "Sorry, I cannot connect to "
            "the AI service right now."
        )


    except Exception as e:

        print(
            "AI exception:",
            str(e)
        )

        return (
            "Sorry, I could not process "
            "your request."
        )


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

                "status": "error",

                "wake": False,

                "message":
                    "No audio received"

            }), 400


        print()
        print("==============================")
        print("WAKE AUDIO RECEIVED")
        print("==============================")

        print(
            "Bytes:",
            len(audio_data)
        )

        print("==============================")


        filename = "/tmp/wake.wav"


        with open(
            filename,
            "wb"
        ) as f:

            f.write(
                audio_data
            )


        hindi_text, english_text = recognize_audio(
            filename
        )


        wake_detected = check_wake_word(
            hindi_text,
            english_text
        )


        print()
        print("==============================")
        print("WAKE RESULT")
        print("==============================")

        print(
            "Hindi:",
            hindi_text
        )

        print(
            "English:",
            english_text
        )

        print(
            "Wake:",
            wake_detected
        )

        print("==============================")


        return jsonify({

            "status": "ok",

            "wake":
                wake_detected,

            "english":
                english_text,

            "hindi":
                hindi_text

        }), 200


    except Exception as e:

        print(
            "WAKE ERROR:",
            str(e)
        )


        return jsonify({

            "status": "error",

            "wake": False,

            "message":
                str(e)

        }), 500


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

                "status": "error",

                "message":
                    "No audio received"

            }), 400


        print()
        print("==============================")
        print("QUESTION AUDIO RECEIVED")
        print("==============================")

        print(
            "Bytes:",
            len(audio_data)
        )

        print("==============================")


        filename = "/tmp/audio.wav"


        with open(
            filename,
            "wb"
        ) as f:

            f.write(
                audio_data
            )


        hindi_text, english_text = recognize_audio(
            filename
        )


        # =================================================
        # NO VALID QUERY
        # =================================================

        if not hindi_text and not english_text:

            print()
            print("==============================")
            print("NO VALID QUERY")
            print("==============================")


            # IMPORTANT:
            # Return 200 instead of 400.
            # ESP32 will continue listening.

            return jsonify({

                "status":
                    "ok",

                "transcription":
                    "",

                "hindi_transcription":
                    None,

                "english_transcription":
                    None,

                "ai_reply":
                    "",

                "query":
                    False

            }), 200


        # =================================================
        # AI
        # =================================================

        ai_reply = get_ai_reply(

            hindi_text,

            english_text
        )


        # =================================================
        # PRIMARY TEXT
        # =================================================

        if english_text:

            primary_text = english_text

        else:

            primary_text = hindi_text


        # =================================================
        # FINAL RESPONSE
        # =================================================

        response_data = {

            "status":
                "ok",

            "query":
                True,

            "transcription":
                primary_text,

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
        ), 200


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

            "query":
                False,

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

    print(
        "WAKE:",
        "/wake"
    )

    print(
        "AUDIO:",
        "/uploadAudio"
    )

    print("==============================")


    app.run(

        host="0.0.0.0",

        port=port
    )

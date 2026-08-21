from flask import Flask, request, jsonify
import os
import tempfile
import speech_recognition as sr
import requests
import re
import time

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
# LIMITS
# =====================================================

MAX_AUDIO_BYTES = 500000

AI_TIMEOUT = 25

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
# WAKE
# =====================================================

@app.route("/wake", methods=["POST"])
def wake():

    try:

        audio_data = request.get_data()

        if not audio_data:
            return jsonify({
                "status": "ok",
                "wake": False,
                "english": None,
                "hindi": None
            })

        if len(audio_data) > MAX_AUDIO_BYTES:
            return jsonify({
                "status": "error",
                "wake": False,
                "message": "Audio too large"
            }), 413

        recognizer = sr.Recognizer()

        temp_file = tempfile.NamedTemporaryFile(
            suffix=".wav",
            delete=False
        )

        filename = temp_file.name

        try:

            temp_file.write(audio_data)
            temp_file.close()

            with sr.AudioFile(filename) as source:

                audio = recognizer.record(source)

            english = None
            hindi = None

            # -------------------------------------------------
            # ENGLISH
            # -------------------------------------------------

            try:

                english = recognizer.recognize_google(
                    audio,
                    language="en-IN"
                )

            except Exception:
                english = None

            # -------------------------------------------------
            # HINDI
            # -------------------------------------------------

            try:

                hindi = recognizer.recognize_google(
                    audio,
                    language="hi-IN"
                )

            except Exception:
                hindi = None

            # -------------------------------------------------
            # WAKE CHECK
            # -------------------------------------------------

            combined = ""

            if english:
                combined += " " + english.lower()

            if hindi:
                combined += " " + hindi.lower()

            combined = combined.strip()

            wake_words = [
                "hello",
                "helo",
                "hallo",
                "hey",
                "हेलो",
                "हैलो"
            ]

            detected = False

            for word in wake_words:

                if word in combined:
                    detected = True
                    break

            return jsonify({

                "status": "ok",

                "wake": detected,

                "english": english,

                "hindi": hindi

            })

        finally:

            try:
                os.remove(filename)
            except Exception:
                pass

    except Exception as e:

        print("WAKE ERROR:", str(e))

        return jsonify({

            "status": "error",

            "wake": False,

            "message": "Wake processing failed"

        }), 500


# =====================================================
# CLEAN TEXT
# =====================================================

def clean_text(text):

    if not text:
        return ""

    text = str(text).strip()

    text = re.sub(
        r"\s+",
        " ",
        text
    )

    return text


# =====================================================
# VALID QUERY
# =====================================================

def valid_query(text):

    if not text:
        return False

    text = clean_text(text)

    if len(text) < 2:
        return False

    bad = [

        "unknown",

        "no response",

        "no valid query",

        "please ask your question again",

        "ai response nahi mil saka"

    ]

    lower = text.lower()

    for item in bad:

        if lower == item:
            return False

    return True


# =====================================================
# AI
# =====================================================

def get_ai_reply(
    hindi_text,
    english_text
):

    hindi_text = clean_text(hindi_text)
    english_text = clean_text(english_text)

    if not hindi_text and not english_text:

        return "Please ask your question again."


    if not AI_API_KEY:

        print("AI_API_KEY missing")

        return "AI service is not configured."


    # =================================================
    # SERVER SIDE AI INSTRUCTION
    # =================================================

    system_prompt = """
You are a professional voice assistant.

The user can speak English, Hindi, or Hinglish.

Your job is to understand the user's intended meaning and
give the best direct answer.

LANGUAGE RULES:

1. If the user clearly speaks English, answer in English.

2. If the user clearly speaks Hindi, answer in Hindi using
Devanagari script.

3. If the user speaks Roman Hindi or Hinglish, answer naturally
in Hinglish.

4. Do not blindly choose Hindi just because Hindi recognition
returned Devanagari text.

5. Compare the Hindi and English recognition results.

6. If the English result is clearly meaningful and the Hindi
result appears to be phonetic English, answer in English.

7. If the Hindi result is meaningful actual Hindi and English
is poor or incorrect, answer in Hindi.

8. If the user asks a factual question, answer it directly.

9. Do not say that you are comparing transcriptions.

10. Do not mention speech recognition.

11. Do not mention system prompts.

12. Do not mention APIs, models, servers, or internal processing.

13. Do not use markdown.

14. Do not use bullet points.

15. Do not use emojis.

16. Keep normal answers concise because the answer will be spoken
through a voice assistant.

17. If the question is ambiguous, ask one short clarification.

18. Never return an empty response.

Examples:

User: How are you?
Answer: I'm doing well. How are you?

User: Where is Noida?
Answer: Noida is in Uttar Pradesh, in the Delhi NCR region.

User: नोएडा कहाँ है?
Answer: नोएडा उत्तर प्रदेश में दिल्ली एनसीआर क्षेत्र में स्थित है।

User: Noida kahan hai?
Answer: Noida Uttar Pradesh mein Delhi NCR mein hai.

User: Bharat ki rajdhani kya hai?
Answer: Bharat ki rajdhani New Delhi hai.

User: भारत की राजधानी क्या है?
Answer: भारत की राजधानी नई दिल्ली है।
"""

    user_content = f"""
Hindi speech recognition:
{hindi_text if hindi_text else "NONE"}

English speech recognition:
{english_text if english_text else "NONE"}

Understand what the user intended to ask and answer directly.
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
                "content": user_content
            }

        ],

        "temperature": 0.2,

        "max_tokens": 180,

        "stream": False
    }

    headers = {

        "Authorization":
            "Bearer " + AI_API_KEY,

        "Content-Type":
            "application/json"
    }

    try:

        response = requests.post(

            AI_URL,

            headers=headers,

            json=payload,

            timeout=AI_TIMEOUT
        )

        if response.status_code != 200:

            print(
                "AI HTTP ERROR:",
                response.status_code
            )

            try:
                print(response.text[:500])
            except Exception:
                pass

            return "AI service is temporarily unavailable."


        data = response.json()

        choices = data.get("choices")

        if not choices:

            return "I could not get an answer right now."


        message = choices[0].get(
            "message",
            {}
        )

        reply = message.get(
            "content",
            ""
        )

        reply = clean_text(reply)


        if not reply:

            return "I could not get an answer right now."


        return reply


    except requests.exceptions.Timeout:

        print("AI TIMEOUT")

        return "AI service took too long to respond."


    except requests.exceptions.ConnectionError:

        print("AI CONNECTION ERROR")

        return "AI service is temporarily unavailable."


    except Exception as e:

        print(
            "AI ERROR:",
            type(e).__name__,
            str(e)
        )

        return "I could not get an answer right now."


# =====================================================
# AUDIO -> SPEECH
# =====================================================

def recognize_audio(filename):

    recognizer = sr.Recognizer()

    recognizer.energy_threshold = 250

    recognizer.dynamic_energy_threshold = True

    recognizer.pause_threshold = 0.7

    recognizer.non_speaking_duration = 0.4


    with sr.AudioFile(filename) as source:

        audio = recognizer.record(source)


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

        hindi_text = clean_text(
            hindi_text
        )

    except sr.UnknownValueError:

        hindi_text = None

    except sr.RequestError as e:

        print(
            "Hindi speech service error:",
            str(e)
        )


    # =================================================
    # ENGLISH
    # =================================================

    try:

        english_text = recognizer.recognize_google(

            audio,

            language="en-IN"

        )

        english_text = clean_text(
            english_text
        )

    except sr.UnknownValueError:

        english_text = None

    except sr.RequestError as e:

        print(
            "English speech service error:",
            str(e)
        )


    return hindi_text, english_text


# =====================================================
# UPLOAD AUDIO
# =====================================================

@app.route(
    "/uploadAudio",
    methods=["POST"]
)
def upload_audio():

    filename = None

    try:

        audio_data = request.get_data()

        # -------------------------------------------------
        # EMPTY AUDIO
        # -------------------------------------------------

        if not audio_data:

            return jsonify({

                "status": "error",

                "message": "No audio received"

            }), 400


        # -------------------------------------------------
        # SIZE CHECK
        # -------------------------------------------------

        if len(audio_data) > MAX_AUDIO_BYTES:

            return jsonify({

                "status": "error",

                "message": "Audio too large"

            }), 413


        # -------------------------------------------------
        # TEMP WAV
        # -------------------------------------------------

        temp_file = tempfile.NamedTemporaryFile(

            suffix=".wav",

            delete=False

        )

        filename = temp_file.name

        temp_file.write(audio_data)

        temp_file.close()


        # -------------------------------------------------
        # SPEECH
        # -------------------------------------------------

        hindi_text, english_text = recognize_audio(
            filename
        )


        # -------------------------------------------------
        # PICK DISPLAY QUERY
        # -------------------------------------------------

        if valid_query(english_text):

            transcription = english_text

        elif valid_query(hindi_text):

            transcription = hindi_text

        else:

            transcription = None


        # -------------------------------------------------
        # NO VALID QUERY
        # -------------------------------------------------

        if not transcription:

            return jsonify({

                "status": "error",

                "message": "Speech not understood",

                "transcription": None,

                "hindi_transcription": hindi_text,

                "english_transcription": english_text,

                "ai_reply":
                    "Please ask your question again."

            }), 400


        # -------------------------------------------------
        # AI
        # -------------------------------------------------

        ai_reply = get_ai_reply(

            hindi_text,

            english_text

        )


        # -------------------------------------------------
        # FINAL
        # -------------------------------------------------

        return jsonify({

            "status": "ok",

            "transcription": transcription,

            "hindi_transcription": hindi_text,

            "english_transcription": english_text,

            "ai_reply": ai_reply

        })


    except Exception as e:

        print(
            "SERVER ERROR:",
            type(e).__name__,
            str(e)
        )

        return jsonify({

            "status": "error",

            "message": "Server processing failed",

            "ai_reply":
                "I could not process your question."

        }), 500


    finally:

        if filename:

            try:
                os.remove(filename)
            except Exception:
                pass


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

    print(
        "ESP32 Voice Server starting..."
    )

    print(
        "Port:",
        port
    )

    print(
        "AI model:",
        AI_MODEL
    )

    app.run(

        host="0.0.0.0",

        port=port

    )

from flask import Flask, request, jsonify
import os
import tempfile
import time
import speech_recognition as sr
import requests


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
    "llama-3.3-70b-versatile"
)

AI_TIMEOUT = 45

MAX_REPLY_CHARS = 1200


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
        "speech": "Google Speech Recognition",
        "ai": "Groq",
        "model": AI_MODEL,
        "api_key": bool(AI_API_KEY)
    })


# =====================================================
# AI SYSTEM INSTRUCTIONS
# =====================================================

AI_INSTRUCTIONS = r"""
You are a professional multilingual voice assistant.

Your job is to understand the user's intended language and answer naturally.

The user may speak:

1. English
2. Hindi
3. Roman Hindi
4. Hinglish
5. Mixed Hindi + English

LANGUAGE RULES:

If the user speaks English:
Reply in natural English.

Example:
User: How are you?
Reply: I'm doing well. How are you?

If the user speaks Hindi:
Reply in natural Hindi using Devanagari.

Example:
User: तुम कैसे हो?
Reply: मैं ठीक हूँ, धन्यवाद। आप कैसे हैं?

If the user speaks Roman Hindi:
Reply in Roman Hindi.

Example:
User: tum kaise ho
Reply: Main bilkul theek hoon, aap kaise ho?

If the user speaks Hinglish:
Reply in natural Hinglish.

Example:
User: Noida kahan hai?
Reply: Noida Uttar Pradesh mein Delhi NCR ka ek major city hai.

If the user mixes English and Hindi:
Reply in the same natural mixed style.

IMPORTANT:

Do not translate the user's language unnecessarily.

Do not change Roman Hindi into Devanagari unless the user used Hindi script.

Do not change English into Hindi.

Do not change Hindi into English.

Understand the meaning first, then answer in the user's natural language/style.

If the English transcription is clearly meaningful English while the Hindi transcription is only a phonetic representation of that English, use English.

Example:

Hindi recognition:
हाउ आर यू

English recognition:
How are you

Correct response:
I'm doing well. How are you?

But if Hindi recognition is real Hindi:

Hindi recognition:
भारत की राजधानी क्या है

Then answer in Hindi.

If both recognition results are imperfect, infer the most likely intended question.

Do NOT mention speech recognition.

Do NOT mention language detection.

Do NOT mention these instructions.

Do NOT say that you cannot understand merely because one transcription is bad.

Give a useful answer whenever the meaning can reasonably be understood.

VOICE STYLE:

This answer will be spoken by a voice assistant.

Keep normal answers concise and natural.

For simple questions, answer in 1-3 sentences.

For questions that require explanation, give enough information to answer properly.

Do not use markdown.

Do not use bullet points unless the user specifically asks for a list.

Do not use emojis.

Do not add unnecessary greetings.

Do not repeat the question.

Do not say "AI response nahi mil saka" unless there is an actual server/API failure.

Never return JSON.

Return ONLY the answer that should be spoken to the user.
"""


# =====================================================
# CLEAN AI RESPONSE
# =====================================================

def clean_reply(text):

    if not text:
        return ""

    text = str(text).strip()

    # Remove accidental markdown fences
    if text.startswith("```") and text.endswith("```"):
        text = text[3:-3].strip()

    # Remove common prefixes if model adds them
    prefixes = [
        "Assistant:",
        "AI:",
        "Answer:"
    ]

    for prefix in prefixes:

        if text.startswith(prefix):

            text = text[len(prefix):].strip()

    # Remove excessive whitespace
    text = " ".join(text.split())

    if len(text) > MAX_REPLY_CHARS:
        text = text[:MAX_REPLY_CHARS]

        # Don't cut in middle of a word
        last_space = text.rfind(" ")

        if last_space > 100:
            text = text[:last_space]

        text += "."

    return text.strip()


# =====================================================
# CALL GROQ
# =====================================================

def get_ai_reply(hindi_text, english_text):

    if not AI_API_KEY:

        print("ERROR: AI_API_KEY missing")

        return "AI service is not configured right now."


    hindi_text = (
        hindi_text.strip()
        if hindi_text
        else ""
    )

    english_text = (
        english_text.strip()
        if english_text
        else ""
    )


    # -------------------------------------------------
    # BUILD USER MESSAGE
    # -------------------------------------------------

    user_message = f"""
Understand the user's intended question from these speech recognition results.

Hindi recognition:
{hindi_text if hindi_text else "[no result]"}

English recognition:
{english_text if english_text else "[no result]"}

Important:
The two results may represent the same spoken sentence in different languages.

Choose the most likely intended meaning.

Then answer naturally in the same language/style the user intended.
"""


    # -------------------------------------------------
    # REQUEST
    # -------------------------------------------------

    payload = {

        "model": AI_MODEL,

        "messages": [

            {
                "role": "system",
                "content": AI_INSTRUCTIONS
            },

            {
                "role": "user",
                "content": user_message
            }

        ],

        "temperature": 0.25,

        "max_completion_tokens": 500,

        "stream": False
    }


    headers = {

        "Authorization":
            "Bearer " + AI_API_KEY,

        "Content-Type":
            "application/json",

        "Accept":
            "application/json"
    }


    # -------------------------------------------------
    # REQUEST WITH RETRY
    # -------------------------------------------------

    last_error = None


    for attempt in range(2):

        try:

            print()
            print("==============================")
            print("AI REQUEST")
            print("==============================")
            print("MODEL:", AI_MODEL)
            print("HINDI:", hindi_text)
            print("ENGLISH:", english_text)
            print("ATTEMPT:", attempt + 1)
            print("==============================")


            response = requests.post(

                AI_URL,

                headers=headers,

                json=payload,

                timeout=AI_TIMEOUT
            )


            print()
            print("==============================")
            print("AI HTTP:", response.status_code)
            print("==============================")


            # -------------------------------------------------
            # SUCCESS
            # -------------------------------------------------

            if response.status_code == 200:

                try:

                    data = response.json()

                except Exception as e:

                    last_error = (
                        "Invalid JSON from AI: "
                        + str(e)
                    )

                    print(last_error)

                    continue


                choices = data.get("choices")


                if not choices:

                    last_error = "AI choices missing"

                    print(last_error)

                    continue


                message = choices[0].get(
                    "message",
                    {}
                )


                reply = message.get(
                    "content",
                    ""
                )


                reply = clean_reply(reply)


                if reply:

                    print()
                    print("==============================")
                    print("AI REPLY")
                    print("==============================")
                    print(reply)
                    print("==============================")


                    return reply


                last_error = "AI returned empty response"

                print(last_error)

                continue


            # -------------------------------------------------
            # API ERROR
            # -------------------------------------------------

            try:

                error_data = response.json()

            except Exception:

                error_data = response.text


            print()
            print("==============================")
            print("AI API ERROR")
            print("==============================")

            print(error_data)

            print("==============================")


            last_error = (
                "HTTP "
                + str(response.status_code)
            )


            # Retry only temporary errors
            if response.status_code in [
                408,
                429,
                500,
                502,
                503,
                504
            ]:

                time.sleep(1)

                continue


            break


        except requests.exceptions.Timeout as e:

            last_error = "AI timeout"

            print(last_error)

            print(str(e))

            time.sleep(1)


        except requests.exceptions.ConnectionError as e:

            last_error = "AI connection error"

            print(last_error)

            print(str(e))

            time.sleep(1)


        except Exception as e:

            last_error = (
                type(e).__name__
                + ": "
                + str(e)
            )

            print()
            print("AI EXCEPTION")
            print(last_error)

            time.sleep(1)


    # -------------------------------------------------
    # FINAL FAILURE
    # -------------------------------------------------

    print()
    print("==============================")
    print("AI FAILED")
    print("==============================")
    print(last_error)
    print("==============================")


    return "I could not get an answer right now. Please ask again."


# =====================================================
# SPEECH RECOGNITION
# =====================================================

def recognize_audio(audio):

    recognizer = sr.Recognizer()

    # Better for voice recordings
    recognizer.energy_threshold = 250

    recognizer.dynamic_energy_threshold = True

    recognizer.pause_threshold = 0.8

    recognizer.phrase_threshold = 0.3

    recognizer.non_speaking_duration = 0.5


    hindi_text = None
    english_text = None


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

        print(
            "Hindi:",
            hindi_text
        )


    except sr.UnknownValueError:

        print(
            "Hindi: no usable result"
        )


    except sr.RequestError as e:

        print(
            "Hindi speech service error:",
            e
        )


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

        print(
            "English:",
            english_text
        )


    except sr.UnknownValueError:

        print(
            "English: no usable result"
        )


    except sr.RequestError as e:

        print(
            "English speech service error:",
            e
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

        # -------------------------------------------------
        # RECEIVE DATA
        # -------------------------------------------------

        audio_data = request.get_data()


        if not audio_data:

            print(
                "No audio received"
            )


            return jsonify({

                "status":
                    "error",

                "message":
                    "No audio received"

            }), 400


        print()
        print("==============================")
        print("AUDIO RECEIVED")
        print("==============================")

        print(
            "Bytes:",
            len(audio_data)
        )

        print("==============================")


        # -------------------------------------------------
        # SAVE TEMP FILE
        # -------------------------------------------------

        fd, filename = tempfile.mkstemp(
            suffix=".wav"
        )


        with os.fdopen(
            fd,
            "wb"
        ) as f:

            f.write(
                audio_data
            )


        # -------------------------------------------------
        # READ AUDIO
        # -------------------------------------------------

        recognizer = sr.Recognizer()


        with sr.AudioFile(
            filename
        ) as source:

            # Small calibration
            # without removing actual speech
            audio = recognizer.record(
                source
            )


        # -------------------------------------------------
        # RECOGNITION
        # -------------------------------------------------

        hindi_text, english_text = recognize_audio(
            audio
        )


        # -------------------------------------------------
        # NO QUERY
        # -------------------------------------------------

        if not hindi_text and not english_text:

            print()
            print(
                "NO VALID SPEECH"
            )


            return jsonify({

                "status":
                    "empty",

                "transcription":
                    "",

                "hindi_transcription":
                    None,

                "english_transcription":
                    None,

                "ai_reply":
                    "I could not understand that. Please ask again."

            }), 200


        # -------------------------------------------------
        # AI
        # -------------------------------------------------

        ai_reply = get_ai_reply(

            hindi_text,

            english_text

        )


        # -------------------------------------------------
        # BEST TRANSCRIPTION
        # -------------------------------------------------

        transcription = (
            english_text
            if english_text
            else hindi_text
        )


        # -------------------------------------------------
        # FINAL RESPONSE
        # -------------------------------------------------

        result = {

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
            "USER:",
            transcription
        )

        print(
            "AI:",
            ai_reply
        )

        print("==============================")


        return jsonify(
            result
        )


    except Exception as e:

        print()
        print("==============================")
        print("SERVER ERROR")
        print("==============================")

        print(
            type(e).__name__
        )

        print(
            str(e)
        )

        print("==============================")


        return jsonify({

            "status":
                "error",

            "message":
                "Server error",

            "ai_reply":
                "I could not process that right now. Please ask again."

        }), 500


    finally:

        # -------------------------------------------------
        # DELETE TEMP FILE
        # -------------------------------------------------

        if filename:

            try:

                if os.path.exists(
                    filename
                ):

                    os.remove(
                        filename
                    )

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


    print()
    print("==============================")
    print("ESP32 VOICE AI SERVER")
    print("==============================")

    print(
        "PORT:",
        port
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

        port=port,

        threaded=True
    )

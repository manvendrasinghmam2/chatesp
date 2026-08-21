from flask import Flask, request, jsonify
import os
import speech_recognition as sr
import requests
import re
import tempfile

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
# CLEAN TEXT
# =====================================================

def clean_text(text):
    if not text:
        return ""

    text = str(text).strip()
    text = re.sub(r"\s+", " ", text)

    return text

# =====================================================
# VALID QUERY
# =====================================================

def is_valid_query(text):

    if not text:
        return False

    text = text.strip()

    if len(text) < 2:
        return False

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
# WAKE WORD CHECK
# =====================================================

def is_hello(text):

    if not text:
        return False

    text = clean_text(text).lower()

    print("WAKE TEXT:", text)

    # Remove punctuation
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()

    # English possibilities
    english_words = [
        "hello",
        "helo",
        "hallo",
        "hellow",
        "halo"
    ]

    for word in english_words:
        if word in text:
            return True

    # Hindi recognition possibilities
    hindi_words = [
        "हेलो",
        "हैलो",
        "हलो"
    ]

    for word in hindi_words:
        if word in text:
            return True

    return False

# =====================================================
# WAKE ENDPOINT
# =====================================================

@app.route("/wake", methods=["POST"])
def wake():

    try:

        audio_data = request.get_data()

        print()
        print("==============================")
        print("WAKE REQUEST")
        print("==============================")

        print(
            "Audio bytes:",
            len(audio_data)
        )

        if not audio_data:

            print("NO AUDIO")

            return jsonify({
                "status": "error",
                "wake": False,
                "message": "No audio received"
            }), 400

        # -------------------------------------------------
        # SAVE TEMP WAV
        # -------------------------------------------------

        fd, filename = tempfile.mkstemp(
            suffix=".wav"
        )

        os.close(fd)

        try:

            with open(filename, "wb") as f:
                f.write(audio_data)

            # -------------------------------------------------
            # GOOGLE SPEECH
            # -------------------------------------------------

            recognizer = sr.Recognizer()

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

                print(
                    "Hindi:",
                    hindi_text
                )

            except sr.UnknownValueError:

                print("Hindi: not understood")

            except sr.RequestError as e:

                print(
                    "Hindi Google error:",
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

                print(
                    "English:",
                    english_text
                )

            except sr.UnknownValueError:

                print("English: not understood")

            except sr.RequestError as e:

                print(
                    "English Google error:",
                    str(e)
                )

            # =================================================
            # CHECK HELLO
            # =================================================

            wake_detected = (
                is_hello(hindi_text)
                or
                is_hello(english_text)
            )

            print()
            print(
                "WAKE DETECTED:",
                wake_detected
            )

            print("==============================")

            return jsonify({

                "status": "ok",

                "wake": wake_detected,

                "hindi": hindi_text,

                "english": english_text

            })

        finally:

            try:
                os.remove(filename)
            except Exception:
                pass

    except Exception as e:

        print()
        print("==============================")
        print("WAKE SERVER ERROR")
        print("==============================")

        print(
            type(e).__name__,
            str(e)
        )

        print("==============================")

        return jsonify({

            "status": "error",

            "wake": False,

            "message": str(e)

        }), 500

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
            "status": "error",
            "message": "No JSON received"
        }), 400

    print(data)

    return jsonify({
        "status": "ok",
        "data": data
    })

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

    if not AI_API_KEY:

        print(
            "AI_API_KEY is NOT configured!"
        )

        return "AI response nahi mil saka."

    if not is_valid_query(hindi_text) and not is_valid_query(english_text):

        return "Please ask your question again."

    system_prompt = """
You are a professional bilingual voice assistant running on an ESP32.

Understand the user's intended language and answer naturally.

If clearly English:
answer in English.

If clearly Hindi:
answer in Hindi using Devanagari.

If Roman Hindi or Hinglish:
answer in natural Hinglish.

Compare both speech recognition results because one may be inaccurate.

Do not mention transcription or speech recognition.

Keep the answer concise because it will be spoken aloud.

Usually answer in 1 to 4 sentences.

Do not use markdown.
Do not use bullet points.
Do not use emojis.
Do not use headings.
Do not repeat the question.

Answer factual questions accurately.
"""

    user_content = f"""
Hindi speech recognition:
{hindi_text if hindi_text else "No result"}

English speech recognition:
{english_text if english_text else "No result"}

Determine the user's intended meaning and language.

Then answer naturally.
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

        "max_completion_tokens": 200,

        "stream": False
    }

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

        response = requests.post(
            AI_URL,
            headers=headers,
            json=payload,
            timeout=35
        )

        print(
            "HTTP:",
            response.status_code
        )

        if response.status_code != 200:

            print(
                response.text
            )

            return "AI response nahi mil saka."

        data = response.json()

        choices = data.get(
            "choices"
        )

        if not choices:

            return "AI response nahi mil saka."

        message = choices[0].get(
            "message",
            {}
        )

        reply = message.get(
            "content",
            ""
        )

        reply = str(
            reply or ""
        ).strip()

        reply = reply.replace(
            "```",
            ""
        ).strip()

        for prefix in [
            "AI:",
            "Answer:",
            "Response:"
        ]:

            if reply.startswith(prefix):

                reply = reply[
                    len(prefix):
                ].strip()

        if not reply:

            return "AI response nahi mil saka."

        print(
            "AI:",
            reply
        )

        print("==============================")

        return reply

    except requests.exceptions.Timeout:

        print("AI TIMEOUT")

        return "AI response nahi mil saka."

    except requests.exceptions.ConnectionError as e:

        print(
            "AI CONNECTION ERROR:",
            str(e)
        )

        return "AI response nahi mil saka."

    except Exception as e:

        print(
            "AI ERROR:",
            type(e).__name__,
            str(e)
        )

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

        audio_data = request.get_data()

        print()
        print("==============================")
        print("QUESTION AUDIO")
        print("==============================")

        print(
            "Audio bytes:",
            len(audio_data)
        )

        if not audio_data:

            return jsonify({

                "status": "error",

                "message":
                    "No audio received",

                "transcription":
                    None,

                "ai_reply":
                    "Please ask your question again."

            }), 400

        # -------------------------------------------------
        # TEMP FILE
        # -------------------------------------------------

        fd, filename = tempfile.mkstemp(
            suffix=".wav"
        )

        os.close(fd)

        try:

            with open(
                filename,
                "wb"
            ) as f:

                f.write(
                    audio_data
                )

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

                return jsonify({

                    "status": "error",

                    "message":
                        "Speech service error",

                    "details":
                        str(e)

                }), 500

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

                return jsonify({

                    "status": "error",

                    "message":
                        "Speech service error",

                    "details":
                        str(e)

                }), 500

            print()
            print("Hindi:")
            print(hindi_text)

            print()
            print("English:")
            print(english_text)

            # =================================================
            # VALIDATION
            # =================================================

            if (
                not is_valid_query(hindi_text)
                and
                not is_valid_query(english_text)
            ):

                return jsonify({

                    "status": "error",

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
                if is_valid_query(
                    english_text
                )
                else hindi_text

            )

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
            print("FINAL")
            print("==============================")

            print(
                response_data
            )

            print("==============================")

            return jsonify(
                response_data
            )

        finally:

            try:
                os.remove(filename)
            except Exception:
                pass

    except Exception as e:

        print()
        print("==============================")
        print("SERVER ERROR")
        print("==============================")

        print(
            type(e).__name__,
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

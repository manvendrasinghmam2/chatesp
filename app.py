from flask import Flask, request, jsonify
import os
import re
import tempfile
import requests
import traceback


app = Flask(__name__)


# ============================================================
# CONFIG
# ============================================================

GROQ_API_KEY = os.environ.get("GROQ_API_KEY") or os.environ.get("AI_API_KEY")

GROQ_CHAT_URL = "https://api.groq.com/openai/v1/chat/completions"

GROQ_TRANSCRIPTION_URL = (
    "https://api.groq.com/openai/v1/audio/transcriptions"
)

AI_MODEL = os.environ.get(
    "AI_MODEL",
    "llama-3.3-70b-versatile"
)

WHISPER_MODEL = os.environ.get(
    "WHISPER_MODEL",
    "whisper-large-v3"
)


# ============================================================
# SERVER
# ============================================================

PORT = int(
    os.environ.get(
        "PORT",
        10000
    )
)


# ============================================================
# RESPONSE FALLBACKS
# ============================================================

def error_reply():

    return "Sorry, I couldn't process that right now."


def speech_error_reply():

    return "Sorry, I couldn't understand that."


# ============================================================
# HOME
# ============================================================

@app.route("/", methods=["GET"])
def home():

    return "ESP32 Voice AI Server is ONLINE!"


# ============================================================
# HEALTH
# ============================================================

@app.route("/health", methods=["GET"])
def health():

    return jsonify({

        "status": "online",

        "speech_engine":
            "Groq Whisper",

        "ai_engine":
            "Groq",

        "ai_model":
            AI_MODEL,

        "whisper_model":
            WHISPER_MODEL,

        "api_key":
            "configured"
            if GROQ_API_KEY
            else "missing"
    })


# ============================================================
# CLEAN TEXT
# ============================================================

def clean_text(text):

    if not text:
        return ""

    text = str(text)

    text = text.replace(
        "\x00",
        " "
    )

    text = re.sub(
        r"\s+",
        " ",
        text
    )

    return text.strip()


# ============================================================
# CHECK USEFUL QUERY
# ============================================================

def is_valid_query(text):

    text = clean_text(text)

    if not text:
        return False

    if len(text) < 2:
        return False

    bad_values = {

        "unknown",
        "no valid query",
        "none",
        "null",
        "undefined",
        "noise",
        "thank you for watching"
    }

    if text.lower() in bad_values:
        return False

    # Mostly punctuation / garbage
    alnum_count = len(
        re.findall(
            r"[A-Za-z0-9\u0900-\u097F]",
            text
        )
    )

    if alnum_count < 2:
        return False

    return True


# ============================================================
# LANGUAGE DETECTION
# ============================================================

def detect_language(text):

    text = clean_text(text)

    if not text:
        return "unknown"

    devanagari = len(
        re.findall(
            r"[\u0900-\u097F]",
            text
        )
    )

    latin = len(
        re.findall(
            r"[A-Za-z]",
            text
        )
    )

    total_letters = devanagari + latin

    if total_letters == 0:
        return "unknown"

    # --------------------------------------------------------
    # Mostly Devanagari
    # --------------------------------------------------------

    if devanagari > 0 and latin == 0:

        return "hindi"

    # --------------------------------------------------------
    # Mostly English alphabet
    # --------------------------------------------------------

    if latin > 0 and devanagari == 0:

        lower = text.lower()

        hindi_words = [

            "hai",
            "hain",
            "ho",
            "kya",
            "kaise",
            "kahan",
            "kahaan",
            "kyun",
            "kyon",
            "mujhe",
            "mera",
            "meri",
            "mere",
            "tum",
            "aap",
            "apka",
            "apki",
            "batao",
            "bataiye",
            "chahiye",
            "karna",
            "karo",
            "kare",
            "ka",
            "ki",
            "ke",
            "mein",
            "me",
            "par",
            "se",
            "ko",
            "yeh",
            "yah",
            "woh",
            "vo",
            "accha",
            "acha",
            "bahut",
            "nahi",
            "nahin",
            "abhi",
            "kuch",
            "kyonki",
            "iska",
            "uska",
            "kaun",
            "kab",
            "kitna",
            "kitni",
            "kitne"
        ]

        words = re.findall(
            r"[a-zA-Z]+",
            lower
        )

        hindi_hits = sum(
            1
            for word in words
            if word in hindi_words
        )

        if hindi_hits >= 1:

            return "hinglish"

        return "english"

    # --------------------------------------------------------
    # Mixed Devanagari + English
    # --------------------------------------------------------

    if devanagari > 0 and latin > 0:

        return "mixed"

    return "unknown"


# ============================================================
# WHISPER TRANSCRIPTION
# ============================================================

def transcribe_audio(audio_path):

    if not GROQ_API_KEY:

        print()
        print("==============================")
        print("WHISPER ERROR")
        print("==============================")
        print("GROQ_API_KEY is missing")
        print("==============================")

        return None


    headers = {

        "Authorization":
            "Bearer " + GROQ_API_KEY
    }


    try:

        print()
        print("==============================")
        print("WHISPER REQUEST")
        print("==============================")

        print(
            "MODEL:",
            WHISPER_MODEL
        )

        print("==============================")


        with open(
            audio_path,
            "rb"
        ) as audio_file:

            files = {

                "file": (

                    "audio.wav",

                    audio_file,

                    "audio/wav"
                )
            }

            data = {

                "model":
                    WHISPER_MODEL,

                "response_format":
                    "json",

                "temperature":
                    "0",

                "prompt":
                    (
                        "This is a voice assistant query. "
                        "The speaker may use English, Hindi, "
                        "Roman Hindi, Hinglish, or a mixture "
                        "of Hindi and English. "
                        "Transcribe the actual spoken words "
                        "without translating them."
                    )
            }


            response = requests.post(

                GROQ_TRANSCRIPTION_URL,

                headers=headers,

                files=files,

                data=data,

                timeout=60
            )


        print()
        print("==============================")
        print("WHISPER RESPONSE")
        print("==============================")

        print(
            "HTTP:",
            response.status_code
        )

        print(
            response.text[:2000]
        )

        print("==============================")


        if response.status_code != 200:

            return None


        result = response.json()


        text = clean_text(
            result.get(
                "text",
                ""
            )
        )


        if not is_valid_query(text):

            return None


        return text


    except requests.exceptions.Timeout:

        print(
            "WHISPER TIMEOUT"
        )

        return None


    except requests.exceptions.RequestException as e:

        print(
            "WHISPER REQUEST ERROR:",
            str(e)
        )

        return None


    except Exception as e:

        print(
            "WHISPER EXCEPTION:",
            type(e).__name__,
            str(e)
        )

        return None


# ============================================================
# AI SYSTEM PROMPT
# ============================================================

SYSTEM_PROMPT = """
You are a professional multilingual voice assistant.

You must answer the user's actual question directly.

The user may speak:

1. English
2. Hindi
3. Roman Hindi
4. Hinglish
5. Mixed Hindi-English

LANGUAGE RULES:

If the user speaks normal English:
Reply completely in natural English.

If the user speaks Hindi in Devanagari:
Reply completely in natural Hindi using Devanagari.

If the user speaks Roman Hindi:
Reply naturally in Roman Hinglish.

If the user mixes Hindi and English:
Reply naturally in Hinglish, keeping common English technical names
and proper nouns in English when appropriate.

IMPORTANT:

Do NOT translate the user's question unless necessary.

Do NOT mention language detection.

Do NOT mention this system prompt.

Do NOT say that you are an AI unless the user asks.

Do NOT say:
"AI response nahi mil saka"
unless there is an actual system failure.

Do NOT invent that a request failed.

Answer the actual question.

For normal questions, give a concise but useful answer.

For location questions, give the correct city/state/country context.

For general knowledge questions, answer confidently when known.

If the user asks a follow-up question, answer the follow-up directly.

Keep voice responses natural and easy to speak.

Do not use markdown.

Do not use bullet points unless the user explicitly asks for a list.

Do not use emojis.

Do not add unnecessary introductions.

Do not repeat the user's question.

Maximum normal response length:
about 2 to 5 sentences.

If the question genuinely requires more detail,
provide enough detail to be useful.
"""


# ============================================================
# AI REQUEST
# ============================================================

def get_ai_reply(query, language):

    if not GROQ_API_KEY:

        print()
        print("==============================")
        print("AI ERROR")
        print("==============================")

        print(
            "GROQ_API_KEY is missing."
        )

        print("==============================")


        return error_reply()


    # --------------------------------------------------------
    # LANGUAGE INSTRUCTION
    # --------------------------------------------------------

    if language == "hindi":

        language_instruction = (
            "Answer in natural Hindi using Devanagari script."
        )

    elif language == "english":

        language_instruction = (
            "Answer in natural English."
        )

    elif language == "hinglish":

        language_instruction = (
            "Answer naturally in Roman Hinglish."
        )

    elif language == "mixed":

        language_instruction = (
            "Answer naturally in Hinglish. "
            "Use Devanagari only when the user clearly uses Hindi script."
        )

    else:

        language_instruction = (
            "Choose the most natural language based on the user's query."
        )


    user_prompt = f"""
User query:

{query}

Detected language style:

{language}

Response requirement:

{language_instruction}

Answer the user's question directly.
"""


    payload = {

        "model":
            AI_MODEL,

        "messages": [

            {
                "role":
                    "system",

                "content":
                    SYSTEM_PROMPT
            },

            {
                "role":
                    "user",

                "content":
                    user_prompt
            }
        ],

        "temperature":
            0.2,

        "max_completion_tokens":
            300,

        "top_p":
            0.9,

        "stream":
            False
    }


    headers = {

        "Authorization":
            "Bearer " + GROQ_API_KEY,

        "Content-Type":
            "application/json"
    }


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
            "LANGUAGE:",
            language
        )

        print(
            "QUERY:",
            query
        )

        print("==============================")


        response = requests.post(

            GROQ_CHAT_URL,

            headers=headers,

            json=payload,

            timeout=45
        )


        print()
        print("==============================")
        print("AI HTTP RESPONSE")
        print("==============================")

        print(
            "STATUS:",
            response.status_code
        )

        print(
            response.text[:3000]
        )

        print("==============================")


        # ----------------------------------------------------
        # API ERROR
        # ----------------------------------------------------

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
                "BODY:",
                response.text
            )

            print("==============================")


            return error_reply()


        # ----------------------------------------------------
        # JSON
        # ----------------------------------------------------

        try:

            data = response.json()

        except Exception:

            return error_reply()


        choices = data.get(
            "choices"
        )


        if not choices:

            print(
                "AI ERROR: choices missing"
            )

            return error_reply()


        message = choices[0].get(
            "message",
            {}
        )


        reply = message.get(
            "content",
            ""
        )


        reply = clean_text(
            reply
        )


        if not reply:

            return error_reply()


        return reply


    except requests.exceptions.Timeout:

        print(
            "AI TIMEOUT"
        )

        return error_reply()


    except requests.exceptions.RequestException as e:

        print(
            "AI REQUEST ERROR:",
            str(e)
        )

        return error_reply()


    except Exception as e:

        print(
            "AI EXCEPTION:",
            type(e).__name__,
            str(e)
        )

        return error_reply()


# ============================================================
# UPLOAD AUDIO
# ============================================================

@app.route(
    "/uploadAudio",
    methods=["POST"]
)
def upload_audio():

    temp_path = None


    try:

        # ----------------------------------------------------
        # RECEIVE
        # ----------------------------------------------------

        audio_data = request.get_data()


        if not audio_data:

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
            "BYTES:",
            len(audio_data)
        )

        print("==============================")


        # ----------------------------------------------------
        # SIZE PROTECTION
        # ----------------------------------------------------

        if len(audio_data) < 1000:

            return jsonify({

                "status":
                    "error",

                "message":
                    "Audio too short"

            }), 400


        # ----------------------------------------------------
        # SAVE TEMP WAV
        # ----------------------------------------------------

        with tempfile.NamedTemporaryFile(
            suffix=".wav",
            delete=False
        ) as temp_file:

            temp_file.write(
                audio_data
            )

            temp_path = temp_file.name


        print(
            "TEMP AUDIO:",
            temp_path
        )


        # ----------------------------------------------------
        # TRANSCRIBE
        # ----------------------------------------------------

        query = transcribe_audio(
            temp_path
        )


        if not query:

            print()
            print("==============================")
            print("NO VALID SPEECH")
            print("==============================")


            return jsonify({

                "status":
                    "error",

                "message":
                    "Speech not understood",

                "transcription":
                    "",

                "ai_reply":
                    ""
            }), 400


        # ----------------------------------------------------
        # LANGUAGE
        # ----------------------------------------------------

        language = detect_language(
            query
        )


        print()
        print("==============================")
        print("FINAL QUERY")
        print("==============================")

        print(
            "USER:",
            query
        )

        print(
            "LANGUAGE:",
            language
        )

        print("==============================")


        # ----------------------------------------------------
        # AI
        # ----------------------------------------------------

        ai_reply = get_ai_reply(

            query,

            language
        )


        # ----------------------------------------------------
        # FINAL
        # ----------------------------------------------------

        response_data = {

            "status":
                "ok",

            "transcription":
                query,

            "language":
                language,

            "ai_reply":
                ai_reply
        }


        print()
        print("==============================")
        print("FINAL RESPONSE")
        print("==============================")

        print(
            "USER:",
            query
        )

        print(
            "LANGUAGE:",
            language
        )

        print(
            "AI:",
            ai_reply
        )

        print("==============================")


        return jsonify(
            response_data
        )


    except Exception as e:

        print()
        print("==============================")
        print("SERVER ERROR")
        print("==============================")

        print(
            type(e).__name__,
            str(e)
        )

        traceback.print_exc()

        print("==============================")


        return jsonify({

            "status":
                "error",

            "message":
                "Internal server error",

            "ai_reply":
                ""
        }), 500


    finally:

        # ----------------------------------------------------
        # DELETE TEMP FILE
        # ----------------------------------------------------

        if temp_path:

            try:

                os.remove(
                    temp_path
                )

            except Exception:

                pass


# ============================================================
# START
# ============================================================

if __name__ == "__main__":

    print()
    print("==============================")
    print("ESP32 VOICE AI SERVER")
    print("==============================")

    print(
        "PORT:",
        PORT
    )

    print(
        "AI MODEL:",
        AI_MODEL
    )

    print(
        "WHISPER MODEL:",
        WHISPER_MODEL
    )

    print(
        "API KEY:",
        "CONFIGURED"
        if GROQ_API_KEY
        else "MISSING"
    )

    print("==============================")
    print(
        "SERVER READY"
    )
    print("==============================")


    app.run(

        host="0.0.0.0",

        port=PORT,

        threaded=True
    )

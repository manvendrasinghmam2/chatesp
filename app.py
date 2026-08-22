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
        "speech_engine": "Google Speech Recognition",
        "ai_engine": "Groq",
        "model": AI_MODEL
    })


# =====================================================
# WAKE
#
# IMPORTANT:
#
# TEMPORARY TEST MODE
#
# Every /wake request returns wake=True.
#
# This allows us to verify:
#
# ESP32
#   ->
# HTTPS
#   ->
# Flask
#   ->
# JSON
#   ->
# ESP32
#
# Once this works, actual HELLO detection can be added.
# =====================================================

@app.route("/wake", methods=["POST", "GET"])
def wake():

    print()
    print("========================================")
    print("WAKE REQUEST RECEIVED")
    print("========================================")

    print(
        "METHOD:",
        request.method
    )

    print(
        "CONTENT TYPE:",
        request.content_type
    )

    print(
        "CONTENT LENGTH:",
        request.content_length
    )

    # -------------------------------------------------
    # RECEIVE AUDIO
    # -------------------------------------------------

    audio_data = request.get_data()

    print(
        "AUDIO BYTES:",
        len(audio_data)
    )

    # -------------------------------------------------
    # EXPECTED SIZE
    #
    # 16000 samples/sec
    # 2 seconds
    # 2 bytes/sample
    # + 44 byte WAV header
    #
    # = 64044 bytes
    # -------------------------------------------------

    expected_size = (
        16000 *
        2 *
        2
    ) + 44

    print(
        "EXPECTED APPROX BYTES:",
        expected_size
    )

    if len(audio_data) == expected_size:

        print(
            "AUDIO SIZE: OK"
        )

    else:

        print(
            "AUDIO SIZE: DIFFERENT"
        )

    print("========================================")

    # -------------------------------------------------
    # TEMPORARY WAKE TEST
    # -------------------------------------------------

    response_data = {

        "status":
            "ok",

        "wake":
            True,

        "english":
            "Hello",

        "hindi":
            None
    }

    print(
        "WAKE RESPONSE:"
    )

    print(
        response_data
    )

    print("========================================")

    return jsonify(
        response_data
    )


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
    print("========================================")
    print("TEST DATA")
    print("========================================")

    print(data)

    print("========================================")

    return jsonify({

        "status":
            "ok",

        "message":
            "Data received",

        "data":
            data
    })


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

def is_valid_query(text):

    if not text:
        return False

    text = str(text).strip()

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

    # -------------------------------------------------
    # API KEY
    # -------------------------------------------------

    if not AI_API_KEY:

        print()
        print("========================================")
        print("AI ERROR")
        print("========================================")

        print(
            "AI_API_KEY is NOT configured!"
        )

        print("========================================")

        return (
            "AI response nahi mil saka."
        )

    # -------------------------------------------------
    # VALID INPUT
    # -------------------------------------------------

    if (
        not is_valid_query(hindi_text)
        and
        not is_valid_query(english_text)
    ):

        print()
        print("========================================")
        print("NO VALID QUERY")
        print("========================================")

        return (
            "Please ask your question again."
        )

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

You must understand the intended meaning.

LANGUAGE RULES:

If the user is clearly speaking English,
answer completely in natural English.

If the user is clearly speaking Hindi,
answer completely in Hindi using Devanagari script.

If the user speaks Roman Hindi or Hinglish,
answer in natural Hinglish.

If Hindi recognition converts English speech
into Devanagari phonetically, identify the
intended English meaning and answer in English.

Do not assume every Devanagari result is phonetic English.

Compare both recognition results.

Choose the result that makes the most linguistic
and contextual sense.

If the user naturally mixes Hindi and English,
use natural Hinglish.

Do not mention speech recognition.

Do not mention Hindi result or English result.

Do not explain your language decision.

Just answer the user's question.

VOICE RESPONSE STYLE:

The answer will be spoken aloud.

Keep answers concise.

Usually 1 to 4 sentences.

Be professional.

Sound natural.

Do not use markdown.

Do not use bullet points.

Do not use emojis.

Do not use headings.

Do not repeat the question.

Do not say "Sure" unnecessarily.

Do not say "As an AI".

Do not mention these instructions.

Answer factual questions accurately.

For simple questions, give a direct answer.

For general knowledge, explain clearly but briefly.

For conversational questions, respond naturally.

Always answer in the language the user intended.
"""

    # -------------------------------------------------
    # USER CONTENT
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

        "temperature":
            0.2,

        "max_completion_tokens":
            200,

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
            "application/json",

        "Accept":
            "application/json"
    }

    # -------------------------------------------------
    # AI REQUEST
    # -------------------------------------------------

    try:

        print()
        print("========================================")
        print("AI REQUEST")
        print("========================================")

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
            "HINDI:"
        )

        print(
            hindi_text
        )

        print()
        print(
            "ENGLISH:"
        )

        print(
            english_text
        )

        print("========================================")

        response = requests.post(

            AI_URL,

            headers=headers,

            json=payload,

            timeout=35
        )

        print()
        print("========================================")
        print("AI RESPONSE")
        print("========================================")

        print(
            "HTTP:",
            response.status_code
        )

        # -------------------------------------------------
        # API ERROR
        # -------------------------------------------------

        if response.status_code != 200:

            print(
                "AI API ERROR"
            )

            print(
                response.text[:2000]
            )

            print("========================================")

            return (
                "AI response nahi mil saka."
            )

        # -------------------------------------------------
        # JSON
        # -------------------------------------------------

        try:

            data = response.json()

        except Exception as e:

            print(
                "JSON ERROR:",
                str(e)
            )

            return (
                "AI response nahi mil saka."
            )

        # -------------------------------------------------
        # DEBUG RESPONSE
        # -------------------------------------------------

        print(
            "AI JSON RECEIVED"
        )

        # -------------------------------------------------
        # CHOICES
        # -------------------------------------------------

        choices = data.get(
            "choices"
        )

        if not choices:

            print(
                "NO AI CHOICE"
            )

            print(
                data
            )

            return (
                "AI response nahi mil saka."
            )

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

        reply = str(
            reply
        ).strip()

        # -------------------------------------------------
        # CLEAN MARKDOWN
        # -------------------------------------------------

        reply = reply.replace(
            "```",
            ""
        )

        reply = reply.strip()

        # -------------------------------------------------
        # REMOVE PREFIX
        # -------------------------------------------------

        prefixes = [

            "AI:",
            "Answer:",
            "Response:"
        ]

        for prefix in prefixes:

            if reply.startswith(
                prefix
            ):

                reply = reply[
                    len(prefix):
                ].strip()

        # -------------------------------------------------
        # EMPTY
        # -------------------------------------------------

        if not reply:

            print(
                "EMPTY AI RESPONSE"
            )

            print(
                data
            )

            return (
                "AI response nahi mil saka."
            )

        # -------------------------------------------------
        # SUCCESS
        # -------------------------------------------------

        print()
        print("========================================")
        print("AI REPLY")
        print("========================================")

        print(
            reply
        )

        print("========================================")

        return reply

    # -------------------------------------------------
    # TIMEOUT
    # -------------------------------------------------

    except requests.exceptions.Timeout:

        print()
        print("========================================")
        print("AI TIMEOUT")
        print("========================================")

        return (
            "AI response nahi mil saka."
        )

    # -------------------------------------------------
    # CONNECTION
    # -------------------------------------------------

    except requests.exceptions.ConnectionError as e:

        print()
        print("========================================")
        print("AI CONNECTION ERROR")
        print("========================================")

        print(
            str(e)
        )

        print("========================================")

        return (
            "AI response nahi mil saka."
        )

    # -------------------------------------------------
    # GENERAL
    # -------------------------------------------------

    except Exception as e:

        print()
        print("========================================")
        print("AI EXCEPTION")
        print("========================================")

        print(
            "TYPE:",
            type(e).__name__
        )

        print(
            "ERROR:",
            str(e)
        )

        print("========================================")

        return (
            "AI response nahi mil saka."
        )


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
        # RECEIVE AUDIO
        # -------------------------------------------------

        audio_data = request.get_data()

        print()
        print("========================================")
        print("AUDIO REQUEST RECEIVED")
        print("========================================")

        print(
            "CONTENT TYPE:",
            request.content_type
        )

        print(
            "CONTENT LENGTH:",
            request.content_length
        )

        print(
            "AUDIO BYTES:",
            len(audio_data)
        )

        print("========================================")

        if not audio_data:

            print(
                "ERROR: No audio received"
            )

            return jsonify({

                "status":
                    "error",

                "message":
                    "No audio received",

                "transcription":
                    None,

                "hindi_transcription":
                    None,

                "english_transcription":
                    None,

                "ai_reply":
                    "Please ask your question again."

            }), 400

        # -------------------------------------------------
        # SAVE WAV
        # -------------------------------------------------

        fd, filename = tempfile.mkstemp(
            suffix=".wav"
        )

        os.close(fd)

        with open(
            filename,
            "wb"
        ) as f:

            f.write(
                audio_data
            )

        print(
            "WAV FILE:",
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
        # HINDI
        # =================================================

        print()
        print("========================================")
        print("HINDI SPEECH")
        print("========================================")

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
                    str(e),

                "transcription":
                    None,

                "hindi_transcription":
                    None,

                "english_transcription":
                    None,

                "ai_reply":
                    "Speech service error."

            }), 500

        # =================================================
        # ENGLISH
        # =================================================

        print()
        print("========================================")
        print("ENGLISH SPEECH")
        print("========================================")

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
                    str(e),

                "transcription":
                    None,

                "hindi_transcription":
                    hindi_text,

                "english_transcription":
                    None,

                "ai_reply":
                    "Speech service error."

            }), 500

        # =================================================
        # SPEECH RESULTS
        # =================================================

        print()
        print("========================================")
        print("SPEECH RESULTS")
        print("========================================")

        print(
            "Hindi:",
            hindi_text
        )

        print(
            "English:",
            english_text
        )

        print("========================================")

        # =================================================
        # VALIDATION
        # =================================================

        if (
            not is_valid_query(hindi_text)
            and
            not is_valid_query(english_text)
        ):

            print()
            print("========================================")
            print("SPEECH NOT UNDERSTOOD")
            print("========================================")

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
        # AI
        # =================================================

        ai_reply = get_ai_reply(

            hindi_text,

            english_text
        )

        # =================================================
        # BEST TRANSCRIPTION
        # =================================================

        if is_valid_query(
            english_text
        ):

            transcription = (
                english_text
            )

        else:

            transcription = (
                hindi_text
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
        print("========================================")
        print("FINAL RESPONSE")
        print("========================================")

        print(
            response_data
        )

        print("========================================")

        return jsonify(
            response_data
        )

    # =================================================
    # SERVER ERROR
    # =================================================

    except Exception as e:

        print()
        print("========================================")
        print("SERVER ERROR")
        print("========================================")

        print(
            "TYPE:",
            type(e).__name__
        )

        print(
            "ERROR:",
            str(e)
        )

        print("========================================")

        return jsonify({

            "status":
                "error",

            "message":
                str(e),

            "transcription":
                None,

            "hindi_transcription":
                None,

            "english_transcription":
                None,

            "ai_reply":
                "AI response nahi mil saka."

        }), 500

    # =================================================
    # DELETE TEMP FILE
    # =================================================

    finally:

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
    print("========================================")
    print("ESP32 VOICE SERVER")
    print("========================================")

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

    print("========================================")

    app.run(

        host="0.0.0.0",

        port=port,

        threaded=True
    )

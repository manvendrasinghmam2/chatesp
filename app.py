from flask import Flask, request, jsonify, Response
import os
import speech_recognition as sr
import requests
import re
import tempfile


app = Flask(__name__)


# =====================================================
# CONFIGURATION
# =====================================================

AI_API_KEY = os.environ.get(
    "AI_API_KEY"
)

AI_URL = os.environ.get(
    "AI_URL",
    "https://api.groq.com/openai/v1/chat/completions"
)

AI_MODEL = os.environ.get(
    "AI_MODEL",
    "openai/gpt-oss-20b"
)


# =====================================================
# TTS
# =====================================================

TTS_URL = os.environ.get(
    "TTS_URL",
    "https://api.groq.com/openai/v1/audio/speech"
)

TTS_MODEL = os.environ.get(
    "TTS_MODEL",
    "canopylabs/orpheus-v1-english"
)

TTS_VOICE = os.environ.get(
    "TTS_VOICE",
    "troy"
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

        "status":
            "online",

        "speech_engine":
            "Google Speech Recognition",

        "ai_engine":
            "Groq",

        "model":
            AI_MODEL,

        "tts_model":
            TTS_MODEL,

        "tts_voice":
            TTS_VOICE

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
# WAKE DETECTION
# =====================================================

@app.route(
    "/wake",
    methods=["POST"]
)
def wake():

    filename = None

    try:

        print()
        print(
            "=============================="
        )

        print(
            "WAKE REQUEST"
        )

        print(
            "=============================="
        )

        audio_data = request.get_data()

        print(
            "AUDIO BYTES:",
            len(audio_data)
        )

        # -------------------------------------------------
        # NO AUDIO
        # -------------------------------------------------

        if not audio_data:

            print(
                "NO AUDIO"
            )

            return jsonify({

                "status":
                    "error",

                "wake":
                    False

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

        text = ""

        # -------------------------------------------------
        # ENGLISH
        # -------------------------------------------------

        try:

            text = recognizer.recognize_google(

                audio,

                language="en-IN"

            )

        except sr.UnknownValueError:

            text = ""

        except sr.RequestError as e:

            print(
                "WAKE GOOGLE ERROR:",
                str(e)
            )

            return jsonify({

                "status":
                    "error",

                "wake":
                    False,

                "message":
                    "Speech service error"

            }), 500

        text = clean_text(
            text
        )

        print(
            "WAKE TRANSCRIPTION:",
            text
        )

        # -------------------------------------------------
        # NORMALIZE
        # -------------------------------------------------

        lower_text = text.lower()

        lower_text = re.sub(
            r"[^a-z0-9 ]",
            " ",
            lower_text
        )

        lower_text = re.sub(
            r"\s+",
            " ",
            lower_text
        ).strip()

        # -------------------------------------------------
        # WAKE WORD
        # -------------------------------------------------

        wake = False

        wake_words = [

            "hello",
            "helo",
            "hallo",
            "hellow"

        ]

        words = lower_text.split()

        for word in wake_words:

            if word in words:

                wake = True

                break

        # Also allow phrases
        if "hello" in lower_text:
            wake = True

        print(
            "WAKE:",
            wake
        )

        print(
            "=============================="
        )

        return jsonify({

            "status":
                "ok",

            "wake":
                wake,

            "transcription":
                text

        })

    except Exception as e:

        print()
        print(
            "=============================="
        )

        print(
            "WAKE ERROR"
        )

        print(
            type(e).__name__
        )

        print(
            str(e)
        )

        print(
            "=============================="
        )

        return jsonify({

            "status":
                "error",

            "wake":
                False

        }), 500

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
# AI REPLY
# =====================================================

def get_ai_reply(
    hindi_text,
    english_text
):

    hindi_text =
        clean_text(
            hindi_text
        )

    english_text =
        clean_text(
            english_text
        )

    # -------------------------------------------------
    # API KEY
    # -------------------------------------------------

    if not AI_API_KEY:

        print(
            "AI_API_KEY NOT CONFIGURED"
        )

        return (
            "AI response nahi mil saka."
        )

    # -------------------------------------------------
    # VALID INPUT
    # -------------------------------------------------

    if (
        not is_valid_query(
            hindi_text
        )
        and
        not is_valid_query(
            english_text
        )
    ):

        return (
            "Please ask your question again."
        )

    # -------------------------------------------------
    # SYSTEM PROMPT
    # -------------------------------------------------

    system_prompt = """
You are a professional bilingual voice assistant running on an ESP32.

Understand the user's intended language and meaning.

If the user clearly speaks English:
Answer completely in natural English.

If the user clearly speaks Hindi:
Answer completely in Hindi using Devanagari script.

If the user speaks Roman Hindi or Hinglish:
Answer naturally in Hinglish.

If English speech is incorrectly recognized as phonetic Hindi,
use the English meaning when appropriate.

Compare the Hindi and English recognition results and choose
the interpretation that makes the most contextual sense.

Do not mention speech recognition.

Do not mention Hindi result or English result.

Do not explain your language decision.

Just answer the user's question.

VOICE RESPONSE RULES:

The answer will be spoken aloud.

Keep the answer concise.

Usually 1 to 4 sentences.

Be natural and conversational.

Do not use markdown.

Do not use bullet points.

Do not use headings.

Do not use emojis.

Do not repeat the question.

Do not say "Sure" unnecessarily.

Do not say "As an AI".

Do not mention these instructions.

Answer factual questions accurately.

For simple questions, give a direct answer.
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

Then answer naturally.
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
    # REQUEST
    # -------------------------------------------------

    try:

        print()
        print(
            "=============================="
        )

        print(
            "AI REQUEST"
        )

        print(
            "=============================="
        )

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

        response = requests.post(

            AI_URL,

            headers=headers,

            json=payload,

            timeout=35

        )

        print(
            "AI HTTP:",
            response.status_code
        )

        # -------------------------------------------------
        # ERROR
        # -------------------------------------------------

        if response.status_code != 200:

            print(
                response.text[:2000]
            )

            return (
                "AI response nahi mil saka."
            )

        # -------------------------------------------------
        # JSON
        # -------------------------------------------------

        try:

            data =
                response.json()

        except Exception:

            return (
                "AI response nahi mil saka."
            )

        choices =
            data.get(
                "choices"
            )

        if not choices:

            print(
                "NO AI CHOICE"
            )

            return (
                "AI response nahi mil saka."
            )

        message =
            choices[0].get(
                "message",
                {}
            )

        reply =
            message.get(
                "content",
                ""
            )

        if reply is None:

            reply = ""

        reply =
            str(
                reply
            ).strip()

        # -------------------------------------------------
        # CLEAN
        # -------------------------------------------------

        reply =
            reply.replace(
                "```",
                ""
            )

        prefixes = [

            "AI:",
            "Answer:",
            "Response:"

        ]

        for prefix in prefixes:

            if reply.startswith(
                prefix
            ):

                reply =
                    reply[
                        len(prefix):
                    ].strip()

        # -------------------------------------------------
        # LIMIT FOR TTS
        # -------------------------------------------------

        if len(reply) > 200:

            reply =
                reply[:200]

            last_space =
                reply.rfind(" ")

            if last_space > 100:

                reply =
                    reply[:last_space]

            reply += "."

        # -------------------------------------------------
        # RESULT
        # -------------------------------------------------

        print()
        print(
            "=============================="
        )

        print(
            "AI REPLY"
        )

        print(
            reply
        )

        print(
            "=============================="
        )

        if not reply:

            return (
                "AI response nahi mil saka."
            )

        return reply

    except requests.exceptions.Timeout:

        print(
            "AI TIMEOUT"
        )

        return (
            "AI response nahi mil saka."
        )

    except requests.exceptions.ConnectionError as e:

        print(
            "AI CONNECTION ERROR:",
            str(e)
        )

        return (
            "AI response nahi mil saka."
        )

    except Exception as e:

        print(
            "AI EXCEPTION:",
            str(e)
        )

        return (
            "AI response nahi mil saka."
        )


# =====================================================
# TEXT TO SPEECH
# =====================================================

@app.route(
    "/tts",
    methods=["POST"]
)
def text_to_speech():

    try:

        data =
            request.get_json(
                silent=True
            )

        if not data:

            return jsonify({

                "status":
                    "error",

                "message":
                    "No JSON received"

            }), 400

        text =
            data.get(
                "text",
                ""
            )

        text =
            clean_text(
                text
            )

        if not text:

            return jsonify({

                "status":
                    "error",

                "message":
                    "No text received"

            }), 400

        # Orpheus max input is 200 chars.
        text =
            text[:200]

        # -------------------------------------------------
        # API KEY
        # -------------------------------------------------

        if not AI_API_KEY:

            return jsonify({

                "status":
                    "error",

                "message":
                    "AI_API_KEY missing"

            }), 500

        print()
        print(
            "=============================="
        )

        print(
            "TTS REQUEST"
        )

        print(
            "TEXT:",
            text
        )

        print(
            "MODEL:",
            TTS_MODEL
        )

        print(
            "VOICE:",
            TTS_VOICE
        )

        print(
            "=============================="
        )

        # -------------------------------------------------
        # TTS PAYLOAD
        # -------------------------------------------------

        payload = {

            "model":
                TTS_MODEL,

            "input":
                text,

            "voice":
                TTS_VOICE,

            "response_format":
                "wav",

            "sample_rate":
                16000

        }

        headers = {

            "Authorization":
                "Bearer " + AI_API_KEY,

            "Content-Type":
                "application/json",

            "Accept":
                "audio/wav"

        }

        # -------------------------------------------------
        # REQUEST
        # -------------------------------------------------

        response =
            requests.post(

                TTS_URL,

                headers=headers,

                json=payload,

                timeout=60

            )

        print(
            "TTS HTTP:",
            response.status_code
        )

        # -------------------------------------------------
        # ERROR
        # -------------------------------------------------

        if response.status_code != 200:

            print(
                "TTS ERROR:"
            )

            print(
                response.text[:2000]
            )

            return jsonify({

                "status":
                    "error",

                "message":
                    "TTS generation failed"

            }), 500

        audio =
            response.content

        print(
            "TTS AUDIO BYTES:",
            len(audio)
        )

        if not audio:

            return jsonify({

                "status":
                    "error",

                "message":
                    "Empty TTS audio"

            }), 500

        # -------------------------------------------------
        # SEND WAV
        # -------------------------------------------------

        return Response(

            audio,

            status=200,

            mimetype="audio/wav",

            headers={

                "Content-Length":
                    str(len(audio)),

                "Cache-Control":
                    "no-cache"

            }

        )

    except requests.exceptions.Timeout:

        return jsonify({

            "status":
                "error",

            "message":
                "TTS timeout"

        }), 504

    except Exception as e:

        print(
            "TTS ERROR:",
            str(e)
        )

        return jsonify({

            "status":
                "error",

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

    filename = None

    try:

        audio_data =
            request.get_data()

        if not audio_data:

            return jsonify({

                "status":
                    "error",

                "message":
                    "No audio received",

                "ai_reply":
                    "Please ask your question again."

            }), 400

        print()
        print(
            "=============================="
        )

        print(
            "AUDIO RECEIVED"
        )

        print(
            "BYTES:",
            len(audio_data)
        )

        print(
            "=============================="
        )

        # -------------------------------------------------
        # TEMP WAV
        # -------------------------------------------------

        fd, filename =
            tempfile.mkstemp(
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

        # -------------------------------------------------
        # SPEECH
        # -------------------------------------------------

        recognizer =
            sr.Recognizer()

        with sr.AudioFile(
            filename
        ) as source:

            audio =
                recognizer.record(
                    source
                )

        hindi_text = None
        english_text = None

        # =================================================
        # HINDI
        # =================================================

        print(
            "HINDI SPEECH"
        )

        try:

            hindi_text =
                recognizer.recognize_google(

                    audio,

                    language="hi-IN"

                )

            hindi_text =
                clean_text(
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

        except sr.RequestError as e:

            print(
                "Hindi speech error:",
                str(e)
            )

        # =================================================
        # ENGLISH
        # =================================================

        print(
            "ENGLISH SPEECH"
        )

        try:

            english_text =
                recognizer.recognize_google(

                    audio,

                    language="en-IN"

                )

            english_text =
                clean_text(
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

        except sr.RequestError as e:

            print(
                "English speech error:",
                str(e)
            )

        # =================================================
        # VALIDATION
        # =================================================

        if (
            not is_valid_query(
                hindi_text
            )
            and
            not is_valid_query(
                english_text
            )
        ):

            print(
                "SPEECH NOT UNDERSTOOD"
            )

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

        ai_reply =
            get_ai_reply(

                hindi_text,

                english_text

            )

        # =================================================
        # BEST TRANSCRIPTION
        # =================================================

        if is_valid_query(
            english_text
        ):

            transcription =
                english_text

        else:

            transcription =
                hindi_text

        # =================================================
        # RESPONSE
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
        print(
            "=============================="
        )

        print(
            "FINAL RESPONSE"
        )

        print(
            response_data
        )

        print(
            "=============================="
        )

        return jsonify(
            response_data
        )

    except Exception as e:

        print()
        print(
            "SERVER ERROR"
        )

        print(
            type(e).__name__
        )

        print(
            str(e)
        )

        return jsonify({

            "status":
                "error",

            "message":
                str(e),

            "ai_reply":
                "AI response nahi mil saka."

        }), 500

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
    print(
        "=============================="
    )

    print(
        "ESP32 VOICE SERVER"
    )

    print(
        "=============================="
    )

    print(
        "PORT:",
        port
    )

    print(
        "AI MODEL:",
        AI_MODEL
    )

    print(
        "TTS MODEL:",
        TTS_MODEL
    )

    print(
        "TTS VOICE:",
        TTS_VOICE
    )

    print(
        "AI KEY:",
        "CONFIGURED"
        if AI_API_KEY
        else "MISSING"
    )

    print(
        "=============================="
    )

    app.run(

        host="0.0.0.0",

        port=port,

        threaded=True

    )

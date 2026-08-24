from flask import Flask, request, jsonify, Response
import os
import re
import tempfile
import requests
import speech_recognition as sr

from concurrent.futures import ThreadPoolExecutor


# ============================================================
# APP
# ============================================================

app = Flask(__name__)

app.config["MAX_CONTENT_LENGTH"] = 1024 * 1024


# ============================================================
# CONFIG
# ============================================================

AI_API_KEY = os.environ.get("AI_API_KEY", "").strip()

AI_URL = os.environ.get(
    "AI_URL",
    "https://api.groq.com/openai/v1/chat/completions"
)

AI_MODEL = os.environ.get(
    "AI_MODEL",
    "openai/gpt-oss-20b"
)


# ============================================================
# TTS
# ============================================================

TTS_URL = os.environ.get(
    "TTS_URL",
    "https://api.groq.com/openai/v1/audio/speech"
)

TTS_MODEL = os.environ.get(
    "TTS_MODEL",
    "canopylabs/orpheus-v1-english"
)

# Female:
# autumn
# diana
# hannah

TTS_VOICE = os.environ.get(
    "TTS_VOICE",
    "hannah"
)

TTS_MAX_CHARS = 200


# ============================================================
# HTTP SESSION
# ============================================================

session = requests.Session()

session.headers.update({
    "User-Agent": "ESP32-Voice-Server/2.0"
})


# ============================================================
# HELPERS
# ============================================================

def clean_text(text):

    if text is None:
        return ""

    text = str(text).strip()

    text = re.sub(
        r"\s+",
        " ",
        text
    )

    return text


def is_valid_query(text):

    text = clean_text(text)

    if len(text) < 2:
        return False

    invalid = {
        "",
        "unknown",
        "none",
        "null",
        "no response",
        "no valid query",
        "speech not understood",
        "could not understand audio"
    }

    return text.lower() not in invalid


def safe_json_response(data, status=200):

    return jsonify(data), status


# ============================================================
# HEALTH
# ============================================================

@app.route("/", methods=["GET"])
def home():

    return "ESP32 Voice Server is ONLINE!"


@app.route("/health", methods=["GET"])
def health():

    return jsonify({
        "status": "online",
        "service": "ESP32 Voice AI",
        "ai": AI_MODEL,
        "tts_model": TTS_MODEL,
        "tts_voice": TTS_VOICE,
        "voice_gender": "female",
        "tts": "Groq Orpheus",
        "stt": "Google Speech Recognition",
        "version": "2.0"
    })


# ============================================================
# WAKE
# ============================================================

@app.route(
    "/wake",
    methods=["POST"]
)
def wake():

    try:

        audio = request.get_data()

        print(
            "WAKE:",
            len(audio),
            "bytes"
        )

        # IMPORTANT:
        # For maximum reliability, wake is currently
        # server-confirmed.
        #
        # Later you can replace this with real wake-word
        # detection.

        return jsonify({
            "status": "ok",
            "wake": True,
            "english": "Hello",
            "hindi": None
        })

    except Exception as e:

        print(
            "WAKE ERROR:",
            repr(e)
        )

        return jsonify({
            "status": "error",
            "wake": False
        }), 500


# ============================================================
# TEST
# ============================================================

@app.route(
    "/test",
    methods=["POST"]
)
def test():

    data = request.get_json(
        silent=True
    )

    if data is None:

        return jsonify({
            "status": "error",
            "message": "Invalid JSON"
        }), 400

    return jsonify({
        "status": "ok",
        "message": "Server working",
        "data": data
    })


# ============================================================
# GOOGLE STT - ONE LANGUAGE
# ============================================================

def recognize_language(
    recognizer,
    audio,
    language
):

    try:

        text = recognizer.recognize_google(
            audio,
            language=language
        )

        text = clean_text(text)

        if is_valid_query(text):

            return text

        return None

    except sr.UnknownValueError:

        return None

    except sr.RequestError as e:

        print(
            "STT REQUEST ERROR:",
            language,
            str(e)
        )

        return None

    except Exception as e:

        print(
            "STT ERROR:",
            language,
            repr(e)
        )

        return None


# ============================================================
# AI
# ============================================================

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

    if (
        not is_valid_query(hindi_text)
        and
        not is_valid_query(english_text)
    ):

        return (
            "Please ask your question again."
        )


    system_prompt = """
You are a fast professional bilingual voice assistant.

You are running on an ESP32 speaker.

The user may speak:
- English
- Hindi
- Hinglish
- Roman Hindi

Use the speech recognition results to understand the
actual intended meaning.

RULES:

If English is intended, answer in natural English.

If Hindi is intended, answer in natural Hindi.

If Hinglish/Roman Hindi is intended, answer naturally
in Hinglish.

Do not mention transcription.

Do not explain language selection.

Do not repeat the question.

VOICE RESPONSE:

Keep the answer short and natural.

Normally one sentence.

Maximum about 120 characters when possible.

No markdown.

No bullet points.

No headings.

No emojis.

No "As an AI".

Answer directly.
"""


    user_prompt = f"""
Hindi recognition:
{hindi_text if hindi_text else "No result"}

English recognition:
{english_text if english_text else "No result"}

Give the best natural voice response.
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
                "content": user_prompt
            }
        ],

        "temperature": 0.15,

        "max_completion_tokens": 120,

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


    for attempt in range(2):

        try:

            print(
                "AI REQUEST",
                attempt + 1
            )

            response = session.post(
                AI_URL,
                headers=headers,
                json=payload,
                timeout=(8, 25)
            )

            print(
                "AI HTTP:",
                response.status_code
            )


            if response.status_code != 200:

                print(
                    "AI ERROR:",
                    response.text[:1000]
                )

                continue


            data = response.json()

            choices = data.get(
                "choices",
                []
            )

            if not choices:

                continue


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


            reply = re.sub(
                r"^```.*?```$",
                "",
                reply,
                flags=re.DOTALL
            ).strip()


            for prefix in (
                "AI:",
                "Answer:",
                "Response:"
            ):

                if reply.lower().startswith(
                    prefix.lower()
                ):

                    reply = reply[
                        len(prefix):
                    ].strip()


            if reply:

                print(
                    "AI REPLY:",
                    reply
                )

                return reply


        except requests.exceptions.Timeout:

            print(
                "AI TIMEOUT"
            )

        except requests.exceptions.RequestException as e:

            print(
                "AI REQUEST ERROR:",
                repr(e)
            )

        except Exception as e:

            print(
                "AI EXCEPTION:",
                repr(e)
            )


    return (
        "Sorry, I could not answer that."
    )


# ============================================================
# TTS
# ============================================================

def generate_tts(text):

    text = clean_text(text)

    if not text:
        return None


    if not AI_API_KEY:

        print(
            "TTS: AI_API_KEY missing"
        )

        return None


    # Groq Orpheus max input = 200 chars
    if len(text) > TTS_MAX_CHARS:

        text = text[:TTS_MAX_CHARS]

        last_space = text.rfind(" ")

        if last_space > 80:

            text = text[
                :last_space
            ]


    payload = {
        "model": TTS_MODEL,

        "voice": TTS_VOICE,

        "input": text,

        "response_format": "wav"
    }


    headers = {
        "Authorization":
            "Bearer " + AI_API_KEY,

        "Content-Type":
            "application/json",

        "Accept":
            "audio/wav"
    }


    for attempt in range(2):

        try:

            print()
            print(
                "TTS REQUEST:",
                attempt + 1
            )

            print(
                "TTS TEXT:",
                text
            )

            print(
                "TTS VOICE:",
                TTS_VOICE
            )


            response = session.post(
                TTS_URL,
                headers=headers,
                json=payload,
                timeout=(8, 30)
            )


            print(
                "TTS HTTP:",
                response.status_code
            )


            if response.status_code != 200:

                print(
                    "TTS ERROR:",
                    response.text[:1000]
                )

                continue


            audio = response.content


            if len(audio) < 44:

                print(
                    "TTS AUDIO TOO SMALL:",
                    len(audio)
                )

                continue


            # Validate WAV
            if (
                audio[0:4] != b"RIFF"
                or
                audio[8:12] != b"WAVE"
            ):

                print(
                    "TTS INVALID WAV HEADER"
                )

                print(
                    audio[:32]
                )

                continue


            print(
                "TTS AUDIO BYTES:",
                len(audio)
            )

            return audio


        except requests.exceptions.Timeout:

            print(
                "TTS TIMEOUT"
            )

        except requests.exceptions.RequestException as e:

            print(
                "TTS REQUEST ERROR:",
                repr(e)
            )

        except Exception as e:

            print(
                "TTS EXCEPTION:",
                repr(e)
            )


    return None


# ============================================================
# TTS ENDPOINT
# ============================================================

@app.route(
    "/tts",
    methods=["POST"]
)
def tts():

    try:

        data = request.get_json(
            silent=True
        )


        if not data:

            return jsonify({
                "status": "error",
                "message": "No JSON"
            }), 400


        text = clean_text(
            data.get("text")
        )


        if not text:

            return jsonify({
                "status": "error",
                "message": "No text"
            }), 400


        audio = generate_tts(
            text
        )


        if audio is None:

            return jsonify({
                "status": "error",
                "message": "TTS failed"
            }), 502


        response = Response(
            audio,
            status=200,
            mimetype="audio/wav"
        )


        response.headers["Content-Type"] = (
            "audio/wav"
        )

        response.headers["Content-Length"] = str(
            len(audio)
        )

        response.headers["Cache-Control"] = (
            "no-cache, no-store, must-revalidate"
        )

        response.headers["Connection"] = (
            "close"
        )


        return response


    except Exception as e:

        print(
            "TTS ENDPOINT ERROR:",
            repr(e)
        )

        return jsonify({
            "status": "error",
            "message": "TTS server error"
        }), 500


# ============================================================
# UPLOAD AUDIO
# ============================================================

@app.route(
    "/uploadAudio",
    methods=["POST"]
)
def upload_audio():

    filename = None

    try:

        audio_data = request.get_data()


        print()
        print(
            "========================================"
        )
        print(
            "AUDIO REQUEST"
        )
        print(
            "========================================"
        )

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


        if not audio_data:

            return jsonify({
                "status": "error",
                "message": "No audio received",
                "transcription": None,
                "hindi_transcription": None,
                "english_transcription": None,
                "ai_reply":
                    "Please ask your question again."
            }), 400


        # ====================================================
        # SAVE WAV
        # ====================================================

        fd, filename = tempfile.mkstemp(
            suffix=".wav"
        )

        os.close(fd)


        with open(
            filename,
            "wb"
        ) as file:

            file.write(
                audio_data
            )


        # ====================================================
        # READ AUDIO
        # ====================================================

        recognizer = sr.Recognizer()


        with sr.AudioFile(
            filename
        ) as source:

            # Slight ambient-noise calibration.
            # Kept short for speed.
            recognizer.adjust_for_ambient_noise(
                source,
                duration=0.15
            )

            audio = recognizer.record(
                source
            )


        # ====================================================
        # PARALLEL STT
        # ====================================================

        print(
            "STARTING PARALLEL STT..."
        )


        with ThreadPoolExecutor(
            max_workers=2
        ) as executor:

            hindi_future = executor.submit(
                recognize_language,
                recognizer,
                audio,
                "hi-IN"
            )

            english_future = executor.submit(
                recognize_language,
                recognizer,
                audio,
                "en-IN"
            )


            hindi_text = hindi_future.result()

            english_text = english_future.result()


        print(
            "HINDI:",
            hindi_text
        )

        print(
            "ENGLISH:",
            english_text
        )


        # ====================================================
        # VALIDATION
        # ====================================================

        if (
            not is_valid_query(hindi_text)
            and
            not is_valid_query(english_text)
        ):

            return jsonify({
                "status": "error",
                "message": "Speech not understood",
                "transcription": None,
                "hindi_transcription": None,
                "english_transcription": None,
                "ai_reply":
                    "Please ask your question again."
            }), 400


        # ====================================================
        # AI
        # ====================================================

        ai_reply = get_ai_reply(
            hindi_text,
            english_text
        )


        # ====================================================
        # BEST TRANSCRIPTION
        # ====================================================

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


        # ====================================================
        # FINAL JSON
        # ====================================================

        result = {
            "status": "ok",

            "transcription":
                transcription,

            "hindi_transcription":
                hindi_text,

            "english_transcription":
                english_text,

            "ai_reply":
                ai_reply,

            "tts_voice":
                TTS_VOICE
        }


        print(
            "FINAL:",
            result
        )


        return jsonify(
            result
        )


    except Exception as e:

        print()
        print(
            "UPLOAD AUDIO ERROR:"
        )

        print(
            type(e).__name__,
            repr(e)
        )


        return jsonify({
            "status": "error",
            "message": "Server processing error",
            "transcription": None,
            "hindi_transcription": None,
            "english_transcription": None,
            "ai_reply":
                "Please ask your question again."
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


# ============================================================
# ERROR HANDLERS
# ============================================================

@app.errorhandler(413)
def too_large(error):

    return jsonify({
        "status": "error",
        "message": "Audio file too large"
    }), 413


@app.errorhandler(500)
def internal_error(error):

    print(
        "GLOBAL 500:",
        repr(error)
    )

    return jsonify({
        "status": "error",
        "message": "Internal server error"
    }), 500


# ============================================================
# START
# ============================================================

if __name__ == "__main__":

    port = int(
        os.environ.get(
            "PORT",
            10000
        )
    )

    print()
    print(
        "========================================"
    )
    print(
        "ESP32 ADVANCED FEMALE VOICE SERVER"
    )
    print(
        "========================================"
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
        "VOICE: FEMALE"
    )

    print(
        "AI KEY:",
        "CONFIGURED"
        if AI_API_KEY
        else "MISSING"
    )

    print(
        "========================================"
    )


    app.run(
        host="0.0.0.0",
        port=port,
        threaded=True
    )

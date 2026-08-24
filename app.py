from flask import Flask, request, jsonify, Response
from groq import Groq
from gtts import gTTS

import os
import io
import wave
import tempfile
import re
import urllib.parse


app = Flask(__name__)


# ============================================================
# CONFIG
# ============================================================

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

STT_MODEL = "whisper-large-v3-turbo"
AI_MODEL = "openai/gpt-oss-20b"

if GROQ_API_KEY:
    client = Groq(api_key=GROQ_API_KEY)
    print("Groq client initialized")
else:
    client = None
    print("WARNING: GROQ_API_KEY NOT SET")


# ============================================================
# HOME
# ============================================================

@app.route("/")
def home():
    return "ESP32 AI SERVER OK", 200


# ============================================================
# HEALTH
# ============================================================

@app.route("/health")
def health():

    return jsonify({
        "status": "online",
        "groq": client is not None,
        "upload": "enabled",
        "wake": "enabled",
        "tts": "enabled",
        "stt": STT_MODEL,
        "ai": AI_MODEL
    }), 200


# ============================================================
# WAV VALIDATION
# ============================================================

def check_wav(data):

    try:

        bio = io.BytesIO(data)

        with wave.open(bio, "rb") as wav:

            channels = wav.getnchannels()
            sample_width = wav.getsampwidth()
            sample_rate = wav.getframerate()
            frames = wav.getnframes()

            duration = (
                frames / float(sample_rate)
                if sample_rate > 0
                else 0
            )

            print("--------------------------------")
            print("WAV INFO")
            print("--------------------------------")
            print("Duration:", duration)
            print("Frames:", frames)
            print("Sample Rate:", sample_rate)
            print("Sample Width:", sample_width)
            print("Channels:", channels)
            print("--------------------------------")

            return {
                "duration": duration,
                "frames": frames,
                "sample_rate": sample_rate,
                "sample_width": sample_width,
                "channels": channels
            }

    except Exception as e:

        print("WAV VALIDATION ERROR:", repr(e))
        return None


# ============================================================
# NORMALIZE TEXT
# ============================================================

def normalize_text(text):

    text = text.lower().strip()

    text = re.sub(
        r"[^\w\s]",
        " ",
        text,
        flags=re.UNICODE
    )

    text = re.sub(
        r"\s+",
        " ",
        text
    )

    return text.strip()


# ============================================================
# WAKE WORD DETECTOR
# ============================================================

def is_wake_word(text):

    normalized = normalize_text(text)

    print("WAKE NORMALIZED:", normalized)

    if not normalized:
        return False

    # Exact / common hello variations
    wake_words = [
        "hello",
        "helo",
        "hellow",
        "hallo",
        "hello wolne",
        "hello wolven",
        "hello wolven ai",
        "hello voice",
        "hello ai",
        "hey hello"
    ]

    for word in wake_words:

        if normalized == word:
            return True

    # If sentence starts with hello
    if normalized.startswith("hello "):
        return True

    if normalized.startswith("helo "):
        return True

    if normalized.startswith("hellow "):
        return True

    # Hindi/phonetic variations
    if "hello" in normalized:
        return True

    return False


# ============================================================
# GROQ TRANSCRIPTION
# ============================================================

def transcribe_audio(temp_path, prompt):

    with open(temp_path, "rb") as audio_file:

        transcription = client.audio.transcriptions.create(

            file=audio_file,

            model=STT_MODEL,

            prompt=prompt,

            response_format="json",

            temperature=0.0
        )

    return transcription.text.strip()


# ============================================================
# WAKE ENDPOINT
# ============================================================

@app.route("/wake", methods=["POST"])
def wake():

    print()
    print("================================")
    print("WAKE WORD REQUEST")
    print("================================")

    temp_path = None

    try:

        data = request.get_data()

        print("BYTES:", len(data))
        print("CONTENT TYPE:", request.content_type)

        if not data:

            return jsonify({
                "status": "error",
                "wake": False,
                "text": "",
                "message": "No audio received"
            }), 400


        # ----------------------------------------------------
        # WAV CHECK
        # ----------------------------------------------------

        wav_info = check_wav(data)

        if wav_info is None:

            return jsonify({
                "status": "error",
                "wake": False,
                "text": "",
                "message": "Invalid WAV"
            }), 400


        if client is None:

            return jsonify({
                "status": "error",
                "wake": False,
                "text": "",
                "message": "GROQ_API_KEY missing"
            }), 500


        # ----------------------------------------------------
        # TEMP FILE
        # ----------------------------------------------------

        temp_file = tempfile.NamedTemporaryFile(
            suffix=".wav",
            delete=False
        )

        temp_path = temp_file.name

        temp_file.write(data)
        temp_file.close()


        # ----------------------------------------------------
        # TRANSCRIBE
        # ----------------------------------------------------

        wake_text = transcribe_audio(

            temp_path,

            (
                "This is a wake word recording. "
                "The user may say hello, hello wolne, "
                "hello AI, or similar pronunciation. "
                "Transcribe only what is actually spoken. "
                "Do not invent words."
            )
        )


        print("WAKE TEXT:", wake_text)


        # ----------------------------------------------------
        # DETECT
        # ----------------------------------------------------

        wake_detected = is_wake_word(wake_text)


        if wake_detected:

            print("################################")
            print("WAKE WORD DETECTED")
            print("################################")

        else:

            print("WAKE WORD NOT DETECTED")


        return jsonify({

            "status": "ok",

            "wake": wake_detected,

            "text": wake_text

        }), 200


    except Exception as e:

        print("WAKE ERROR:", repr(e))

        return jsonify({

            "status": "error",

            "wake": False,

            "text": "",

            "error": str(e)

        }), 500


    finally:

        if temp_path:

            try:
                os.remove(temp_path)
            except Exception:
                pass


# ============================================================
# UPLOAD AUDIO
# ============================================================

@app.route("/uploadAudio", methods=["POST"])
def upload_audio():

    print()
    print("================================")
    print("UPLOAD AUDIO REQUEST")
    print("================================")

    temp_path = None

    try:

        data = request.get_data()

        print("Content-Type:", request.content_type)
        print("Content-Length:", request.content_length)
        print("AUDIO BYTES:", len(data))


        # ----------------------------------------------------
        # EMPTY
        # ----------------------------------------------------

        if not data:

            return jsonify({

                "status": "error",
                "message": "No audio received",
                "text": "",
                "ai_response": ""

            }), 400


        # ----------------------------------------------------
        # WAV
        # ----------------------------------------------------

        wav_info = check_wav(data)

        if wav_info is None:

            return jsonify({

                "status": "error",
                "message": "Invalid WAV file",
                "text": "",
                "ai_response": ""

            }), 400


        print("WAV CHECK: PASS")


        # ----------------------------------------------------
        # GROQ
        # ----------------------------------------------------

        if client is None:

            return jsonify({

                "status": "error",
                "message": "GROQ_API_KEY is missing",
                "text": "",
                "ai_response": ""

            }), 500


        # ----------------------------------------------------
        # TEMP WAV
        # ----------------------------------------------------

        temp_file = tempfile.NamedTemporaryFile(
            suffix=".wav",
            delete=False
        )

        temp_path = temp_file.name

        temp_file.write(data)
        temp_file.close()


        # ====================================================
        # STT
        # ====================================================

        print()
        print("================================")
        print("GROQ WHISPER STT")
        print("================================")

        user_text = transcribe_audio(

            temp_path,

            (
                "The speaker may speak Hindi, English, "
                "or Hinglish. "
                "Transcribe exactly what the speaker says. "
                "Do not translate Hindi into English. "
                "Keep Hindi words in Hindi when appropriate."
            )
        )


        print("USER TEXT:", user_text)


        # ----------------------------------------------------
        # NO SPEECH
        # ----------------------------------------------------

        if not user_text:

            return jsonify({

                "status": "ok",

                "bytes": len(data),

                "message":
                    "Audio received but speech not understood",

                "text": "",

                "ai_response": ""

            }), 200


        # ====================================================
        # AI
        # ====================================================

        print()
        print("================================")
        print("GROQ AI")
        print("================================")

        print("MODEL:", AI_MODEL)
        print("USER:", user_text)


        completion = client.chat.completions.create(

            model=AI_MODEL,

            messages=[

                {
                    "role": "system",

                    "content": (
                        "You are a helpful voice assistant. "

                        "The user may speak Hindi, English, "
                        "or Hinglish. "

                        "Understand all three languages. "

                        "If the user speaks Hindi, reply in Hindi. "

                        "If the user speaks English, reply in English. "

                        "If the user speaks Hinglish, reply in "
                        "natural Hinglish. "

                        "Do not translate unnecessarily. "

                        "Do not use markdown. "

                        "Do not use emojis. "

                        "Keep the answer concise because it will "
                        "be spoken through a speaker."
                    )
                },

                {
                    "role": "user",
                    "content": user_text
                }

            ],

            temperature=0.3,

            max_completion_tokens=300,

            reasoning_effort="low"
        )


        ai_response = (
            completion
            .choices[0]
            .message
            .content
            .strip()
        )


        print()
        print("AI RESPONSE:")
        print(ai_response)


        # ====================================================
        # SUCCESS
        # ====================================================

        return jsonify({

            "status": "ok",

            "bytes": len(data),

            "message":
                "Audio processed successfully",

            "text": user_text,

            "ai_response": ai_response

        }), 200


    except Exception as e:

        print()
        print("================================")
        print("AUDIO PROCESSING ERROR")
        print("================================")

        print("ERROR:", repr(e))


        return jsonify({

            "status": "error",

            "message": "Audio processing failed",

            "error": str(e),

            "text": "",

            "ai_response": ""

        }), 500


    finally:

        if temp_path:

            try:
                os.remove(temp_path)
            except Exception:
                pass


# ============================================================
# TTS
# ============================================================

@app.route("/tts", methods=["GET"])
def tts():

    text = request.args.get(
        "text",
        ""
    ).strip()

    lang = request.args.get(
        "lang",
        "en"
    ).strip().lower()


    print()
    print("================================")
    print("TTS REQUEST")
    print("================================")

    print("TEXT:", text)
    print("LANG:", lang)


    if not text:

        return jsonify({
            "status": "error",
            "message": "Text is empty"
        }), 400


    # --------------------------------------------------------
    # LIMIT
    # --------------------------------------------------------

    if len(text) > 500:

        text = text[:500]


    # --------------------------------------------------------
    # LANGUAGE
    # --------------------------------------------------------

    if lang not in [
        "en",
        "hi"
    ]:

        lang = "en"


    temp_path = None

    try:

        # ----------------------------------------------------
        # CREATE MP3
        # ----------------------------------------------------

        temp_file = tempfile.NamedTemporaryFile(
            suffix=".mp3",
            delete=False
        )

        temp_path = temp_file.name

        temp_file.close()


        tts = gTTS(
            text=text,
            lang=lang,
            slow=False
        )

        tts.save(temp_path)


        # ----------------------------------------------------
        # READ MP3
        # ----------------------------------------------------

        with open(
            temp_path,
            "rb"
        ) as audio_file:

            audio_data = audio_file.read()


        print(
            "MP3 BYTES:",
            len(audio_data)
        )


        # ----------------------------------------------------
        # RESPONSE
        # ----------------------------------------------------

        return Response(

            audio_data,

            status=200,

            mimetype="audio/mpeg",

            headers={

                "Content-Length":
                    str(len(audio_data)),

                "Cache-Control":
                    "no-cache",

                "Connection":
                    "close"

            }
        )


    except Exception as e:

        print()
        print("TTS ERROR:")
        print(repr(e))


        return jsonify({

            "status": "error",

            "message":
                "TTS generation failed",

            "error":
                str(e)

        }), 500


    finally:

        if temp_path:

            try:
                os.remove(temp_path)
            except Exception:
                pass


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
    print("================================")
    print("ESP32 VOICE AI SERVER")
    print("================================")

    print("PORT:", port)
    print("STT:", STT_MODEL)
    print("AI:", AI_MODEL)
    print("WAKE: ENABLED")
    print("TTS: ENABLED")


    app.run(

        host="0.0.0.0",

        port=port
    )

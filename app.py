from flask import Flask, request, jsonify
from groq import Groq
import os
import io
import wave
import tempfile
import urllib.parse
import subprocess

app = Flask(__name__)

# ============================================================
# GROQ
# ============================================================

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

if not GROQ_API_KEY:
    print("WARNING: GROQ_API_KEY NOT SET")
    client = None
else:
    client = Groq(api_key=GROQ_API_KEY)
    print("Groq client initialized")


# ============================================================
# MODELS
# ============================================================

STT_MODEL = "whisper-large-v3-turbo"
AI_MODEL = "openai/gpt-oss-20b"


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
        "stt": STT_MODEL,
        "ai": AI_MODEL,
        "wake_word": "hello",
        "tts": "enabled"
    }), 200


# ============================================================
# WAV CHECK
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
            print("Channels:", channels)
            print("Sample Width:", sample_width)
            print("Sample Rate:", sample_rate)
            print("Frames:", frames)
            print("Duration:", duration)
            print("--------------------------------")

            return {
                "channels": channels,
                "sample_width": sample_width,
                "sample_rate": sample_rate,
                "frames": frames,
                "duration": duration
            }

    except Exception as e:

        print("WAV ERROR:", repr(e))
        return None


# ============================================================
# TRANSCRIBE
# ============================================================

def transcribe_wav(data):

    temp_path = None

    try:

        temp_file = tempfile.NamedTemporaryFile(
            suffix=".wav",
            delete=False
        )

        temp_path = temp_file.name

        temp_file.write(data)
        temp_file.close()

        with open(temp_path, "rb") as audio_file:

            result = client.audio.transcriptions.create(
                file=audio_file,
                model=STT_MODEL,
                prompt=(
                    "The speaker may speak Hindi, English, "
                    "or Hinglish. Transcribe exactly what "
                    "the speaker says. Preserve Hindi words "
                    "and do not translate them."
                ),
                response_format="json",
                temperature=0.0
            )

        text = result.text.strip()

        return text

    finally:

        if temp_path:

            try:
                os.remove(temp_path)
            except Exception:
                pass


# ============================================================
# WAKE WORD
# ============================================================

@app.route("/wake", methods=["POST"])
def wake():

    print()
    print("================================")
    print("WAKE WORD REQUEST")
    print("================================")

    try:

        data = request.get_data()

        print("BYTES:", len(data))

        if not data:
            return jsonify({
                "status": "ok",
                "wake": False,
                "text": ""
            }), 200

        if client is None:
            return jsonify({
                "status": "error",
                "wake": False,
                "text": "",
                "message": "GROQ_API_KEY missing"
            }), 500

        if check_wav(data) is None:
            return jsonify({
                "status": "error",
                "wake": False,
                "text": ""
            }), 400

        text = transcribe_wav(data)

        print("WAKE TEXT:", text)

        normalized = text.lower().strip()

        # Hindi/English variations
        wake = (
            "hello" in normalized
            or "हेलो" in normalized
            or "हैलो" in normalized
        )

        return jsonify({
            "status": "ok",
            "wake": wake,
            "text": text
        }), 200

    except Exception as e:

        print("WAKE ERROR:", repr(e))

        return jsonify({
            "status": "error",
            "wake": False,
            "text": "",
            "error": str(e)
        }), 500


# ============================================================
# MAIN AI
# ============================================================

@app.route("/uploadAudio", methods=["POST"])
def upload_audio():

    print()
    print("================================")
    print("UPLOAD AUDIO REQUEST")
    print("================================")

    try:

        data = request.get_data()

        print("Content-Type:", request.content_type)
        print("Bytes:", len(data))

        if not data:

            return jsonify({
                "status": "error",
                "message": "No audio received",
                "text": "",
                "ai_response": ""
            }), 400

        wav_info = check_wav(data)

        if wav_info is None:

            return jsonify({
                "status": "error",
                "message": "Invalid WAV file",
                "text": "",
                "ai_response": ""
            }), 400

        if client is None:

            return jsonify({
                "status": "error",
                "message": "GROQ_API_KEY missing",
                "text": "",
                "ai_response": ""
            }), 500


        # ====================================================
        # STT
        # ====================================================

        print()
        print("================================")
        print("WHISPER")
        print("================================")

        user_text = transcribe_wav(data)

        print("USER:", user_text)

        if not user_text:

            return jsonify({
                "status": "ok",
                "bytes": len(data),
                "message": "No speech detected",
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

        completion = client.chat.completions.create(

            model=AI_MODEL,

            messages=[

                {
                    "role": "system",
                    "content": (
                        "You are a voice assistant. "
                        "The user can speak Hindi, English, "
                        "or Hinglish. "
                        "Reply in the same language style. "
                        "Hindi input must get Hindi output. "
                        "English input must get English output. "
                        "Hinglish input must get natural Hinglish output. "
                        "Keep the answer concise because it will "
                        "be spoken aloud. "
                        "Do not use markdown. "
                        "Do not use emojis. "
                        "Do not use bullet points unless necessary."
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

        print("AI:", ai_response)


        # ====================================================
        # RESULT
        # ====================================================

        return jsonify({

            "status": "ok",
            "bytes": len(data),
            "message": "Audio processed successfully",
            "text": user_text,
            "ai_response": ai_response

        }), 200


    except Exception as e:

        print()
        print("================================")
        print("AI ERROR")
        print("================================")

        print(repr(e))

        return jsonify({

            "status": "error",
            "message": "Audio processing failed",
            "error": str(e),
            "text": "",
            "ai_response": ""

        }), 500


# ============================================================
# SIMPLE TTS
# ============================================================

@app.route("/tts", methods=["GET"])
def tts():

    text = request.args.get("text", "").strip()
    lang = request.args.get("lang", "en").strip()

    print()
    print("================================")
    print("TTS REQUEST")
    print("================================")

    print("TEXT:", text)
    print("LANG:", lang)

    if not text:

        return "No text", 400


    # --------------------------------------------------------
    # NOTE:
    # This endpoint expects your server to have a TTS command.
    #
    # If using Linux Render:
    # install espeak-ng in build environment.
    # --------------------------------------------------------

    try:

        output = tempfile.NamedTemporaryFile(
            suffix=".wav",
            delete=False
        )

        output_path = output.name
        output.close()


        # Hindi:
        # hi
        #
        # English:
        # en
        #
        # Hinglish:
        # en is usually safest.

        voice = "hi" if lang == "hi" else "en"


        command = [
            "espeak-ng",
            "-v",
            voice,
            "-s",
            "145",
            "-w",
            output_path,
            text
        ]


        subprocess.run(
            command,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )


        with open(output_path, "rb") as f:
            audio_data = f.read()


        os.remove(output_path)


        from flask import Response

        return Response(
            audio_data,
            status=200,
            mimetype="audio/wav",
            headers={
                "Content-Length": str(len(audio_data)),
                "Cache-Control": "no-cache"
            }
        )


    except Exception as e:

        print("TTS ERROR:", repr(e))

        try:
            if os.path.exists(output_path):
                os.remove(output_path)
        except Exception:
            pass

        return jsonify({
            "status": "error",
            "error": str(e)
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
    print("================================")
    print("ESP32 VOICE AI SERVER")
    print("================================")

    print("PORT:", port)
    print("STT:", STT_MODEL)
    print("AI:", AI_MODEL)
    print("WAKE: hello")

    app.run(
        host="0.0.0.0",
        port=port
    )

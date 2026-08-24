from flask import Flask, request, jsonify
from groq import Groq
import os
import io
import wave
import tempfile

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
        "stt": "whisper-large-v3-turbo",
        "ai": "llama-3.3-70b-versatile"
    }), 200


# ============================================================
# TTS
# Keep your existing TTS route if you already have one.
# ============================================================

@app.route("/tts")
def tts():

    text = request.args.get("text", "")
    lang = request.args.get("lang", "en")

    if not text:
        return jsonify({
            "error": "text missing"
        }), 400

    print("TTS REQUEST")
    print("TEXT:", text)
    print("LANG:", lang)

    # --------------------------------------------------------
    # IMPORTANT:
    # Put your existing working TTS code here.
    # This route is NOT changed by upload/STT.
    # --------------------------------------------------------

    return jsonify({
        "status": "ok",
        "text": text,
        "lang": lang
    }), 200


# ============================================================
# VALIDATE WAV
# ============================================================

def check_wav(data):

    try:

        bio = io.BytesIO(data)

        with wave.open(bio, "rb") as wav:

            channels = wav.getnchannels()
            sample_width = wav.getsampwidth()
            sample_rate = wav.getframerate()
            frames = wav.getnframes()

            duration = frames / float(sample_rate)

            print("--------------------------------")
            print("WAV INFO")
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

        print("WAV VALIDATION ERROR:", repr(e))

        return None


# ============================================================
# UPLOAD AUDIO
# ============================================================

@app.route("/uploadAudio", methods=["POST"])
def upload_audio():

    print()
    print("================================")
    print("UPLOAD AUDIO REQUEST")
    print("================================")

    try:

        # ----------------------------------------------------
        # READ AUDIO
        # ----------------------------------------------------

        data = request.get_data()

        print("Content-Type:", request.content_type)
        print("Content-Length:", request.content_length)
        print("AUDIO BYTES:", len(data))

        if not data:

            return jsonify({
                "status": "error",
                "message": "No audio received",
                "text": "",
                "ai_response": ""
            }), 400


        # ----------------------------------------------------
        # CHECK WAV
        # ----------------------------------------------------

        wav_info = check_wav(data)

        if wav_info is None:

            return jsonify({
                "status": "error",
                "message": "Invalid WAV file",
                "text": "",
                "ai_response": ""
            }), 400


        # ----------------------------------------------------
        # BASIC WAV CHECK
        # ----------------------------------------------------

        print("WAV CHECK PASSED")

        print(
            "Format:",
            wav_info["channels"],
            "channel(s),",
            wav_info["sample_rate"],
            "Hz,",
            wav_info["sample_width"] * 8,
            "bit"
        )


        # ----------------------------------------------------
        # GROQ CHECK
        # ----------------------------------------------------

        if client is None:

            return jsonify({
                "status": "error",
                "message": "GROQ_API_KEY is missing",
                "text": "",
                "ai_response": ""
            }), 500


        # ----------------------------------------------------
        # SAVE TEMP WAV
        # ----------------------------------------------------

        temp_file = tempfile.NamedTemporaryFile(
            suffix=".wav",
            delete=False
        )

        temp_path = temp_file.name

        try:

            temp_file.write(data)
            temp_file.flush()
            temp_file.close()

            print("TEMP WAV:", temp_path)


            # =================================================
            # SPEECH TO TEXT
            # =================================================

            print()
            print("================================")
            print("GROQ WHISPER")
            print("================================")

            print("Starting transcription...")

            with open(temp_path, "rb") as audio_file:

                transcription = client.audio.transcriptions.create(

                    file=audio_file,

                    model="whisper-large-v3-turbo",

                    # Hindi + English mixed speech
                    prompt=(
                        "The speaker may speak Hindi, English, "
                        "or Hinglish. Transcribe exactly what "
                        "the speaker says."
                    ),

                    response_format="json",

                    temperature=0.0
                )


            user_text = transcription.text.strip()


            print("TRANSCRIPTION:")
            print(user_text)


            # =================================================
            # EMPTY SPEECH
            # =================================================

            if not user_text:

                print("NO SPEECH DETECTED")

                return jsonify({

                    "status": "ok",

                    "bytes": len(data),

                    "message": "Audio received but speech not understood",

                    "text": "",

                    "ai_response": ""

                }), 200


            # =================================================
            # AI
            # =================================================

            print()
            print("================================")
            print("GROQ AI")
            print("================================")

            print("USER:", user_text)


            completion = client.chat.completions.create(

                model="llama-3.3-70b-versatile",

                messages=[

                    {
                        "role": "system",
                        "content": (
                            "You are a helpful voice assistant. "
                            "The user may speak Hindi, English, "
                            "or Hinglish. Understand all three. "
                            "Reply naturally and concisely. "
                            "If the user speaks Hindi or Hinglish, "
                            "you may reply in Hindi/Hinglish. "
                            "Do not use markdown. "
                            "Keep voice responses short."
                        )
                    },

                    {
                        "role": "user",
                        "content": user_text
                    }

                ],

                temperature=0.3,

                max_tokens=300
            )


            ai_response = (
                completion
                .choices[0]
                .message
                .content
                .strip()
            )


            print("AI RESPONSE:")
            print(ai_response)


            # =================================================
            # FINAL RESPONSE
            # =================================================

            print()
            print("================================")
            print("AI PIPELINE SUCCESS")
            print("================================")

            return jsonify({

                "status": "ok",

                "bytes": len(data),

                "message": "Audio processed successfully",

                "text": user_text,

                "ai_response": ai_response

            }), 200


        finally:

            # ------------------------------------------------
            # DELETE TEMP FILE
            # ------------------------------------------------

            try:
                os.remove(temp_path)
                print("TEMP FILE DELETED")
            except Exception:
                pass


    except Exception as e:

        print()
        print("================================")
        print("UPLOAD / AI ERROR")
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
# START
# ============================================================

if __name__ == "__main__":

    port = int(
        os.environ.get(
            "PORT",
            10000
        )
    )

    app.run(
        host="0.0.0.0",
        port=port
    )

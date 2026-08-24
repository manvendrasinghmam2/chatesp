from flask import Flask, request, jsonify, Response
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

    print("================================")
    print("WARNING: GROQ_API_KEY NOT SET")
    print("================================")

    client = None

else:

    client = Groq(
        api_key=GROQ_API_KEY
    )

    print("================================")
    print("GROQ CLIENT INITIALIZED")
    print("================================")


# ============================================================
# MODELS
# ============================================================

STT_MODEL = "whisper-large-v3-turbo"

AI_MODEL = "openai/gpt-oss-20b"

TTS_MODEL = "canopylabs/orpheus-v1-english"

TTS_VOICE = "troy"


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

        "stt": STT_MODEL,

        "ai": AI_MODEL,

        "tts": TTS_MODEL,

        "tts_voice": TTS_VOICE

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

            if sample_rate > 0:

                duration = (
                    frames /
                    float(sample_rate)
                )

            else:

                duration = 0


            print()
            print("--------------------------------")
            print("WAV INFO")
            print("--------------------------------")

            print("Channels:", channels)

            print(
                "Sample Width:",
                sample_width
            )

            print(
                "Sample Rate:",
                sample_rate
            )

            print(
                "Frames:",
                frames
            )

            print(
                "Duration:",
                duration
            )

            print("--------------------------------")


            return {

                "channels": channels,

                "sample_width": sample_width,

                "sample_rate": sample_rate,

                "frames": frames,

                "duration": duration

            }


    except Exception as e:

        print()
        print("WAV VALIDATION ERROR:")
        print(repr(e))

        return None


# ============================================================
# UPLOAD AUDIO
# ============================================================

@app.route(
    "/uploadAudio",
    methods=["POST"]
)
def upload_audio():

    print()
    print("================================")
    print("UPLOAD AUDIO REQUEST")
    print("================================")

    temp_path = None

    try:

        # ----------------------------------------------------
        # REQUEST INFO
        # ----------------------------------------------------

        print(
            "Method:",
            request.method
        )

        print(
            "Content-Type:",
            request.content_type
        )

        print(
            "Content-Length:",
            request.content_length
        )


        # ----------------------------------------------------
        # READ AUDIO
        # ----------------------------------------------------

        data = request.get_data()

        print(
            "AUDIO BYTES:",
            len(data)
        )


        # ----------------------------------------------------
        # EMPTY
        # ----------------------------------------------------

        if not data:

            print("ERROR: EMPTY AUDIO")

            return jsonify({

                "status": "error",

                "message": "No audio received",

                "text": "",

                "ai_response": ""

            }), 400


        # ----------------------------------------------------
        # WAV VALIDATION
        # ----------------------------------------------------

        wav_info = check_wav(data)

        if wav_info is None:

            print("ERROR: INVALID WAV")

            return jsonify({

                "status": "error",

                "message": "Invalid WAV file",

                "text": "",

                "ai_response": ""

            }), 400


        print()
        print("WAV CHECK: PASS")


        # ----------------------------------------------------
        # GROQ CHECK
        # ----------------------------------------------------

        if client is None:

            print(
                "ERROR: GROQ_API_KEY MISSING"
            )

            return jsonify({

                "status": "error",

                "message":
                    "GROQ_API_KEY is missing",

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

        temp_file.flush()

        temp_file.close()


        print(
            "TEMP WAV:",
            temp_path
        )


        # ====================================================
        # SPEECH TO TEXT
        # ====================================================

        print()
        print("================================")
        print("GROQ WHISPER STT")
        print("================================")

        print(
            "Model:",
            STT_MODEL
        )

        print(
            "Starting transcription..."
        )


        with open(
            temp_path,
            "rb"
        ) as audio_file:

            transcription = (
                client
                .audio
                .transcriptions
                .create(

                    file=audio_file,

                    model=STT_MODEL,

                    prompt=(

                        "The speaker may speak "
                        "Hindi, English, or Hinglish. "

                        "Transcribe exactly what "
                        "the speaker says. "

                        "Do not translate Hindi "
                        "into English. "

                        "Keep Hindi words in Hindi "
                        "when appropriate."

                    ),

                    response_format="json",

                    temperature=0.0

                )
            )


        user_text = (
            transcription
            .text
            .strip()
        )


        print()
        print("TRANSCRIPTION:")
        print(user_text)


        # ====================================================
        # NO SPEECH
        # ====================================================

        if not user_text:

            print()
            print("NO SPEECH DETECTED")

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

        print(
            "Model:",
            AI_MODEL
        )

        print(
            "USER:",
            user_text
        )


        completion = (
            client
            .chat
            .completions
            .create(

                model=AI_MODEL,

                messages=[

                    {
                        "role": "system",

                        "content": (

                            "You are a helpful "
                            "voice assistant. "

                            "The user may speak "
                            "Hindi, English, "
                            "or Hinglish. "

                            "Understand all three "
                            "languages. "

                            "Reply naturally and "
                            "concisely. "

                            "If the user speaks "
                            "Hindi, reply in Hindi. "

                            "If the user speaks "
                            "Hinglish, reply in "
                            "natural Hinglish. "

                            "If the user speaks "
                            "English, reply in "
                            "English. "

                            "Do not use markdown. "

                            "Do not use bullet points "
                            "unless necessary. "

                            "Keep answers short "
                            "because the response "
                            "will be spoken through "
                            "a speaker."

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

        print()
        print("================================")
        print("AI PIPELINE SUCCESS")
        print("================================")


        return jsonify({

            "status": "ok",

            "bytes": len(data),

            "message":
                "Audio processed successfully",

            "text": user_text,

            "ai_response": ai_response

        }), 200


    # ========================================================
    # ERROR
    # ========================================================

    except Exception as e:

        print()
        print("================================")
        print("AUDIO PROCESSING ERROR")
        print("================================")

        print(
            "ERROR:",
            repr(e)
        )


        return jsonify({

            "status": "error",

            "message":
                "Audio processing failed",

            "error": str(e),

            "text": "",

            "ai_response": ""

        }), 500


    # ========================================================
    # CLEANUP
    # ========================================================

    finally:

        if temp_path:

            try:

                os.remove(
                    temp_path
                )

                print(
                    "TEMP WAV DELETED"
                )

            except Exception:

                pass


# ============================================================
# TTS
# ============================================================

@app.route(
    "/tts",
    methods=["GET"]
)
def tts():

    print()
    print("================================")
    print("TTS REQUEST")
    print("================================")


    # --------------------------------------------------------
    # GET TEXT
    # --------------------------------------------------------

    text = request.args.get(
        "text",
        ""
    ).strip()

    lang = request.args.get(
        "lang",
        "en"
    )


    print(
        "LANG:",
        lang
    )

    print(
        "TEXT:",
        text
    )


    # --------------------------------------------------------
    # EMPTY TEXT
    # --------------------------------------------------------

    if not text:

        print(
            "TTS ERROR: EMPTY TEXT"
        )

        return jsonify({

            "status": "error",

            "message":
                "No text provided"

        }), 400


    # --------------------------------------------------------
    # GROQ CHECK
    # --------------------------------------------------------

    if client is None:

        print(
            "TTS ERROR: GROQ_API_KEY MISSING"
        )

        return jsonify({

            "status": "error",

            "message":
                "GROQ_API_KEY is missing"

        }), 500


    try:

        # ----------------------------------------------------
        # LIMIT TEXT
        # ----------------------------------------------------

        if len(text) > 200:

            print(
                "TTS TEXT TOO LONG:",
                len(text)
            )

            text = text[:200]


        # ----------------------------------------------------
        # TTS
        # ----------------------------------------------------

        print()
        print(
            "TTS MODEL:",
            TTS_MODEL
        )

        print(
            "TTS VOICE:",
            TTS_VOICE
        )

        print(
            "Generating speech..."
        )


        speech_response = (

            client
            .audio
            .speech
            .create(

                model=TTS_MODEL,

                voice=TTS_VOICE,

                input=text,

                response_format="wav"

            )

        )


        # ----------------------------------------------------
        # READ AUDIO
        # ----------------------------------------------------

        audio_bytes = (
            speech_response
            .read()
        )


        print(
            "TTS AUDIO BYTES:",
            len(audio_bytes)
        )


        # ----------------------------------------------------
        # EMPTY AUDIO
        # ----------------------------------------------------

        if not audio_bytes:

            print(
                "TTS ERROR: EMPTY AUDIO"
            )

            return jsonify({

                "status": "error",

                "message":
                    "TTS returned empty audio"

            }), 500


        # ----------------------------------------------------
        # SUCCESS
        # ----------------------------------------------------

        print()
        print("================================")
        print("TTS SUCCESS")
        print("================================")


        return Response(

            audio_bytes,

            status=200,

            mimetype="audio/wav",

            headers={

                "Content-Length":
                    str(len(audio_bytes)),

                "Cache-Control":
                    "no-cache",

                "Connection":
                    "close"

            }

        )


    except Exception as e:

        print()
        print("================================")
        print("TTS ERROR")
        print("================================")

        print(
            "ERROR:",
            repr(e)
        )


        return jsonify({

            "status": "error",

            "message":
                "TTS generation failed",

            "error": str(e)

        }), 500


# ============================================================
# START SERVER
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
    print("ESP32 AI SERVER")
    print("================================")

    print(
        "PORT:",
        port
    )

    print(
        "STT:",
        STT_MODEL
    )

    print(
        "AI:",
        AI_MODEL
    )

    print(
        "TTS:",
        TTS_MODEL
    )

    print(
        "TTS VOICE:",
        TTS_VOICE
    )


    app.run(

        host="0.0.0.0",

        port=port

    )

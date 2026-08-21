from flask import Flask, request, jsonify
from groq import Groq

import os
import tempfile
import traceback
import wave


app = Flask(__name__)


# =====================================================
# GROQ
# =====================================================

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

if not GROQ_API_KEY:
    print("WARNING: GROQ_API_KEY is missing")


groq_client = (
    Groq(api_key=GROQ_API_KEY)
    if GROQ_API_KEY
    else None
)


# =====================================================
# MODELS
# =====================================================

WHISPER_MODEL = "whisper-large-v3-turbo"
CHAT_MODEL = "llama-3.3-70b-versatile"


# =====================================================
# LIMITS
# =====================================================

MAX_AUDIO_SIZE = 10 * 1024 * 1024


# =====================================================
# HOME
# =====================================================

@app.route("/", methods=["GET"])
def home():

    return jsonify({
        "status": "online",
        "message": "ESP32 Voice AI Server",

        "endpoints": {
            "wake": "/wake",
            "upload_audio": "/uploadAudio",
            "health": "/health"
        }
    })


# =====================================================
# HEALTH
# =====================================================

@app.route("/health", methods=["GET"])
def health():

    return jsonify({

        "status": "healthy",

        "groq_configured":
            groq_client is not None,

        "whisper_model":
            WHISPER_MODEL,

        "chat_model":
            CHAT_MODEL
    })


# =====================================================
# COMMON WAV VALIDATION
# =====================================================

def validate_wav(wav_data):

    if not wav_data:

        return False, "No audio received"


    if len(wav_data) < 44:

        return False, "Invalid WAV: file too small"


    if wav_data[0:4] != b"RIFF":

        return False, (
            "Invalid WAV: RIFF header missing"
        )


    if wav_data[8:12] != b"WAVE":

        return False, (
            "Invalid WAV: WAVE header missing"
        )


    return True, ""


# =====================================================
# COMMON TRANSCRIPTION
# =====================================================

def transcribe_audio(wav_data, wake_mode=False):

    temp_path = None

    try:

        # -------------------------------------------------
        # SAVE WAV
        # -------------------------------------------------

        with tempfile.NamedTemporaryFile(
            suffix=".wav",
            delete=False
        ) as temp:

            temp.write(wav_data)

            temp_path = temp.name


        print(
            "Temporary WAV:",
            temp_path,
            flush=True
        )


        # -------------------------------------------------
        # WAV INFO
        # -------------------------------------------------

        try:

            with wave.open(
                temp_path,
                "rb"
            ) as wav:

                channels = wav.getnchannels()
                sample_width = wav.getsampwidth()
                sample_rate = wav.getframerate()
                frames = wav.getnframes()

                duration = (
                    frames / sample_rate
                    if sample_rate > 0
                    else 0
                )


                print(
                    "WAV INFO",
                    flush=True
                )

                print(
                    "Channels:",
                    channels,
                    flush=True
                )

                print(
                    "Sample width:",
                    sample_width,
                    flush=True
                )

                print(
                    "Sample rate:",
                    sample_rate,
                    flush=True
                )

                print(
                    "Frames:",
                    frames,
                    flush=True
                )

                print(
                    "Duration:",
                    duration,
                    flush=True
                )

        except Exception as e:

            print(
                "WAV inspection warning:",
                e,
                flush=True
            )


        # -------------------------------------------------
        # GROQ CHECK
        # -------------------------------------------------

        if groq_client is None:

            raise RuntimeError(
                "GROQ_API_KEY missing on Render"
            )


        # -------------------------------------------------
        # TRANSCRIPTION
        # -------------------------------------------------

        print(
            "Sending audio to Groq Whisper...",
            flush=True
        )


        with open(
            temp_path,
            "rb"
        ) as audio_file:

            if wake_mode:

                # -----------------------------------------
                # WAKE WORD PROMPT
                # -----------------------------------------

                prompt = (
                    "The wake word is hello. "
                    "The speaker may say hello, "
                    "hello ESP32, or hello assistant. "
                    "Transcribe exactly what is spoken."
                )

            else:

                # -----------------------------------------
                # NORMAL SPEECH PROMPT
                # -----------------------------------------

                prompt = (
                    "The speaker may use Hindi, "
                    "English, Hinglish, or Roman Hindi. "
                    "Transcribe exactly what is spoken. "
                    "Do not translate Hindi into English. "
                    "Do not translate English into Hindi. "
                    "Keep Roman Hindi in Roman letters."
                )


            transcription_result = (
                groq_client.audio.transcriptions.create(

                    file=audio_file,

                    model=WHISPER_MODEL,

                    response_format="json",

                    temperature=0.0,

                    prompt=prompt
                )
            )


        transcription = (
            transcription_result.text or ""
        ).strip()


        print(
            "TRANSCRIPTION:",
            transcription,
            flush=True
        )


        return transcription


    finally:

        # -------------------------------------------------
        # DELETE TEMP FILE
        # -------------------------------------------------

        if temp_path:

            try:

                os.remove(
                    temp_path
                )

            except Exception:

                pass


# =====================================================
# HELLO DETECTION
# =====================================================

def is_hello(text):

    if not text:
        return False


    text = text.lower().strip()


    # Remove common punctuation

    for character in [
        ",",
        ".",
        "!",
        "?",
        ":",
        ";"
    ]:

        text = text.replace(
            character,
            " "
        )


    words = text.split()


    # -------------------------------------------------
    # EXACT / NEAR HELLO
    # -------------------------------------------------

    hello_words = [
        "hello",
        "helo",
        "hallo",
        "hellow",
        "hullo"
    ]


    for word in words:

        if word in hello_words:

            return True


    # -------------------------------------------------
    # PHRASES
    # -------------------------------------------------

    if "hello esp32" in text:
        return True


    if "hello assistant" in text:
        return True


    if "hello ai" in text:
        return True


    return False


# =====================================================
# WAKE ENDPOINT
# =====================================================

@app.route("/wake", methods=["POST"])
def wake():

    print()
    print("========================================")
    print("WAKE WORD REQUEST")
    print("========================================")


    try:

        # -------------------------------------------------
        # RAW BODY
        # -------------------------------------------------

        wav_data = request.get_data()


        print(
            "Wake bytes:",
            len(wav_data),
            flush=True
        )


        # -------------------------------------------------
        # SIZE CHECK
        # -------------------------------------------------

        if len(wav_data) > MAX_AUDIO_SIZE:

            return jsonify({

                "wake": False,

                "transcription": "",

                "error":
                    "Wake audio too large"

            }), 413


        # -------------------------------------------------
        # WAV CHECK
        # -------------------------------------------------

        valid, error = validate_wav(
            wav_data
        )


        if not valid:

            return jsonify({

                "wake": False,

                "transcription": "",

                "error": error

            }), 400


        print(
            "Wake WAV header: OK",
            flush=True
        )


        # -------------------------------------------------
        # TRANSCRIBE
        # -------------------------------------------------

        transcription = transcribe_audio(
            wav_data,
            wake_mode=True
        )


        # -------------------------------------------------
        # CHECK HELLO
        # -------------------------------------------------

        detected = is_hello(
            transcription
        )


        print()
        print(
            "WAKE TRANSCRIPTION:",
            transcription,
            flush=True
        )

        print(
            "HELLO DETECTED:",
            detected,
            flush=True
        )


        print(
            "========================================",
            flush=True
        )


        # -------------------------------------------------
        # RESPONSE TO ESP32
        # -------------------------------------------------

        return jsonify({

            "status": "success",

            "wake": detected,

            "transcription":
                transcription

        })


    except Exception as e:

        print()
        print(
            "WAKE ERROR:",
            str(e),
            flush=True
        )

        traceback.print_exc()


        return jsonify({

            "status": "error",

            "wake": False,

            "transcription": "",

            "error": str(e)

        }), 500


# =====================================================
# UPLOAD AUDIO
# =====================================================

@app.route("/uploadAudio", methods=["POST"])
def upload_audio():

    print()
    print("========================================")
    print("NEW ESP32 AUDIO REQUEST")
    print("========================================")


    try:

        # -------------------------------------------------
        # READ RAW BODY
        # -------------------------------------------------

        wav_data = request.get_data()


        print(
            "Received bytes:",
            len(wav_data),
            flush=True
        )


        if not wav_data:

            return jsonify({

                "status": "error",

                "transcription": "",

                "ai_reply": "",

                "error":
                    "No audio received"

            }), 400


        # -------------------------------------------------
        # SIZE CHECK
        # -------------------------------------------------

        if len(wav_data) > MAX_AUDIO_SIZE:

            return jsonify({

                "status": "error",

                "transcription": "",

                "ai_reply": "",

                "error":
                    "Audio file too large"

            }), 413


        # -------------------------------------------------
        # WAV CHECK
        # -------------------------------------------------

        valid, error = validate_wav(
            wav_data
        )


        if not valid:

            return jsonify({

                "status": "error",

                "transcription": "",

                "ai_reply": "",

                "error": error

            }), 400


        print(
            "WAV header: OK",
            flush=True
        )


        # -------------------------------------------------
        # TRANSCRIPTION
        # -------------------------------------------------

        try:

            transcription = transcribe_audio(
                wav_data,
                wake_mode=False
            )


        except Exception as e:

            print()
            print(
                "WHISPER ERROR:",
                str(e),
                flush=True
            )

            traceback.print_exc()


            return jsonify({

                "status": "error",

                "transcription": "",

                "ai_reply": "",

                "error":
                    "Speech recognition failed: "
                    + str(e)

            }), 500


        # -------------------------------------------------
        # EMPTY SPEECH
        # -------------------------------------------------

        if not transcription:

            return jsonify({

                "status": "success",

                "transcription": "",

                "ai_reply":
                    "Mujhe aapki awaaz clear nahi mili, please dobara bolo."

            })


        print()
        print(
            "USER:",
            transcription,
            flush=True
        )


        # -------------------------------------------------
        # AI RESPONSE
        # -------------------------------------------------

        try:

            ai_reply = generate_reply(
                transcription
            )


        except Exception as e:

            print()
            print(
                "AI ERROR:",
                str(e),
                flush=True
            )

            traceback.print_exc()


            return jsonify({

                "status": "error",

                "transcription":
                    transcription,

                "ai_reply": "",

                "error":
                    "AI response failed: "
                    + str(e)

            }), 500


        # -------------------------------------------------
        # FINAL RESULT
        # -------------------------------------------------

        print()
        print("========================================")
        print("FINAL RESULT")
        print("========================================")


        print(
            "Text:",
            transcription,
            flush=True
        )


        print(
            "AI:",
            ai_reply,
            flush=True
        )


        print(
            "========================================",
            flush=True
        )


        # -------------------------------------------------
        # RESPONSE TO ESP32
        # -------------------------------------------------

        return jsonify({

            "status": "success",

            "transcription":
                transcription,

            "ai_reply":
                ai_reply

        })


    except Exception as e:

        print()
        print("========================================")
        print("SERVER ERROR")
        print("========================================")


        print(
            str(e),
            flush=True
        )


        traceback.print_exc()


        return jsonify({

            "status": "error",

            "transcription": "",

            "ai_reply": "",

            "error": str(e)

        }), 500


# =====================================================
# AI
# =====================================================

def generate_reply(user_text):

    system_prompt = """

You are a friendly voice assistant running on an ESP32.

The user can speak:

1. English
2. Hindi
3. Hinglish
4. Roman Hindi
5. Hindi + English mixed
6. English + Hindi mixed

IMPORTANT LANGUAGE RULES:

- Reply in the SAME language/style as the user.
- English input -> English reply.
- Hindi spoken/written in Devanagari -> Hindi Devanagari reply.
- Roman Hindi -> Roman Hindi.
- Hinglish -> Hinglish.
- Hindi + English mixed -> naturally mix Hindi and English.

- Do NOT unnecessarily translate.
- Do NOT change Roman Hindi into Devanagari.
- Do NOT change English into Hindi unless the user does so.

- Keep replies short because this is an ESP32 voice assistant.
- Normally answer in 1 to 3 short sentences.
- Be natural and conversational.
- Understand spelling mistakes caused by speech recognition.
- If the transcription is slightly wrong, infer the most likely meaning.

Examples:

User:
hello how are you

Assistant:
I'm good! How can I help you?

User:
tum kaise ho

Assistant:
Main bilkul theek hoon! Aap kaise ho?

User:
bhai tum kaise ho

Assistant:
Main bilkul theek hoon bhai! Batao kya help chahiye?

User:
what is esp32

Assistant:
ESP32 ek powerful microcontroller hai with built-in WiFi and Bluetooth.

User:
ESP32 kya hai

Assistant:
ESP32 ek powerful microcontroller hai jisme WiFi aur Bluetooth built-in hota hai.

User:
mujhe weather batao

Assistant:
Bilkul! Aap kis city ka weather jaana chahte ho?

User:
what is wifi

Assistant:
WiFi ek wireless technology hai jo devices ko internet ya local network se connect karti hai.

Now respond naturally to the user's exact message.

"""


    response = (
        groq_client
        .chat
        .completions
        .create(

            model=CHAT_MODEL,

            messages=[

                {
                    "role": "system",
                    "content": system_prompt
                },

                {
                    "role": "user",
                    "content": user_text
                }

            ],

            temperature=0.2,

            max_tokens=150
        )
    )


    reply = (
        response
        .choices[0]
        .message
        .content
    )


    if not reply:

        return (
            "Sorry, mujhe samajh nahi aaya."
        )


    return reply.strip()


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
    print("========================================")
    print("ESP32 VOICE AI SERVER")
    print("========================================")


    print(
        "Port:",
        port
    )


    print(
        "Wake endpoint:",
        "/wake"
    )


    print(
        "Upload endpoint:",
        "/uploadAudio"
    )


    print(
        "Whisper:",
        WHISPER_MODEL
    )


    print(
        "Chat:",
        CHAT_MODEL
    )


    print(
        "Groq:",
        "READY"
        if groq_client
        else "MISSING"
    )


    print(
        "========================================"
    )


    app.run(
        host="0.0.0.0",
        port=port
    )

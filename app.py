from flask import Flask, request, jsonify, Response
import os
import requests
import re
import tempfile
import time

app = Flask(__name__)

# =====================================================
# CONFIG
# =====================================================

AI_API_KEY = os.environ.get("AI_API_KEY")

AI_URL = os.environ.get(
    "AI_URL",
    "https://api.groq.com/openai/v1/chat/completions"
)

# Fast model
AI_MODEL = os.environ.get(
    "AI_MODEL",
    "llama-3.1-8b-instant"
)

# =====================================================
# STT
# =====================================================

STT_URL = os.environ.get(
    "STT_URL",
    "https://api.groq.com/openai/v1/audio/transcriptions"
)

STT_MODEL = os.environ.get(
    "STT_MODEL",
    "whisper-large-v3-turbo"
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

# FEMALE VOICE
TTS_VOICE = os.environ.get(
    "TTS_VOICE",
    "autumn"
)

# Groq Orpheus max input is 200 chars
TTS_MAX_CHARS = 200

# Fast but still natural
TTS_SPEED = float(
    os.environ.get(
        "TTS_SPEED",
        "1.12"
    )
)

TTS_SAMPLE_RATE = 16000


# =====================================================
# HOME
# =====================================================

@app.route("/", methods=["GET"])
def home():

    print("\n========================================")
    print("HOME REQUEST")
    print("========================================")

    return "ESP32 Female Voice Server is ONLINE!"


# =====================================================
# HEALTH
# =====================================================

@app.route("/health", methods=["GET"])
def health():

    data = {
        "status": "online",

        "speech_engine": "Groq Whisper",
        "speech_model": STT_MODEL,

        "ai_engine": "Groq",
        "ai_model": AI_MODEL,

        "tts_engine": "Groq Orpheus",
        "tts_model": TTS_MODEL,
        "tts_voice": TTS_VOICE,
        "tts_speed": TTS_SPEED,
        "tts_sample_rate": TTS_SAMPLE_RATE
    }

    print("\n========================================")
    print("HEALTH")
    print("========================================")
    print(data)

    return jsonify(data)


# =====================================================
# WAKE
# =====================================================

@app.route("/wake", methods=["POST", "GET"])
def wake():

    print("\n========================================")
    print("WAKE REQUEST RECEIVED")
    print("========================================")

    audio_data = request.get_data()

    print("METHOD:", request.method)
    print("CONTENT TYPE:", request.content_type)
    print("AUDIO BYTES:", len(audio_data))

    response_data = {
        "status": "ok",
        "wake": True,
        "english": "Hello",
        "hindi": None
    }

    print("WAKE RESPONSE:", response_data)
    print("========================================")

    return jsonify(response_data)


# =====================================================
# TEST
# =====================================================

@app.route("/test", methods=["POST"])
def test():

    data = request.get_json(silent=True)

    print("\n========================================")
    print("TEST REQUEST")
    print("========================================")
    print("DATA:", data)

    if not data:

        return jsonify({
            "status": "error",
            "message": "No JSON received"
        }), 400

    return jsonify({
        "status": "ok",
        "message": "Data received",
        "data": data
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
# STT
# =====================================================

def transcribe_audio(filename):

    if not AI_API_KEY:

        print("STT ERROR: AI_API_KEY missing")

        return None

    try:

        print("\n========================================")
        print("STT REQUEST")
        print("========================================")

        start_time = time.time()

        headers = {
            "Authorization": "Bearer " + AI_API_KEY,
            "Accept": "application/json"
        }

        with open(
            filename,
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
                "model": STT_MODEL,
                "response_format": "json",
                "temperature": "0"
            }

            response = requests.post(
                STT_URL,
                headers=headers,
                files=files,
                data=data,
                timeout=15
            )

        elapsed = time.time() - start_time

        print("STT HTTP:", response.status_code)
        print("STT TIME:", round(elapsed, 3), "seconds")

        if response.status_code != 200:

            print("STT ERROR BODY:")
            print(response.text[:3000])

            print("========================================")

            return None

        result = response.json()

        text = result.get(
            "text",
            ""
        )

        text = clean_text(text)

        print("TRANSCRIPTION:", text)
        print("========================================")

        if not is_valid_query(text):
            return None

        return text

    except requests.exceptions.Timeout:

        print("STT TIMEOUT")
        return None

    except requests.exceptions.ConnectionError:

        print("STT CONNECTION ERROR")
        return None

    except Exception as e:

        print(
            "STT EXCEPTION:",
            type(e).__name__,
            str(e)
        )

        return None


# =====================================================
# AI
# =====================================================

def get_ai_reply(user_text):

    user_text = clean_text(user_text)

    if not AI_API_KEY:

        return "AI response nahi mil saka."

    if not is_valid_query(user_text):

        return "Please ask your question again."

    system_prompt = """
You are a very fast bilingual voice assistant.

Understand Hindi, English and Hinglish.

Reply in the same natural language style as the user.

Hindi user -> Hindi.
English user -> English.
Hinglish user -> natural Hinglish.

Keep answers extremely short and conversational.

Usually one sentence.
Maximum around 100 characters when possible.

No markdown.
No bullets.
No emojis.
No unnecessary explanation.
Do not repeat the question.
Do not mention AI.

Sound like a friendly female voice assistant.
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
                "content": user_text
            }
        ],

        "temperature": 0.2,

        "max_completion_tokens": 60,

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

    try:

        print("\n========================================")
        print("AI REQUEST")
        print("========================================")

        print("MODEL:", AI_MODEL)
        print("USER:", user_text)

        start_time = time.time()

        response = requests.post(
            AI_URL,
            headers=headers,
            json=payload,
            timeout=15
        )

        elapsed = time.time() - start_time

        print(
            "AI HTTP:",
            response.status_code
        )

        print(
            "AI TIME:",
            round(elapsed, 3),
            "seconds"
        )

        if response.status_code != 200:

            print("AI ERROR BODY:")
            print(response.text[:3000])

            print("========================================")

            return "AI response nahi mil saka."

        data = response.json()

        choices = data.get("choices")

        if not choices:

            print("AI ERROR: choices missing")
            return "AI response nahi mil saka."

        message = choices[0].get(
            "message",
            {}
        )

        reply = message.get(
            "content",
            ""
        )

        if reply is None:
            reply = ""

        reply = str(reply).strip()

        reply = reply.replace(
            "```",
            ""
        ).strip()

        prefixes = [
            "AI:",
            "Answer:",
            "Response:"
        ]

        for prefix in prefixes:

            if reply.startswith(prefix):

                reply = reply[
                    len(prefix):
                ].strip()

        if not reply:

            return "AI response nahi mil saka."

        print("AI REPLY:", reply)
        print("========================================")

        return reply

    except requests.exceptions.Timeout:

        print("AI TIMEOUT")
        return "AI response nahi mil saka."

    except requests.exceptions.ConnectionError:

        print("AI CONNECTION ERROR")
        return "AI response nahi mil saka."

    except Exception as e:

        print(
            "AI EXCEPTION:",
            type(e).__name__,
            str(e)
        )

        return "AI response nahi mil saka."


# =====================================================
# TTS
# =====================================================

def generate_tts(text):

    text = clean_text(text)

    if not text:
        return None

    if not AI_API_KEY:

        print("TTS ERROR: AI_API_KEY missing")

        return None

    # Maximum 200 chars
    if len(text) > TTS_MAX_CHARS:

        text = text[:TTS_MAX_CHARS]

        last_dot = text.rfind(".")

        if last_dot > 40:

            text = text[:last_dot + 1]

    payload = {
        "model": TTS_MODEL,

        "voice": TTS_VOICE,

        "input": text,

        "response_format": "wav",

        "sample_rate": TTS_SAMPLE_RATE,

        "speed": TTS_SPEED
    }

    headers = {
        "Authorization":
            "Bearer " + AI_API_KEY,

        "Content-Type":
            "application/json",

        "Accept":
            "audio/wav"
    }

    try:

        print("\n========================================")
        print("TTS REQUEST")
        print("========================================")

        print("TTS MODEL:", TTS_MODEL)
        print("TTS VOICE:", TTS_VOICE)
        print("TTS SPEED:", TTS_SPEED)
        print("TTS SAMPLE RATE:", TTS_SAMPLE_RATE)
        print("TTS TEXT:", text)

        start_time = time.time()

        response = requests.post(
            TTS_URL,
            headers=headers,
            json=payload,
            timeout=20
        )

        elapsed = time.time() - start_time

        print(
            "TTS HTTP:",
            response.status_code
        )

        print(
            "TTS TIME:",
            round(elapsed, 3),
            "seconds"
        )

        if response.status_code != 200:

            print("TTS ERROR BODY:")
            print(response.text[:3000])

            print("========================================")

            return None

        audio_data = response.content

        print(
            "TTS AUDIO BYTES:",
            len(audio_data)
        )

        if not audio_data:

            print("TTS ERROR: empty audio")

            return None

        print("TTS SUCCESS")
        print("========================================")

        return audio_data

    except requests.exceptions.Timeout:

        print("TTS TIMEOUT")
        return None

    except requests.exceptions.ConnectionError:

        print("TTS CONNECTION ERROR")
        return None

    except Exception as e:

        print(
            "TTS EXCEPTION:",
            type(e).__name__,
            str(e)
        )

        return None


# =====================================================
# TTS ENDPOINT
# =====================================================

@app.route("/tts", methods=["POST"])
def tts():

    start_time = time.time()

    print("\n========================================")
    print("ESP32 TTS ENDPOINT")
    print("========================================")

    try:

        data = request.get_json(
            silent=True
        )

        print("JSON:", data)

        if not data:

            return jsonify({
                "status": "error",
                "message": "No JSON received"
            }), 400

        text = clean_text(
            data.get("text")
        )

        print("TEXT:", text)

        if not text:

            return jsonify({
                "status": "error",
                "message": "No text received"
            }), 400

        audio_data = generate_tts(text)

        if audio_data is None:

            return jsonify({
                "status": "error",
                "message": "TTS generation failed"
            }), 500

        total_time = time.time() - start_time

        print(
            "TOTAL TTS ENDPOINT TIME:",
            round(total_time, 3),
            "seconds"
        )

        print("========================================")

        return Response(
            audio_data,
            status=200,
            mimetype="audio/wav",
            headers={
                "Cache-Control": "no-cache",
                "Content-Length":
                    str(len(audio_data)),
                "Connection": "close"
            }
        )

    except Exception as e:

        print(
            "TTS SERVER ERROR:",
            type(e).__name__,
            str(e)
        )

        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


# =====================================================
# UPLOAD AUDIO
# =====================================================

@app.route("/uploadAudio", methods=["POST"])
def upload_audio():

    filename = None

    total_start = time.time()

    print("\n")
    print("========================================")
    print("NEW AUDIO REQUEST")
    print("========================================")

    try:

        audio_data = request.get_data()

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

            print("ERROR: NO AUDIO")

            return jsonify({
                "status": "error",
                "message": "No audio received",
                "transcription": None,
                "hindi_transcription": None,
                "english_transcription": None,
                "ai_reply":
                    "Please ask your question again."
            }), 400

        # =================================================
        # SAVE AUDIO
        # =================================================

        save_start = time.time()

        fd, filename = tempfile.mkstemp(
            suffix=".wav"
        )

        os.close(fd)

        with open(
            filename,
            "wb"
        ) as f:

            f.write(audio_data)

        print(
            "WAV SAVED:",
            filename
        )

        print(
            "SAVE TIME:",
            round(
                time.time() - save_start,
                3
            ),
            "seconds"
        )

        # =================================================
        # STT
        # =================================================

        stt_start = time.time()

        transcription = transcribe_audio(
            filename
        )

        stt_time = time.time() - stt_start

        print(
            "STT TOTAL:",
            round(stt_time, 3),
            "seconds"
        )

        if not is_valid_query(
            transcription
        ):

            print(
                "ERROR: SPEECH NOT UNDERSTOOD"
            )

            return jsonify({
                "status": "error",
                "message":
                    "Speech not understood",

                "transcription": None,

                "hindi_transcription": None,

                "english_transcription": None,

                "ai_reply":
                    "Please ask your question again."
            }), 400

        # =================================================
        # AI
        # =================================================

        ai_start = time.time()

        ai_reply = get_ai_reply(
            transcription
        )

        ai_time = time.time() - ai_start

        print(
            "AI TOTAL:",
            round(ai_time, 3),
            "seconds"
        )

        # =================================================
        # TOTAL
        # =================================================

        total_time = (
            time.time() -
            total_start
        )

        response_data = {

            "status":
                "ok",

            "transcription":
                transcription,

            "hindi_transcription":
                transcription,

            "english_transcription":
                transcription,

            "ai_reply":
                ai_reply,

            "stt_time":
                round(stt_time, 3),

            "ai_time":
                round(ai_time, 3),

            "processing_time":
                round(total_time, 3)
        }

        print("\n========================================")
        print("FINAL RESPONSE")
        print("========================================")

        print(
            "TRANSCRIPTION:",
            transcription
        )

        print(
            "AI REPLY:",
            ai_reply
        )

        print(
            "STT TIME:",
            round(stt_time, 3),
            "sec"
        )

        print(
            "AI TIME:",
            round(ai_time, 3),
            "sec"
        )

        print(
            "TOTAL:",
            round(total_time, 3),
            "sec"
        )

        print("========================================")

        return jsonify(
            response_data
        )

    except Exception as e:

        print("\n========================================")
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

    finally:

        if filename:

            try:

                if os.path.exists(
                    filename
                ):

                    os.remove(
                        filename
                    )

                    print(
                        "TEMP WAV DELETED"
                    )

            except Exception as e:

                print(
                    "TEMP FILE DELETE ERROR:",
                    str(e)
                )


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
    print("ESP32 FEMALE VOICE ASSISTANT")
    print("========================================")

    print("PORT:", port)

    print("STT MODEL:", STT_MODEL)

    print("AI MODEL:", AI_MODEL)

    print("TTS MODEL:", TTS_MODEL)

    print("TTS VOICE:", TTS_VOICE)

    print("TTS SPEED:", TTS_SPEED)

    print("TTS SAMPLE RATE:", TTS_SAMPLE_RATE)

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

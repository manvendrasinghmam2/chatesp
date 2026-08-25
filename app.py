from flask import Flask, request, jsonify, Response
import os
import speech_recognition as sr
import requests
import re
import tempfile
import traceback


app = Flask(__name__)


# ============================================================
# CONFIG
# ============================================================

AI_API_KEY = os.environ.get("AI_API_KEY")

AI_URL = os.environ.get(
    "AI_URL",
    "https://api.groq.com/openai/v1/chat/completions"
)

AI_MODEL = os.environ.get(
    "AI_MODEL",
    "openai/gpt-oss-20b"
)


# ============================================================
# GROQ TTS
# ============================================================

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
    "hannah"
)

TTS_MAX_CHARS = 200


# ============================================================
# APP
# ============================================================

@app.route("/", methods=["GET"])
def home():

    return "ESP32 Voice Server is ONLINE!"


# ============================================================
# HEALTH
# ============================================================

@app.route("/health", methods=["GET"])
def health():

    return jsonify({
        "status": "online",
        "speech_engine": "Google Speech Recognition",
        "ai_engine": "Groq",
        "model": AI_MODEL,
        "tts_engine": "Groq Orpheus",
        "tts_model": TTS_MODEL,
        "tts_voice": TTS_VOICE
    })


# ============================================================
# BASIC TEST
# ============================================================

@app.route("/test", methods=["POST"])
def test():

    try:

        data = request.get_json(silent=True)

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

    except Exception as e:

        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


# ============================================================
# WAKE
# ============================================================

@app.route("/wake", methods=["POST", "GET"])
def wake():

    print()
    print("========================================")
    print("WAKE REQUEST RECEIVED")
    print("========================================")

    try:

        audio_data = request.get_data()

        print(
            "AUDIO BYTES:",
            len(audio_data)
        )

        response_data = {
            "status": "ok",
            "wake": True,
            "english": "Hello",
            "hindi": None
        }

        print(
            "WAKE RESPONSE:",
            response_data
        )

        print("========================================")

        return jsonify(response_data)

    except Exception as e:

        print(
            "WAKE ERROR:",
            str(e)
        )

        traceback.print_exc()

        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


# ============================================================
# CLEAN TEXT
# ============================================================

def clean_text(text):

    if text is None:
        return ""

    text = str(text)

    text = text.strip()

    text = text.replace("```", "")

    text = re.sub(
        r"[\r\n]+",
        " ",
        text
    )

    text = re.sub(
        r"\s+",
        " ",
        text
    )

    return text.strip()


# ============================================================
# DETECT DEVANAGARI
# ============================================================

def contains_devanagari(text):

    if not text:
        return False

    return bool(
        re.search(
            r"[\u0900-\u097F]",
            str(text)
        )
    )


# ============================================================
# HAS LETTER / DIGIT
# ============================================================

def has_letter_or_digit(text):

    if not text:
        return False

    return bool(
        re.search(
            r"[A-Za-z0-9]",
            str(text)
        )
    )


# ============================================================
# SAFE ENGLISH TTS TEXT
# ============================================================

def clean_tts_text(text):

    text = clean_text(text)

    if not text:
        return ""

    # --------------------------------------------------------
    # Prefixes
    # --------------------------------------------------------

    prefixes = [
        "AI:",
        "Answer:",
        "Response:",
        "Assistant:",
        "Diana:"
    ]

    for prefix in prefixes:

        if text.lower().startswith(
            prefix.lower()
        ):

            text = text[
                len(prefix):
            ].strip()

    # --------------------------------------------------------
    # Markdown
    # --------------------------------------------------------

    text = text.replace(
        "**",
        ""
    )

    text = text.replace(
        "__",
        ""
    )

    text = text.replace(
        "*",
        ""
    )

    # --------------------------------------------------------
    # IMPORTANT:
    #
    # DO NOT silently delete Hindi.
    #
    # If Devanagari is still present here,
    # caller must convert it first.
    # --------------------------------------------------------

    if contains_devanagari(text):

        print(
            "TTS CLEAN: DEVANAGARI DETECTED"
        )

        return ""

    # --------------------------------------------------------
    # Keep only ASCII
    # --------------------------------------------------------

    text = re.sub(
        r"[^\x00-\x7F]+",
        " ",
        text
    )

    text = re.sub(
        r"\s+",
        " ",
        text
    )

    text = text.strip()

    # --------------------------------------------------------
    # Remove punctuation-only text
    # --------------------------------------------------------

    if not has_letter_or_digit(text):

        print(
            "TTS CLEAN: NO LETTER/DIGIT"
        )

        return ""

    # --------------------------------------------------------
    # Maximum 200 characters
    # --------------------------------------------------------

    if len(text) > TTS_MAX_CHARS:

        text = text[
            :TTS_MAX_CHARS
        ]

        positions = [
            text.rfind("."),
            text.rfind("?"),
            text.rfind("!"),
            text.rfind(",")
        ]

        best = max(positions)

        if best >= 40:

            text = text[
                :best + 1
            ]

    return text.strip()


# ============================================================
# VALID QUERY
# ============================================================

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


# ============================================================
# AI REQUEST
# ============================================================

def call_ai_chat(
    system_prompt,
    user_content,
    temperature=0.2,
    max_tokens=200
):

    if not AI_API_KEY:

        print(
            "AI ERROR: AI_API_KEY missing"
        )

        return ""

    payload = {

        "model":
            AI_MODEL,

        "messages": [

            {
                "role": "system",
                "content": system_prompt
            },

            {
                "role": "user",
                "content": user_content
            }
        ],

        "temperature":
            temperature,

        "max_completion_tokens":
            max_tokens,

        "stream":
            False
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

        if response.status_code != 200:

            print(
                "AI SERVER ERROR:"
            )

            print(
                response.text[:3000]
            )

            return ""

        try:

            data = response.json()

        except Exception as e:

            print(
                "AI JSON ERROR:",
                str(e)
            )

            return ""

        choices = data.get(
            "choices"
        )

        if not choices:

            print(
                "AI ERROR: choices missing"
            )

            print(data)

            return ""

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

        reply = clean_text(reply)

        prefixes = [
            "AI:",
            "Answer:",
            "Response:",
            "Assistant:",
            "Diana:"
        ]

        for prefix in prefixes:

            if reply.lower().startswith(
                prefix.lower()
            ):

                reply = reply[
                    len(prefix):
                ].strip()

        return reply

    except requests.exceptions.Timeout:

        print(
            "AI TIMEOUT"
        )

        return ""

    except requests.exceptions.ConnectionError as e:

        print(
            "AI CONNECTION ERROR:",
            str(e)
        )

        return ""

    except Exception as e:

        print(
            "AI EXCEPTION:",
            type(e).__name__,
            str(e)
        )

        traceback.print_exc()

        return ""


# ============================================================
# GET AI REPLY
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

    if not AI_API_KEY:

        print(
            "AI ERROR: AI_API_KEY missing"
        )

        return "No AI response. Try again."

    if (
        not is_valid_query(hindi_text)
        and
        not is_valid_query(english_text)
    ):

        return (
            "Please ask your question again."
        )

    system_prompt = """
You are Diana, a concise bilingual voice assistant running
on an ESP32.

The user's speech may be:
English, Hindi, Hinglish, or Roman Hindi.

Understand the intended meaning from the recognition results.

STRICT LANGUAGE RULE:

NEVER use Devanagari Hindi script.

If the user speaks Hindi:
reply ONLY in Roman Hindi using English letters.

If the user speaks Hinglish:
reply in natural Hinglish.

If the user speaks English:
reply in natural English.

Examples:

User: Aap kaise ho?
Answer: Main bilkul theek hoon. Aap kaise hain?

User: Mujhe time batao.
Answer: Bilkul, main aapko time bata deta hoon.

User: What is the capital of India?
Answer: The capital of India is New Delhi.

VOICE RULES:

Keep answers short.

Usually one or two sentences.

Maximum about 150 characters when possible.

No markdown.

No bullet points.

No emojis.

No headings.

Do not repeat the question.

Do not say "As an AI".

Sound natural and conversational.

IMPORTANT:
The answer will be sent directly to an English TTS engine.
Therefore NEVER output Hindi characters such as:
अ आ इ ई उ ए ओ क ख ग
or any Devanagari script.

Return ONLY the answer.
"""

    user_content = f"""
Hindi speech recognition:
{hindi_text if hindi_text else "No result"}

English speech recognition:
{english_text if english_text else "No result"}

Determine the intended meaning and answer naturally.
"""

    print()
    print("========================================")
    print("AI REQUEST")
    print("========================================")

    print(
        "HINDI INPUT:",
        hindi_text
    )

    print(
        "ENGLISH INPUT:",
        english_text
    )

    reply = call_ai_chat(
        system_prompt,
        user_content,
        temperature=0.15,
        max_tokens=200
    )

    if not reply:

        return (
            "No AI response. Try again."
        )

    print()
    print("AI REPLY:")
    print(reply)

    # --------------------------------------------------------
    # SAFETY CHECK
    # --------------------------------------------------------

    if contains_devanagari(reply):

        print()
        print(
            "WARNING: AI RETURNED DEVANAGARI"
        )

        print(
            "Starting ROMANIZATION FALLBACK..."
        )

        romanized = romanize_hindi(
            reply
        )

        if romanized:

            reply = romanized

            print(
                "ROMANIZED AI REPLY:"
            )

            print(reply)

        else:

            print(
                "ROMANIZATION FAILED"
            )

            # Safe fallback so TTS doesn't receive Hindi
            reply = (
                "Okay, I understand."
            )

    print("========================================")

    return reply


# ============================================================
# ROMANIZE HINDI
# ============================================================

def romanize_hindi(text):

    text = clean_text(text)

    if not text:
        return ""

    print()
    print("========================================")
    print("HINDI ROMANIZATION")
    print("========================================")

    print(
        "ORIGINAL:",
        text
    )

    system_prompt = """
You convert Hindi written in Devanagari into natural Roman Hindi.

Rules:

1. Convert Hindi Devanagari to English/Roman letters.
2. Preserve the exact meaning.
3. Do NOT translate the meaning into unrelated English.
4. Make it easy for an English TTS voice to pronounce.
5. Do not use Devanagari.
6. Do not add explanations.
7. Return ONLY the Roman Hindi sentence.

Examples:

ठीक है.
Theek hai.

मैं आपकी मदद कर सकता हूँ.
Main aapki madad kar sakta hoon.

आप कैसे हैं?
Aap kaise hain?

बहुत अच्छा.
Bahut achha.
"""

    user_content = f"""
Convert this text to natural Roman Hindi:

{text}
"""

    result = call_ai_chat(
        system_prompt,
        user_content,
        temperature=0.0,
        max_tokens=120
    )

    result = clean_text(
        result
    )

    if not result:

        print(
            "ROMANIZATION: EMPTY"
        )

        return ""

    if contains_devanagari(result):

        print(
            "ROMANIZATION FAILED: STILL DEVANAGARI"
        )

        print(
            "RESULT:",
            result
        )

        return ""

    if not has_letter_or_digit(result):

        print(
            "ROMANIZATION FAILED: NO LETTER/DIGIT"
        )

        return ""

    print(
        "ROMANIZED:",
        result
    )

    print("========================================")

    return result


# ============================================================
# PREPARE TTS TEXT
# ============================================================

def prepare_tts_text(text):

    text = clean_text(text)

    print()
    print("========================================")
    print("PREPARE TTS TEXT")
    print("========================================")

    print(
        "INPUT:",
        text
    )

    if not text:

        print(
            "TTS PREPARE: EMPTY"
        )

        return ""

    # --------------------------------------------------------
    # Hindi detected
    # --------------------------------------------------------

    if contains_devanagari(text):

        print(
            "TTS PREPARE: HINDI DETECTED"
        )

        text = romanize_hindi(
            text
        )

        if not text:

            print(
                "TTS PREPARE: ROMANIZATION FAILED"
            )

            return ""

    # --------------------------------------------------------
    # Clean
    # --------------------------------------------------------

    text = clean_tts_text(
        text
    )

    if not text:

        print(
            "TTS PREPARE: INVALID AFTER CLEAN"
        )

        return ""

    if contains_devanagari(text):

        print(
            "TTS PREPARE: DEVANAGARI STILL PRESENT"
        )

        return ""

    if not has_letter_or_digit(text):

        print(
            "TTS PREPARE: NO LETTER OR DIGIT"
        )

        return ""

    # --------------------------------------------------------
    # 200 character limit
    # --------------------------------------------------------

    if len(text) > TTS_MAX_CHARS:

        text = text[
            :TTS_MAX_CHARS
        ]

    print(
        "FINAL TTS TEXT:",
        text
    )

    print(
        "TTS CHARACTERS:",
        len(text)
    )

    print("========================================")

    return text


# ============================================================
# GENERATE TTS
# ============================================================

def generate_tts(text):

    print()
    print("========================================")
    print("TTS REQUEST")
    print("========================================")

    original_text = clean_text(
        text
    )

    print(
        "ORIGINAL TTS TEXT:",
        original_text
    )

    # --------------------------------------------------------
    # Prepare text
    # --------------------------------------------------------

    text = prepare_tts_text(
        original_text
    )

    if not text:

        print(
            "TTS ERROR: Could not prepare text"
        )

        return None

    print(
        "TTS TEXT:",
        text
    )

    print(
        "TTS MODEL:",
        TTS_MODEL
    )

    print(
        "TTS VOICE:",
        TTS_VOICE
    )

    # --------------------------------------------------------
    # API key
    # --------------------------------------------------------

    if not AI_API_KEY:

        print(
            "TTS ERROR: AI_API_KEY missing"
        )

        return None

    # --------------------------------------------------------
    # Final safety
    # --------------------------------------------------------

    if contains_devanagari(text):

        print(
            "TTS BLOCKED: DEVANAGARI"
        )

        return None

    if not has_letter_or_digit(text):

        print(
            "TTS BLOCKED: NO LETTER/DIGIT"
        )

        return None

    # --------------------------------------------------------
    # Payload
    # --------------------------------------------------------

    payload = {

        "model":
            TTS_MODEL,

        "input":
            text,

        "voice":
            TTS_VOICE,

        "response_format":
            "wav"
    }

    headers = {

        "Authorization":
            "Bearer " + AI_API_KEY,

        "Content-Type":
            "application/json",

        "Accept":
            "audio/wav"
    }

    print()
    print(
        "TTS PAYLOAD:"
    )

    print(
        payload
    )

    print(
        "SENDING TTS REQUEST..."
    )

    try:

        response = requests.post(

            TTS_URL,

            headers=headers,

            json=payload,

            timeout=60
        )

        print()
        print(
            "TTS HTTP:",
            response.status_code
        )

        print(
            "TTS CONTENT TYPE:",
            response.headers.get(
                "Content-Type"
            )
        )

        print(
            "TTS CONTENT LENGTH:",
            response.headers.get(
                "Content-Length",
                "-1"
            )
        )

        # ----------------------------------------------------
        # SUCCESS
        # ----------------------------------------------------

        if response.status_code == 200:

            audio_data = response.content

            print(
                "TTS AUDIO BYTES:",
                len(audio_data)
            )

            if not audio_data:

                print(
                    "TTS ERROR: EMPTY AUDIO"
                )

                return None

            # WAV validation
            if len(audio_data) >= 12:

                print(
                    "TTS HEADER:",
                    audio_data[:12]
                )

                if (
                    audio_data[0:4] != b"RIFF"
                    or
                    audio_data[8:12] != b"WAVE"
                ):

                    print(
                        "WARNING: RESPONSE IS NOT NORMAL WAV"
                    )

            print(
                "TTS SUCCESS"
            )

            print("========================================")

            return audio_data

        # ----------------------------------------------------
        # ERROR
        # ----------------------------------------------------

        print()
        print("========================================")
        print("TTS SERVER ERROR")
        print("========================================")

        print(
            "HTTP CODE:",
            response.status_code
        )

        print(
            "RESPONSE HEADERS:"
        )

        for key, value in response.headers.items():

            print(
                key,
                ":",
                value
            )

        try:

            print(
                "ERROR BODY:",
                response.text[:5000]
            )

        except Exception:

            print(
                "Could not read error body."
            )

        print("========================================")

        return None

    except requests.exceptions.Timeout:

        print(
            "TTS TIMEOUT"
        )

        return None

    except requests.exceptions.ConnectionError as e:

        print(
            "TTS CONNECTION ERROR:",
            str(e)
        )

        return None

    except Exception as e:

        print(
            "TTS EXCEPTION:",
            type(e).__name__,
            str(e)
        )

        traceback.print_exc()

        return None


# ============================================================
# TTS ENDPOINT
# ============================================================

@app.route("/tts", methods=["POST"])
def tts():

    print()
    print("========================================")
    print("TTS ENDPOINT")
    print("========================================")

    try:

        data = request.get_json(
            silent=True
        )

        if not data:

            print(
                "TTS: NO JSON RECEIVED"
            )

            return jsonify({
                "status": "error",
                "message": "No JSON received"
            }), 400

        print(
            "TTS JSON:",
            data
        )

        text = clean_text(
            data.get("text")
        )

        if not text:

            return jsonify({
                "status": "error",
                "message": "No text received"
            }), 400

        audio_data = generate_tts(
            text
        )

        if audio_data is None:

            return jsonify({
                "status": "error",
                "message": "TTS generation failed"
            }), 500

        # ----------------------------------------------------
        # IMPORTANT:
        # Explicit Content-Length
        # ----------------------------------------------------

        return Response(

            audio_data,

            status=200,

            mimetype="audio/wav",

            headers={

                "Content-Type":
                    "audio/wav",

                "Content-Length":
                    str(len(audio_data)),

                "Cache-Control":
                    "no-cache",

                "Connection":
                    "close",

                "Content-Disposition":
                    "inline; filename=speech.wav"
            }
        )

    except Exception as e:

        print(
            "TTS SERVER EXCEPTION:",
            type(e).__name__,
            str(e)
        )

        traceback.print_exc()

        return jsonify({

            "status":
                "error",

            "message":
                str(e)

        }), 500


# ============================================================
# DIRECT TTS TEST - ENGLISH
# ============================================================

@app.route("/test-tts", methods=["GET"])
def test_tts():

    print()
    print("========================================")
    print("DIRECT TTS TEST")
    print("========================================")

    test_text = (
        "Hello, I am Diana. "
        "How can I help you?"
    )

    audio_data = generate_tts(
        test_text
    )

    if audio_data is None:

        return jsonify({

            "status":
                "error",

            "message":
                "TTS test failed"

        }), 500

    return Response(

        audio_data,

        status=200,

        mimetype="audio/wav",

        headers={

            "Content-Type":
                "audio/wav",

            "Content-Length":
                str(len(audio_data)),

            "Cache-Control":
                "no-cache",

            "Connection":
                "close",

            "Content-Disposition":
                "inline; filename=diana-test.wav"
        }
    )


# ============================================================
# DIRECT HINDI TTS TEST
# ============================================================

@app.route("/test-hindi-tts", methods=["GET"])
def test_hindi_tts():

    print()
    print("========================================")
    print("HINDI TTS TEST")
    print("========================================")

    test_text = "ठीक है, मैं आपकी मदद कर सकती हूँ."

    print(
        "TEST HINDI:",
        test_text
    )

    audio_data = generate_tts(
        test_text
    )

    if audio_data is None:

        return jsonify({

            "status":
                "error",

            "message":
                "Hindi TTS test failed"

        }), 500

    return Response(

        audio_data,

        status=200,

        mimetype="audio/wav",

        headers={

            "Content-Type":
                "audio/wav",

            "Content-Length":
                str(len(audio_data)),

            "Cache-Control":
                "no-cache",

            "Connection":
                "close",

            "Content-Disposition":
                "inline; filename=hindi-test.wav"
        }
    )


# ============================================================
# UPLOAD AUDIO
# ============================================================

@app.route("/uploadAudio", methods=["POST"])
def upload_audio():

    filename = None

    try:

        print()
        print("========================================")
        print("AUDIO REQUEST RECEIVED")
        print("========================================")

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

        print("========================================")

        if not audio_data:

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

        # ----------------------------------------------------
        # SAVE WAV
        # ----------------------------------------------------

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

        # ----------------------------------------------------
        # SPEECH RECOGNITION
        # ----------------------------------------------------

        recognizer = sr.Recognizer()

        with sr.AudioFile(
            filename
        ) as source:

            audio = recognizer.record(
                source
            )

        hindi_text = None
        english_text = None

        # ----------------------------------------------------
        # HINDI
        # ----------------------------------------------------

        print()
        print("HINDI SPEECH")

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
                    str(e)

            }), 500

        # ----------------------------------------------------
        # ENGLISH
        # ----------------------------------------------------

        print()
        print("ENGLISH SPEECH")

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

                "hindi_transcription":
                    hindi_text,

                "english_transcription":
                    None

            }), 500

        # ----------------------------------------------------
        # VALIDATION
        # ----------------------------------------------------

        if (
            not is_valid_query(hindi_text)
            and
            not is_valid_query(english_text)
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

        # ----------------------------------------------------
        # AI
        # ----------------------------------------------------

        ai_reply = get_ai_reply(

            hindi_text,

            english_text
        )

        # ----------------------------------------------------
        # BEST TRANSCRIPTION
        # ----------------------------------------------------

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

        # ----------------------------------------------------
        # FINAL
        # ----------------------------------------------------

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

    except Exception as e:

        print()
        print("========================================")
        print("SERVER ERROR")
        print("========================================")

        print(
            type(e).__name__,
            str(e)
        )

        traceback.print_exc()

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
                "No AI response. Try again."

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
    print("========================================")
    print("ESP32 VOICE SERVER")
    print("========================================")

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

    print("========================================")

    app.run(

        host="0.0.0.0",

        port=port,

        threaded=True
    )

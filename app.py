from flask import Flask, request, jsonify, send_file
import os
import re
import tempfile
import requests
import speech_recognition as sr

from gtts import gTTS
from pydub import AudioSegment


app = Flask(__name__)


# =====================================================
# CONFIG
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

@app.route("/")
def home():

    return "ESP32 Voice Server is ONLINE!"


# =====================================================
# HEALTH
# =====================================================

@app.route("/health")
def health():

    return jsonify({
        "status": "online",
        "ai_model": AI_MODEL,
        "tts": "gTTS",
        "audio_format": "16-bit PCM WAV"
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
# AI
# =====================================================

def get_ai_reply(
    hindi_text,
    english_text
):

    hindi_text = clean_text(hindi_text)
    english_text = clean_text(english_text)

    if not AI_API_KEY:

        print("AI_API_KEY missing")

        return "AI response nahi mil saka."

    if (
        not is_valid_query(hindi_text)
        and
        not is_valid_query(english_text)
    ):

        return "Please ask your question again."

    system_prompt = """
You are a professional bilingual voice assistant running on an ESP32.

Understand the user's intended language and answer naturally.

If the user speaks English, answer in English.

If the user speaks Hindi, answer in Hindi using Devanagari.

If the user speaks Hinglish, answer naturally in Hinglish.

If Hindi recognition contains phonetic English such as:

हाउ आर यू

and English recognition says:

How are you

then understand that the user intended English.

Compare both recognition results and determine the most likely intended meaning.

Do not mention speech recognition.

Do not mention Hindi or English recognition.

Keep voice responses concise.

Usually 1 to 4 sentences.

Do not use markdown.

Do not use bullet points.

Do not use emojis.

Do not use headings.

Do not repeat the question.

Do not say "As an AI".

Answer naturally as a voice assistant.
"""

    user_content = f"""
Hindi speech recognition:
{hindi_text if hindi_text else "No result"}

English speech recognition:
{english_text if english_text else "No result"}

Determine the intended meaning and answer naturally.
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
                "content": user_content
            }

        ],

        "temperature": 0.2,

        "max_completion_tokens": 200,

        "stream": False
    }

    headers = {

        "Authorization":
            "Bearer " + AI_API_KEY,

        "Content-Type":
            "application/json"
    }

    try:

        print()
        print("==============================")
        print("AI REQUEST")
        print("==============================")

        print("MODEL:", AI_MODEL)

        print("Hindi:", hindi_text)
        print("English:", english_text)

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
                response.text[:2000]
            )

            return "AI response nahi mil saka."

        data = response.json()

        choices = data.get(
            "choices"
        )

        if not choices:

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

        reply = str(
            reply
        ).strip()

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

        print()
        print("==============================")
        print("AI REPLY")
        print("==============================")

        print(reply)

        print("==============================")

        return reply

    except Exception as e:

        print(
            "AI ERROR:",
            type(e).__name__,
            str(e)
        )

        return "AI response nahi mil saka."


# =====================================================
# CREATE WAV TTS
# =====================================================

def create_tts_wav(
    text,
    output_file
):

    text = clean_text(text)

    if not text:

        return False

    try:

        # ---------------------------------------------
        # Decide TTS language
        # ---------------------------------------------

        # Devanagari -> Hindi
        if re.search(
            r"[\u0900-\u097F]",
            text
        ):

            language = "hi"

        else:

            language = "en"

        print()
        print("==============================")
        print("TTS")
        print("==============================")

        print("Language:", language)
        print("Text:", text)

        # ---------------------------------------------
        # Temporary MP3
        # ---------------------------------------------

        fd, mp3_file = tempfile.mkstemp(
            suffix=".mp3"
        )

        os.close(fd)

        try:

            tts = gTTS(
                text=text,
                lang=language,
                slow=False
            )

            tts.save(
                mp3_file
            )

            # -----------------------------------------
            # MP3 -> WAV
            # -----------------------------------------

            audio = AudioSegment.from_mp3(
                mp3_file
            )

            # ESP32 friendly format:
            #
            # 16 kHz
            # mono
            # 16-bit PCM

            audio = audio.set_frame_rate(
                16000
            )

            audio = audio.set_channels(
                1
            )

            audio = audio.set_sample_width(
                2
            )

            audio.export(
                output_file,
                format="wav",
                parameters=[
                    "-acodec",
                    "pcm_s16le"
                ]
            )

            print(
                "TTS WAV created:",
                output_file
            )

            return True

        finally:

            try:

                if os.path.exists(
                    mp3_file
                ):

                    os.remove(
                        mp3_file
                    )

            except Exception:
                pass

    except Exception as e:

        print()
        print("==============================")
        print("TTS ERROR")
        print("==============================")

        print(
            type(e).__name__
        )

        print(
            str(e)
        )

        return False


# =====================================================
# WAKE
# =====================================================

@app.route(
    "/wake",
    methods=["POST"]
)
def wake():

    try:

        audio_data = request.get_data()

        print()
        print("==============================")
        print("WAKE REQUEST")
        print("==============================")

        print(
            "Audio bytes:",
            len(audio_data)
        )

        if not audio_data:

            return jsonify({
                "status": "error",
                "wake": False
            })

        fd, filename = tempfile.mkstemp(
            suffix=".wav"
        )

        os.close(fd)

        try:

            with open(
                filename,
                "wb"
            ) as f:

                f.write(
                    audio_data
                )

            recognizer = sr.Recognizer()

            with sr.AudioFile(
                filename
            ) as source:

                audio = recognizer.record(
                    source
                )

            text = ""

            # -----------------------------------------
            # English wake detection
            # -----------------------------------------

            try:

                text = recognizer.recognize_google(
                    audio,
                    language="en-IN"
                )

            except sr.UnknownValueError:

                text = ""

            except sr.RequestError as e:

                print(
                    "Wake speech error:",
                    str(e)
                )

            text = clean_text(
                text
            )

            print(
                "Wake transcription:",
                text
            )

            lower = text.lower()

            wake_words = [
                "hello",
                "hello assistant",
                "hey",
                "hey assistant",
                "hi assistant",
                "hello ai",
                "hey ai"
            ]

            detected = False

            for word in wake_words:

                if word in lower:

                    detected = True
                    break

            print(
                "WAKE:",
                detected
            )

            print("==============================")

            return jsonify({

                "status":
                    "ok",

                "wake":
                    detected,

                "transcription":
                    text

            })

        finally:

            try:

                if os.path.exists(
                    filename
                ):

                    os.remove(
                        filename
                    )

            except Exception:
                pass

    except Exception as e:

        print(
            "WAKE ERROR:",
            str(e)
        )

        return jsonify({
            "status": "error",
            "wake": False
        })


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

        audio_data = request.get_data()

        print()
        print("==============================")
        print("AUDIO RECEIVED")
        print("==============================")

        print(
            "Audio bytes:",
            len(audio_data)
        )

        if not audio_data:

            return jsonify({

                "status":
                    "error",

                "transcription":
                    None,

                "ai_reply":
                    "Please ask your question again."

            }), 400

        # ---------------------------------------------
        # Save WAV
        # ---------------------------------------------

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

        try:

            hindi_text = recognizer.recognize_google(

                audio,

                language="hi-IN"
            )

            hindi_text = clean_text(
                hindi_text
            )

        except sr.UnknownValueError:

            hindi_text = None

        except sr.RequestError as e:

            print(
                "Speech error:",
                str(e)
            )

            return jsonify({

                "status":
                    "error",

                "message":
                    "Speech service error"

            }), 500

        # =================================================
        # ENGLISH
        # =================================================

        try:

            english_text = recognizer.recognize_google(

                audio,

                language="en-IN"
            )

            english_text = clean_text(
                english_text
            )

        except sr.UnknownValueError:

            english_text = None

        except sr.RequestError as e:

            print(
                "Speech error:",
                str(e)
            )

            return jsonify({

                "status":
                    "error",

                "message":
                    "Speech service error"

            }), 500

        # =================================================
        # PRINT
        # =================================================

        print()
        print("==============================")
        print("SPEECH RESULTS")
        print("==============================")

        print(
            "Hindi:",
            hindi_text
        )

        print(
            "English:",
            english_text
        )

        print("==============================")

        # =================================================
        # VALIDATION
        # =================================================

        if (
            not is_valid_query(hindi_text)
            and
            not is_valid_query(english_text)
        ):

            return jsonify({

                "status":
                    "error",

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

            transcription = english_text

        else:

            transcription = hindi_text

        # =================================================
        # FINAL
        # =================================================

        print()
        print("==============================")
        print("FINAL")
        print("==============================")

        print(
            "USER:",
            transcription
        )

        print(
            "AI:",
            ai_reply
        )

        print("==============================")

        return jsonify({

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

        })

    except Exception as e:

        print()
        print("==============================")
        print("SERVER ERROR")
        print("==============================")

        print(
            type(e).__name__
        )

        print(
            str(e)
        )

        print("==============================")

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
# TTS ENDPOINT
# =====================================================

@app.route(
    "/tts",
    methods=["POST"]
)
def tts():

    wav_file = None

    try:

        data = request.get_json(
            silent=True
        )

        if not data:

            return jsonify({
                "status": "error",
                "message": "No JSON"
            }), 400

        text = data.get(
            "text",
            ""
        )

        text = clean_text(
            text
        )

        if not text:

            return jsonify({
                "status": "error",
                "message": "No text"
            }), 400

        fd, wav_file = tempfile.mkstemp(
            suffix=".wav"
        )

        os.close(fd)

        success = create_tts_wav(

            text,

            wav_file
        )

        if not success:

            return jsonify({

                "status":
                    "error",

                "message":
                    "TTS failed"

            }), 500

        print(
            "Sending WAV..."
        )

        return send_file(

            wav_file,

            mimetype="audio/wav",

            as_attachment=False,

            download_name="reply.wav"
        )

    except Exception as e:

        print(
            "TTS endpoint error:",
            str(e)
        )

        return jsonify({

            "status":
                "error",

            "message":
                str(e)

        }), 500

    # NOTE:
    # send_file may still be reading the file when this
    # function returns, so don't delete it immediately.


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
    print("==============================")
    print("ESP32 VOICE SERVER")
    print("==============================")

    print(
        "PORT:",
        port
    )

    print(
        "MODEL:",
        AI_MODEL
    )

    print(
        "AI KEY:",
        "CONFIGURED"
        if AI_API_KEY
        else "MISSING"
    )

    print("==============================")

    app.run(

        host="0.0.0.0",

        port=port,

        threaded=True
    )

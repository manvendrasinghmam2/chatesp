from flask import Flask, request, jsonify, Response
import os
import re
import tempfile
import uuid
import threading
import queue
import json

import requests
import speech_recognition as sr
from gtts import gTTS


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
# TTS STORAGE
# =====================================================

TTS_FOLDER = os.path.join(
    tempfile.gettempdir(),
    "esp32_tts"
)

os.makedirs(
    TTS_FOLDER,
    exist_ok=True
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
        "ai": "Groq",
        "model": AI_MODEL,
        "tts": "Google TTS"
    })


# =====================================================
# WAKE
# =====================================================

@app.route(
    "/wake",
    methods=["POST", "GET"]
)
def wake():

    print()
    print("==============================")
    print("WAKE REQUEST")
    print("==============================")

    if request.method == "POST":

        audio_data = request.get_data()

        print(
            "AUDIO:",
            len(audio_data),
            "bytes"
        )

    return jsonify({
        "status": "ok",
        "wake": True,
        "english": "Hello",
        "hindi": None
    })


# =====================================================
# CLEAN
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
# VALID
# =====================================================

def is_valid_query(text):

    if not text:
        return False

    text = str(text).strip()

    if len(text) < 2:
        return False

    bad = [
        "unknown",
        "none",
        "null",
        "no response",
        "no valid query",
        "speech not understood"
    ]

    if text.lower() in bad:
        return False

    return True


# =====================================================
# AI SYSTEM PROMPT
# =====================================================

SYSTEM_PROMPT = """
You are a professional bilingual voice assistant running on an ESP32.

Understand the user's intended language.

If clearly English:
answer in English.

If clearly Hindi:
answer in Hindi using Devanagari.

If Roman Hindi or Hinglish:
answer in natural Hinglish.

If Hindi recognition contains phonetic English,
use the English meaning when appropriate.

Compare Hindi and English recognition and determine
the intended meaning.

Do not mention speech recognition.

Do not explain your language decision.

VOICE STYLE:

Keep the answer short and natural.

Usually 1 to 4 sentences.

No markdown.

No bullet points.

No headings.

No emojis.

No unnecessary "Sure".

Do not repeat the question.

The response will be spoken aloud.
"""


# =====================================================
# AI STREAM
# =====================================================

def ai_stream(
    hindi_text,
    english_text
):

    user_content = f"""
Hindi speech recognition:
{hindi_text if hindi_text else "No result"}

English speech recognition:
{english_text if english_text else "No result"}

Understand the user's intended meaning and answer naturally.
"""


    payload = {

        "model":
            AI_MODEL,

        "messages": [

            {
                "role":
                    "system",

                "content":
                    SYSTEM_PROMPT
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
            True
    }


    headers = {

        "Authorization":
            "Bearer " + AI_API_KEY,

        "Content-Type":
            "application/json",

        "Accept":
            "text/event-stream"
    }


    response = requests.post(

        AI_URL,

        headers=headers,

        json=payload,

        stream=True,

        timeout=60
    )


    if response.status_code != 200:

        print(
            "AI ERROR:",
            response.status_code
        )

        print(
            response.text[:1000]
        )

        return


    for line in response.iter_lines(
        decode_unicode=True
    ):

        if not line:
            continue

        if not line.startswith("data:"):
            continue

        data = line[
            5:
        ].strip()


        if data == "[DONE]":
            break


        try:

            obj = json.loads(
                data
            )

            choices = obj.get(
                "choices",
                []
            )

            if not choices:
                continue

            delta = choices[0].get(
                "delta",
                {}
            )

            text = delta.get(
                "content"
            )

            if text:
                yield text

        except Exception:
            continue


# =====================================================
# TTS LANGUAGE
# =====================================================

def detect_tts_language(text):

    if re.search(
        r"[\u0900-\u097F]",
        text
    ):
        return "hi"

    return "en"


# =====================================================
# CREATE TTS
# =====================================================

def create_tts(text):

    text = clean_text(text)

    if not text:
        return None


    try:

        language =
            detect_tts_language(text)

        filename = (
            str(uuid.uuid4())
            + ".mp3"
        )

        filepath = os.path.join(
            TTS_FOLDER,
            filename
        )


        tts = gTTS(
            text=text,
            lang=language,
            slow=False
        )

        tts.save(
            filepath
        )


        print(
            "TTS CREATED:",
            filename
        )


        return filename


    except Exception as e:

        print(
            "TTS ERROR:",
            type(e).__name__,
            str(e)
        )

        return None


# =====================================================
# TTS FILE
# =====================================================

@app.route(
    "/tts/<filename>"
)
def tts_file(filename):

    filepath = os.path.join(
        TTS_FOLDER,
        filename
    )


    if not os.path.exists(
        filepath
    ):

        return (
            "Not found",
            404
        )


    def generate():

        try:

            with open(
                filepath,
                "rb"
            ) as f:

                while True:

                    data = f.read(
                        4096
                    )

                    if not data:
                        break

                    yield data

        finally:

            try:

                os.remove(
                    filepath
                )

            except Exception:
                pass


    return Response(

        generate(),

        mimetype="audio/mpeg",

        headers={
            "Cache-Control":
                "no-cache",
            "Connection":
                "keep-alive"
        }
    )


# =====================================================
# STREAM TTS
#
# Server creates small sentence chunks.
#
# ESP32 receives:
#
# /streamTTS/<id>
#
# each line contains MP3 URL
# =====================================================

streams = {}


# =====================================================
# CREATE STREAM
# =====================================================

@app.route(
    "/streamTTS",
    methods=["POST"]
)
def stream_tts():

    data = request.get_json(
        silent=True
    )


    if not data:

        return jsonify({
            "status": "error"
        }), 400


    hindi_text = clean_text(
        data.get(
            "hindi",
            ""
        )
    )


    english_text = clean_text(
        data.get(
            "english",
            ""
        )
    )


    if (
        not is_valid_query(
            hindi_text
        )
        and
        not is_valid_query(
            english_text
        )
    ):

        return jsonify({
            "status": "error",
            "message":
                "Invalid query"
        }), 400


    stream_id = str(
        uuid.uuid4()
    )


    q = queue.Queue()

    streams[
        stream_id
    ] = q


    thread = threading.Thread(

        target=generate_stream,

        args=(

            stream_id,

            q,

            hindi_text,

            english_text
        ),

        daemon=True
    )


    thread.start()


    base_url = (
        request.host_url.rstrip("/")
    )


    return jsonify({

        "status":
            "ok",

        "stream_id":
            stream_id,

        "stream_url":
            base_url +
            "/streamTTS/" +
            stream_id
    })


# =====================================================
# GENERATE STREAM
# =====================================================

def generate_stream(

    stream_id,
    q,
    hindi_text,
    english_text
):

    full_answer = ""

    buffer = ""


    try:

        for token in ai_stream(

            hindi_text,

            english_text
        ):

            full_answer += token

            buffer += token

            print(
                token,
                end="",
                flush=True
            )


            # -------------------------------------------------
            # SEND WHEN SENTENCE FINISHES
            # -------------------------------------------------

            if re.search(
                r"[.!?।]\s*$",
                buffer
            ):

                text = clean_text(
                    buffer
                )

                if text:

                    filename =
                        create_tts(
                            text
                        )


                    if filename:

                        q.put(
                            filename
                        )


                buffer = ""


        # -------------------------------------------------
        # REMAINING TEXT
        # -------------------------------------------------

        if buffer.strip():

            filename =
                create_tts(
                    buffer
                )


            if filename:

                q.put(
                    filename
                )


        print()

        print(
            "FINAL AI:",
            full_answer
        )


    except Exception as e:

        print(
            "STREAM ERROR:",
            type(e).__name__,
            str(e)
        )


    finally:

        q.put(
            "__DONE__"
        )


# =====================================================
# STREAM URL
# =====================================================

@app.route(
    "/streamTTS/<stream_id>"
)
def stream_url(stream_id):

    q = streams.get(
        stream_id
    )


    if q is None:

        return (
            "Invalid stream",
            404
        )


    base_url = (
        request.host_url.rstrip("/")
    )


    def generate():

        try:

            while True:

                filename = q.get()

                if filename == "__DONE__":

                    break


                url = (
                    base_url +
                    "/tts/" +
                    filename
                )


                # ESP32 gets URL line
                yield (
                    url + "\n"
                )


        finally:

            streams.pop(
                stream_id,
                None
            )


    return Response(

        generate(),

        mimetype="text/plain",

        headers={
            "Cache-Control":
                "no-cache"
        }
    )


# =====================================================
# UPLOAD AUDIO
# =====================================================

@app.route(
    "/uploadAudio",
    methods=["POST"]
)
def upload_audio():

    temp_file = None


    try:

        audio_data =
            request.get_data()


        if not audio_data:

            return jsonify({

                "status":
                    "error",

                "message":
                    "No audio"

            }), 400


        # -------------------------------------------------
        # SAVE WAV
        # -------------------------------------------------

        fd, temp_file =
            tempfile.mkstemp(
                suffix=".wav"
            )

        os.close(
            fd
        )


        with open(
            temp_file,
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
            temp_file
        ) as source:

            audio =
                recognizer.record(
                    source
                )


        hindi_text = None
        english_text = None


        # -------------------------------------------------
        # HINDI
        # -------------------------------------------------

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


        except (
            sr.UnknownValueError
        ):

            hindi_text = None


        except sr.RequestError as e:

            return jsonify({

                "status":
                    "error",

                "message":
                    str(e)

            }), 500


        # -------------------------------------------------
        # ENGLISH
        # -------------------------------------------------

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


        except (
            sr.UnknownValueError
        ):

            english_text = None


        except sr.RequestError as e:

            return jsonify({

                "status":
                    "error",

                "message":
                    str(e)

            }), 500


        print()
        print("==============================")
        print("USER")
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


        # -------------------------------------------------
        # VALIDATION
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

            return jsonify({

                "status":
                    "error",

                "message":
                    "Speech not understood",

                "transcription":
                    None,

                "ai_reply":
                    "Please ask your question again.",

                "stream_url":
                    None

            }), 400


        # -------------------------------------------------
        # NORMAL AI REPLY
        # -------------------------------------------------

        # We generate AI once here for compatibility
        # and also provide the normal transcription.
        #
        # For live speech use /streamTTS.

        reply_parts = []

        for token in ai_stream(

            hindi_text,

            english_text
        ):

            reply_parts.append(
                token
            )


        ai_reply = clean_text(
            "".join(
                reply_parts
            )
        )


        print()
        print("==============================")
        print("AI")
        print("==============================")
        print(ai_reply)
        print("==============================")


        # -------------------------------------------------
        # CREATE COMPLETE TTS
        # -------------------------------------------------

        filename =
            create_tts(
                ai_reply
            )


        tts_url = None


        if filename:

            tts_url = (
                request.host_url.rstrip("/")
                + "/tts/"
                + filename
            )


        # -------------------------------------------------
        # TRANSCRIPTION
        # -------------------------------------------------

        if is_valid_query(
            english_text
        ):

            transcription =
                english_text

        else:

            transcription =
                hindi_text


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
                ai_reply,

            "tts_url":
                tts_url

        })


    except Exception as e:

        print(
            "SERVER ERROR:",
            type(e).__name__,
            str(e)
        )


        return jsonify({

            "status":
                "error",

            "message":
                str(e)

        }), 500


    finally:

        if temp_file:

            try:

                if os.path.exists(
                    temp_file
                ):

                    os.remove(
                        temp_file
                    )

            except Exception:
                pass


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


    print(
        "ESP32 VOICE SERVER"
    )

    print(
        "PORT:",
        port
    )

    print(
        "MODEL:",
        AI_MODEL
    )


    app.run(

        host="0.0.0.0",

        port=port,

        threaded=True
    )

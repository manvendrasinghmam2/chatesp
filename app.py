from flask import Flask, request, jsonify, Response
import os
import re
import tempfile
import traceback
import threading
import time
import requests
import speech_recognition as sr

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
# MEMORY
# ============================================================

MAX_MEMORY_MESSAGES = 12
MEMORY_TIMEOUT = 1800

conversation_memory = {}
memory_lock = threading.Lock()

AI_ERROR = "No AI response. Try again."


# ============================================================
# HOME
# ============================================================

@app.route("/")
def home():

    return "Hannah ESP32 Voice Server is ONLINE!"


# ============================================================
# HEALTH
# ============================================================

@app.route("/health")
def health():

    return jsonify({

        "status": "online",

        "assistant": "Hannah",

        "ai_model": AI_MODEL,

        "tts_model": TTS_MODEL,

        "tts_voice": TTS_VOICE,

        "memory": True

    })


# ============================================================
# CLEAN TEXT
# ============================================================

def clean_text(text):

    if text is None:
        return ""

    text = str(text).strip()

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
# VALID QUERY
# ============================================================

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


# ============================================================
# SESSION ID
# ============================================================

def get_session_id():

    session_id = request.headers.get(
        "X-Session-ID"
    )

    if not session_id:

        try:

            data = request.get_json(
                silent=True
            )

            if data:
                session_id = data.get(
                    "session_id"
                )

        except Exception:
            pass

    if not session_id:
        session_id = "default"

    session_id = str(
        session_id
    )

    session_id = re.sub(
        r"[^a-zA-Z0-9_-]",
        "_",
        session_id
    )

    return session_id[:80]


# ============================================================
# MEMORY CLEANUP
# ============================================================

def cleanup_memory():

    now = time.time()

    with memory_lock:

        remove = []

        for sid, data in conversation_memory.items():

            if (
                now -
                data.get(
                    "last_activity",
                    0
                )
                >
                MEMORY_TIMEOUT
            ):

                remove.append(sid)

        for sid in remove:

            del conversation_memory[sid]


# ============================================================
# GET MEMORY
# ============================================================

def get_memory(session_id):

    cleanup_memory()

    with memory_lock:

        data = conversation_memory.get(
            session_id
        )

        if not data:
            return []

        return list(
            data.get(
                "messages",
                []
            )
        )


# ============================================================
# ADD MEMORY
# ============================================================

def add_memory(
    session_id,
    role,
    content
):

    content = clean_text(
        content
    )

    if not content:
        return

    with memory_lock:

        if session_id not in conversation_memory:

            conversation_memory[
                session_id
            ] = {

                "messages": [],

                "last_activity":
                    time.time()

            }

        messages = conversation_memory[
            session_id
        ]["messages"]

        messages.append({

            "role": role,

            "content": content

        })

        conversation_memory[
            session_id
        ]["messages"
        ] = messages[
            -MAX_MEMORY_MESSAGES:
        ]

        conversation_memory[
            session_id
        ]["last_activity"] = time.time()


# ============================================================
# CLEAR MEMORY
# ============================================================

@app.route(
    "/clear-memory",
    methods=["GET", "POST"]
)
def clear_memory():

    sid = get_session_id()

    with memory_lock:

        if sid in conversation_memory:

            del conversation_memory[sid]

    return jsonify({

        "status": "ok",

        "session_id": sid,

        "memory_cleared": True

    })


# ============================================================
# LANGUAGE DETECTION
# ============================================================

def detect_language(
    hindi_text,
    english_text
):

    hindi_text = clean_text(
        hindi_text
    ).lower()

    english_text = clean_text(
        english_text
    ).lower()

    # --------------------------------------------------------
    # English words written by Hindi speech recognition
    # --------------------------------------------------------

    english_phonetic = [

        "हाउ आर यू",
        "हाउ आरयू",
        "व्हाट इज योर नेम",
        "व्हाट्स योर नेम",
        "व्हेयर आर यू",
        "व्हाट कैन यू डू",
        "हाउ डू यू डू",
        "गुड मॉर्निंग",
        "गुड आफ्टरनून",
        "गुड इवनिंग",
        "गुड नाइट",
        "थैंक यू",
        "थैंक्यू",
        "आई एम फाइन",
        "आई एम गुड",
        "आई एम ओके",
        "हैलो",
        "हेलो",
        "हाय",
        "टेल मी",
        "व्हाट इज",
        "व्हाट आर",
        "व्हाई",
        "व्हेन",
        "व्हेयर",
        "हू आर",
        "कैन यू",
        "कुड यू",
        "प्लीज",
        "एक्सप्लेन"

    ]

    for phrase in english_phonetic:

        if phrase in hindi_text:

            return "english"

    # --------------------------------------------------------
    # English detection
    # --------------------------------------------------------

    english_words = {

        "hello",
        "hi",
        "hey",
        "how",
        "are",
        "you",
        "what",
        "is",
        "your",
        "name",
        "who",
        "where",
        "why",
        "when",
        "can",
        "could",
        "would",
        "tell",
        "explain",
        "please",
        "good",
        "morning",
        "evening",
        "night",
        "thank",
        "thanks",
        "robot",
        "robotics",
        "electronics",
        "ai",
        "artificial",
        "intelligence",
        "aerospace",
        "technology",
        "stem",
        "education",
        "help",
        "work",
        "working"

    }

    eng_count = 0

    for word in english_text.split():

        word = re.sub(
            r"[^a-zA-Z]",
            "",
            word
        ).lower()

        if word in english_words:

            eng_count += 1

    # --------------------------------------------------------
    # Roman Hindi
    # --------------------------------------------------------

    roman_hindi = {

        "kya",
        "kaise",
        "kaisa",
        "kaisi",
        "aap",
        "aapko",
        "mujhe",
        "mujhko",
        "mera",
        "meri",
        "mere",
        "hamara",
        "humara",
        "batao",
        "bataiye",
        "hai",
        "hain",
        "hoon",
        "hun",
        "mein",
        "me",
        "ka",
        "ki",
        "ke",
        "ko",
        "se",
        "par",
        "kyun",
        "kyon",
        "kab",
        "kahan",
        "kar",
        "karo",
        "karna",
        "karta",
        "karte",
        "karti",
        "bata",
        "chahiye",
        "chahta",
        "chahti",
        "ye",
        "woh",
        "vo",
        "iska",
        "iske",
        "uska",
        "uske",
        "aapka",
        "aapki",
        "aapke"

    }

    roman_count = 0

    for word in hindi_text.split():

        word = re.sub(
            r"[^a-zA-Z]",
            "",
            word
        ).lower()

        if word in roman_hindi:

            roman_count += 1

    if eng_count > 0 and roman_count > 0:

        return "hinglish"

    if eng_count > 0:

        return "english"

    if roman_count > 0:

        return "hindi"

    # Devanagari normally means Hindi
    if hindi_text:

        return "hindi"

    if english_text:

        return "english"

    return "unknown"


# ============================================================
# TTS CLEAN
# ============================================================

def clean_tts_text(text):

    text = clean_text(
        text
    )

    if not text:
        return ""

    prefixes = [

        "AI:",
        "Answer:",
        "Response:",
        "Assistant:",
        "Hannah:"

    ]

    for prefix in prefixes:

        if text.lower().startswith(
            prefix.lower()
        ):

            text = text[
                len(prefix):
            ].strip()

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

    # Remove Devanagari because Hannah is
    # Orpheus English voice
    text = re.sub(
        r"[\u0900-\u097F]",
        " ",
        text
    )

    text = re.sub(
        r"[^\x00-\x7F]",
        " ",
        text
    )

    text = re.sub(
        r"\s+",
        " ",
        text
    )

    text = text.strip()

    # ========================================================
    # HARD 200 CHARACTER LIMIT
    # ========================================================

    if len(text) > TTS_MAX_CHARS:

        text = text[
            :TTS_MAX_CHARS
        ]

        # End at last complete word
        space = text.rfind(" ")

        if space > 80:

            text = text[:space]

        # Prefer punctuation
        punctuation = [

            text.rfind("."),

            text.rfind("?"),

            text.rfind("!"),

        ]

        best = max(
            punctuation
        )

        if best >= 60:

            text = text[
                :best + 1
            ]

    return text.strip()


# ============================================================
# AI
# ============================================================

def get_ai_reply(
    hindi_text,
    english_text,
    session_id
):

    hindi_text = clean_text(
        hindi_text
    )

    english_text = clean_text(
        english_text
    )

    if not AI_API_KEY:

        print(
            "ERROR: AI_API_KEY missing"
        )

        return AI_ERROR

    if (
        not is_valid_query(hindi_text)
        and
        not is_valid_query(english_text)
    ):

        return (
            "Please ask your question again."
        )

    language = detect_language(
        hindi_text,
        english_text
    )

    print(
        "DETECTED LANGUAGE:",
        language
    )

    system_prompt = """

You are Hannah, a friendly female voice assistant for
Avitron Aerospace Pvt. Ltd.

Your main area is:

STEM education,
AI,
Artificial Intelligence,
Robotics,
Electronics,
Embedded Systems,
ESP32,
Arduino,
Sensors,
Programming,
Science,
Technology,
Aerospace.

You may also answer basic conversation questions such as:

How are you?
What is your name?
Who are you?
Hello.
Good morning.
Thank you.

============================================================
LANGUAGE
============================================================

English question:
Answer ONLY in English.

Hindi question:
Answer in Roman Hindi using English letters.

Hinglish question:
Answer naturally in Hinglish.

NEVER use Devanagari in the answer.

IMPORTANT:

If Hindi speech recognition produces English words in
Devanagari, understand them as English.

Example:

हाउ आर यू

Answer:

I am doing great. How can I help you?

NOT:

Main theek hoon.

Example:

व्हाट इज योर नेम

Answer:

My name is Hannah.

NOT:

Mera naam Hannah hai.

============================================================
DOMAIN
============================================================

Prefer questions related to:

STEM education
AI
Robotics
Electronics
Embedded systems
ESP32
Arduino
Sensors
Programming
Science
Technology
Aerospace.

If the user asks something completely unrelated:

English:

I can help with STEM education, AI, robotics, electronics and related technology. What would you like to ask?

Hindi:

Main STEM education, AI, robotics, electronics aur related technology mein help kar sakti hoon. Aap kya poochna chahenge?

============================================================
MEMORY
============================================================

Remember the previous conversation.

If user says:

Tell me more.
Explain that.
What about this?
How does it work?
Iske baare mein batao.
Ye kaise kaam karta hai?

Use the previous conversation context.

============================================================
STYLE
============================================================

Sound natural and conversational.

Basic questions should be short.

Technical questions can be more detailed.

No markdown.
No headings.
No bullets.
No emojis.
Do not repeat the question.
Do not say "As an AI".

Return ONLY the answer.
"""

    messages = [

        {
            "role": "system",
            "content": system_prompt
        }

    ]

    # Previous memory
    for item in get_memory(
        session_id
    ):

        messages.append({

            "role":
                item["role"],

            "content":
                item["content"]

        })

    user_content = f"""

Hindi recognition:
{hindi_text if hindi_text else "No result"}

English recognition:
{english_text if english_text else "No result"}

Detected language:
{language}

Answer according to the detected language.
"""

    messages.append({

        "role":
            "user",

        "content":
            user_content

    })

    payload = {

        "model":
            AI_MODEL,

        "messages":
            messages,

        "temperature":
            0.2,

        "max_completion_tokens":
            500,

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

        print()
        print("========================================")
        print("AI REQUEST")
        print("========================================")

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
                "AI ERROR BODY:"
            )

            print(
                response.text[:5000]
            )

            return AI_ERROR

        data = response.json()

        choices = data.get(
            "choices"
        )

        if not choices:

            print(
                "AI choices missing"
            )

            print(data)

            return AI_ERROR

        reply = choices[0].get(
            "message",
            {}
        ).get(
            "content",
            ""
        )

        reply = clean_text(
            reply
        )

        for prefix in [

            "AI:",
            "Answer:",
            "Response:",
            "Assistant:",
            "Hannah:"

        ]:

            if reply.lower().startswith(
                prefix.lower()
            ):

                reply = reply[
                    len(prefix):
                ].strip()

        if not reply:

            return AI_ERROR

        # Save memory
        user_memory = (

            english_text

            if language == "english"
            and is_valid_query(
                english_text
            )

            else hindi_text

            if is_valid_query(
                hindi_text
            )

            else english_text

        )

        if user_memory:

            add_memory(
                session_id,
                "user",
                user_memory
            )

        add_memory(
            session_id,
            "assistant",
            reply
        )

        print()
        print(
            "AI REPLY:",
            reply
        )

        return reply

    except Exception as e:

        print(
            "AI EXCEPTION:",
            type(e).__name__,
            str(e)
        )

        traceback.print_exc()

        return AI_ERROR


# ============================================================
# GROQ TTS
# ============================================================

def generate_tts(text):

    text = clean_tts_text(
        text
    )

    print()
    print("========================================")
    print("HANNAH TTS")
    print("========================================")

    print(
        "TEXT:",
        text
    )

    print(
        "TEXT LENGTH:",
        len(text)
    )

    print(
        "MODEL:",
        TTS_MODEL
    )

    print(
        "VOICE:",
        TTS_VOICE
    )

    if not text:

        print(
            "TTS FAILED: EMPTY TEXT"
        )

        return None

    if not AI_API_KEY:

        print(
            "TTS FAILED: API KEY MISSING"
        )

        return None

    # ========================================================
    # EXACT GROQ ORPHEUS PAYLOAD
    # ========================================================

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

    try:

        print(
            "SENDING TO GROQ..."
        )

        response = requests.post(

            TTS_URL,

            headers=headers,

            json=payload,

            timeout=60

        )

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

        print(
            "TTS TRANSFER:",
            response.headers.get(
                "Transfer-Encoding",
                "none"
            )
        )

        # ====================================================
        # ONLY ACCEPT 200
        # ====================================================

        if response.status_code != 200:

            print()
            print("========================================")
            print("TTS SERVER ERROR")
            print("========================================")

            print(
                "STATUS:",
                response.status_code
            )

            print(
                "HEADERS:"
            )

            print(
                dict(response.headers)
            )

            print(
                "ERROR BODY:"
            )

            try:

                print(
                    response.text[:10000]
                )

            except Exception as e:

                print(
                    "Cannot read error body:",
                    str(e)
                )

            print("========================================")

            return None

        # ====================================================
        # AUDIO
        # ====================================================

        audio = response.content

        if not audio:

            print(
                "TTS ERROR: EMPTY AUDIO"
            )

            return None

        # ====================================================
        # BASIC WAV CHECK
        # ====================================================

        if not audio.startswith(
            b"RIFF"
        ):

            print(
                "WARNING: RESPONSE DOES NOT START WITH RIFF"
            )

            print(
                "FIRST BYTES:",
                audio[:20]
            )

            return None

        print(
            "AUDIO BYTES:",
            len(audio)
        )

        print(
            "VALID WAV: YES"
        )

        print(
            "TTS SUCCESS"
        )

        print("========================================")

        return audio

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

@app.route(
    "/tts",
    methods=["POST"]
)
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

            return jsonify({

                "status":
                    "error",

                "message":
                    "No JSON received"

            }), 400

        text = clean_text(
            data.get("text")
        )

        if not text:

            return jsonify({

                "status":
                    "error",

                "message":
                    "No text received"

            }), 400

        audio = generate_tts(
            text
        )

        # IMPORTANT:
        # Never send an error as audio.
        if audio is None:

            return jsonify({

                "status":
                    "error",

                "message":
                    "TTS generation failed"

            }), 500

        return Response(

            audio,

            status=200,

            mimetype="audio/wav",

            headers={

                "Cache-Control":
                    "no-cache, no-store, must-revalidate",

                "Pragma":
                    "no-cache",

                "Expires":
                    "0",

                "Content-Disposition":
                    "inline; filename=hannah.wav"

            }

        )

    except Exception as e:

        print(
            "TTS ENDPOINT ERROR:",
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
# DIRECT TTS TEST
# ============================================================

@app.route(
    "/test-tts",
    methods=["GET"]
)
def test_tts():

    test_text = (
        "Hello, I am Hannah. "
        "How can I help you today?"
    )

    print()
    print("========================================")
    print("DIRECT HANNAH TTS TEST")
    print("========================================")

    audio = generate_tts(
        test_text
    )

    if audio is None:

        return jsonify({

            "status":
                "error",

            "message":
                "Hannah TTS failed",

            "model":
                TTS_MODEL,

            "voice":
                TTS_VOICE

        }), 500

    return Response(

        audio,

        status=200,

        mimetype="audio/wav",

        headers={

            "Cache-Control":
                "no-cache",

            "Content-Disposition":
                "inline; filename=hannah-test.wav"

        }

    )


# ============================================================
# MEMORY STATUS
# ============================================================

@app.route(
    "/memory-status",
    methods=["GET"]
)
def memory_status():

    sid = get_session_id()

    memory = get_memory(
        sid
    )

    return jsonify({

        "status":
            "ok",

        "session_id":
            sid,

        "messages":
            memory

    })


# ============================================================
# WAKE
# ============================================================

@app.route(
    "/wake",
    methods=["POST", "GET"]
)
def wake():

    try:

        audio = request.get_data()

        print(
            "WAKE BYTES:",
            len(audio)
        )

        return jsonify({

            "status":
                "ok",

            "wake":
                True,

            "english":
                "Hello",

            "hindi":
                None

        })

    except Exception as e:

        return jsonify({

            "status":
                "error",

            "message":
                str(e)

        }), 500


# ============================================================
# AUDIO UPLOAD
# ============================================================

@app.route(
    "/uploadAudio",
    methods=["POST"]
)
def upload_audio():

    filename = None

    try:

        print()
        print("========================================")
        print("AUDIO REQUEST")
        print("========================================")

        session_id = get_session_id()

        audio_data = request.get_data()

        print(
            "SESSION:",
            session_id
        )

        print(
            "CONTENT TYPE:",
            request.content_type
        )

        print(
            "AUDIO BYTES:",
            len(audio_data)
        )

        if not audio_data:

            return jsonify({

                "status":
                    "error",

                "message":
                    "No audio received"

            }), 400

        # ====================================================
        # SAVE AUDIO
        # ====================================================

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

        # ====================================================
        # RECOGNITION
        # ====================================================

        recognizer = sr.Recognizer()

        with sr.AudioFile(
            filename
        ) as source:

            audio = recognizer.record(
                source
            )

        hindi_text = None
        english_text = None

        # ====================================================
        # HINDI
        # ====================================================

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
                "Hindi not understood"
            )

        except sr.RequestError as e:

            print(
                "Google Hindi error:",
                str(e)
            )

        # ====================================================
        # ENGLISH
        # ====================================================

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
                "English not understood"
            )

        except sr.RequestError as e:

            print(
                "Google English error:",
                str(e)
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

                "status":
                    "error",

                "message":
                    "Speech not understood",

                "ai_reply":
                    "Please ask your question again."

            }), 400

        # ====================================================
        # AI
        # ====================================================

        ai_reply = get_ai_reply(

            hindi_text,

            english_text,

            session_id

        )

        language = detect_language(

            hindi_text,

            english_text

        )

        # ====================================================
        # TRANSCRIPTION
        # ====================================================

        if language == "english":

            transcription = (

                english_text

                if is_valid_query(
                    english_text
                )

                else hindi_text

            )

        else:

            transcription = (

                hindi_text

                if is_valid_query(
                    hindi_text
                )

                else english_text

            )

        response_data = {

            "status":
                "ok",

            "session_id":
                session_id,

            "language":
                language,

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

        return jsonify(
            response_data
        )

    except Exception as e:

        print(
            "SERVER ERROR:",
            type(e).__name__,
            str(e)
        )

        traceback.print_exc()

        return jsonify({

            "status":
                "error",

            "message":
                str(e),

            "ai_reply":
                AI_ERROR

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
    print("HANNAH ESP32 VOICE SERVER")
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
        "MEMORY: ENABLED"
    )

    print(
        "API KEY:",
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

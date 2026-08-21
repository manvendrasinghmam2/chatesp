from flask import Flask, request, jsonify
import os
import re
import json
import time
import tempfile
import requests


# =========================================================
# APP
# =========================================================

app = Flask(__name__)


# =========================================================
# CONFIG
# =========================================================

AI_API_KEY = os.environ.get("AI_API_KEY", "").strip()

AI_URL = os.environ.get(
    "AI_URL",
    "https://api.groq.com/openai/v1/chat/completions"
)

AI_MODEL = os.environ.get(
    "AI_MODEL",
    "llama-3.1-8b-instant"
)

# Groq Whisper
WHISPER_URL = (
    "https://api.groq.com/openai/v1/audio/transcriptions"
)

WHISPER_MODEL = os.environ.get(
    "WHISPER_MODEL",
    "whisper-large-v3-turbo"
)

# Memory per device/session
MAX_MEMORY_TURNS = 6

# Maximum audio accepted
MAX_AUDIO_BYTES = 1000000


# =========================================================
# CONVERSATION MEMORY
# =========================================================
#
# ESP32 currently doesn't send a user/session ID.
# We therefore keep one conversation for this ESP32.
#
# If later you add multiple devices, add device_id.
# =========================================================

conversation_memory = []


# =========================================================
# HOME
# =========================================================

@app.route("/", methods=["GET"])
def home():

    return "ESP32 Voice Server is ONLINE!"


# =========================================================
# HEALTH
# =========================================================

@app.route("/health", methods=["GET"])
def health():

    return jsonify({
        "status": "online",
        "speech_engine": "Groq Whisper",
        "ai_engine": "Groq",
        "model": AI_MODEL,
        "whisper_model": WHISPER_MODEL,
        "memory_turns": len(conversation_memory)
    })


# =========================================================
# RESET MEMORY
# =========================================================

@app.route("/reset_memory", methods=["GET", "POST"])
def reset_memory():

    conversation_memory.clear()

    return jsonify({
        "status": "ok",
        "message": "Conversation memory cleared."
    })


# =========================================================
# WAKE
# =========================================================
#
# ESP32 only needs a successful wake response.
#
# NOTE:
# For a real wake-word system, /wake should also inspect
# the audio. For now we keep HELLO detection compatible
# with your existing ESP32 flow.
# =========================================================

@app.route("/wake", methods=["POST", "GET"])
def wake():

    return jsonify({
        "status": "ok",
        "wake": True
    })


# =========================================================
# TEXT CLEAN
# =========================================================

def clean_text(text):

    if not text:
        return ""

    text = str(text)

    text = text.replace("\x00", " ")

    text = re.sub(
        r"\s+",
        " ",
        text
    )

    return text.strip()


# =========================================================
# VALID QUERY
# =========================================================

def is_valid_query(text):

    text = clean_text(text)

    if not text:
        return False

    if len(text) < 2:
        return False

    bad = {
        "unknown",
        "none",
        "null",
        "noise",
        "silence",
        "thank you",
        "thanks",
        "okay",
        "ok"
    }

    if text.lower() in bad:
        return False

    return True


# =========================================================
# NORMALIZE STT
# =========================================================

def normalize_transcription(text):

    text = clean_text(text)

    if not text:
        return ""

    # Common Whisper/recognition artifacts
    text = re.sub(
        r"^(you|the user)\s*:\s*",
        "",
        text,
        flags=re.IGNORECASE
    )

    text = text.strip()

    return text


# =========================================================
# MEMORY
# =========================================================

def add_memory(user_text, assistant_text):

    global conversation_memory

    user_text = clean_text(user_text)
    assistant_text = clean_text(assistant_text)

    if not user_text or not assistant_text:
        return

    conversation_memory.append({
        "user": user_text,
        "assistant": assistant_text
    })

    if len(conversation_memory) > MAX_MEMORY_TURNS:
        conversation_memory = conversation_memory[
            -MAX_MEMORY_TURNS:
        ]


def memory_for_prompt():

    if not conversation_memory:
        return "No previous conversation."

    lines = []

    for item in conversation_memory:

        lines.append(
            "User: " +
            item["user"]
        )

        lines.append(
            "Assistant: " +
            item["assistant"]
        )

    return "\n".join(lines)


# =========================================================
# FOLLOW-UP DETECTION
# =========================================================

def is_followup_question(text):

    text = clean_text(text).lower()

    followups = [
        "iske baare mein batao",
        "is ke baare mein batao",
        "iske bare mein batao",
        "is ke bare mein batao",
        "iske baare me batao",
        "is ke baare me batao",
        "iske bare me batao",
        "uske baare mein batao",
        "uske bare mein batao",
        "iske baare mein",
        "iske bare mein",
        "ke baare mein batao",
        "ke bare mein batao",
        "बारे में बताओ",
        "के बारे में बताओ",
        "इसके बारे में बताओ",
        "उसके बारे में बताओ",
        "aur batao",
        "और बताओ",
        "tell me more",
        "more about it",
        "what about it",
        "what about that",
        "and what about it"
    ]

    for phrase in followups:

        if phrase in text:
            return True

    return False


# =========================================================
# WEATHER DETECTION
# =========================================================

def is_weather_question(text):

    text = clean_text(text).lower()

    keywords = [
        "weather",
        "temperature",
        "forecast",
        "rain",
        "raining",
        "बारिश",
        "मौसम",
        "तापमान",
        "गरमी",
        "गर्मी",
        "ठंड"
    ]

    for word in keywords:

        if word in text:
            return True

    return False


# =========================================================
# WEATHER LOCATION EXTRACTION
# =========================================================

def extract_weather_location(text):

    text = clean_text(text)

    patterns = [

        r"weather\s+(?:in|at|of)\s+(.+)",
        r"temperature\s+(?:in|at|of)\s+(.+)",
        r"forecast\s+(?:in|at|of)\s+(.+)",

        r"मौसम\s+(.+)",
        r"तापमान\s+(.+)"
    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            text,
            flags=re.IGNORECASE
        )

        if match:

            location = clean_text(
                match.group(1)
            )

            if location:
                return location

    return ""


# =========================================================
# FIND LOCATION IN MEMORY
# =========================================================

def find_location_from_memory():

    # Search newest user messages first.

    for item in reversed(conversation_memory):

        user = item.get(
            "user",
            ""
        )

        # Common location patterns

        patterns = [

            r"\b(?:in|at)\s+([A-Za-z][A-Za-z .-]{2,40})$",

            r"^([A-Za-z][A-Za-z .-]{2,40})\s+city$",

            r"^([A-Za-z][A-Za-z .-]{2,40})$"
        ]

        for pattern in patterns:

            match = re.search(
                pattern,
                user,
                flags=re.IGNORECASE
            )

            if match:

                location = clean_text(
                    match.group(1)
                )

                if location:

                    # Avoid obvious conversational words
                    bad = {
                        "yes",
                        "no",
                        "hello",
                        "okay",
                        "ok",
                        "weather",
                        "today"
                    }

                    if location.lower() not in bad:
                        return location

    return ""


# =========================================================
# GEOCODING
# =========================================================

def geocode_location(location):

    location = clean_text(location)

    if not location:
        return None

    try:

        response = requests.get(

            "https://geocoding-api.open-meteo.com/v1/search",

            params={
                "name": location,
                "count": 1,
                "language": "en",
                "format": "json"
            },

            timeout=8
        )

        if response.status_code != 200:
            return None

        data = response.json()

        results = data.get(
            "results",
            []
        )

        if not results:
            return None

        item = results[0]

        return {
            "name": item.get(
                "name",
                location
            ),
            "latitude": item.get(
                "latitude"
            ),
            "longitude": item.get(
                "longitude"
            ),
            "country": item.get(
                "country",
                ""
            ),
            "admin1": item.get(
                "admin1",
                ""
            )
        }

    except Exception as e:

        print(
            "GEOCODING ERROR:",
            str(e)
        )

        return None


# =========================================================
# LIVE WEATHER
# =========================================================

def get_weather(location):

    geo = geocode_location(
        location
    )

    if not geo:
        return None

    try:

        response = requests.get(

            "https://api.open-meteo.com/v1/forecast",

            params={

                "latitude":
                    geo["latitude"],

                "longitude":
                    geo["longitude"],

                "current":
                    "temperature_2m,relative_humidity_2m,"
                    "apparent_temperature,"
                    "precipitation,rain,weather_code,"
                    "wind_speed_10m",

                "timezone":
                    "auto"
            },

            timeout=8
        )

        if response.status_code != 200:
            return None

        data = response.json()

        current = data.get(
            "current",
            {}
        )

        return {

            "location":
                geo["name"],

            "country":
                geo["country"],

            "temperature":
                current.get(
                    "temperature_2m"
                ),

            "feels_like":
                current.get(
                    "apparent_temperature"
                ),

            "humidity":
                current.get(
                    "relative_humidity_2m"
                ),

            "rain":
                current.get(
                    "rain"
                ),

            "precipitation":
                current.get(
                    "precipitation"
                ),

            "wind":
                current.get(
                    "wind_speed_10m"
                ),

            "weather_code":
                current.get(
                    "weather_code"
                )
        }

    except Exception as e:

        print(
            "WEATHER ERROR:",
            str(e)
        )

        return None


# =========================================================
# WEATHER DESCRIPTION
# =========================================================

def weather_description(code):

    if code is None:
        return "current conditions"

    code = int(code)

    mapping = {

        0: "clear sky",

        1: "mainly clear",
        2: "partly cloudy",
        3: "overcast",

        45: "foggy",
        48: "foggy",

        51: "light drizzle",
        53: "moderate drizzle",
        55: "heavy drizzle",

        61: "light rain",
        63: "moderate rain",
        65: "heavy rain",

        71: "light snow",
        73: "moderate snow",
        75: "heavy snow",

        80: "light rain showers",
        81: "moderate rain showers",
        82: "heavy rain showers",

        95: "thunderstorm",
        96: "thunderstorm with hail",
        99: "thunderstorm with hail"
    }

    return mapping.get(
        code,
        "mixed conditions"
    )


# =========================================================
# WEATHER RESPONSE
# =========================================================

def weather_reply(weather, language_hint):

    if not weather:
        return ""

    location = weather["location"]

    temp = weather["temperature"]

    feels = weather["feels_like"]

    humidity = weather["humidity"]

    wind = weather["wind"]

    condition = weather_description(
        weather["weather_code"]
    )

    if language_hint == "hindi":

        return (
            f"{location} में अभी तापमान लगभग "
            f"{temp} डिग्री सेल्सियस है और मौसम "
            f"{condition} है। महसूस होने वाला तापमान "
            f"{feels} डिग्री है, नमी {humidity} प्रतिशत "
            f"और हवा लगभग {wind} किलोमीटर प्रति घंटे है।"
        )

    if language_hint == "hinglish":

        return (
            f"{location} mein abhi temperature "
            f"lagbhag {temp} degree Celsius hai aur "
            f"weather {condition} hai. Feels-like "
            f"temperature {feels} degree hai, humidity "
            f"{humidity} percent aur wind around "
            f"{wind} kilometer per hour hai."
        )

    return (
        f"In {location}, it's currently about "
        f"{temp} degrees Celsius with {condition}. "
        f"It feels like {feels} degrees, humidity is "
        f"{humidity} percent, and wind is around "
        f"{wind} kilometers per hour."
    )


# =========================================================
# LANGUAGE HINT
# =========================================================

def language_hint(text):

    text = clean_text(text)

    # Devanagari
    if re.search(
        r"[\u0900-\u097F]",
        text
    ):

        # Hindi common words
        hindi_words = [
            "क्या",
            "कैसे",
            "कहाँ",
            "बताओ",
            "मौसम",
            "तापमान",
            "आज",
            "में",
            "का",
            "की",
            "है"
        ]

        for word in hindi_words:

            if word in text:
                return "hindi"

        return "hindi"

    # Roman Hindi / Hinglish
    hinglish_words = [
        "kya",
        "kaise",
        "kahan",
        "batao",
        "mein",
        "hai",
        "ka",
        "ki",
        "ke",
        "mujhe",
        "aaj",
        "baare",
        "barae"
    ]

    lower = text.lower()

    for word in hinglish_words:

        if re.search(
            r"\b" + re.escape(word) + r"\b",
            lower
        ):
            return "hinglish"

    return "english"


# =========================================================
# TRANSCRIBE WITH GROQ WHISPER
# =========================================================

def transcribe_audio(audio_bytes):

    if not AI_API_KEY:
        print("AI_API_KEY missing.")
        return ""

    if not audio_bytes:
        return ""

    if len(audio_bytes) > MAX_AUDIO_BYTES:
        print(
            "Audio too large:",
            len(audio_bytes)
        )

    temp_path = None

    try:

        with tempfile.NamedTemporaryFile(
            suffix=".wav",
            delete=False
        ) as temp:

            temp.write(
                audio_bytes
            )

            temp_path = temp.name

        headers = {
            "Authorization":
                "Bearer " + AI_API_KEY
        }

        with open(
            temp_path,
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

                "model":
                    WHISPER_MODEL,

                "temperature":
                    "0",

                "response_format":
                    "json"
            }

            response = requests.post(

                WHISPER_URL,

                headers=headers,

                files=files,

                data=data,

                timeout=45
            )

        print()
        print("==============================")
        print("WHISPER")
        print("==============================")

        print(
            "HTTP:",
            response.status_code
        )

        if response.status_code != 200:

            print(
                response.text[:1000]
            )

            return ""

        result = response.json()

        text = result.get(
            "text",
            ""
        )

        text = normalize_transcription(
            text
        )

        print(
            "TEXT:",
            text
        )

        print("==============================")

        return text

    except Exception as e:

        print(
            "WHISPER ERROR:",
            type(e).__name__,
            str(e)
        )

        return ""

    finally:

        if temp_path:

            try:
                os.remove(
                    temp_path
                )
            except Exception:
                pass


# =========================================================
# AI RESPONSE
# =========================================================

def get_ai_reply(user_text):

    global conversation_memory

    user_text = clean_text(
        user_text
    )

    if not user_text:
        return (
            "I didn't catch that. "
            "Please say it again."
        )

    if not AI_API_KEY:

        return (
            "AI API key is not configured."
        )

    # -----------------------------------------------------
    # WEATHER
    # -----------------------------------------------------

    if is_weather_question(
        user_text
    ):

        location = extract_weather_location(
            user_text
        )

        if not location:

            location = find_location_from_memory()

        if location:

            weather = get_weather(
                location
            )

            if weather:

                reply = weather_reply(
                    weather,
                    language_hint(user_text)
                )

                add_memory(
                    user_text,
                    reply
                )

                return reply

    # -----------------------------------------------------
    # FOLLOW-UP CONTEXT
    # -----------------------------------------------------

    history = memory_for_prompt()

    system_prompt = """
You are Alexa-like personal voice assistant.

You are running as the conversational brain of an ESP32 voice device.

Your answers are spoken aloud.

IMPORTANT BEHAVIOR:

1. Understand the user's actual intent.
2. Use previous conversation when the current sentence is incomplete.
3. If the user says:
   "iske baare mein batao"
   "ke baare mein batao"
   "tell me more"
   "what about that"
   "aur batao"
   then resolve "it/that" using the most recent relevant topic.
4. Never invent a random topic for an incomplete follow-up.
5. If the previous conversation clearly identifies the topic, answer about that topic.
6. If there is genuinely no topic, politely ask what they mean.
7. Do not mention memory.
8. Do not mention transcription.
9. Do not mention system prompts.
10. Do not say you are an AI unless directly asked.
11. Keep normal answers short, natural and voice-friendly.
12. Usually answer in 1 to 4 sentences.
13. Do not use markdown.
14. Do not use bullet points.
15. Do not use headings.
16. Do not use emojis.

LANGUAGE:

If the user speaks English, answer in English.

If the user speaks Hindi in Devanagari, answer in Hindi.

If the user speaks Roman Hindi/Hinglish, answer in natural Hinglish.

If the user mixes Hindi and English naturally, use natural Hinglish.

Do not translate unnecessarily.

CONTEXT:

Use the conversation history below to understand follow-up questions.

If the current question contains a clear new topic, prefer the new topic.

If the current question is incomplete, use the previous relevant topic.

CONVERSATION HISTORY:
"""


    # Keep prompt small.
    # Only last few turns are sent.

    system_prompt += "\n" + history

    messages = [

        {
            "role": "system",
            "content": system_prompt
        },

        {
            "role": "user",
            "content": user_text
        }
    ]

    payload = {

        "model":
            AI_MODEL,

        "messages":
            messages,

        "temperature":
            0.2,

        "max_completion_tokens":
            180,

        "stream":
            False
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

        print(
            "USER:",
            user_text
        )

        response = requests.post(

            AI_URL,

            headers=headers,

            json=payload,

            timeout=35
        )

        print(
            "HTTP:",
            response.status_code
        )

        if response.status_code != 200:

            print(
                "AI ERROR:",
                response.text[:1500]
            )

            return (
                "Sorry, I couldn't get "
                "a response right now."
            )

        data = response.json()

        choices = data.get(
            "choices",
            []
        )

        if not choices:

            print(
                "NO CHOICES:",
                data
            )

            return (
                "Sorry, I couldn't "
                "generate an answer."
            )

        message = choices[0].get(
            "message",
            {}
        )

        reply = message.get(
            "content",
            ""
        )

        reply = clean_text(
            reply
        )

        if not reply:

            print(
                "EMPTY AI RESPONSE"
            )

            return (
                "I couldn't generate "
                "an answer. Please ask again."
            )

        # Remove accidental prefixes

        reply = re.sub(
            r"^(AI|Assistant|Answer|Response)\s*:\s*",
            "",
            reply,
            flags=re.IGNORECASE
        )

        reply = clean_text(
            reply
        )

        # Store only successful answer

        add_memory(
            user_text,
            reply
        )

        print(
            "AI:",
            reply
        )

        print("==============================")

        return reply

    except requests.exceptions.Timeout:

        print(
            "AI TIMEOUT"
        )

        return (
            "The response is taking too long. "
            "Please try again."
        )

    except requests.exceptions.ConnectionError as e:

        print(
            "AI CONNECTION ERROR:",
            str(e)
        )

        return (
            "I can't reach the AI service "
            "right now."
        )

    except Exception as e:

        print(
            "AI EXCEPTION:",
            type(e).__name__,
            str(e)
        )

        return (
            "Something went wrong. "
            "Please try again."
        )


# =========================================================
# UPLOAD AUDIO
# =========================================================

@app.route(
    "/uploadAudio",
    methods=["POST"]
)
def upload_audio():

    start_time = time.time()

    try:

        # -------------------------------------------------
        # RECEIVE
        # -------------------------------------------------

        audio_data = request.get_data()

        print()
        print("==============================")
        print("AUDIO RECEIVED")
        print("==============================")

        print(
            "Bytes:",
            len(audio_data)
        )

        if not audio_data:

            return jsonify({

                "status":
                    "error",

                "transcription":
                    "",

                "ai_reply":
                    "I didn't hear anything."
            }), 400

        # -------------------------------------------------
        # TRANSCRIPTION
        # -------------------------------------------------

        transcription = transcribe_audio(
            audio_data
        )

        if not is_valid_query(
            transcription
        ):

            print(
                "NO VALID SPEECH"
            )

            return jsonify({

                "status":
                    "empty",

                "transcription":
                    "",

                "ai_reply":
                    ""
            })

        # -------------------------------------------------
        # AI
        # -------------------------------------------------

        ai_reply = get_ai_reply(
            transcription
        )

        # -------------------------------------------------
        # FINAL
        # -------------------------------------------------

        elapsed = (
            time.time() -
            start_time
        )

        response_data = {

            "status":
                "ok",

            "transcription":
                transcription,

            "ai_reply":
                ai_reply,

            "processing_seconds":
                round(
                    elapsed,
                    2
                )
        }

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

        print(
            "TIME:",
            round(
                elapsed,
                2
            ),
            "sec"
        )

        print("==============================")

        return jsonify(
            response_data
        )

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

            "transcription":
                "",

            "ai_reply":
                "Sorry, something went wrong."

        }), 500


# =========================================================
# START
# =========================================================

if __name__ == "__main__":

    port = int(
        os.environ.get(
            "PORT",
            "10000"
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
        "AI MODEL:",
        AI_MODEL
    )

    print(
        "WHISPER MODEL:",
        WHISPER_MODEL
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
        port=port
    )

from flask import Flask, request, jsonify
import os
import speech_recognition as sr
import requests
import re
import threading
from datetime import datetime
from zoneinfo import ZoneInfo


# =====================================================
# APP
# =====================================================

app = Flask(__name__)


# =====================================================
# CONFIG
# =====================================================

AI_API_KEY = os.environ.get(
    "AI_API_KEY"
)

AI_URL = os.environ.get(
    "AI_URL",
    "https://api.groq.com/openai/v1/chat/completions"
)

AI_MODEL = os.environ.get(
    "AI_MODEL",
    "llama-3.1-8b-instant"
)


# =====================================================
# MEMORY
# =====================================================

MAX_MEMORY_MESSAGES = 16

conversation_history = []

memory_lock = threading.Lock()


# =====================================================
# MEMORY FUNCTIONS
# =====================================================

def add_memory(
    role,
    content
):

    if not content:
        return

    content = str(
        content
    ).strip()

    if not content:
        return

    with memory_lock:

        conversation_history.append({

            "role":
                role,

            "content":
                content
        })


        # Keep memory compact

        while (
            len(conversation_history)
            >
            MAX_MEMORY_MESSAGES
        ):

            conversation_history.pop(
                0
            )


# =====================================================
# GET MEMORY
# =====================================================

def get_memory():

    with memory_lock:

        return list(
            conversation_history
        )


# =====================================================
# CLEAR MEMORY
# =====================================================

def clear_memory():

    with memory_lock:

        conversation_history.clear()


# =====================================================
# HOME
# =====================================================

@app.route(
    "/",
    methods=["GET"]
)
def home():

    return (
        "ESP32 Voice AI Server ONLINE"
    )


# =====================================================
# HEALTH
# =====================================================

@app.route(
    "/health",
    methods=["GET"]
)
def health():

    return jsonify({

        "status":
            "online",

        "ai":
            AI_MODEL,

        "memory_messages":
            len(
                get_memory()
            ),

        "memory_limit":
            MAX_MEMORY_MESSAGES,

        "weather":
            "Open-Meteo"
    })


# =====================================================
# MEMORY
# =====================================================

@app.route(
    "/memory",
    methods=["GET"]
)
def memory():

    return jsonify({

        "count":
            len(
                get_memory()
            ),

        "messages":
            get_memory()
    })


# =====================================================
# RESET
# =====================================================

@app.route(
    "/reset",
    methods=["GET", "POST"]
)
def reset():

    clear_memory()

    print(
        "Conversation memory cleared."
    )

    return jsonify({

        "status":
            "ok",

        "message":
            "Memory cleared."
    })


# =====================================================
# WAKE
# =====================================================

@app.route(
    "/wake",
    methods=["POST", "GET"]
)
def wake():

    # NOTE:
    # This currently accepts every wake request.
    #
    # Real HELLO detection can be added later.

    return jsonify({

        "status":
            "ok",

        "wake":
            True
    })


# =====================================================
# CLEAN TEXT
# =====================================================

def clean_text(
    text
):

    if not text:
        return ""

    text = str(
        text
    ).strip()

    text = re.sub(
        r"\s+",
        " ",
        text
    )

    return text


# =====================================================
# VALID QUERY
# =====================================================

def is_valid_query(
    text
):

    if not text:
        return False

    text = str(
        text
    ).strip()

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
# WEATHER
# =====================================================

WEATHER_CODES = {

    0:
        "clear sky",

    1:
        "mainly clear",

    2:
        "partly cloudy",

    3:
        "overcast",

    45:
        "foggy",

    48:
        "foggy",

    51:
        "light drizzle",

    53:
        "drizzle",

    55:
        "heavy drizzle",

    61:
        "light rain",

    63:
        "rain",

    65:
        "heavy rain",

    71:
        "light snow",

    73:
        "snow",

    75:
        "heavy snow",

    80:
        "rain showers",

    81:
        "rain showers",

    82:
        "heavy rain showers",

    95:
        "thunderstorm",

    96:
        "thunderstorm with hail",

    99:
        "thunderstorm with hail"
}


# =====================================================
# GEOCODE CITY
# =====================================================

def geocode_city(
    city
):

    city = clean_text(
        city
    )

    if not city:
        return None


    try:

        response = requests.get(

            "https://geocoding-api.open-meteo.com/v1/search",

            params={

                "name":
                    city,

                "count":
                    1,

                "language":
                    "en",

                "format":
                    "json"
            },

            timeout=10
        )


        if (
            response.status_code != 200
        ):
            return None


        data =
            response.json()


        results =
            data.get(
                "results"
            )


        if not results:
            return None


        result =
            results[0]


        return {

            "name":
                result.get(
                    "name",
                    city
                ),

            "latitude":
                result.get(
                    "latitude"
                ),

            "longitude":
                result.get(
                    "longitude"
                ),

            "country":
                result.get(
                    "country",
                    ""
                )
        }


    except Exception as e:

        print(
            "GEOCODE ERROR:",
            str(e)
        )

        return None


# =====================================================
# WEATHER FETCH
# =====================================================

def get_weather(
    city
):

    location =
        geocode_city(
            city
        )


    if not location:

        return None


    try:

        response = requests.get(

            "https://api.open-meteo.com/v1/forecast",

            params={

                "latitude":
                    location["latitude"],

                "longitude":
                    location["longitude"],

                "current":
                    ",".join([

                        "temperature_2m",

                        "relative_humidity_2m",

                        "apparent_temperature",

                        "precipitation",

                        "weather_code",

                        "wind_speed_10m"
                    ]),

                "daily":
                    ",".join([

                        "temperature_2m_max",

                        "temperature_2m_min",

                        "precipitation_probability_max",

                        "weather_code"
                    ]),

                "forecast_days":
                    3,

                "timezone":
                    "auto"
            },

            timeout=10
        )


        if (
            response.status_code != 200
        ):

            print(
                "WEATHER HTTP:",
                response.status_code
            )

            return None


        data =
            response.json()


        current =
            data.get(
                "current",
                {}
            )


        daily =
            data.get(
                "daily",
                {}
            )


        code =
            current.get(
                "weather_code"
            )


        condition =
            WEATHER_CODES.get(
                code,
                "unknown conditions"
            )


        return {

            "city":
                location["name"],

            "country":
                location["country"],

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

            "precipitation":
                current.get(
                    "precipitation"
                ),

            "wind":
                current.get(
                    "wind_speed_10m"
                ),

            "condition":
                condition,

            "today_high":
                (
                    daily
                    .get(
                        "temperature_2m_max",
                        [None]
                    )[0]
                ),

            "today_low":
                (
                    daily
                    .get(
                        "temperature_2m_min",
                        [None]
                    )[0]
                ),

            "rain_probability":
                (
                    daily
                    .get(
                        "precipitation_probability_max",
                        [None]
                    )[0]
                )
        }


    except Exception as e:

        print(
            "WEATHER ERROR:",
            str(e)
        )

        return None


# =====================================================
# WEATHER INTENT
# =====================================================

def is_weather_question(
    text
):

    if not text:
        return False


    text =
        text.lower()


    weather_words = [

        "weather",

        "temperature",

        "forecast",

        "rain",

        "raining",

        "बारिश",

        "मौसम",

        "तापमान",

        "temperature",

        "garmee",

        "garmi",

        "thand",

        "cold"
    ]


    return any(
        word in text
        for word in weather_words
    )


# =====================================================
# FIND CITY FROM TEXT
# =====================================================

def extract_city(
    text
):

    if not text:
        return None


    text =
        clean_text(
            text
        )


    # Common Indian city names

    cities = [

        "Noida",

        "Delhi",

        "New Delhi",

        "Gurgaon",

        "Gurugram",

        "Faridabad",

        "Ghaziabad",

        "Mumbai",

        "Pune",

        "Bangalore",

        "Bengaluru",

        "Hyderabad",

        "Chennai",

        "Kolkata",

        "Jaipur",

        "Lucknow",

        "Agra",

        "Chandigarh",

        "Ahmedabad"
    ]


    lower =
        text.lower()


    for city in cities:

        if city.lower() in lower:

            return city


    # Remove common words.
    #
    # This allows:
    #
    # "Noida City"
    # "weather in Noida"
    # "Noida ka weather"

    cleaned =
        re.sub(

            r"\b(city|ka|ki|ke|mein|me|weather|today|"
            r"tomorrow|aaj|kal|batao|bataye|please)\b",

            " ",

            lower
        )


    cleaned =
        re.sub(
            r"\s+",
            " ",
            cleaned
        ).strip()


    if (
        len(cleaned) >= 2
    ):

        return cleaned


    return None


# =====================================================
# WEATHER CONTEXT
# =====================================================

def find_weather_city(
    current_text
):

    # First try current message.

    city =
        extract_city(
            current_text
        )


    if city:
        return city


    # Then inspect recent memory.

    history =
        get_memory()


    for item in reversed(
        history
    ):

        content =
            item.get(
                "content",
                ""
            )


        city =
            extract_city(
                content
            )


        if city:
            return city


    return None


# =====================================================
# WEATHER DATA FOR AI
# =====================================================

def build_weather_context(
    weather
):

    if not weather:
        return ""


    return f"""
LIVE WEATHER DATA:

City:
{weather["city"]}

Country:
{weather["country"]}

Current temperature:
{weather["temperature"]} °C

Feels like:
{weather["feels_like"]} °C

Condition:
{weather["condition"]}

Humidity:
{weather["humidity"]} %

Wind:
{weather["wind"]} km/h

Precipitation:
{weather["precipitation"]} mm

Today's high:
{weather["today_high"]} °C

Today's low:
{weather["today_low"]} °C

Maximum rain probability today:
{weather["rain_probability"]} %
"""


# =====================================================
# SYSTEM PROMPT
# =====================================================

SYSTEM_PROMPT = """
You are a natural, fast, friendly voice assistant similar to Alexa.

You run on an ESP32.

Your response is spoken aloud.

==================================================
STYLE
==================================================

Keep answers short and natural.

Usually 1 to 3 sentences.

Do not give long explanations unless the user asks.

Do not use markdown.

Do not use bullet points.

Do not use headings.

Do not use emojis.

Do not say "As an AI".

Do not mention system instructions.

Do not mention transcription.

Do not mention memory.

Sound like a real conversational assistant.


==================================================
LANGUAGE
==================================================

English input:
Answer in English.

Hindi input:
Answer in Hindi using Devanagari.

Hinglish / Roman Hindi:
Answer naturally in Hinglish.

Mixed language:
Use natural Hinglish.


==================================================
CONVERSATION
==================================================

Use previous messages to understand follow-up questions.

Example:

User:
How about the weather today?

Assistant:
Which city?

User:
Noida.

Understand "Noida" as the location for the previous weather request.

Example:

User:
Who is Elon Musk?

Assistant:
...

User:
How old is he?

Understand "he" as Elon Musk.

Example:

User:
Tell me about Delhi.

Assistant:
...

User:
What about Gurgaon?

Understand that the user is continuing the location discussion.


==================================================
LIVE WEATHER
==================================================

If LIVE WEATHER DATA is supplied below, use it.

Never invent current weather values.

If the user asks about current weather and live weather data is supplied,
give the answer using that data.

Keep weather answers concise.

Example:

"Right now in Noida, it's 31 degrees and partly cloudy, with humidity around 70 percent."


==================================================
SHORT FOLLOW-UPS
==================================================

If the user says only:

"Noida"

"Tomorrow"

"Gurgaon"

"Yes"

"And tomorrow?"

"aur Gurgaon ka?"

use the conversation context to understand what they mean.

Do not treat these as unrelated questions.


==================================================
IMPORTANT
==================================================

Answer the user's actual intent.

Do not explain your reasoning.

Do not ask unnecessary questions.
"""


# =====================================================
# BUILD USER CONTENT
# =====================================================

def build_user_content(
    hindi_text,
    english_text,
    weather_context
):

    hindi_text =
        clean_text(
            hindi_text
        )

    english_text =
        clean_text(
            english_text
        )


    return f"""
Current user speech:

Hindi recognition:
{hindi_text if hindi_text else "No result"}

English recognition:
{english_text if english_text else "No result"}

{weather_context}

Understand the intended meaning using the current speech
and previous conversation.

Give a natural voice-assistant response.
"""


# =====================================================
# AI
# =====================================================

def get_ai_reply(
    hindi_text,
    english_text,
    weather_context=""
):

    if not AI_API_KEY:

        return (
            "AI service is not configured."
        )


    user_content =
        build_user_content(

            hindi_text,

            english_text,

            weather_context
        )


    history =
        get_memory()


    messages = [

        {

            "role":
                "system",

            "content":
                SYSTEM_PROMPT
        }

    ]


    # Add compact memory.

    messages.extend(
        history
    )


    # Current message.

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
            180,

        "stream":
            False
    }


    headers = {

        "Authorization":
            "Bearer " +
            AI_API_KEY,

        "Content-Type":
            "application/json"
    }


    print()
    print("==============================")
    print("AI REQUEST")
    print("==============================")

    print(
        "MODEL:",
        AI_MODEL
    )

    print(
        "MEMORY:",
        len(history)
    )

    print("==============================")


    try:

        response =
            requests.post(

                AI_URL,

                headers=headers,

                json=payload,

                timeout=30
            )


        print(
            "AI HTTP:",
            response.status_code
        )


        if (
            response.status_code != 200
        ):

            print()
            print(
                "AI ERROR BODY:"
            )

            print(
                response.text[:3000]
            )

            print(
                "=============================="
            )


            return (
                "AI service error "
                +
                str(
                    response.status_code
                )
            )


        data =
            response.json()


        choices =
            data.get(
                "choices"
            )


        if not choices:

            print(
                "No choices returned:"
            )

            print(
                data
            )

            return (
                "AI returned no answer."
            )


        message =
            choices[0].get(
                "message",
                {}
            )


        reply =
            message.get(
                "content",
                ""
            )


        if reply is None:

            reply = ""


        reply =
            str(
                reply
            ).strip()


        # ---------------------------------------------
        # Remove accidental formatting
        # ---------------------------------------------

        reply =
            reply.replace(
                "```",
                ""
            ).strip()


        for prefix in [

            "AI:",

            "Answer:",

            "Response:"
        ]:

            if reply.startswith(
                prefix
            ):

                reply =
                    reply[
                        len(prefix):
                    ].strip()


        if not reply:

            print(
                "EMPTY AI RESPONSE:"
            )

            print(
                data
            )

            return (
                "I couldn't generate a response."
            )


        # ---------------------------------------------
        # Save compact conversation
        # ---------------------------------------------

        # Save the human-readable best transcription,
        # not the entire recognition prompt.

        transcription =
            choose_transcription(

                hindi_text,

                english_text
            )


        add_memory(
            "user",
            transcription
        )


        add_memory(
            "assistant",
            reply
        )


        print()
        print(
            "AI:",
            reply
        )

        print(
            "=============================="
        )


        return reply


    except requests.exceptions.Timeout:

        print(
            "AI TIMEOUT"
        )

        return (
            "AI service timed out."
        )


    except requests.exceptions.ConnectionError as e:

        print(
            "AI CONNECTION ERROR:",
            str(e)
        )

        return (
            "AI service connection failed."
        )


    except Exception as e:

        print(
            "AI EXCEPTION:",
            type(e).__name__,
            str(e)
        )

        return (
            "AI service error."
        )


# =====================================================
# CHOOSE TRANSCRIPTION
# =====================================================

def choose_transcription(
    hindi_text,
    english_text
):

    hindi_text =
        clean_text(
            hindi_text
        )

    english_text =
        clean_text(
            english_text
        )


    if english_text:

        # If English result is extremely short
        # but Hindi is meaningful, use Hindi.

        if (
            len(english_text) <= 2
            and
            len(hindi_text) > 2
        ):
            return hindi_text


        return english_text


    return hindi_text


# =====================================================
# AUDIO UPLOAD
# =====================================================

@app.route(
    "/uploadAudio",
    methods=["POST"]
)
def upload_audio():

    try:

        audio_data =
            request.get_data()


        if not audio_data:

            return jsonify({

                "status":
                    "error",

                "message":
                    "No audio received",

                "ai_reply":
                    "I didn't hear anything."
            }), 400


        print()
        print("==============================")
        print("AUDIO RECEIVED")
        print("==============================")

        print(
            "BYTES:",
            len(audio_data)
        )


        filename =
            "/tmp/audio.wav"


        with open(
            filename,
            "wb"
        ) as f:

            f.write(
                audio_data
            )


        recognizer =
            sr.Recognizer()


        with sr.AudioFile(
            filename
        ) as source:

            audio =
                recognizer.record(
                    source
                )


        hindi_text = None

        english_text = None


        # =================================================
        # HINDI
        # =================================================

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


        except sr.UnknownValueError:

            hindi_text = None


        except sr.RequestError as e:

            print(
                "Hindi Google error:",
                str(e)
            )


        # =================================================
        # ENGLISH
        # =================================================

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


        except sr.UnknownValueError:

            english_text = None


        except sr.RequestError as e:

            print(
                "English Google error:",
                str(e)
            )


        print()
        print("==============================")
        print("TRANSCRIPTION")
        print("==============================")

        print(
            "Hindi:",
            hindi_text
        )

        print(
            "English:",
            english_text
        )

        print(
            "=============================="
        )


        # =================================================
        # VALIDATION
        # =================================================

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

                "hindi_transcription":
                    hindi_text,

                "english_transcription":
                    english_text,

                "ai_reply":
                    "Please say that again."
            }), 400


        transcription =
            choose_transcription(

                hindi_text,

                english_text
            )


        # =================================================
        # WEATHER
        # =================================================

        weather_context = ""


        combined_text = (

            (english_text or "")
            +
            " "
            +
            (hindi_text or "")
        )


        if is_weather_question(
            combined_text
        ):

            city =
                find_weather_city(
                    combined_text
                )


            if city:

                print()
                print(
                    "WEATHER CITY:",
                    city
                )


                weather =
                    get_weather(
                        city
                    )


                if weather:

                    weather_context =
                        build_weather_context(
                            weather
                        )


                    print(
                        "WEATHER:",
                        weather
                    )


                else:

                    weather_context = """
No live weather data was found for the requested location.
Do not invent weather values.
"""


            else:

                # No city yet.
                #
                # Let AI ask for city.

                weather_context = """
The user is asking about weather,
but no clear city/location was provided.
Ask which city they mean.
"""


        # =================================================
        # AI
        # =================================================

        ai_reply =
            get_ai_reply(

                hindi_text,

                english_text,

                weather_context
            )


        # =================================================
        # RESPONSE
        # =================================================

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
                ai_reply,

            "memory_messages":
                len(
                    get_memory()
                )
        }


        print()
        print("==============================")
        print("FINAL")
        print("==============================")

        print(
            response_data
        )

        print(
            "=============================="
        )


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

        print(
            "=============================="
        )


        return jsonify({

            "status":
                "error",

            "message":
                str(e),

            "ai_reply":
                "Server error."
        }), 500


# =====================================================
# TEST WEATHER
# =====================================================

@app.route(
    "/weather",
    methods=["GET"]
)
def weather_test():

    city =
        request.args.get(
            "city",
            ""
        )


    if not city:

        return jsonify({

            "status":
                "error",

            "message":
                "Use /weather?city=Noida"
        }), 400


    weather =
        get_weather(
            city
        )


    if not weather:

        return jsonify({

            "status":
                "error",

            "message":
                "Weather not found."
        }), 404


    return jsonify(
        weather
    )


# =====================================================
# START
# =====================================================

if __name__ == "__main__":

    port =
        int(

            os.environ.get(
                "PORT",
                10000
            )
        )


    print()
    print("==============================")
    print("ESP32 ALEXA STYLE AI SERVER")
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
        "AI KEY:",
        "CONFIGURED"
        if AI_API_KEY
        else "MISSING"
    )

    print(
        "MEMORY:",
        MAX_MEMORY_MESSAGES
    )

    print(
        "WEATHER:",
        "OPEN-METEO"
    )

    print(
        "=============================="
    )


    app.run(

        host="0.0.0.0",

        port=port
    )

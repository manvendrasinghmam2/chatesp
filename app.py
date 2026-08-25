import os
import requests
import json
import traceback


# ============================================================
# CONFIG
# ============================================================

API_KEY = os.environ.get("AI_API_KEY")

TTS_URL = "https://api.groq.com/openai/v1/audio/speech"

TTS_MODEL = "canopylabs/orpheus-v1-english"

TTS_VOICE = "hannah"


# ============================================================
# TEST
# ============================================================

def test_tts():

    print()
    print("========================================")
    print("GROQ TTS DIRECT TEST")
    print("========================================")

    print("API KEY:", "FOUND" if API_KEY else "MISSING")
    print("TTS URL:", TTS_URL)
    print("MODEL:", TTS_MODEL)
    print("VOICE:", TTS_VOICE)

    print("========================================")

    if not API_KEY:
        print("ERROR: AI_API_KEY is missing")
        return

    text = "Hello, I am Hannah. How can I help you?"

    payload = {
        "model": TTS_MODEL,
        "input": text,
        "voice": TTS_VOICE,
        "response_format": "wav"
    }

    headers = {
        "Authorization": "Bearer " + API_KEY,
        "Content-Type": "application/json",
        "Accept": "audio/wav"
    }

    print()
    print("TEXT:")
    print(text)

    print()
    print("SENDING REQUEST...")
    print("========================================")

    try:

        response = requests.post(
            TTS_URL,
            headers=headers,
            json=payload,
            timeout=60
        )

        print()
        print("HTTP STATUS:")
        print(response.status_code)

        print()
        print("CONTENT TYPE:")
        print(response.headers.get("Content-Type"))

        print()
        print("CONTENT LENGTH:")
        print(response.headers.get("Content-Length"))

        print()
        print("ALL HEADERS:")
        print(dict(response.headers))

        # ====================================================
        # SUCCESS
        # ====================================================

        if response.status_code == 200:

            audio = response.content

            print()
            print("========================================")
            print("TTS SUCCESS")
            print("========================================")

            print("AUDIO BYTES:")
            print(len(audio))

            if len(audio) == 0:
                print("ERROR: Empty audio received")
                return

            with open(
                "hannah-test.wav",
                "wb"
            ) as f:

                f.write(audio)

            print()
            print("FILE CREATED:")
            print("hannah-test.wav")

            print()
            print("TTS IS WORKING!")
            print("========================================")

            return

        # ====================================================
        # ERROR
        # ====================================================

        print()
        print("========================================")
        print("TTS FAILED")
        print("========================================")

        print("HTTP STATUS:")
        print(response.status_code)

        print()
        print("RAW ERROR BODY:")

        try:
            print(response.text)

        except Exception:
            print("Unable to read response text")

        print()
        print("========================================")

        # Try JSON
        try:

            error_json = response.json()

            print("JSON ERROR:")
            print(
                json.dumps(
                    error_json,
                    indent=2
                )
            )

        except Exception:

            print("Response is not JSON")

        print("========================================")

    except requests.exceptions.Timeout:

        print()
        print("========================================")
        print("REQUEST TIMEOUT")
        print("========================================")

    except requests.exceptions.ConnectionError as e:

        print()
        print("========================================")
        print("CONNECTION ERROR")
        print("========================================")

        print(str(e))

    except Exception as e:

        print()
        print("========================================")
        print("PYTHON ERROR")
        print("========================================")

        print(type(e).__name__)
        print(str(e))

        traceback.print_exc()


# ============================================================
# START
# ============================================================

if __name__ == "__main__":
    test_tts()

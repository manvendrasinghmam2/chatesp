import os
import requests

API_KEY = os.environ.get("AI_API_KEY")

URL = "https://api.groq.com/openai/v1/audio/speech"

MODEL = "canopylabs/orpheus-v1-english"
VOICE = "hannah"

TEXT = "Hello, I am Hannah. How can I help you?"

print("========================================")
print("GROQ TTS TEST")
print("========================================")

if not API_KEY:
    print("ERROR: AI_API_KEY missing")
    exit()

payload = {
    "model": MODEL,
    "input": TEXT,
    "voice": VOICE,
    "response_format": "wav"
}

headers = {
    "Authorization": "Bearer " + API_KEY,
    "Content-Type": "application/json",
    "Accept": "audio/wav"
}

print("MODEL:", MODEL)
print("VOICE:", VOICE)
print("TEXT:", TEXT)
print("SENDING REQUEST...")

try:

    response = requests.post(
        URL,
        headers=headers,
        json=payload,
        timeout=60
    )

    print()
    print("HTTP STATUS:", response.status_code)
    print("CONTENT TYPE:",
          response.headers.get("Content-Type"))
    print("CONTENT LENGTH:",
          response.headers.get("Content-Length"))
    print("BYTES RECEIVED:",
          len(response.content))

    if response.status_code == 200:

        if len(response.content) == 0:
            print("ERROR: Empty audio received")
            exit()

        filename = "hannah_test.wav"

        with open(filename, "wb") as f:
            f.write(response.content)

        print()
        print("========================================")
        print("TTS SUCCESS")
        print("========================================")
        print("FILE:", filename)
        print("AUDIO BYTES:", len(response.content))
        print("You can play:", filename)

    else:

        print()
        print("========================================")
        print("TTS FAILED")
        print("========================================")

        print("STATUS:", response.status_code)

        print("SERVER RESPONSE:")
        print(response.text[:10000])

        print("========================================")

except requests.exceptions.Timeout:

    print("ERROR: TTS REQUEST TIMEOUT")

except requests.exceptions.ConnectionError as e:

    print("ERROR: NETWORK / CONNECTION")
    print(e)

except Exception as e:

    print("ERROR:", type(e).__name__)
    print(e)

from flask import Flask, request, jsonify
import os

app = Flask(__name__)

# 10 MB limit
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024


@app.route("/", methods=["GET"])
def home():
    return "ESP32 AI SERVER OK", 200


@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "status": "online",
        "upload_test": "enabled"
    }), 200


@app.route("/uploadAudio", methods=["POST"])
def upload_audio():

    print("================================")
    print("UPLOAD AUDIO REQUEST")
    print("================================")

    print("METHOD:", request.method)
    print("CONTENT TYPE:", request.content_type)
    print("CONTENT LENGTH:", request.content_length)

    try:
        # Read complete body
        data = request.get_data(
            cache=False,
            as_text=False
        )

        size = len(data)

        print("BODY RECEIVED")
        print("BYTES:", size)

        if size == 0:
            print("ERROR: EMPTY BODY")

            return jsonify({
                "status": "error",
                "message": "Empty audio body",
                "bytes": 0
            }), 400

        # Basic WAV check
        if size >= 12:

            riff = data[0:4]
            wave = data[8:12]

            print("HEADER:", riff, wave)

            if riff == b"RIFF" and wave == b"WAVE":
                print("WAV HEADER: OK")
            else:
                print("WAV HEADER: INVALID")

        print("UPLOAD SUCCESS")

        return jsonify({
            "status": "ok",
            "message": "Audio received",
            "bytes": size
        }), 200

    except Exception as e:

        print("UPLOAD ERROR:", repr(e))

        return jsonify({
            "status": "error",
            "error": str(e)
        }), 500


@app.errorhandler(413)
def too_large(error):

    print("UPLOAD TOO LARGE")

    return jsonify({
        "status": "error",
        "message": "Audio too large"
    }), 413


@app.errorhandler(400)
def bad_request(error):

    print("BAD REQUEST:", repr(error))

    return jsonify({
        "status": "error",
        "message": "Bad request"
    }), 400


if __name__ == "__main__":

    port = int(os.environ.get("PORT", 10000))

    app.run(
        host="0.0.0.0",
        port=port
    )

from flask import Flask, request, jsonify

app = Flask(__name__)


@app.route("/")
def home():
    return "ESP32 AI SERVER OK", 200


@app.route("/health")
def health():
    return jsonify({
        "status": "online",
        "upload_test": "enabled"
    }), 200


@app.route("/uploadAudio", methods=["POST"])
def upload_audio():

    print("================================")
    print("UPLOAD AUDIO REQUEST RECEIVED")
    print("================================")

    print("Method:", request.method)
    print("Content-Type:", request.content_type)
    print("Content-Length:", request.content_length)

    try:

        data = request.get_data()

        print("AUDIO RECEIVED")
        print("Bytes:", len(data))

        return jsonify({
            "status": "ok",
            "message": "Audio received",
            "bytes": len(data)
        }), 200

    except Exception as e:

        print("UPLOAD ERROR:", repr(e))

        return jsonify({
            "status": "error",
            "error": str(e)
        }), 500


if __name__ == "__main__":

    import os

    port = int(
        os.environ.get(
            "PORT",
            10000
        )
    )

    app.run(
        host="0.0.0.0",
        port=port
    )

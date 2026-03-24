import os
import sys

from flask import Flask, jsonify, render_template, request
from flask_cors import CORS


sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from API.chatbot import chatbot_reply  # noqa: E402


app = Flask(
    __name__,
    template_folder="../FRONTEND",
    static_folder="../FRONTEND",
    static_url_path="",
)
CORS(app)


@app.route("/")
def home():
    return render_template("chat.html")


@app.route("/api/chat", methods=["POST"])
def chat():
    try:
        data = request.get_json(silent=True) or {}
        message = str(data.get("message", "")).strip()
        session_id = str(data.get("session_id", "default")).strip() or "default"

        if not message:
            return jsonify({"error": "Message vide", "status": "error"}), 400

        reply = chatbot_reply(message, session_id=session_id)
        return jsonify(
            {
                "response": reply["response"],
                "intent": reply["intent"],
                "confidence": round(float(reply["confidence"]), 4),
                "matched_pattern": reply["matched_pattern"],
                "quick_replies": reply["quick_replies"],
                "status": "success",
            }
        )
    except Exception as exc:
        print(f"Erreur API: {exc}")
        return jsonify({"error": str(exc), "status": "error"}), 500


if __name__ == "__main__":
    print("\n" + "=" * 50)
    print("Demarrage de l'API Assistant M365...")
    print("Accedez au chatbot sur : http://localhost:5000")
    print("=" * 50 + "\n")
    app.run(debug=True, host="0.0.0.0", port=5000)

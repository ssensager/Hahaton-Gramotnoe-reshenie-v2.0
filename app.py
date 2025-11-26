from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), "backend"))
from chat import ChatRAG


import time

app = Flask(__name__)
CORS(app)

rag = ChatRAG()

chats = {}


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/new_chat", methods=["POST"])
def new_chat():
    chat_id = int(time.time() * 1000)
    chats[chat_id] = []
    return jsonify({"chat_id": chat_id})


@app.route("/api/delete_chat", methods=["POST"])
def delete_chat():
    data = request.json
    chat_id = data.get("chat_id")
    if chat_id in chats:
        del chats[chat_id]
    return jsonify({"status": "ok"})


@app.route("/api/get_messages/<int:chat_id>", methods=["GET"])
def get_messages(chat_id):
    return jsonify({"messages": chats.get(chat_id, [])})


@app.route("/api/send_message", methods=["POST"])
def send_message():
    data = request.json
    chat_id = data.get("chat_id")
    user_msg = data.get("message", "")

    if chat_id not in chats:
        return jsonify({"error": "chat not found"}), 404

    chats[chat_id].append({"role": "user", "text": user_msg})


    ai_reply = rag.answer(user_msg)

    if isinstance(ai_reply, dict):
        raw_answer = ai_reply.get("answer") or ""
        rag_ctx = ai_reply.get("rag_context")
        raw_top_docs = ai_reply.get("top_documents")

        # Truncate each top_documents element after the first period.
        top_docs_list = []
        if isinstance(raw_top_docs, list):
            for item in raw_top_docs:
                s = str(item) if item is not None else ""
                idx = s.find('.')
                if idx != -1:
                    top_docs_list.append(s[:idx].strip())
                else:
                    top_docs_list.append(s.strip())
        elif raw_top_docs is not None:
            s = str(raw_top_docs)
            idx = s.find('.')
            if idx != -1:
                top_docs_list = [s[:idx+1].strip()]
            else:
                top_docs_list = [s.strip()]
        else:
            top_docs_list = []

        top_docs_text = "\n".join([t for t in top_docs_list if t])

        answer_text = str(raw_answer)
        if top_docs_text:
            answer_text = answer_text + "\n\nДокументы:\n" + top_docs_text

        top_docs = raw_top_docs
    else:
        answer_text = str(ai_reply)
        rag_ctx = None
        top_docs = None

    chats[chat_id].append({"role": "ai", "text": answer_text})

    return jsonify({"reply": answer_text, "rag_context": rag_ctx, "top_documents": top_docs})


if __name__ == "__main__":
    app.run(debug=True)

import json
import numpy as np
import pandas as pd
import faiss
import torch
import os
from sentence_transformers import SentenceTransformer
from transformers import AutoTokenizer, AutoModelForSequenceClassification
from llama_cpp import Llama


INDEX_DIR = "backend/step2_index"
SBERT_DIR = "backend/models/sbert_local"
RERANK_DIR = "backend/models/reranker_local"

TOP_K = 10
LLM_PATH = "backend/models/qwen/qwen2.5-1.5b-instruct-q4_k_m.gguf"

HISTORY_SIZE = 5


def load_llm():
    llm = Llama(
        model_path=LLM_PATH,
        n_ctx=32768,
        n_threads=6,
        n_gpu_layers=0,
        verbose=False
    )
    return llm


def ask_llm(llm, user_question, rag_context, chat_history):
    history_text = ""
    for msg in chat_history[-HISTORY_SIZE:]:
        history_text += f"<|im_start|>{msg['role']}\n{msg['text']}<|im_end|>\n"

    prompt = f"""
<|im_start|>system
Ты — русскоязычный RAG-ассистент.
Отвечай строго по предоставленному контексту RAG и истории диалога.
Не придумывай фактов. 
Если контекст не содержит ответа — скажи об этом.
<|im_end|>

{history_text}

<|im_start|>user
Вопрос: {user_question}

Контекст (RAG):
{rag_context}
<|im_end|>

<|im_start|>assistant
"""
    out = llm(prompt, max_tokens=256, stop=["<|im_end|>", "<|im_start|>"])
    return out["choices"][0]["text"].strip()



def extract_best_sentences(question, text, max_sentences=2):
    text = text.replace("\n", " ").replace("\t", " ")
    sents = [s.strip() for s in text.split(".") if len(s.strip()) > 8]
    if not sents:
        return text[:700]

    q_words = set([w.lower() for w in question.split() if len(w) > 2])
    scored = []
    for s in sents:
        s_words = set(w.lower() for w in s.split())
        score = len(q_words & s_words)
        scored.append((score, -len(s), s))

    scored.sort(reverse=True)
    return " ".join([x[2] for x in scored[:max_sentences]])[:700]


def clean_text(t):
    t = t.replace("\n", " ").replace("•", " ")
    return " ".join(t.split())


def normalize_scores(arr):
    arr = np.array(arr, dtype="float32")
    arr -= np.min(arr)
    if np.max(arr) > 0:
        arr /= (np.max(arr) + 1e-9)
    return arr



def try_load_reranker(path):
    try:
        tok = AutoTokenizer.from_pretrained(path)

        
        ckpt_path = os.path.join(path, "pytorch_model.bin")
        has_classifier = True
        if os.path.exists(ckpt_path):
            try:
                sd = torch.load(ckpt_path, map_location="cpu")
                keys = list(sd.keys()) if isinstance(sd, dict) else []
                has_classifier = any(
                    ("classifier.weight" in k or "classifier.bias" in k or k.endswith("classifier.weight") or k.endswith("classifier.bias"))
                    for k in keys
                )
            except Exception:
                
                has_classifier = True

        if not has_classifier:
            print(f"[WARN] reranker checkpoint at {path} is missing classifier weights — falling back to SBERT scoring")
            return None, None

        model = AutoModelForSequenceClassification.from_pretrained(path)
        return model, tok
    except Exception as e:
        print(f"[WARN] failed to load reranker from {path}: {e}")
        return None, None


def rerank_with_cross_encoder(model, tok, query, contexts, device="cpu"):
    try:
        enc = tok.batch_encode_plus(
            [(query, c) for c in contexts],
            padding=True, truncation=True,
            max_length=512, return_tensors="pt"
        )
        enc = {k: v.to(device) for k, v in enc.items()}
        with torch.no_grad():
            logits = model(**enc).logits
        return logits[:, 0].cpu().numpy()
    except:
        return None


def rerank_with_sbert(sbert, query, contexts):
    q = sbert.encode([query], convert_to_numpy=True)[0]
    c = sbert.encode(contexts, convert_to_numpy=True)
    q /= np.linalg.norm(q) + 1e-12
    c /= np.linalg.norm(c, axis=1, keepdims=True) + 1e-12
    return (c @ q).astype("float32")


class ChatRAG:
    def __init__(self):

        print("→ Load SBERT")
        self.sbert = SentenceTransformer(SBERT_DIR)

        print("→ Load reranker")
        self.rerank_model, self.rerank_tok = try_load_reranker(RERANK_DIR)
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        if self.rerank_model:
            self.rerank_model.to(self.device)
            print("[OK] cross-encoder loaded")
        else:
            print("[INFO] fallback to SBERT scoring")

        print("→ Load FAISS")
        self.index = faiss.read_index(os.path.join(INDEX_DIR, "faiss_index.idx"))

        print("→ Load metadata")
        self.metas = []
        with open(os.path.join(INDEX_DIR, "meta.jsonl"), "r", encoding="utf-8") as f:
            for l in f:
                self.metas.append(json.loads(l))

        print("→ Load LLM")
        self.llm = load_llm()

        self.history = []

    def add_history(self, role, text):
        self.history.append({"role": role, "text": text})

    def answer(self, user_message):
        self.add_history("user", user_message)
        q_emb = self.sbert.encode([user_message], convert_to_numpy=True)[0].astype("float32")
        faiss.normalize_L2(q_emb.reshape(1, -1))

        D, I = self.index.search(q_emb.reshape(1, -1), TOP_K)

        ctx_raw = []
        docs_raw = []

        for i in I[0]:
            ctx_raw.append(clean_text(self.metas[i]["text"]))
            docs_raw.append(self.metas[i]["doc"])

        ce_scores = (
            rerank_with_cross_encoder(
                self.rerank_model, self.rerank_tok, user_message, ctx_raw, self.device
            )
            if self.rerank_model
            else None
        )

        if ce_scores is None:
            ce_scores = rerank_with_sbert(self.sbert, user_message, ctx_raw)

        final_scores = normalize_scores(ce_scores)
        order = np.argsort(-final_scores)

        
        top_ctx = []
        top_docs = []
        for idx in order[:3]:
            best = extract_best_sentences(user_message, ctx_raw[idx], max_sentences=3)
            top_ctx.append(best)
            top_docs.append(docs_raw[idx])

        rag_context = "\n---\n".join(top_ctx)[:4000]

        
        answer = ask_llm(self.llm, user_message, rag_context, self.history)

        self.add_history("assistant", answer)

        
        return {
            "answer": answer,
            "rag_context": rag_context,
            "top_documents": top_docs
        }



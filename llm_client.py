# llm_client.py
from llama_cpp import Llama
import os

MODEL_PATH = "/home/dima/models/qwen2.5-1.5b-instruct-q4_k_m.gguf"
llm = None

def get_llm():
    global llm
    if llm is None:
        print("🔄 Загрузка LLM...")
        llm = Llama(model_path=MODEL_PATH, n_ctx=1024, n_threads=2, verbose=False)
        print("✅ LLM загружена")
    return llm

def generate(prompt, max_tokens=128):
    model = get_llm()
    response = model.create_chat_completion(
        messages=[
            {"role": "system", "content": "Ты домашний ассистент Вася. Отвечай кратко."},
            {"role": "user", "content": prompt}
        ],
        max_tokens=max_tokens,
        temperature=0.5
    )
    return response["choices"][0]["message"]["content"]

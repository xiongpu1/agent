import os

Qwen_API_KEY = os.getenv("DASHSCOPE_API_KEY")
Qwen_URL_BASE = "https://dashscope.aliyuncs.com/compatible-mode/v1"
Qwen_MODEL = "dashscope/qwen3-max"
Qwen_EMBEDDING = "dashscope/text-embedding-v4" # 禁止使用，因为LiteLLM不支持dashscope/text-embedding-v4

# Gemini_KEY = os.getenv("GEMINI_API_KEY")
# Gemini_API_BASE = "https://gemini.googleapis.com/v1"
# Gemini_MODEL = "gemini/gemini-2.5-pro"

# Groq_KEY = os.getenv("GROQ_API_KEY")
# Groq_API_BASE = "https://api.groq.com/v1"
# Groq_MODEL = "groq/llama-3.3-70b-versatile"

Ollama_QWEN3_VL_MODEL = "ollama/qwen3-vl:30b-a3b-instruct-bf16"
Ollama_QWEN3_EMBEDDING = "ollama/qwen3-embedding:latest"
Ollama_BASE_URL = "http://localhost:11434"
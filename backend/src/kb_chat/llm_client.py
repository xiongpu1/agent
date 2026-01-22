import os
from typing import Any, Dict, Iterator, List, Optional

from litellm import completion


def _build_kwargs(messages: List[Dict[str, str]], model: Optional[str] = None, stream: bool = False) -> Dict[str, Any]:
    m = (model or os.getenv("DEFAULT_LLM_MODEL", "")).strip() or "dashscope/qwen3-max"

    timeout_s = 60
    try:
        timeout_s = int(os.getenv("KBCHAT_LLM_TIMEOUT_SECONDS", "60"))
    except Exception:
        timeout_s = 60

    kwargs: Dict[str, Any] = {
        "model": m,
        "messages": messages,
        "temperature": 0.2,
        "stream": stream,
        "timeout": timeout_s,
        "request_timeout": timeout_s,
    }

    api_key = os.getenv("DASHSCOPE_API_KEY")
    if api_key:
        kwargs["api_key"] = api_key

    kwargs["api_base"] = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    return kwargs


def chat_json(messages: List[Dict[str, str]], model: Optional[str] = None) -> Any:
    resp = completion(**_build_kwargs(messages=messages, model=model, stream=False))
    return resp


def chat_stream(messages: List[Dict[str, str]], model: Optional[str] = None) -> Iterator[Any]:
    return completion(**_build_kwargs(messages=messages, model=model, stream=True))

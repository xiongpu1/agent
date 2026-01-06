"""Unified LLM client wrapper built on top of litellm.

The client supports both remote DashScope (qwen3-max) and local Ollama
deployments by selecting the appropriate API key and base URL. The public
interface (`generate` / `generate_with_retry`) remains stable so higher-level
ACE agents do not need to change when switching models.
"""

import json
import logging
import os
import time
from typing import Dict, Any, Optional

from litellm import completion


logger = logging.getLogger(__name__)


class LLMClient:
    """Wrapper for litellm-backed LLM calls (DashScope or Ollama)."""

    def __init__(
        self,
        api_key: Optional[str],
        model_name: str = "qwen3-vl",
        base_url: Optional[str] = None,
    ):
        raw_model = model_name or os.environ.get("ACE_LLM_MODEL")
        if not raw_model or raw_model == "qwen3-vl":
            raw_model = os.environ.get("OLLAMA_MODEL", "ollama/qwen3-vl:30b-a3b-instruct-bf16")
        self.model_name = raw_model

        # Decide provider based on prefix; default to Ollama if unspecified.
        if base_url:
            api_base = base_url
        elif self.model_name.startswith("dashscope/"):
            api_base = os.environ.get(
                "DASHSCOPE_API_BASE_URL",
                "https://dashscope.aliyuncs.com/compatible-mode/v1",
            )
        else:
            api_base = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")

        self.api_base = api_base.rstrip("/")

        if api_key:
            self.api_key = api_key
        elif self.model_name.startswith("dashscope/"):
            self.api_key = os.environ.get("DASHSCOPE_API_KEY")
        else:
            self.api_key = (
                os.environ.get("OLLAMA_API_KEY")
                or os.environ.get("GROQ_API_KEY")
                or "ollama"
            )

    def _call_model(
        self,
        prompt: str,
        temperature: float = 0.3,
        max_tokens: int = 1000,
    ) -> str:
        """Call configured LLM endpoint and return raw text content.

        The framework's prompts already instruct the model to answer in JSON,
        so this method simply returns the text content, which will then be
        parsed by `generate`. This implementation delegates to litellm, which
        understands both DashScope and Ollama-compatible endpoints.
        """

        resp = completion(
            model=self.model_name,
            api_base=self.api_base,
            api_key=self.api_key,
            messages=[
                {"role": "user", "content": prompt},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
        )

        # litellm returns an OpenAI-style response with choices.
        try:
            choices = getattr(resp, "choices", None) or resp["choices"]
        except Exception:
            raise ValueError(f"Unexpected litellm response format: {resp}")

        if not choices:
            raise ValueError(f"Empty litellm choices: {resp}")

        message = getattr(choices[0], "message", None) or choices[0]["message"]
        content = message.get("content")

        if not isinstance(content, str):
            raise ValueError(f"Unexpected message content in litellm response: {resp}")
        return content

    def generate(
        self,
        prompt: str,
        temperature: float = 0.3,
        max_tokens: int = 1000,
        response_format: str = "json",
    ) -> Optional[Dict[str, Any]]:
        """Generate completion from prompt via local Ollama.

        The prompts in this framework ask the model to respond in JSON.
        This method calls Ollama, then attempts to parse the returned text
        into a Python dictionary.

        Args:
            prompt: Input prompt
            temperature: Sampling temperature
            max_tokens: Maximum number of tokens to generate
            response_format: Expected response format (currently only json)
        Returns:
            Parsed JSON response or None on error
        """
        try:
            raw_text = self._call_model(
                prompt=prompt,
                temperature=temperature,
                max_tokens=max_tokens,
            )

            # The model is instructed to return JSON; try to parse it.
            raw_text = raw_text.strip()

            # In case the model wraps JSON with extra commentary, try to
            # extract the first JSON object/array.
            if not (raw_text.startswith("{") or raw_text.startswith("[")):
                # Best-effort: find first '{' and last '}'
                start = raw_text.find("{")
                end = raw_text.rfind("}")
                if start != -1 and end != -1 and end > start:
                    raw_text = raw_text[start : end + 1]

            return json.loads(raw_text)
        except Exception as e:
            logger.error(f"LLM generation error (local ollama): {e}")
            return None
    
    def generate_with_retry(
        self,
        prompt: str,
        temperature: float = 0.3,
        max_tokens: int = 1000,
        max_retries: int = 3,
        retry_delay: float = 1.0,
    ) -> Optional[Dict[str, Any]]:
        """Generate with simple retry logic for local Ollama calls."""

        last_error: Optional[Exception] = None
        for attempt in range(max_retries):
            try:
                result = self.generate(
                    prompt=prompt,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                if result is not None:
                    return result
            except Exception as e:
                last_error = e
                logger.error(
                    "Attempt %d/%d failed (local ollama): %s",
                    attempt + 1,
                    max_retries,
                    e,
                )

            if attempt < max_retries - 1:
                time.sleep(retry_delay)

        logger.error("All retry attempts to local Ollama failed. Last error: %s", last_error)
        return None
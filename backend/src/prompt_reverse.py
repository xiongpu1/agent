"""Generate reverse prompts from OCR images using qwen3-vl-plus."""

from __future__ import annotations

import base64
import json
import mimetypes
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Iterable, List, Tuple

from openai import OpenAI

DASHSCOPE_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
DEFAULT_MODEL = "qwen3-vl-plus-2025-12-19"
DEFAULT_USER_PROMPT = (
    "请用中文输出一句话画面描述，用于复现图片内容。\n"
    "要求：1) 1 句，不超过 60 字；2) 只写画面主体/场景/布局与清晰可见的关键文字或数值；"
    "3) 不要列表、不要步骤、不要解释；4) 仅输出描述文本。"
)
MAX_REVERSE_PROMPT_CHARS = int(os.getenv("PROMPT_REVERSE_MAX_CHARS", "90"))
MAX_REVERSE_PROMPT_TOKENS = int(os.getenv("PROMPT_REVERSE_MAX_TOKENS", "128"))
MAX_REVERSE_PROMPT_SENTENCES = int(os.getenv("PROMPT_REVERSE_MAX_SENTENCES", "1"))


def _normalize_reverse_prompt(text: str, *, max_chars: int = MAX_REVERSE_PROMPT_CHARS) -> str:
    content = (text or "").strip()
    if not content:
        return ""

    content = content.replace("\r\n", "\n").replace("\r", "\n")
    content = re.sub(r"```.*?```", "", content, flags=re.S)
    content = re.sub(r"^(提示词|描述|prompt|Prompt)\s*[:：]\s*", "", content).strip()
    content = content.strip('"\'“”‘’')
    content = re.sub(r"[ \t]+", " ", content)
    content = re.sub(r"\n{3,}", "\n\n", content).strip()

    lines = [line.strip() for line in content.split("\n") if line.strip()]
    cleaned_lines: List[str] = []
    for line in lines:
        line = re.sub(r"^[-*•]+\s+", "", line)
        line = re.sub(r"^\d+\s*[).、】【-]\s*", "", line)
        if line:
            cleaned_lines.append(line)

    if len(cleaned_lines) > 2:
        content = " ".join(cleaned_lines[:2])
    else:
        content = " ".join(cleaned_lines)

    sentences = [s.strip() for s in re.split(r"(?<=[。！？.!?])\s*", content) if s.strip()]
    max_sentences = MAX_REVERSE_PROMPT_SENTENCES
    if max_sentences > 0 and len(sentences) > max_sentences:
        content = " ".join(sentences[:max_sentences])
    else:
        content = " ".join(sentences)

    content = re.sub(r"\s+", " ", content).strip()

    if max_chars > 0 and len(content) > max_chars:
        suffix = "…"
        cut = max_chars - len(suffix)
        if cut <= 0:
            return suffix
        content = content[:cut].rstrip() + suffix
    return content


def _ensure_client() -> OpenAI:
    api_key = os.getenv("DASHSCOPE_API_KEY")
    if not api_key:
        raise RuntimeError("缺少 DASHSCOPE_API_KEY，无法调用 qwen3-vl-plus")
    return OpenAI(api_key=api_key, base_url=DASHSCOPE_BASE_URL)


def _guess_mime(path: Path) -> str:
    mime, _ = mimetypes.guess_type(path.name)
    return mime or "application/octet-stream"


def _image_to_data_url(image_path: Path) -> str:
    mime = _guess_mime(image_path)
    data = image_path.read_bytes()
    b64 = base64.b64encode(data).decode("utf-8")
    return f"data:{mime};base64,{b64}"


def generate_prompt_for_image(
    image_path: Path,
    *,
    model: str = DEFAULT_MODEL,
    user_prompt: str = DEFAULT_USER_PROMPT,
) -> Tuple[str, dict]:
    """
    Call qwen3-vl-plus to generate a reverse prompt for the given image.

    Returns (text_content, raw_response_dict)
    """
    client = _ensure_client()
    data_url = _image_to_data_url(image_path)

    completion = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": data_url}},
                    {"type": "text", "text": user_prompt},
                ],
            }
        ],
        max_tokens=MAX_REVERSE_PROMPT_TOKENS,
        stream=False,
    )

    choice = completion.choices[0].message
    content_text = _normalize_reverse_prompt(choice.content or "")
    raw = completion.model_dump()
    return content_text, raw


def run_prompt_reverse_for_entries(
    prepared_entries: Iterable[dict],
    output_root: Path,
    *,
    model: str = DEFAULT_MODEL,
    user_prompt: str = DEFAULT_USER_PROMPT,
) -> Tuple[List[str], List[dict]]:
    """
    For each prepared entry (contains label, relative_dir, image_stem, image_path),
    call qwen3-vl-plus and store outputs alongside OCR artifacts.

    Returns (warnings, logs) where logs is a list of dict entries.
    """
    warnings: List[str] = []
    logs: List[dict] = []
    try:
        client = _ensure_client()
    except Exception as exc:  # noqa: BLE001
        return [f"提示词反推已跳过：{exc}"], logs

    for entry in prepared_entries or []:
        try:
            label = entry["label"]
            relative_dir = entry.get("relative_dir")
            image_stem = entry["image_stem"]

            target_dir = output_root / label
            if relative_dir:
                target_dir = target_dir / relative_dir
            target_dir.mkdir(parents=True, exist_ok=True)

            images_dir = target_dir / "images"
            image_candidates = []
            if images_dir.exists():
                image_candidates = sorted(
                    p for p in images_dir.glob("*") if p.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}
                )

            if not image_candidates:
                warnings.append(f"{image_stem}: images/ 目录下未找到可用于提示词反推的图片")
                logs.append(
                    {
                        "label": label,
                        "image_stem": image_stem,
                        "image": str(images_dir),
                        "status": "error",
                        "prompt_path": "",
                        "message": "images/ 目录无图片，已跳过",
                    }
                )
                continue

            entry_page_stem = entry.get("image_stem") or ""
            for target_image_path in image_candidates:
                log_item = {
                    "label": label,
                    # Use page-level stem from prepared entry to avoid collisions across images named 0/1/2
                    "image_stem": entry_page_stem or target_image_path.stem,
                    "image": str(target_image_path),
                    "status": "processing",
                    "prompt_path": "",
                    "message": "",
                }

                data_url = _image_to_data_url(target_image_path)
                completion = client.chat.completions.create(
                    model=model,
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {"type": "image_url", "image_url": {"url": data_url}},
                                {"type": "text", "text": user_prompt},
                            ],
                        }
                    ],
                    max_tokens=MAX_REVERSE_PROMPT_TOKENS,
                    stream=False,
                )

                choice = completion.choices[0].message
                content_text = _normalize_reverse_prompt(choice.content or "")

                prompt_txt_path = images_dir / f"{target_image_path.stem}.txt"
                prompt_txt_path.write_text(content_text, encoding="utf-8")
                log_item["status"] = "success"
                log_item["prompt_path"] = str(prompt_txt_path)
                log_item["message"] = content_text[:200]
                logs.append(log_item)
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"{entry.get('image_stem')}: {exc}")
            log_item = {
                "label": entry.get("label"),
                "image_stem": entry.get("image_stem"),
                "image": str(entry.get("image_path")),
                "status": "error",
                "prompt_path": "",
                "message": str(exc),
            }
            logs.append(log_item)

    return warnings, logs

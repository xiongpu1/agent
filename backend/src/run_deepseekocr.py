#!/usr/bin/env python3
"""Reusable DeepSeek-OCR launcher with stdout capture."""

from __future__ import annotations

import argparse
import contextlib
import io
import os
import sys
from pathlib import Path
from typing import Callable, Iterable

from transformers import AutoModel, AutoTokenizer
import torch

# ---------------------------------------------------------------------------
# Model bootstrap
# ---------------------------------------------------------------------------
# Pin to GPU1 by default; override with env if需要。
os.environ.setdefault("CUDA_VISIBLE_DEVICES", "1")
# Reduce碎片风险，可外部覆盖
os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")
MODEL_NAME = "deepseek-ai/DeepSeek-OCR"
DEFAULT_LOCAL_MODEL_PATH = \
    "/root/.cache/huggingface/hub/models--deepseek-ai--DeepSeek-OCR/" \
    "snapshots/9f30c71f441d010e5429c532364a86705536c53a"

LOCAL_MODEL_DIR = Path(
    os.getenv("DEEPSEEK_OCR_LOCAL_PATH", DEFAULT_LOCAL_MODEL_PATH)
).expanduser()

_TOKENIZER = None
_MODEL = None


def _ensure_model():
    """Lazy-load tokenizer/model so importing this module is lightweight."""

    global _TOKENIZER, _MODEL
    if _TOKENIZER is None or _MODEL is None:
        model_source = (
            str(LOCAL_MODEL_DIR)
            if LOCAL_MODEL_DIR.exists()
            else MODEL_NAME
        )

        _TOKENIZER = AutoTokenizer.from_pretrained(model_source, trust_remote_code=True)
        _MODEL = AutoModel.from_pretrained(
            model_source,
            trust_remote_code=True,
            use_safetensors=True,
        )
        _MODEL = _MODEL.eval().cuda().to(torch.bfloat16)
    return _TOKENIZER, _MODEL


# ---------------------------------------------------------------------------
# Default configuration
# ---------------------------------------------------------------------------
DEFAULT_INPUT_DIR = "/root/workspace/syp/ocr/Peer_Profiles/Masrren"
DEFAULT_OUTPUT_DIR = "/root/workspace/syp/ocr/result_deepseek/Masrren"

PROMPT = "<image>\n<|grounding|>Convert the document to markdown. "
BASE_SIZE = 1024
IMAGE_SIZE = 640
CROP_MODE = True
SAVE_RESULTS = True
TEST_COMPRESS = True
IMG_EXTS = {".jpg", ".jpeg", ".png", ".webp"}


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------
@contextlib.contextmanager
def capture_stdout():
    buffer = io.StringIO()
    old_stdout = sys.stdout
    sys.stdout = buffer
    try:
        yield buffer
    finally:
        sys.stdout = old_stdout


def iter_images(base_dir: Path, allowed_exts: set[str]):
    for root, _, files in os.walk(base_dir):
        for filename in files:
            ext = os.path.splitext(filename)[1].lower()
            if ext in allowed_exts:
                yield Path(root) / filename


def run_ocr(
    input_dir: str | os.PathLike,
    output_dir: str | os.PathLike,
    *,
    prompt: str = PROMPT,
    base_size: int = BASE_SIZE,
    image_size: int = IMAGE_SIZE,
    crop_mode: bool = CROP_MODE,
    save_results: bool = SAVE_RESULTS,
    test_compress: bool = TEST_COMPRESS,
    allowed_exts: Iterable[str] | None = None,
    progress_callback: Callable[[dict], None] | None = None,
):
    """Run DeepSeek-OCR on every image under ``input_dir``."""

    tokenizer, model = _ensure_model()
    allowed_exts = set(allowed_exts or IMG_EXTS)

    input_dir = Path(input_dir).expanduser().resolve()
    output_dir = Path(output_dir).expanduser().resolve()

    if not input_dir.exists():
        raise FileNotFoundError(f"Input directory not found: {input_dir}")

    images = list(iter_images(input_dir, allowed_exts))
    total = len(images)

    if progress_callback:
        progress_callback({
            "event": "start",
            "total": total,
            "input_dir": str(input_dir),
        })

    for idx, img_path in enumerate(images, start=1):
        rel_dir = img_path.parent.relative_to(input_dir)
        img_stem = img_path.stem
        target_dir = output_dir / rel_dir / img_stem
        target_dir.mkdir(parents=True, exist_ok=True)

        print(f"▶ Processing: {img_path}")
        if progress_callback:
            progress_callback({
                "event": "before_image",
                "index": idx,
                "total": total,
                "image_path": str(img_path),
                "target_dir": str(target_dir),
            })
        try:
            with capture_stdout() as buf:
                _ = model.infer(
                    tokenizer,
                    prompt=prompt,
                    image_file=str(img_path),
                    output_path=str(target_dir),
                    base_size=base_size,
                    image_size=image_size,
                    crop_mode=crop_mode,
                    save_results=save_results,
                    test_compress=test_compress,
                )

            raw_stdout = buf.getvalue().strip()
            if raw_stdout:
                stdout_path = target_dir / f"{img_stem}.stdout.md"
                stdout_path.write_text(raw_stdout, encoding="utf-8")
                print(f"  ↳ saved stdout: {stdout_path}")

        except Exception as exc:  # noqa: BLE001 - surface any failure
            print(f"⚠️ Failed on {img_path}: {exc}")
            if progress_callback:
                progress_callback({
                    "event": "after_image",
                    "index": idx,
                    "total": total,
                    "image_path": str(img_path),
                    "status": "error",
                    "error": str(exc),
                })
        else:
            print(f"✓ Done: {img_path} -> {target_dir}")
            if progress_callback:
                progress_callback({
                    "event": "after_image",
                    "index": idx,
                    "total": total,
                    "image_path": str(img_path),
                    "status": "success",
                })

    print("✅ OCR run finished.")
    if progress_callback:
        progress_callback({
            "event": "complete",
            "total": total,
            "input_dir": str(input_dir),
        })


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def parse_args(args: list[str] | None = None):
    parser = argparse.ArgumentParser(description="Batch DeepSeek-OCR runner")
    parser.add_argument("--input-dir", default=DEFAULT_INPUT_DIR, help="Directory containing images")
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR, help="Directory to store outputs")
    parser.add_argument("--prompt", default=PROMPT, help="Prompt passed to DeepSeek-OCR")
    parser.add_argument("--base-size", type=int, default=BASE_SIZE)
    parser.add_argument("--image-size", type=int, default=IMAGE_SIZE)
    parser.add_argument("--no-crop", action="store_true", help="Disable crop mode")
    parser.add_argument("--no-save", action="store_true", help="Disable saving of DeepSeek outputs")
    parser.add_argument("--no-compress", action="store_true", help="Disable compression test")
    return parser.parse_args(args=args)


def main(argv: list[str] | None = None):
    options = parse_args(argv)
    run_ocr(
        input_dir=options.input_dir,
        output_dir=options.output_dir,
        prompt=options.prompt,
        base_size=options.base_size,
        image_size=options.image_size,
        crop_mode=not options.no_crop,
        save_results=not options.no_save,
        test_compress=not options.no_compress,
    )


if __name__ == "__main__":
    main()

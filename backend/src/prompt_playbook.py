# -*- coding: utf-8 -*-
"""Utilities for exposing prompt playbook data to the frontend."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json
import re
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

from src.manual_ocr import MANUAL_OCR_ROOT
from src.api_queries import BACKEND_ROOT
from src.rag_specsheet import SPEC_SHEET_SYSTEM_PROMPT
from src.manual_book import MANUAL_BOOK_SYSTEM_PROMPT


PROMPT_PLAYBOOK_TYPES = ("spec", "manual", "poster", "other")
TYPE_HINTS = {
    "spec": ("spec", "specsheet", "规格"),
    "manual": ("manual", "guide", "说明", "book"),
    "poster": ("poster", "宣传", "海报"),
}

PROMPT_FILE_CANDIDATES = {
    "spec": {
        "question": ["question_spec.txt", "question.txt"],
        "context": ["context_spec.txt", "context.txt"],
        "ground_truth": [
            "truth_specsheet.json",
            "truth/specsheet.json",
            "truth/spec.json",
        ],
    },
    "manual": {
        "question": ["question_manual.txt", "question.txt"],
        "context": ["context_manual.txt", "context.txt"],
        "ground_truth": [
            "truth_manual.json",
            "truth/manual.json",
        ],
    },
    "poster": {
        "question": ["question_poster.txt", "question.txt"],
        "context": ["context_poster.txt", "context.txt"],
        "ground_truth": ["truth/poster.json"],
    },
    "other": {
        "question": ["question_other.txt", "question.txt"],
        "context": ["context_other.txt", "context.txt"],
        "ground_truth": ["truth/other.json"],
    },
}


@dataclass
class PlaybookFile:
    """Normalized representation of a text artifact."""

    name: str
    path: str
    size: int
    content: str
    preview: str


def _detect_playbook_type(filename: str) -> str:
    lower = (filename or "").lower()
    for target_type, hints in TYPE_HINTS.items():
        if any(hint in lower for hint in hints):
            return target_type
    return "other"


def _read_text_file(file_path: Path) -> str:
    try:
        return file_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return file_path.read_text(encoding="utf-8", errors="ignore")


def _serialize_file(file_path: Path) -> PlaybookFile:
    try:
        rel_path = file_path.resolve().relative_to(BACKEND_ROOT.resolve()).as_posix()
    except ValueError:
        rel_path = file_path.as_posix()

    content = _read_text_file(file_path)
    preview = content.strip().replace("\n", " ")[:240]

    return PlaybookFile(
        name=file_path.name,
        path=rel_path,
        size=file_path.stat().st_size if file_path.exists() else 0,
        content=content,
        preview=preview,
    )


def _collect_variant_files(folder: Path) -> Dict[str, List[PlaybookFile]]:
    buckets: Dict[str, List[PlaybookFile]] = {}
    if not folder.exists() or not folder.is_dir():
        return buckets

    for file_path in sorted(folder.rglob("*")):
        if not file_path.is_file():
            continue
        pb_type = _detect_playbook_type(file_path.name)
        buckets.setdefault(pb_type, []).append(_serialize_file(file_path))
    return buckets


def _merge_variants(
    generate_map: Dict[str, List[PlaybookFile]],
    truth_map: Dict[str, List[PlaybookFile]],
) -> Dict[str, Dict[str, List[PlaybookFile]]]:
    playbooks: Dict[str, Dict[str, List[PlaybookFile]]] = {}
    all_types = set(generate_map.keys()) | set(truth_map.keys())
    for pb_type in all_types:
        playbooks[pb_type] = {
            "generate": generate_map.get(pb_type, []),
            "truth": truth_map.get(pb_type, []),
        }
    return playbooks


def list_prompt_playbooks(
    product_names: Optional[Iterable[str]] = None,
    playbook_type: Optional[str] = None,
) -> List[Dict[str, object]]:
    """Scan manual_ocr_results directories and aggregate generate/truth files."""

    if not MANUAL_OCR_ROOT.exists():
        return []

    normalized_filter = {name.lower() for name in product_names} if product_names else None
    requested_type = playbook_type.lower() if playbook_type else None

    items: List[Dict[str, object]] = []

    for folder in sorted(MANUAL_OCR_ROOT.iterdir()):
        if not folder.is_dir():
            continue

        folder_key = folder.name.lower()
        if normalized_filter and folder_key not in normalized_filter:
            continue

        generate_map = _collect_variant_files(folder / "generate")
        truth_map = _collect_variant_files(folder / "truth")
        playbooks = _merge_variants(generate_map, truth_map)

        for pb_type, bucket in playbooks.items():
            truth_text = _join_file_contents(bucket.get("truth", []))
            generate_text = _join_file_contents(bucket.get("generate", []))
            prompt_bundle = _build_context_prompt(
                folder,
                pb_type,
                folder.name,
                truth_text,
                generate_text,
            )
            bucket["question"] = prompt_bundle["question"]
            bucket["ground_truth"] = prompt_bundle["ground_truth"]
            bucket["context"] = prompt_bundle["context"]

        if requested_type:
            playbooks = {k: v for k, v in playbooks.items() if k == requested_type}

        if not playbooks:
            continue

        items.append(
            {
                "product_name": folder.name,
                "folder_name": folder.name,
                "playbooks": playbooks,
            }
        )

    return items


def _relative_to_backend(path: Path) -> str:
    try:
        return path.resolve().relative_to(BACKEND_ROOT.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def persist_ace_dataset(
    folder_name: str,
    playbook_type: str,
    samples: List[Dict[str, object]],
) -> Optional[Path]:
    """Persist ACE dataset payload for traceability (legacy per-product storage)."""

    if not MANUAL_OCR_ROOT.exists():
        return None

    target_dir = MANUAL_OCR_ROOT / folder_name / "ace_samples"
    target_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    file_path = target_dir / f"dataset_{playbook_type}_{timestamp}.json"
    file_path.write_text(
        json.dumps(samples, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return file_path


DATASET_ROOT = MANUAL_OCR_ROOT / "_datasets"

SYSTEM_PROMPT_MAP: Dict[str, str] = {
    "spec": SPEC_SHEET_SYSTEM_PROMPT,
    "manual": MANUAL_BOOK_SYSTEM_PROMPT,
    "poster": "You are a marketing prompt engineer. Generate persuasive poster copy based on the provided context.",
    "other": "You are a helpful assistant that optimizes prompts for the provided context.",
}


def get_system_prompt(playbook_type: str) -> str:
    return SYSTEM_PROMPT_MAP.get(playbook_type, SYSTEM_PROMPT_MAP["other"])


def _join_file_contents(files: List[PlaybookFile]) -> str:
    return "\n\n".join(file.content.strip() for file in files if file.content).strip()


def _load_prompt_snapshot(folder: Path, playbook_type: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """Load question/context/ground truth snapshots written during generation."""

    if not folder.exists() or not folder.is_dir():
        return None, None, None

    candidates = PROMPT_FILE_CANDIDATES.get(playbook_type, PROMPT_FILE_CANDIDATES["other"])

    def _read_first(paths: List[str]) -> Optional[str]:
        for relative in paths:
            target = folder / relative
            if target.exists():
                return target.read_text(encoding="utf-8", errors="ignore").strip() or None
        return None

    question = _read_first(candidates.get("question", []))
    context = _read_first(candidates.get("context", []))
    ground_truth = _read_first(candidates.get("ground_truth", []))

    return question, context, ground_truth


def _build_context_prompt(
    folder: Path,
    playbook_type: str,
    product_name: str,
    truth_text: str,
    generate_text: str,
) -> Dict[str, Optional[str]]:
    question_snapshot, context_snapshot, ground_truth_snapshot = _load_prompt_snapshot(
        folder, playbook_type
    )

    if question_snapshot and context_snapshot and ground_truth_snapshot:
        return {
            "question": question_snapshot,
            "context": context_snapshot,
            "ground_truth": ground_truth_snapshot,
        }

    text_source = truth_text or generate_text or ""
    default_context = text_source.strip()

    if not default_context:
        return {
            "question": get_system_prompt(playbook_type),
            "context": "",
            "ground_truth": "",
        }

    return {
        "question": question_snapshot or get_system_prompt(playbook_type),
        "context": default_context,
        "ground_truth": ground_truth_snapshot or truth_text,
    }


def _sanitize_dataset_name(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_\-]+", "_", (value or "").strip())
    cleaned = re.sub(r"_+", "_", cleaned).strip("_")
    return cleaned or "dataset"


MAX_DATASET_RULES = 200


def normalize_rules(rules: Optional[List[Dict[str, object]]]) -> List[Dict[str, object]]:
    if not rules:
        return []
    trimmed: List[Dict[str, object]] = []
    for entry in rules[:MAX_DATASET_RULES]:
        if isinstance(entry, dict):
            trimmed.append(
                {
                    "id": entry.get("id"),
                    "content": entry.get("content"),
                    "score": entry.get("score"),
                    "metadata": entry.get("metadata"),
                }
            )
        else:
            trimmed.append({"content": str(entry)})
    return trimmed


def persist_named_dataset(
    dataset_name: str,
    playbook_type: str,
    samples: List[Dict[str, object]],
    description: Optional[str] = None,
    global_rules: Optional[List[Dict[str, object]]] = None,
    custom_rules: Optional[List[Dict[str, object]]] = None,
) -> Optional[Path]:
    """Persist a named ACE dataset that can include cross-product samples."""

    if not MANUAL_OCR_ROOT.exists():
        return None

    DATASET_ROOT.mkdir(parents=True, exist_ok=True)
    safe_name = _sanitize_dataset_name(dataset_name)
    dataset_dir = DATASET_ROOT / safe_name
    dataset_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    file_path = dataset_dir / f"dataset_{playbook_type}_{timestamp}.json"
    beijing_tz = timezone(timedelta(hours=8))
    submitted_at = datetime.now(tz=beijing_tz).isoformat()
    normalized_global = normalize_rules(global_rules)
    normalized_custom = normalize_rules(custom_rules)
    payload = {
        "dataset_name": dataset_name,
        "playbook_type": playbook_type,
        "description": (description or "").strip() or None,
        "submitted_at": submitted_at,
        "sample_count": len(samples),
        "samples": samples,
        "global_rules": normalized_global,
        "custom_rules": normalized_custom,
        # legacy alias for existing tooling
        "rules": normalized_global,
    }
    file_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return file_path


def list_saved_datasets(limit: int = 20) -> List[Dict[str, object]]:
    """Enumerate persisted ACE datasets sorted by newest first."""

    if not DATASET_ROOT.exists():
        return []

    entries: List[Dict[str, object]] = []
    for dataset_dir in DATASET_ROOT.iterdir():
        if not dataset_dir.is_dir():
            continue
        for dataset_file in dataset_dir.glob("dataset_*.json"):
            try:
                data = json.loads(dataset_file.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue
            samples = data.get("samples", []) or []
            global_rules = data.get("global_rules") or data.get("rules") or []
            custom_rules = data.get("custom_rules") or []
            entries.append(
                {
                    "dataset_name": data.get("dataset_name", dataset_dir.name),
                    "playbook_type": data.get("playbook_type", "spec"),
                    "description": data.get("description"),
                    "submitted_at": data.get("submitted_at") or datetime.utcfromtimestamp(dataset_file.stat().st_mtime).isoformat() + "Z",
                    "sample_count": data.get("sample_count") or len(samples),
                    "file_path": _relative_to_backend(dataset_file),
                    "samples": [
                        {
                            "product_name": sample.get("product_name"),
                            "folder_name": sample.get("folder_name"),
                            "playbook_type": sample.get("playbook_type"),
                            "question_preview": (sample.get("question") or sample.get("system_prompt") or "")[:160],
                            "context_preview": (sample.get("context") or sample.get("generate") or "")[:160],
                            "ground_truth_preview": (sample.get("ground_truth") or sample.get("truth") or "")[:160],
                        }
                        for sample in samples
                    ],
                    "global_rules": global_rules,
                    "custom_rules": custom_rules,
                    "rules": global_rules,
                }
            )

    entries.sort(key=lambda item: item.get("submitted_at", ""), reverse=True)
    if limit and limit > 0:
        return entries[:limit]
    return entries


def delete_saved_dataset(file_path: str) -> bool:
    if not file_path:
        return False

    target = (BACKEND_ROOT / file_path).resolve()
    try:
        target.relative_to(DATASET_ROOT.resolve())
    except ValueError:
        raise ValueError("Attempting to delete dataset outside allowed directory")

    if not target.exists():
        return False

    target.unlink()

    parent = target.parent
    if parent.is_dir() and not any(parent.iterdir()):
        parent.rmdir()
    return True


def get_playbook_rules(limit: Optional[int] = None, playbook_type: str = "spec") -> List[Dict[str, object]]:
    """Return current ACE playbook snapshot for the requested playbook_type."""

    try:
        from src.ace_integration import get_ace_manager
    except Exception:
        return []

    manager = get_ace_manager(playbook_type or "spec")
    rules = manager.get_playbook_snapshot(limit)
    return rules or []


def delete_playbook_rule(rule_id: str, playbook_type: str = "spec") -> bool:
    if not rule_id:
        return False

    try:
        from src.ace_integration import get_ace_manager
    except Exception:
        return False

    manager = get_ace_manager(playbook_type or "spec")
    return manager.remove_rule(rule_id)

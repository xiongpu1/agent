"""Helpers for persisting specsheet JSON files inside manual OCR session folders."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Optional, Union, Dict, Any

from .manual_ocr import MANUAL_OCR_ROOT
from .specsheet_models import SpecsheetData


def _sanitize_part(value: Optional[str], fallback: str) -> str:
    if not value:
        return fallback
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", value.strip())
    return cleaned or fallback


def _session_directory(session_id: str) -> Path:
    sanitized_session = _sanitize_part(session_id, "unknown-session")
    return MANUAL_OCR_ROOT / sanitized_session


def _specsheet_path(session_id: str, bom_code: Optional[str] = None) -> Path:
    base_dir = _session_directory(session_id)
    suffix = ""
    if bom_code:
        suffix = f"_{_sanitize_part(bom_code, 'default')}"
    filename = f"specsheet{suffix}.json"
    return base_dir / filename


def save_specsheet_for_session(
    session_id: str,
    specsheet_payload: Union[SpecsheetData, Dict[str, Any]],
    bom_code: Optional[str] = None,
) -> SpecsheetData:
    """Persist a specsheet JSON inside the manual OCR session directory."""
    if not session_id:
        raise ValueError("session_id 不能为空")

    if isinstance(specsheet_payload, SpecsheetData):
        specsheet_data = specsheet_payload
    else:
        specsheet_data = SpecsheetData(**specsheet_payload)

    path = _specsheet_path(session_id, bom_code)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(specsheet_data.dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    return specsheet_data


def load_specsheet_for_session(
    session_id: str,
    bom_code: Optional[str] = None,
) -> Optional[SpecsheetData]:
    """Load specsheet JSON from manual OCR session directory."""
    if not session_id:
        return None

    path = _specsheet_path(session_id, bom_code)
    if not path.exists():
        return None

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return SpecsheetData(**payload)
    except Exception:
        return None

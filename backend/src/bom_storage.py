import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Any, List

from src.api_queries import BACKEND_ROOT
from src.manual_ocr import MANUAL_OCR_ROOT


BOM_SAVE_ROOT = BACKEND_ROOT / "bom_auto_results"
SESSION_BOM_FILENAME = "bom.json"


def _ensure_directory(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _sanitize_filename_part(value: Optional[str], fallback: str) -> str:
    if not value:
        return fallback
    cleaned = re.sub(r"[^A-Za-z0-9_-]+", "_", value.strip())
    return cleaned or fallback


def _session_bom_path(session_id: str) -> Path:
    sanitized = _sanitize_filename_part(session_id, "unknown-session")
    return MANUAL_OCR_ROOT / sanitized / SESSION_BOM_FILENAME


def _legacy_bom_path(product_name: Optional[str], bom_type: Optional[str]) -> Path:
    timestamp_part = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    filename = "{ts}_{product}_{bom}.json".format(
        ts=timestamp_part,
        product=_sanitize_filename_part(product_name, "unknown-product"),
        bom=_sanitize_filename_part(bom_type, "unknown-bom"),
    )
    return BOM_SAVE_ROOT / filename


def save_bom_code_to_file(
    *,
    code: str,
    product_name: Optional[str],
    bom_type: Optional[str],
    session_id: Optional[str] = None,
    selections: Optional[Dict[str, str]] = None,
    segments: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    Persist the generated 22-digit BOM code to the local filesystem.

    If session_id is provided, the file is stored under
    backend/manual_ocr_results/<session_id>/bom.json so it can be
    retrieved when the same session is opened again. Otherwise it falls
    back to backend/bom_auto_results/<timestamp>_<product>_<bom>.json.
    """

    timestamp = datetime.utcnow().replace(tzinfo=timezone.utc).isoformat()

    if session_id:
        file_path = _session_bom_path(session_id)
    else:
        file_path = _legacy_bom_path(product_name, bom_type)

    _ensure_directory(file_path.parent)

    payload = {
        "code": code,
        "productName": product_name,
        "bomType": bom_type,
        "sessionId": session_id,
        "savedAt": timestamp,
        "selections": selections or {},
        "segments": segments or [],
    }

    file_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    try:
        relative_path = file_path.relative_to(BACKEND_ROOT).as_posix()
    except ValueError:
        relative_path = file_path.as_posix()

    return {
        **payload,
        "path": relative_path,
        "absolutePath": str(file_path),
    }


def load_bom_code_for_session(session_id: str) -> Optional[Dict[str, Any]]:
    if not session_id:
        return None

    file_path = _session_bom_path(session_id)
    if not file_path.exists():
        return None

    try:
        content = json.loads(file_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None

    try:
        relative_path = file_path.relative_to(BACKEND_ROOT).as_posix()
    except ValueError:
        relative_path = file_path.as_posix()

    return {
        **content,
        "path": relative_path,
        "absolutePath": str(file_path),
    }

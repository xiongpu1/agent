"""Utilities to orchestrate manual OCR jobs triggered from the frontend."""

from __future__ import annotations

import asyncio
import json
import mimetypes
import os
import re
import shutil
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple
from uuid import uuid4

from fastapi import UploadFile
from pdf2image import convert_from_path

from src.api_queries import BACKEND_ROOT
from src.run_deepseekocr import IMG_EXTS, run_ocr
from src.manual_progress import progress_manager
from src.prompt_reverse import run_prompt_reverse_for_entries, DEFAULT_USER_PROMPT

MANUAL_UPLOAD_ROOT = BACKEND_ROOT / "manual_uploads"
MANUAL_OCR_ROOT = BACKEND_ROOT / "manual_ocr_results"
SESSION_RECORD_FILE = "session.json"

MANUAL_OCR_AUTO_PROMPT_REVERSE = os.getenv("MANUAL_OCR_AUTO_PROMPT_REVERSE", "0").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}

PDF_EXTS = {".pdf"}
OFFICE_DOC_EXTS = frozenset({".doc", ".docx", ".ppt", ".pptx", ".xls", ".xlsx"})
LIBREOFFICE_CMD = os.getenv("LIBREOFFICE_CMD", "libreoffice")


# ---------------------------------------------------------------------------
# Filesystem helpers
# ---------------------------------------------------------------------------


def ensure_directories() -> None:
    MANUAL_UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)
    MANUAL_OCR_ROOT.mkdir(parents=True, exist_ok=True)


def _safe_relative_to_backend(path: Path) -> str:
    try:
        return path.resolve().relative_to(BACKEND_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def _sanitize_identifier(value: str | None, fallback: str) -> str:
    if not value:
        return fallback
    cleaned = re.sub(r"[^A-Za-z0-9]+", "_", value.strip())
    cleaned = re.sub(r"_+", "_", cleaned).strip("_")
    return cleaned or fallback


def _session_storage_name(session_id: str) -> str:
    return _sanitize_identifier(session_id, "unknown_session")


def _resolve_storage_path(root: Path, session_id: str) -> Path:
    """Return the directory for a session, supporting legacy names with hyphens."""

    sanitized = root / _session_storage_name(session_id)
    if sanitized.exists():
        return sanitized

    legacy = root / (session_id or "")
    if session_id and legacy.exists():
        return legacy

    return sanitized


def session_dir(session_id: str) -> Path:
    return _resolve_storage_path(MANUAL_UPLOAD_ROOT, session_id)


def ocr_dir(session_id: str) -> Path:
    return _resolve_storage_path(MANUAL_OCR_ROOT, session_id)


def session_record_path(session_id: str) -> Path:
    return session_dir(session_id) / SESSION_RECORD_FILE


def save_session_record(payload: dict) -> None:
    ensure_directories()
    record_path = session_record_path(payload["session_id"])
    record_path.parent.mkdir(parents=True, exist_ok=True)
    record_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def load_session_record(session_id: str) -> dict | None:
    path = session_record_path(session_id)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def list_session_records(limit: int = 50) -> List[dict]:
    ensure_directories()
    records: List[dict] = []
    for record_path in MANUAL_UPLOAD_ROOT.glob(f"*/{SESSION_RECORD_FILE}"):
        try:
            records.append(json.loads(record_path.read_text(encoding="utf-8")))
        except json.JSONDecodeError:
            continue
    records.sort(key=lambda item: item.get("created_at", ""), reverse=True)
    return records[: limit if limit > 0 else len(records)]


def delete_manual_session(session_id: str) -> bool:
    deleted = False
    upload_dir = session_dir(session_id)
    if upload_dir.exists():
        shutil.rmtree(upload_dir, ignore_errors=True)
        deleted = True

    ocr_result_dir = ocr_dir(session_id)
    if ocr_result_dir.exists():
        shutil.rmtree(ocr_result_dir, ignore_errors=True)
        deleted = True

    progress_manager.delete(session_id)
    return deleted


def clear_manual_history() -> int:
    ensure_directories()
    count = 0
    for directory in MANUAL_UPLOAD_ROOT.iterdir():
        if directory.is_dir():
            if delete_manual_session(directory.name):
                count += 1
    return count


# ---------------------------------------------------------------------------
# File metadata helpers
# ---------------------------------------------------------------------------


def guess_mime(path: Path) -> str:
    mime, _ = mimetypes.guess_type(path.name)
    return mime or "application/octet-stream"


def build_file_record(path: Path) -> dict:
    if not path.exists():
        return {}
    stat_result = path.stat()
    relative_path = _safe_relative_to_backend(path)
    return {
        "id": f"{path.stem}-{stat_result.st_mtime_ns}",
        "name": path.name,
        "size": stat_result.st_size,
        "type": guess_mime(path),
        "path": relative_path,
        "url": f"/api/files/{relative_path}",
        "lastModified": int(stat_result.st_mtime * 1000),
        "previewUrl": "",
    }


def build_file_records(paths: List[Path]) -> List[dict]:
    return [record for path in paths if (record := build_file_record(path))]


def secure_filename(filename: str | None) -> str:
    filename = filename or ""
    filename = os.path.basename(filename)
    filename = re.sub(r"[^A-Za-z0-9._-]+", "_", filename).strip("._")
    return filename or f"file_{uuid4().hex}.dat"


def persist_uploads(files: List[UploadFile], destination: Path) -> List[Path]:
    saved: List[Path] = []
    destination.mkdir(parents=True, exist_ok=True)
    for upload in files or []:
        if not upload.filename:
            continue
        filename = secure_filename(upload.filename)
        dest_path = destination / filename
        with dest_path.open("wb") as target:
            shutil.copyfileobj(upload.file, target)
        saved.append(dest_path)
    return saved


# ---------------------------------------------------------------------------
# Session creation helpers
# ---------------------------------------------------------------------------


def generate_session_id(product_name: str | None, bom_code: str | None) -> str:
    product_part = _sanitize_identifier(product_name, "product")
    bom_part = _sanitize_identifier(bom_code, "bom")
    candidate = f"{product_part}_{bom_part}"
    storage = _session_storage_name(candidate)
    if not (MANUAL_UPLOAD_ROOT / storage).exists() and not (MANUAL_OCR_ROOT / storage).exists():
        return candidate

    timestamp = int(datetime.utcnow().timestamp() * 1000)
    suffix = uuid4().hex[:6]
    return f"manual_{timestamp}_{suffix}"


def _create_manual_session_entry_sync(
    product_name: str,
    bom_code: str | None,
    product_files: List[UploadFile],
    accessory_files: List[UploadFile],
    bom_type: str | None = None,
) -> dict:
    ensure_directories()

    if not product_name or not product_name.strip():
        raise ValueError("product_name 不能为空")

    session_id = generate_session_id(product_name, bom_code)
    base_dir = session_dir(session_id)
    product_dir = base_dir / "products"
    accessory_dir = base_dir / "accessories"

    saved_product_paths = persist_uploads(product_files, product_dir)
    saved_accessory_paths = persist_uploads(accessory_files, accessory_dir)

    payload = {
        "session_id": session_id,
        "product_name": product_name.strip(),
        "bom_code": (bom_code or "").strip() or None,
        "bom_type": (bom_type or "").strip() or None,
        "created_at": datetime.utcnow().isoformat(),
        "status": "pending",
        "product_files": build_file_records(saved_product_paths),
        "accessory_files": build_file_records(saved_accessory_paths),
        "product_upload_count": len(saved_product_paths),
        "accessory_upload_count": len(saved_accessory_paths),
        "product_ocr_groups": [],
        "accessory_ocr_groups": [],
    }

    save_session_record(payload)
    return payload


async def create_manual_session_entry(
    product_name: str,
    bom_code: str | None,
    product_files: List[UploadFile],
    accessory_files: List[UploadFile],
    bom_type: str | None = None,
) -> dict:
    return _create_manual_session_entry_sync(product_name, bom_code, product_files, accessory_files, bom_type)


# ---------------------------------------------------------------------------
# OCR preparation helpers
# ---------------------------------------------------------------------------


def convert_pdf_to_images(pdf_path: Path, output_dir: Path, source_name: str | None = None) -> List[dict]:
    pages_dir = output_dir / pdf_path.stem
    pages_dir.mkdir(parents=True, exist_ok=True)

    images = convert_from_path(str(pdf_path))
    entries: List[dict] = []
    for index, image in enumerate(images, start=1):
        page_stem = f"{pdf_path.stem}__page{index:03d}"
        page_dir = pages_dir / page_stem
        page_dir.mkdir(parents=True, exist_ok=True)
        image_path = page_dir / f"{page_stem}.png"
        image.save(image_path, "PNG")
        entries.append(
            {
                "source_name": source_name or pdf_path.name,
                "source_size": pdf_path.stat().st_size,
                "source_mime": guess_mime(pdf_path),
                "page_number": index,
                "image_stem": page_stem,
                "image_path": image_path,
                "relative_dir": page_dir.relative_to(output_dir).as_posix(),
            }
        )
    return entries


def convert_office_to_pdf(source_path: Path, temp_dir: Path) -> Path:
    temp_dir.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        [
            LIBREOFFICE_CMD,
            "--headless",
            "--convert-to",
            "pdf",
            "--outdir",
            str(temp_dir),
            str(source_path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"LibreOffice 转换失败: {result.stderr.strip() or result.stdout.strip()}")

    converted = temp_dir / f"{source_path.stem}.pdf"
    if not converted.exists():
        raise FileNotFoundError(f"未找到转换后的 PDF: {converted}")
    return converted


def prepare_images_for_directory(label: str, source_dir: Path, prepared_dir: Path) -> Tuple[List[dict], List[str]]:
    """Convert uploaded files under source_dir into page-level image entries for OCR."""
    prepared_entries: List[dict] = []
    errors: List[str] = []

    if not source_dir.exists():
        return prepared_entries, errors

    prepared_dir.mkdir(parents=True, exist_ok=True)
    temp_dir = prepared_dir / "__office_pdf"
    temp_dir.mkdir(parents=True, exist_ok=True)

    for file_path in sorted(p for p in source_dir.iterdir() if p.is_file()):
        ext = file_path.suffix.lower()
        try:
            if ext in PDF_EXTS:
                entries = convert_pdf_to_images(file_path, prepared_dir, source_name=file_path.name)
            elif ext in OFFICE_DOC_EXTS:
                pdf_path = convert_office_to_pdf(file_path, temp_dir)
                entries = convert_pdf_to_images(pdf_path, prepared_dir, source_name=file_path.name)
            elif ext in IMG_EXTS:
                page_stem = file_path.stem
                page_dir = prepared_dir / file_path.stem / page_stem
                page_dir.mkdir(parents=True, exist_ok=True)
                target_path = page_dir / file_path.name
                shutil.copy2(file_path, target_path)
                entries = [
                    {
                        "source_name": file_path.name,
                        "source_size": file_path.stat().st_size,
                        "source_mime": guess_mime(file_path),
                        "page_number": 1,
                        "image_stem": page_stem,
                        "image_path": target_path,
                        "relative_dir": page_dir.relative_to(prepared_dir).as_posix(),
                    }
                ]
            else:
                continue

            for entry in entries:
                prepared_entries.append(
                    {
                        "label": label,
                        "relative_dir": entry.get("relative_dir"),
                        "image_stem": entry["image_stem"],
                        "image_path": entry.get("image_path"),
                        "page_number": entry.get("page_number"),
                        "source_name": entry.get("source_name") or file_path.name,
                        "source_size": entry.get("source_size", 0),
                        "source_mime": entry.get("source_mime", "application/octet-stream"),
                    }
                )
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{file_path.name}: {exc}")

    return prepared_entries, errors


def assemble_ocr_groups(output_dir: Path, prepared_entries: List[dict]) -> List[dict]:
    """Build OCR group/page/artifact structure from OCR output directory."""
    groups: Dict[str, dict] = {}

    def _collect_artifacts(label: str, relative_dir: str) -> List[dict]:
        page_root = output_dir / label
        if relative_dir:
            page_root = page_root / relative_dir
        artifacts: List[dict] = []
        if not page_root.exists():
            return artifacts
        for file_path in page_root.rglob("*"):
            if not file_path.is_file():
                continue
            rel_path = _safe_relative_to_backend(file_path)
            mime = guess_mime(file_path)
            suffix = file_path.suffix.lower()
            if suffix in IMG_EXTS:
                kind = "image"
            elif suffix in {".md", ".txt"}:
                kind = "markdown"
            elif suffix == ".mmd":
                kind = "diagram"
            else:
                kind = "file"
            artifacts.append(
                {
                    "name": file_path.name,
                    "path": rel_path,
                    "type": mime,
                    "size": file_path.stat().st_size,
                    "url": f"/api/files/{rel_path}",
                    "kind": kind,
                    "parent_dir": file_path.parent.name if file_path.parent.name else None,
                }
            )
        return sorted(artifacts, key=lambda a: a["name"])

    for entry in prepared_entries:
        source_name = entry.get("source_name") or "unknown"
        key = source_name
        group = groups.setdefault(
            key,
            {
                "source_name": source_name,
                "source_size": entry.get("source_size", 0),
                "source_mime": entry.get("source_mime", "application/octet-stream"),
                "pages": [],
            },
        )
        page_number = entry.get("page_number")
        image_stem = entry.get("image_stem")
        relative_dir = entry.get("relative_dir") or ""
        label = entry.get("label") or "products"
        artifacts = _collect_artifacts(label, relative_dir)
        page = {
            "page_number": page_number,
            "image_stem": image_stem,
            "artifacts": artifacts,
        }
        group["pages"].append(page)

    for group in groups.values():
        group["pages"].sort(key=lambda item: item.get("page_number") or 0)

    return list(groups.values())


def _append_prompt_artifact(record: dict, label: str, image_stem: str, prompt_path: Path) -> None:
    """Append generated prompt txt to the matching page artifacts without rebuilding groups."""
    if not prompt_path.exists():
        return
    relative_path = _safe_relative_to_backend(prompt_path)
    parent_dir = prompt_path.parent.name if prompt_path.parent.name else None

    derived_image_stem = ""
    try:
        if prompt_path.parent.name == "images":
            derived_image_stem = prompt_path.parent.parent.name
    except Exception:
        derived_image_stem = ""

    stem_candidates = [s for s in [image_stem, derived_image_stem] if s]
    if not stem_candidates:
        return
    if label == "products":
        groups = record.setdefault("product_ocr_groups", [])
    else:
        groups = record.setdefault("accessory_ocr_groups", [])
    artifact = {
        "name": prompt_path.name,
        "path": relative_path,
        "type": guess_mime(prompt_path),
        "size": prompt_path.stat().st_size,
        "url": f"/api/files/{relative_path}",
        "kind": "markdown",
        "parent_dir": parent_dir,
    }

    # Remove any previously-misassigned artifact entries that point to the same file.
    # This allows re-running prompt-reverse to "move" txt artifacts back to the correct page.
    for group in groups:
        for page in group.get("pages", []):
            artifacts = page.get("artifacts") or []
            if not artifacts:
                continue
            page["artifacts"] = [a for a in artifacts if a.get("path") != relative_path]

    for group in groups:
        for page in group.get("pages", []):
            if page.get("image_stem") in stem_candidates:
                artifacts = page.setdefault("artifacts", [])
                if any(a.get("path") == relative_path for a in artifacts):
                    return
                artifacts.append(artifact)
                return

    target_group = groups[0] if groups else None
    if target_group is None:
        target_group = {
            "source_name": stem_candidates[0],
            "source_size": 0,
            "source_mime": "application/octet-stream",
            "pages": [],
        }
        groups.append(target_group)

    target_group.setdefault("pages", []).append(
        {"page_number": None, "image_stem": stem_candidates[0], "artifacts": [artifact]}
    )


# ---------------------------------------------------------------------------
# OCR execution
# ---------------------------------------------------------------------------


def run_ocr_for_directory(
    input_dir: Path,
    output_dir: Path,
    session_id: str,
    label: str,
) -> None:
    if not input_dir.exists():
        return

    output_dir.mkdir(parents=True, exist_ok=True)

    def progress_callback(event: dict) -> None:
        event_type = event.get("event")
        if event_type == "before_image":
            progress_manager.update(
                session_id,
                current_file=f"{label}:{event.get('image_path')}",
                detail=f"{label} 文件 OCR 执行中…",
            )
        elif event_type == "after_image":
            progress_manager.increment_ocr_completed(session_id)
        elif event_type == "complete":
            progress_manager.update(session_id, detail=f"{label} OCR 完成")

    run_ocr(
        input_dir=str(input_dir),
        output_dir=str(output_dir / label),
        allowed_exts=IMG_EXTS,
        progress_callback=progress_callback,
    )


def _append_uploads_to_session(
    session_record: dict,
    product_files: List[UploadFile],
    accessory_files: List[UploadFile],
) -> dict:
    session_id = session_record["session_id"]
    base_dir = session_dir(session_id)
    product_dir = base_dir / "products"
    accessory_dir = base_dir / "accessories"

    new_product_paths = persist_uploads(product_files, product_dir)
    new_accessory_paths = persist_uploads(accessory_files, accessory_dir)

    if new_product_paths:
        session_record["product_files"].extend(build_file_records(new_product_paths))
        session_record["product_upload_count"] = session_record.get("product_upload_count", 0) + len(new_product_paths)

    if new_accessory_paths:
        session_record["accessory_files"].extend(build_file_records(new_accessory_paths))
        session_record["accessory_upload_count"] = session_record.get("accessory_upload_count", 0) + len(new_accessory_paths)

    save_session_record(session_record)
    return session_record


def _build_entries_from_output_dir(output_dir: Path, label: str) -> List[dict]:
    """Rebuild minimal entries from existing OCR output directories to re-run prompt reverse."""
    entries: List[dict] = []
    label_dir = output_dir / label
    if not label_dir.exists():
        return entries

    for root, _, files in os.walk(label_dir):
        root_path = Path(root)
        image_files = [Path(root_path / f) for f in files if Path(f).suffix.lower() in IMG_EXTS]
        if not image_files:
            continue
        image_file = sorted(image_files)[0]

        # root_path points to an images/ directory under a page folder.
        # We must use the page-level stem (e.g. Masrren___page006) instead of
        # the numeric image filename stem (0/1/2), otherwise prompt artifacts
        # get appended to the wrong page.
        image_stem = ""
        try:
            if root_path.name == "images":
                image_stem = root_path.parent.name
        except Exception:
            image_stem = ""
        if not image_stem:
            image_stem = image_file.stem
        relative_dir = ""
        try:
            relative_dir = root_path.parent.relative_to(label_dir).as_posix()
        except Exception:
            relative_dir = ""
        entries.append(
            {
                "label": label,
                "relative_dir": relative_dir or None,
                "image_stem": image_stem,
                "image_path": image_file,
                "page_number": None,
                "source_name": root_path.parts[-2] if len(root_path.parts) >= 2 else image_file.name,
            }
        )
    return entries


def _run_manual_session_sync(session_id: str) -> dict:
    ensure_directories()
    record = load_session_record(session_id)
    if not record:
        raise ValueError("Manual OCR session not found")

    base_dir = session_dir(session_id)
    output_dir = ocr_dir(session_id)
    output_dir.mkdir(parents=True, exist_ok=True)

    product_dir = base_dir / "products"
    accessory_dir = base_dir / "accessories"

    total_files = record.get("product_upload_count", 0) + record.get("accessory_upload_count", 0)
    progress_manager.start_session(
        session_id,
        product_name=record.get("product_name", ""),
        total_files=total_files,
    )

    prepared_entries: List[dict] = []
    errors: List[str] = []

    with tempfile.TemporaryDirectory() as tmp_dir_str:
        tmp_dir = Path(tmp_dir_str)
        product_prepared, product_errors = prepare_images_for_directory("products", product_dir, tmp_dir / "products")
        accessory_prepared, accessory_errors = prepare_images_for_directory(
            "accessories",
            accessory_dir,
            tmp_dir / "accessories",
        )
        prepared_entries.extend(product_prepared)
        prepared_entries.extend(accessory_prepared)
        errors.extend(product_errors)
        errors.extend(accessory_errors)

        progress_manager.set_ocr_totals(session_id, len(prepared_entries))

        try:
            run_ocr_for_directory(tmp_dir / "products", output_dir, session_id, "products")
            if product_prepared:
                progress_manager.increment_processed_files(session_id, 1)
            run_ocr_for_directory(tmp_dir / "accessories", output_dir, session_id, "accessories")
            if accessory_prepared:
                progress_manager.increment_processed_files(session_id, 1)
        except Exception as exc:  # noqa: BLE001
            progress_manager.mark_complete(session_id, False, str(exc))
            record["status"] = "exception"
            record["error"] = str(exc)
            save_session_record(record)
            raise

        if MANUAL_OCR_AUTO_PROMPT_REVERSE:
            try:
                reverse_warnings, reverse_logs = run_prompt_reverse_for_entries(prepared_entries, output_dir)
                if reverse_warnings:
                    errors.extend([f"[提示词反推]{w}" for w in reverse_warnings])
                if reverse_logs:
                    record["prompt_reverse_logs"] = reverse_logs
            except Exception as exc:  # noqa: BLE001
                errors.append(f"[提示词反推] 执行失败：{exc}")

    product_groups = assemble_ocr_groups(output_dir, [entry for entry in prepared_entries if entry["label"] == "products"])
    accessory_groups = assemble_ocr_groups(output_dir, [entry for entry in prepared_entries if entry["label"] == "accessories"])

    record["product_ocr_groups"] = product_groups
    record["accessory_ocr_groups"] = accessory_groups
    record["status"] = "success"
    record["completed_at"] = datetime.utcnow().isoformat()
    if errors:
        record["warnings"] = errors

    save_session_record(record)
    progress_manager.mark_complete(session_id, True)
    return record


async def run_manual_session(session_id: str) -> dict:
    return await asyncio.to_thread(_run_manual_session_sync, session_id)


def _run_prompt_reverse_only(session_id: str, user_prompt: str | None = None) -> dict:
    record = load_session_record(session_id)
    if not record:
        raise ValueError("Manual OCR session not found")

    output_dir = ocr_dir(session_id)
    if not output_dir.exists():
        raise ValueError("OCR 结果不存在，请先执行文件 OCR")

    entries: List[dict] = []
    entries.extend(_build_entries_from_output_dir(output_dir, "products"))
    entries.extend(_build_entries_from_output_dir(output_dir, "accessories"))
    if not entries:
        raise ValueError("未找到可用于提示词反推的图片文件，请先完成 OCR")

    _, logs = run_prompt_reverse_for_entries(
        entries,
        output_dir,
        user_prompt=user_prompt or DEFAULT_USER_PROMPT,
    )

    for log_item in logs:
        if log_item.get("status") != "success":
            continue
        prompt_path = log_item.get("prompt_path")
        if not prompt_path:
            continue
        label = log_item.get("label") or "products"
        image_stem = log_item.get("image_stem") or Path(prompt_path).stem
        _append_prompt_artifact(record, label, image_stem, Path(prompt_path))

    save_session_record(record)
    return record


async def run_prompt_reverse_only(session_id: str, user_prompt: str | None = None) -> dict:
    return await asyncio.to_thread(_run_prompt_reverse_only, session_id, user_prompt)


async def handle_manual_ocr(
    product_name: str,
    product_files: List[UploadFile],
    accessory_files: List[UploadFile],
    session_id: str | None = None,
    bom_code: str | None = None,
    bom_type: str | None = None,
) -> dict:
    if session_id:
        record = load_session_record(session_id)
        if not record:
            raise ValueError("指定的 session_id 不存在")
        record = _append_uploads_to_session(record, product_files, accessory_files)
        if bom_type:
            record["bom_type"] = bom_type
        save_session_record(record)
    else:
        record = _create_manual_session_entry_sync(product_name, bom_code, product_files, accessory_files, bom_type)
        session_id = record["session_id"]

    return await asyncio.to_thread(_run_manual_session_sync, session_id)

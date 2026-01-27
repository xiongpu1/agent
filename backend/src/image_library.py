import json
import os
import re
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse

from src.dingtalk_auth import _COOKIE_NAME, _get_session


router = APIRouter()


_MAX_BYTES = 10 * 1024 * 1024
_ALLOWED_EXTS = {"jpg", "jpeg", "png"}
_ALLOWED_MIME = {"image/jpeg", "image/png"}


def _now_ms() -> int:
    return int(time.time() * 1000)


def _sanitize_user_component(value: str) -> str:
    v = (value or "").strip()
    if not v:
        return ""
    v = re.sub(r"[^A-Za-z0-9_.-]", "_", v)
    v = re.sub(r"_+", "_", v).strip("_")
    return v


def _base_dir() -> Path:
    p = (os.getenv("IMAGE_LIBRARY_DIR") or "").strip()
    if p:
        return Path(p)
    return Path(__file__).resolve().parent.parent / "data_storage" / "image_library"


def _db_path() -> Path:
    p = (os.getenv("IMAGE_LIBRARY_DB") or "").strip()
    if p:
        return Path(p)
    return _base_dir() / "image_library.sqlite3"


def _ensure_db() -> None:
    base = _base_dir()
    base.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(str(_db_path())) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS image_assets (
              id TEXT PRIMARY KEY,
              owner_userid TEXT NOT NULL,
              owner_name TEXT NOT NULL,
              original_filename TEXT NOT NULL,
              mime_type TEXT NOT NULL,
              size_bytes INTEGER NOT NULL,
              rel_path TEXT NOT NULL,
              created_at_ms INTEGER NOT NULL,
              updated_at_ms INTEGER NOT NULL,
              title TEXT NOT NULL,
              tags_json TEXT NOT NULL,
              remark TEXT NOT NULL,
              product_name TEXT NOT NULL
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_image_owner ON image_assets(owner_userid)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_image_created ON image_assets(created_at_ms)")
        conn.commit()


def _current_user(request: Request) -> Dict[str, Any]:
    sid = request.cookies.get(_COOKIE_NAME) or ""
    user = _get_session(sid)
    if not user:
        raise HTTPException(status_code=401, detail="not logged in")
    if not (user.get("userid") or "").strip():
        raise HTTPException(status_code=401, detail="invalid session")
    return user


def _guess_ext(file: UploadFile) -> str:
    name = str(file.filename or "").strip()
    ext = ""
    if "." in name:
        ext = name.rsplit(".", 1)[1].lower()
    if ext == "jpeg":
        ext = "jpg"
    if ext in _ALLOWED_EXTS:
        return ext
    if file.content_type == "image/jpeg":
        return "jpg"
    if file.content_type == "image/png":
        return "png"
    raise HTTPException(status_code=400, detail="Only jpg/png files are allowed")


def _read_and_save(upload: UploadFile, out_path: Path) -> int:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    total = 0
    with out_path.open("wb") as f:
        while True:
            chunk = upload.file.read(1024 * 1024)
            if not chunk:
                break
            total += len(chunk)
            if total > _MAX_BYTES:
                raise HTTPException(status_code=400, detail="File too large (max 10MB)")
            f.write(chunk)
    return total


def _row_to_item(row: sqlite3.Row) -> Dict[str, Any]:
    tags = []
    try:
        tags = json.loads(row["tags_json"] or "[]")
    except Exception:
        tags = []
    return {
        "id": row["id"],
        "original_filename": row["original_filename"],
        "mime_type": row["mime_type"],
        "size_bytes": int(row["size_bytes"] or 0),
        "created_at_ms": int(row["created_at_ms"] or 0),
        "updated_at_ms": int(row["updated_at_ms"] or 0),
        "title": row["title"],
        "tags": tags if isinstance(tags, list) else [],
        "remark": row["remark"],
        "product_name": row["product_name"],
        "file_url": f"/api/images/{row['id']}/file",
    }


@router.post("/api/images/upload")
async def upload_images(request: Request, files: List[UploadFile] = File(...)):  # type: ignore
    user = _current_user(request)
    userid = str(user.get("userid") or "").strip()
    username = str(user.get("name") or "").strip()
    if not files:
        raise HTTPException(status_code=400, detail="Missing files")

    _ensure_db()
    owner_dir = _base_dir() / "users" / _sanitize_user_component(userid) / "original"

    created = _now_ms()
    items: List[Dict[str, Any]] = []
    with sqlite3.connect(str(_db_path())) as conn:
        conn.row_factory = sqlite3.Row
        for f in files:
            if not f:
                continue
            ext = _guess_ext(f)
            mime = str(f.content_type or "").strip().lower()
            if mime and mime not in _ALLOWED_MIME:
                raise HTTPException(status_code=400, detail="Only jpg/png files are allowed")

            image_id = uuid.uuid4().hex
            rel = Path("users") / _sanitize_user_component(userid) / "original" / f"{image_id}.{ext}"
            abs_path = _base_dir() / rel

            size_bytes = _read_and_save(f, abs_path)

            conn.execute(
                """
                INSERT INTO image_assets(
                  id, owner_userid, owner_name, original_filename, mime_type, size_bytes, rel_path,
                  created_at_ms, updated_at_ms, title, tags_json, remark, product_name
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    image_id,
                    userid,
                    username,
                    str(f.filename or ""),
                    mime or ("image/jpeg" if ext == "jpg" else "image/png"),
                    int(size_bytes),
                    str(rel),
                    int(created),
                    int(created),
                    "",
                    "[]",
                    "",
                    "",
                ),
            )
            cur = conn.execute("SELECT * FROM image_assets WHERE id = ?", (image_id,))
            row = cur.fetchone()
            if row:
                items.append(_row_to_item(row))
        conn.commit()

    return {"items": items}


@router.get("/api/images")
async def list_images(request: Request, keyword: str = "", limit: int = 100, offset: int = 0):
    user = _current_user(request)
    userid = str(user.get("userid") or "").strip()
    _ensure_db()

    kw = (keyword or "").strip().lower()
    limit = max(1, min(int(limit or 100), 200))
    offset = max(0, int(offset or 0))

    with sqlite3.connect(str(_db_path())) as conn:
        conn.row_factory = sqlite3.Row
        if kw:
            like = f"%{kw}%"
            cur = conn.execute(
                """
                SELECT * FROM image_assets
                WHERE owner_userid = ?
                  AND (
                    lower(original_filename) LIKE ?
                    OR lower(title) LIKE ?
                    OR lower(remark) LIKE ?
                    OR lower(product_name) LIKE ?
                    OR lower(tags_json) LIKE ?
                  )
                ORDER BY created_at_ms DESC
                LIMIT ? OFFSET ?
                """,
                (userid, like, like, like, like, like, limit, offset),
            )
        else:
            cur = conn.execute(
                """
                SELECT * FROM image_assets
                WHERE owner_userid = ?
                ORDER BY created_at_ms DESC
                LIMIT ? OFFSET ?
                """,
                (userid, limit, offset),
            )
        rows = cur.fetchall()

    return {"items": [_row_to_item(r) for r in rows]}


@router.get("/api/images/{image_id}/file")
async def get_image_file(request: Request, image_id: str):
    user = _current_user(request)
    userid = str(user.get("userid") or "").strip()
    _ensure_db()

    with sqlite3.connect(str(_db_path())) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.execute("SELECT * FROM image_assets WHERE id = ?", (image_id,))
        row = cur.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="not found")

    if str(row["owner_userid"] or "") != userid:
        raise HTTPException(status_code=403, detail="forbidden")

    rel = str(row["rel_path"] or "").lstrip("/")
    base = _base_dir().resolve()
    target = (base / rel).resolve()
    if target != base and base not in target.parents:
        raise HTTPException(status_code=400, detail="invalid file")
    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail="file missing")

    media_type = str(row["mime_type"] or "application/octet-stream")
    return FileResponse(path=str(target), media_type=media_type)


@router.patch("/api/images/{image_id}")
async def update_image(request: Request, image_id: str, payload: Dict[str, Any] = Body(...)):  # type: ignore
    user = _current_user(request)
    userid = str(user.get("userid") or "").strip()
    _ensure_db()

    original_filename = str((payload or {}).get("original_filename") or "")
    title = str((payload or {}).get("title") or "")
    remark = str((payload or {}).get("remark") or "")
    product_name = str((payload or {}).get("product_name") or "")

    tags_in = (payload or {}).get("tags")
    tags: List[str] = []
    if isinstance(tags_in, list):
        for t in tags_in:
            s = str(t or "").strip()
            if s:
                tags.append(s)
    tags = tags[:50]
    tags_json = json.dumps(tags, ensure_ascii=False)

    with sqlite3.connect(str(_db_path())) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.execute("SELECT * FROM image_assets WHERE id = ?", (image_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="not found")
        if str(row["owner_userid"] or "") != userid:
            raise HTTPException(status_code=403, detail="forbidden")

        now = _now_ms()
        set_original = original_filename.strip()
        if set_original:
            # Keep as metadata only; does not change actual stored file name.
            if len(set_original) > 255:
                set_original = set_original[:255]

        conn.execute(
            """
            UPDATE image_assets
            SET original_filename = COALESCE(NULLIF(?, ''), original_filename),
                title = ?,
                tags_json = ?,
                remark = ?,
                product_name = ?,
                updated_at_ms = ?
            WHERE id = ?
            """,
            (set_original, title, tags_json, remark, product_name, int(now), image_id),
        )
        conn.commit()

        cur2 = conn.execute("SELECT * FROM image_assets WHERE id = ?", (image_id,))
        row2 = cur2.fetchone()

    return {"item": _row_to_item(row2)}


@router.delete("/api/images/{image_id}")
async def delete_image(request: Request, image_id: str):
    user = _current_user(request)
    userid = str(user.get("userid") or "").strip()
    _ensure_db()

    rel_path: Optional[str] = None
    with sqlite3.connect(str(_db_path())) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.execute("SELECT * FROM image_assets WHERE id = ?", (image_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="not found")
        if str(row["owner_userid"] or "") != userid:
            raise HTTPException(status_code=403, detail="forbidden")
        rel_path = str(row["rel_path"] or "")

        conn.execute("DELETE FROM image_assets WHERE id = ?", (image_id,))
        conn.commit()

    if rel_path:
        base = _base_dir().resolve()
        target = (base / rel_path.lstrip("/")).resolve()
        try:
            if target != base and base in target.parents and target.exists() and target.is_file():
                target.unlink()
        except Exception:
            pass

    return {"ok": True}

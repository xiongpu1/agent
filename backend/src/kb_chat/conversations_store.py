import json
import os
import sqlite3
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple


def _db_path() -> str:
    p = (os.getenv("KBCHAT_CONV_DB_PATH") or "").strip()
    if not p:
        p = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data_storage", "kbchat_conversations.sqlite3")
    os.makedirs(os.path.dirname(p), exist_ok=True)
    return p


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(_db_path(), timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def _now_ms() -> int:
    return int(time.time() * 1000)


def init_db() -> None:
    conn = _connect()
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS conversations (
                id TEXT PRIMARY KEY,
                owner_userid TEXT NOT NULL,
                title TEXT NOT NULL,
                created_at_ms INTEGER NOT NULL,
                updated_at_ms INTEGER NOT NULL
            )
            """
        )
        # Backward compatible migration: older DBs may miss owner_userid.
        cols = [r[1] for r in conn.execute("PRAGMA table_info(conversations)").fetchall()]
        if "owner_userid" not in cols:
            conn.execute("ALTER TABLE conversations ADD COLUMN owner_userid TEXT NOT NULL DEFAULT ''")

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS messages (
                id TEXT PRIMARY KEY,
                conversation_id TEXT NOT NULL,
                seq INTEGER NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                reasoning TEXT,
                citations_json TEXT,
                created_at_ms INTEGER NOT NULL,
                FOREIGN KEY(conversation_id) REFERENCES conversations(id)
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_messages_conv_seq ON messages(conversation_id, seq)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_conversations_owner ON conversations(owner_userid)")
        conn.commit()
    finally:
        conn.close()


def create_conversation(owner_userid: str, initial_title: Optional[str] = None) -> Dict[str, Any]:
    init_db()
    ou = (owner_userid or "").strip()
    if not ou:
        raise ValueError("owner_userid required")
    cid = str(uuid.uuid4())
    now = _now_ms()
    title = (initial_title or "新对话").strip() or "新对话"
    conn = _connect()
    try:
        conn.execute(
            "INSERT INTO conversations(id, owner_userid, title, created_at_ms, updated_at_ms) VALUES(?,?,?,?,?)",
            (cid, ou, title, now, now),
        )
        conn.commit()
    finally:
        conn.close()
    return {"id": cid, "title": title, "created_at_ms": now, "updated_at_ms": now}


def list_conversations(owner_userid: str, limit: int = 50, offset: int = 0, q: str = "") -> List[Dict[str, Any]]:
    init_db()
    ou = (owner_userid or "").strip()
    if not ou:
        return []
    lim = max(1, min(int(limit or 50), 200))
    off = max(0, int(offset or 0))
    query = (q or "").strip()

    conn = _connect()
    try:
        if query:
            rows = conn.execute(
                "SELECT id, title, created_at_ms, updated_at_ms FROM conversations WHERE owner_userid = ? AND title LIKE ? ORDER BY updated_at_ms DESC LIMIT ? OFFSET ?",
                (ou, f"%{query}%", lim, off),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT id, title, created_at_ms, updated_at_ms FROM conversations WHERE owner_userid = ? ORDER BY updated_at_ms DESC LIMIT ? OFFSET ?",
                (ou, lim, off),
            ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_conversation(owner_userid: str, conversation_id: str) -> Optional[Dict[str, Any]]:
    init_db()
    ou = (owner_userid or "").strip()
    if not ou:
        return None
    cid = (conversation_id or "").strip()
    if not cid:
        return None
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT id, title, created_at_ms, updated_at_ms FROM conversations WHERE id = ? AND owner_userid = ?",
            (cid, ou),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def _assert_owns_conversation(conn: sqlite3.Connection, owner_userid: str, conversation_id: str) -> None:
    ou = (owner_userid or "").strip()
    cid = (conversation_id or "").strip()
    if not ou or not cid:
        raise ValueError("owner_userid/conversation_id required")
    row = conn.execute(
        "SELECT id FROM conversations WHERE id = ? AND owner_userid = ?",
        (cid, ou),
    ).fetchone()
    if not row:
        raise ValueError("conversation not found")


def _next_seq(conn: sqlite3.Connection, conversation_id: str) -> int:
    row = conn.execute(
        "SELECT COALESCE(MAX(seq), 0) AS m FROM messages WHERE conversation_id = ?",
        (conversation_id,),
    ).fetchone()
    m = int(row["m"]) if row else 0
    return m + 1


def append_message(
    owner_userid: str,
    conversation_id: str,
    role: str,
    content: str,
    reasoning: str = "",
    citations: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    init_db()
    cid = (conversation_id or "").strip()
    if not cid:
        raise ValueError("conversation_id required")
    r = (role or "").strip()
    if r not in {"user", "assistant", "system"}:
        raise ValueError("invalid role")
    txt = (content or "").strip()
    if not txt:
        raise ValueError("empty content")

    now = _now_ms()
    mid = str(uuid.uuid4())
    citations_json = ""
    if citations is not None:
        try:
            citations_json = json.dumps(citations, ensure_ascii=False, default=str)
        except Exception:
            citations_json = ""

    conn = _connect()
    try:
        _assert_owns_conversation(conn, owner_userid, cid)
        seq = _next_seq(conn, cid)
        conn.execute(
            "INSERT INTO messages(id, conversation_id, seq, role, content, reasoning, citations_json, created_at_ms) VALUES(?,?,?,?,?,?,?,?)",
            (mid, cid, seq, r, txt, (reasoning or "").strip() or None, citations_json or None, now),
        )
        conn.execute("UPDATE conversations SET updated_at_ms = ? WHERE id = ?", (now, cid))
        conn.commit()
        return {
            "id": mid,
            "conversation_id": cid,
            "seq": seq,
            "role": r,
            "content": txt,
            "reasoning": (reasoning or "").strip(),
            "citations": citations or [],
            "created_at_ms": now,
        }
    finally:
        conn.close()


def list_messages(owner_userid: str, conversation_id: str, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
    init_db()
    ou = (owner_userid or "").strip()
    if not ou:
        return []
    cid = (conversation_id or "").strip()
    if not cid:
        return []
    lim = max(1, min(int(limit or 50), 500))
    off = max(0, int(offset or 0))

    conn = _connect()
    try:
        try:
            _assert_owns_conversation(conn, ou, cid)
        except Exception:
            return []
        rows = conn.execute(
            "SELECT id, conversation_id, seq, role, content, reasoning, citations_json, created_at_ms FROM messages WHERE conversation_id = ? ORDER BY seq ASC LIMIT ? OFFSET ?",
            (cid, lim, off),
        ).fetchall()
        out: List[Dict[str, Any]] = []
        for r in rows:
            d = dict(r)
            cj = d.get("citations_json")
            if isinstance(cj, str) and cj.strip():
                try:
                    d["citations"] = json.loads(cj)
                except Exception:
                    d["citations"] = []
            else:
                d["citations"] = []
            d.pop("citations_json", None)
            if d.get("reasoning") is None:
                d["reasoning"] = ""
            out.append(d)
        return out
    finally:
        conn.close()


def set_conversation_title(owner_userid: str, conversation_id: str, title: str) -> None:
    init_db()
    ou = (owner_userid or "").strip()
    if not ou:
        return
    cid = (conversation_id or "").strip()
    if not cid:
        return
    t = (title or "").strip()
    if not t:
        return
    now = _now_ms()
    conn = _connect()
    try:
        conn.execute(
            "UPDATE conversations SET title = ?, updated_at_ms = ? WHERE id = ? AND owner_userid = ?",
            (t, now, cid, ou),
        )
        conn.commit()
    finally:
        conn.close()


def delete_conversation(owner_userid: str, conversation_id: str) -> None:
    init_db()
    ou = (owner_userid or "").strip()
    if not ou:
        return
    cid = (conversation_id or "").strip()
    if not cid:
        return
    conn = _connect()
    try:
        # Only delete if conversation belongs to user.
        row = conn.execute("SELECT id FROM conversations WHERE id = ? AND owner_userid = ?", (cid, ou)).fetchone()
        if not row:
            return
        conn.execute("DELETE FROM messages WHERE conversation_id = ?", (cid,))
        conn.execute("DELETE FROM conversations WHERE id = ? AND owner_userid = ?", (cid, ou))
        conn.commit()
    finally:
        conn.close()

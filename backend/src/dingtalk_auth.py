import hashlib
import json
import os
import sqlite3
import time
import uuid
import urllib.parse
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, Body, HTTPException, Query, Request
from fastapi.responses import JSONResponse


router = APIRouter()


_COOKIE_NAME = os.getenv("DINGTALK_SESSION_COOKIE", "dt_session")
_SESSION_TTL_SECONDS = int(os.getenv("DINGTALK_SESSION_TTL_SECONDS", "604800") or "604800")


def _db_path() -> Path:
    p = os.getenv("DINGTALK_SESSION_DB")
    if p:
        return Path(p)
    return Path(__file__).resolve().parent.parent / "data_storage" / "dingtalk_sessions.sqlite3"


def _ensure_db() -> None:
    path = _db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(str(path)) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sessions (
              session_id TEXT PRIMARY KEY,
              user_json TEXT NOT NULL,
              created_at_ms INTEGER NOT NULL,
              expires_at_ms INTEGER NOT NULL
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_expires ON sessions(expires_at_ms)")
        conn.commit()


def _now_ms() -> int:
    return int(time.time() * 1000)


def _put_session(session_id: str, user: Dict[str, Any]) -> None:
    _ensure_db()
    created = _now_ms()
    expires = created + _SESSION_TTL_SECONDS * 1000
    with sqlite3.connect(str(_db_path())) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO sessions(session_id, user_json, created_at_ms, expires_at_ms) VALUES (?, ?, ?, ?)",
            (session_id, json.dumps(user, ensure_ascii=False), created, expires),
        )
        conn.commit()


def _get_session(session_id: str) -> Optional[Dict[str, Any]]:
    if not session_id:
        return None
    _ensure_db()
    now = _now_ms()
    with sqlite3.connect(str(_db_path())) as conn:
        cur = conn.execute(
            "SELECT user_json, expires_at_ms FROM sessions WHERE session_id = ?",
            (session_id,),
        )
        row = cur.fetchone()
        if not row:
            return None
        user_json, expires_at_ms = row
        if int(expires_at_ms or 0) <= now:
            conn.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
            conn.commit()
            return None
        try:
            return json.loads(user_json)
        except Exception:
            return None


def _http_json(url: str, method: str = "GET", data: Optional[Dict[str, Any]] = None, timeout: int = 6) -> Dict[str, Any]:
    body = None
    headers = {"Accept": "application/json"}
    if data is not None:
        body = json.dumps(data).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(url=url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        raw = ""
        try:
            raw = e.read().decode("utf-8", errors="replace")
        except Exception:
            pass
        raise HTTPException(status_code=502, detail=f"DingTalk HTTPError {e.code}: {raw or str(e)}")
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"DingTalk request failed: {e}")


def _dingtalk_app_key() -> str:
    v = (os.getenv("DINGTALK_CLIENT_ID") or os.getenv("DINGTALK_APP_KEY") or "").strip()
    if not v:
        raise HTTPException(status_code=500, detail="Missing DINGTALK_CLIENT_ID")
    return v


def _dingtalk_app_secret() -> str:
    v = (os.getenv("DINGTALK_CLIENT_SECRET") or os.getenv("DINGTALK_APP_SECRET") or "").strip()
    if not v:
        raise HTTPException(status_code=500, detail="Missing DINGTALK_CLIENT_SECRET")
    return v


def _dingtalk_corp_id() -> str:
    v = (os.getenv("DINGTALK_CORP_ID") or "").strip()
    if not v:
        raise HTTPException(status_code=500, detail="Missing DINGTALK_CORP_ID")
    return v


def _dingtalk_agent_id() -> str:
    v = (os.getenv("DINGTALK_AGENT_ID") or "").strip()
    if not v:
        raise HTTPException(status_code=500, detail="Missing DINGTALK_AGENT_ID")
    return v


def _get_access_token() -> str:
    qs = urllib.parse.urlencode({"appkey": _dingtalk_app_key(), "appsecret": _dingtalk_app_secret()})
    url = f"https://oapi.dingtalk.com/gettoken?{qs}"
    data = _http_json(url)
    if int(data.get("errcode") or 0) != 0:
        raise HTTPException(status_code=502, detail=f"Failed to get access_token: {data}")
    token = str(data.get("access_token") or "").strip()
    if not token:
        raise HTTPException(status_code=502, detail=f"Missing access_token: {data}")
    return token


def _get_jsapi_ticket(access_token: str) -> str:
    url = f"https://oapi.dingtalk.com/get_jsapi_ticket?access_token={urllib.parse.quote(access_token)}&type=jsapi"
    data = _http_json(url)
    if int(data.get("errcode") or 0) != 0:
        raise HTTPException(status_code=502, detail=f"Failed to get jsapi_ticket: {data}")
    ticket = str(data.get("ticket") or "").strip()
    if not ticket:
        raise HTTPException(status_code=502, detail=f"Missing jsapi_ticket: {data}")
    return ticket


def _signature(jsapi_ticket: str, nonce_str: str, timestamp: str, url: str) -> str:
    s = f"jsapi_ticket={jsapi_ticket}&noncestr={nonce_str}&timestamp={timestamp}&url={url}"
    return hashlib.sha1(s.encode("utf-8")).hexdigest()


@router.get("/api/auth/dingtalk/js_config")
async def dingtalk_js_config(url: str = Query(...)):
    raw_url = (url or "").strip()
    if not raw_url:
        raise HTTPException(status_code=400, detail="Missing url")

    if "#" in raw_url:
        raw_url = raw_url.split("#", 1)[0]

    access_token = _get_access_token()
    ticket = _get_jsapi_ticket(access_token)

    nonce_str = uuid.uuid4().hex
    timestamp = int(time.time())
    sig = _signature(ticket, nonce_str, str(timestamp), raw_url)

    return {
        "corpId": _dingtalk_corp_id(),
        "agentId": _dingtalk_agent_id(),
        "timeStamp": timestamp,
        "nonceStr": nonce_str,
        "signature": sig,
    }


def _get_userid_by_auth_code(access_token: str, auth_code: str) -> str:
    # Prefer v2 endpoint.
    url_v2 = f"https://oapi.dingtalk.com/topapi/v2/user/getuserinfo?access_token={urllib.parse.quote(access_token)}"
    try:
        data = _http_json(url_v2, method="POST", data={"code": auth_code})
        if int(data.get("errcode") or 0) == 0:
            result = data.get("result") or {}
            userid = str(result.get("userid") or "").strip()
            if userid:
                return userid
    except HTTPException:
        pass

    # Fallback legacy endpoint.
    qs = urllib.parse.urlencode({"access_token": access_token, "code": auth_code})
    url = f"https://oapi.dingtalk.com/user/getuserinfo?{qs}"
    data = _http_json(url)
    if int(data.get("errcode") or 0) != 0:
        raise HTTPException(status_code=502, detail=f"Failed to get userid: {data}")
    userid = str((data.get("userid") or "")).strip()
    if not userid:
        raise HTTPException(status_code=502, detail=f"Missing userid: {data}")
    return userid


def _get_user_detail(access_token: str, userid: str) -> Dict[str, Any]:
    # Prefer v2 endpoint.
    url_v2 = f"https://oapi.dingtalk.com/topapi/v2/user/get?access_token={urllib.parse.quote(access_token)}"
    try:
        data = _http_json(url_v2, method="POST", data={"userid": userid})
        if int(data.get("errcode") or 0) == 0 and isinstance(data.get("result"), dict):
            return data
    except HTTPException:
        pass

    # Fallback legacy endpoint.
    qs = urllib.parse.urlencode({"access_token": access_token, "userid": userid})
    url = f"https://oapi.dingtalk.com/user/get?{qs}"
    data = _http_json(url)
    if int(data.get("errcode") or 0) != 0:
        raise HTTPException(status_code=502, detail=f"Failed to get user detail: {data}")
    return data


@router.post("/api/auth/dingtalk/login")
async def dingtalk_login(request: Request, payload: Dict[str, Any] = Body(...)):  # type: ignore
    auth_code = str((payload or {}).get("authCode") or "").strip()
    if not auth_code:
        raise HTTPException(status_code=400, detail="Missing authCode")

    access_token = _get_access_token()
    userid = _get_userid_by_auth_code(access_token, auth_code)
    detail = _get_user_detail(access_token, userid)

    detail_result = detail.get("result") if isinstance(detail, dict) else None
    if isinstance(detail_result, dict):
        u = detail_result
    else:
        u = detail

    user = {
        "userid": userid,
        "name": u.get("name") or "",
        "avatar": u.get("avatar") or "",
        "mobile": u.get("mobile") or "",
        "unionid": u.get("unionid") or "",
    }

    session_id = uuid.uuid4().hex
    _put_session(session_id, user)

    forwarded_proto = str(request.headers.get("x-forwarded-proto") or "").strip().lower()
    scheme = forwarded_proto or str(getattr(request.url, "scheme", "") or "").lower()
    is_secure = scheme == "https"

    resp = JSONResponse({"ok": True, "user": user})
    resp.set_cookie(
        key=_COOKIE_NAME,
        value=session_id,
        httponly=True,
        secure=is_secure,
        samesite="none" if is_secure else "lax",
        max_age=_SESSION_TTL_SECONDS,
        path="/",
    )
    return resp


@router.get("/api/auth/me")
async def auth_me(request: Request):
    sid = request.cookies.get(_COOKIE_NAME) or ""
    user = _get_session(sid)
    if not user:
        raise HTTPException(status_code=401, detail="not logged in")
    return {"user": user}

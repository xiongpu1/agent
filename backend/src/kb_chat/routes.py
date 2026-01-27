import json
import os
import uuid
from typing import Any, Dict, Optional
import time
import re

from fastapi import APIRouter, Body, HTTPException, Query, Request
from fastapi.responses import StreamingResponse

from src.dingtalk_auth import _COOKIE_NAME, _get_session

from .neo4j_schema import probe_schema
from .service import (
    answer_smalltalk_llm,
    answer_bom_candidates,
    answer_nonstream,
    answer_material_codes_list,
    answer_products_list,
    build_citations,
    decide_clarify,
    generate_cypher,
    generate_suggestions,
    is_smalltalk,
    repair_cypher,
    reflect_failure,
    route_intent,
    agent_mode_enabled,
    agent_orchestrate,
    run_cypher,
    smalltalk_reply,
    stream_smalltalk_llm,
    stream_material_codes_list,
    stream_products_list,
    stream_bom_candidates,
    stream_answer,
)

from .conversations_store import (
    append_message,
    create_conversation,
    delete_conversation,
    get_conversation,
    list_conversations,
    list_messages,
    set_conversation_title,
)

router = APIRouter()


def _maybe_userid(request: Request) -> str:
    try:
        sid = request.cookies.get(_COOKIE_NAME) or ""
        user = _get_session(sid)
        if not user:
            return ""
        return str(user.get("userid") or "").strip()
    except Exception:
        return ""


def _require_userid(request: Request) -> str:
    uid = _maybe_userid(request)
    if not uid:
        raise HTTPException(status_code=401, detail="not logged in")
    return uid

# In-memory per-session state for UX flows (best-effort). This avoids LLM hallucinating
# candidate selections and allows deterministic mapping of "1/2" to actual DB candidates.
_SESSION_STATE: Dict[str, Dict[str, Any]] = {}


@router.post("/api/kb/conversations")
async def kb_create_conversation(request: Request, payload: Dict[str, Any] = Body(default={})):  # type: ignore
    owner_userid = _require_userid(request)
    title = payload.get("title") if isinstance(payload, dict) else None
    conv = create_conversation(owner_userid, initial_title=str(title) if title else None)
    return {"conversation": conv}


@router.get("/api/kb/conversations")
async def kb_list_conversations(
    request: Request,
    q: str = Query(default=""),
    limit: int = Query(default=50),
    offset: int = Query(default=0),
):
    owner_userid = _require_userid(request)
    items = list_conversations(owner_userid, limit=limit, offset=offset, q=q)
    return {"conversations": items}


@router.get("/api/kb/conversations/{conversation_id}")
async def kb_get_conversation(request: Request, conversation_id: str):
    owner_userid = _require_userid(request)
    conv = get_conversation(owner_userid, conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="conversation not found")
    return {"conversation": conv}


@router.get("/api/kb/conversations/{conversation_id}/messages")
async def kb_get_messages(
    request: Request,
    conversation_id: str,
    limit: int = Query(default=200),
    offset: int = Query(default=0),
):
    owner_userid = _require_userid(request)
    conv = get_conversation(owner_userid, conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="conversation not found")
    msgs = list_messages(owner_userid, conversation_id, limit=limit, offset=offset)
    return {"messages": msgs}


@router.delete("/api/kb/conversations/{conversation_id}")
async def kb_delete_conversation(request: Request, conversation_id: str):
    owner_userid = _require_userid(request)
    delete_conversation(owner_userid, conversation_id)
    return {"ok": True}


def _debug_llm_enabled() -> bool:
    v = (os.getenv("KBCHAT_DEBUG_LLM", "1") or "1").strip().lower()
    if v in {"0", "false", "no", "n", "off"}:
        return False
    return True


def _extract_candidate_index(message: str) -> Optional[int]:
    text = (message or "").strip()
    if not text:
        return None
    # Support long utterances, e.g.:
    # - "1" / "2"
    # - "第3个" / "刚刚第3个"
    # - "看第3个配置" / "我要第3个的产品配置"
    # Use search instead of match to allow leading/trailing words.
    m = re.search(r"(?:^|\D)(?:第\s*)?(\d{1,2})\s*(?:个|号)?(?:\D|$)", text)
    if not m:
        m = re.match(r"^(\d{1,2})$", text)
        if not m:
            return None
    try:
        idx = int(m.group(1))
    except Exception:
        return None
    return idx if 1 <= idx <= 50 else None


def _set_last_bom_candidates(session_id: str, material_code: str, candidates: list) -> None:
    if not session_id:
        return
    st = _SESSION_STATE.setdefault(session_id, {})
    st["last_bom_material_code"] = material_code
    st["last_bom_candidates"] = candidates


def _get_last_bom_candidates(session_id: str) -> list:
    if not session_id:
        return []
    st = _SESSION_STATE.get(session_id) or {}
    cands = st.get("last_bom_candidates")
    return cands if isinstance(cands, list) else []


def _candidate_identifier(cand: Any) -> str:
    # cand can be like {"rel_type":.., "labels":.., "bom":{...}}
    if isinstance(cand, dict) and isinstance(cand.get("bom"), dict):
        b = cand["bom"]
        for k in ("bom_id", "bom_code", "bomId", "bomCode", "code", "id", "name", "title"):
            v = b.get(k)
            if isinstance(v, str) and v.strip():
                return v.strip()
            if v is not None and str(v).strip():
                return str(v).strip()
    if isinstance(cand, dict):
        for k in ("bom_id", "bom_code", "bomId", "bomCode", "code", "id", "name", "title"):
            v = cand.get(k)
            if isinstance(v, str) and v.strip():
                return v.strip()
            if v is not None and str(v).strip():
                return str(v).strip()
    return ""


def _query_config_for_bom_identifier(identifier: str, limit: int = 200) -> list:
    ident = (identifier or "").strip()
    if not ident:
        return []
    # Step 1: locate a BOM-like node by matching common id/code/name fields.
    # Step 2: expand 1-2 hops to config-like nodes.
    cypher = (
        "MATCH (b) "
        "WHERE (b.bom_id = $ident OR b.bom_code = $ident OR b.bomId = $ident OR b.bomCode = $ident "
        "   OR b.code = $ident OR b.id = $ident OR b.name = $ident OR b.title = $ident "
        "   OR toString(b.bom_id) = $ident OR toString(b.bom_code) = $ident OR toString(b.id) = $ident) "
        "WITH b "
        "OPTIONAL MATCH (b)-[r1]-(x) "
        "OPTIONAL MATCH (x)-[r2]-(y) "
        "WITH b, r1, x, r2, y "
        "WHERE x IS NOT NULL AND ("
        "  any(l IN labels(x) WHERE toUpper(l) CONTAINS 'CONFIG') "
        "  OR any(l IN labels(x) WHERE toUpper(l) CONTAINS 'BOM') "
        "  OR x.bom_id IS NOT NULL OR x.bom_code IS NOT NULL OR x.bomId IS NOT NULL OR x.bomCode IS NOT NULL"
        ") "
        "RETURN labels(b) AS b_labels, b{.*} AS bom, type(r1) AS r1_type, labels(x) AS x_labels, x{.*} AS node1, type(r2) AS r2_type, labels(y) AS y_labels, y{.*} AS node2 "
        "LIMIT $limit"
    )
    return run_cypher(cypher, {"ident": ident, "limit": limit})


def _strict_no_candidates_text(material_code: str) -> str:
    mc = (material_code or "").strip()
    head = f"未在知识库中查到 {mc} 的BOM候选。" if mc else "未在知识库中查到BOM候选。"
    return (
        head
        + "\n"
        + "可能原因：该系列并非 Material.material_code，或图谱中BOM关系/字段命名不同。"
        + "\n"
        + "你可以：\n"
        + "(1) 直接粘贴完整BOM号；\n"
        + "(2) 换一个物料编码/型号再试；\n"
        + "(3) 告诉我你想看的系列关键词，我先帮你在库里定位对应节点。"
    )


def _is_list_products_question(message: str) -> bool:
    text = (message or "").strip().lower()
    if not text:
        return False
    patterns = [
        r"(一共|全部|所有)?(有|有哪些|列出|罗列|展示).{0,10}(产品|型号|机型)",
        r"(产品|型号|机型).{0,10}(列表|清单)",
    ]
    return any(re.search(p, text) for p in patterns)


def _bom_candidates_limit() -> int:
    try:
        v = int(os.getenv("KBCHAT_BOM_CANDIDATES_LIMIT", "10"))
        return max(1, min(v, 50))
    except Exception:
        return 10


def _query_boms_for_material(material_code: str, limit: int) -> list:
    def _escape_rel_type(t: str) -> str:
        # Relationship type is inserted into the Cypher string; keep it safe.
        # Neo4j allows backticks for escaping. Double backticks inside.
        return "`" + t.replace("`", "``") + "`"

    schema = probe_schema()
    rel_types = schema.get("relationshipTypes") or []
    bom_like = [rt for rt in rel_types if isinstance(rt, str) and "BOM" in rt.upper()]
    bom_like = bom_like[:20]
    rel_union = "|".join(_escape_rel_type(rt) for rt in bom_like) if bom_like else ""

    # 1) Prefer schema-driven explicit BOM-like relationships (both directions)
    if rel_union:
        cypher = (
            "MATCH (m:Material) "
            "WHERE toString(m.material_code) = $material_code "
            f"OPTIONAL MATCH (m)-[r:{rel_union}]-(b) "
            "RETURN type(r) AS rel_type, labels(b) AS labels, b{.*} AS bom "
            "LIMIT $limit"
        )
        rows = run_cypher(cypher, {"material_code": material_code, "limit": limit})
        out = []
        for r in rows:
            if not isinstance(r, dict):
                continue
            bom = r.get("bom")
            if isinstance(bom, dict) and bom:
                out.append({"rel_type": r.get("rel_type") or "", "labels": r.get("labels") or [], "bom": bom})
        if out:
            return out

    # 2) Fallback: traverse 1-hop neighbors and select nodes that *look like* BOM by labels or properties.
    # This avoids missing data when relationshipTypes do not contain 'BOM'.
    cypher_fb = (
        "MATCH (m:Material) "
        "WHERE toString(m.material_code) = $material_code "
        "OPTIONAL MATCH (m)-[r]-(b) "
        "WITH r, b "
        "WHERE b IS NOT NULL AND ("
        "  any(l IN labels(b) WHERE toUpper(l) CONTAINS 'BOM') "
        "  OR b.bom_id IS NOT NULL OR b.bom_code IS NOT NULL OR b.bomId IS NOT NULL OR b.bomCode IS NOT NULL"
        ") "
        "RETURN type(r) AS rel_type, labels(b) AS labels, b{.*} AS bom "
        "LIMIT $limit"
    )
    rows = run_cypher(cypher_fb, {"material_code": material_code, "limit": limit})
    out = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        bom = r.get("bom")
        if isinstance(bom, dict) and bom:
            out.append({"rel_type": r.get("rel_type") or "", "labels": r.get("labels") or [], "bom": bom})
    return out


def _is_material_codes_question(message: str) -> bool:
    text = (message or "").strip().lower()
    if not text:
        return False
    patterns = [
        r"(物料|material).{0,6}(编码|code).{0,6}(有哪些|多少|一共|总共|列表|清单|列出)",
        r"(有哪些|多少|一共|总共|列出).{0,10}(物料|material).{0,6}(编码|code)",
    ]
    return any(re.search(p, text) for p in patterns)


def _material_codes_limit() -> int:
    try:
        v = int(os.getenv("KBCHAT_MATERIAL_CODES_LIMIT", "500"))
        return max(1, min(v, 2000))
    except Exception:
        return 500


def _format_products_list(rows: list, limit: int) -> str:
    products = []
    for row in rows[: max(limit, 1)]:
        p = row.get("product") if isinstance(row, dict) else None
        if not isinstance(p, dict):
            continue
        name = (p.get("display_name_zh") or p.get("name") or p.get("display_name_en") or "").strip()
        material_code = str(p.get("material_code") or "").strip()
        product_id = str(p.get("product_id") or "").strip()
        product_type = str(p.get("product_type_zh") or "").strip()
        if not name:
            name = material_code or product_id or "产品"
        meta = []
        if material_code:
            meta.append(f"物料:{material_code}")
        if product_id:
            meta.append(f"ID:{product_id}")
        if product_type:
            meta.append(f"类型:{product_type}")
        tail = ("（" + "，".join(meta) + "）") if meta else ""
        products.append(f"- {name}{tail}")
    if not products:
        return "知识库中未找到产品记录。"
    more = "" if len(rows) <= limit else f"\n\n仅展示前{limit}条，如需查看某一类/某个型号，请继续输入关键词或物料编码。"
    return f"当前库中检索到产品记录（展示前{min(len(rows), limit)}条）：\n" + "\n".join(products) + more


def _list_products_limit() -> int:
    try:
        v = int(os.getenv("KBCHAT_LIST_PRODUCTS_LIMIT", "200"))
        return max(1, min(v, 1000))
    except Exception:
        return 200


def _sse(event: str, data: Any) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _sse_comment(text: str) -> str:
    # SSE comment line (ignored by client) useful to force flush.
    return f": {text}\n\n"


def _build_streaming_response(gen):
    resp = StreamingResponse(gen(), media_type="text/event-stream")
    # Reduce buffering in proxies (nginx, etc.) so the frontend receives deltas immediately.
    resp.headers["Cache-Control"] = "no-cache"
    resp.headers["Connection"] = "keep-alive"
    resp.headers["X-Accel-Buffering"] = "no"
    return resp


@router.get("/api/kb/chat/suggestions")
async def kb_chat_suggestions(
    moduleKey: str = Query(default="kbChat"),
    productName: str = Query(default=""),
    materialCode: str = Query(default=""),
    bomId: str = Query(default=""),
):
    suggestions = generate_suggestions({
        "moduleKey": moduleKey,
        "productName": productName,
        "materialCode": materialCode,
        "bomId": bomId,
    })
    return {"suggestions": suggestions}


@router.get("/api/kb/chat/schema")
async def kb_chat_schema():
    """Return probed Neo4j schema (labels/relationships/properties/patterns).

    This is intended for integration/debugging.
    """

    return probe_schema(force=True)


@router.post("/api/kb/chat")
async def kb_chat(request: Request, payload: Dict[str, Any] = Body(...)):
    """Non-streaming KB chat endpoint (JSON). Used as a fallback when SSE is blocked."""

    conversation_id = (payload.get("conversationId") or "").strip()
    message = (payload.get("message") or "").strip()
    context = payload.get("context") if isinstance(payload.get("context"), dict) else {}
    local_mode = bool(payload.get("local"))
    history_in = payload.get("history") if isinstance(payload.get("history"), list) else None

    owner_userid = _maybe_userid(request)
    if not local_mode:
        if not owner_userid:
            raise HTTPException(status_code=401, detail="not logged in")
        if not conversation_id:
            raise HTTPException(status_code=400, detail="conversationId 不能为空")
        conv = get_conversation(owner_userid, conversation_id)
        if not conv:
            raise HTTPException(status_code=404, detail="conversation not found")

        # Load history from DB
        db_msgs = list_messages(owner_userid, conversation_id, limit=24, offset=0)
        history = [
            {"role": m.get("role"), "content": m.get("content")}
            for m in db_msgs
            if m.get("role") in {"user", "assistant", "system"}
        ]
        session_id = conversation_id
    else:
        # Local mode: allow chatting without login and without persistence.
        history = []
        if isinstance(history_in, list):
            for it in history_in:
                if not isinstance(it, dict):
                    continue
                r = str(it.get("role") or "").strip()
                c = str(it.get("content") or "").strip()
                if r in {"user", "assistant", "system"} and c:
                    history.append({"role": r, "content": c})
        history = history[-24:]
        session_id = conversation_id or "local"

    if not message:
        raise HTTPException(status_code=400, detail="message 不能为空")

    if agent_mode_enabled():
        if not local_mode:
            append_message(owner_userid, conversation_id, role="user", content=message)
        out = agent_orchestrate(message, history=history, context=context, session_id=session_id)
        if not local_mode:
            append_message(
                owner_userid,
                conversation_id,
                role="assistant",
                content=out.get("content") or "",
                reasoning=out.get("reasoning") or "",
                citations=out.get("citations") or [],
            )
        return {
            "conversationId": conversation_id,
            "type": out.get("type") or "answer",
            "content": out.get("content") or "",
            "citations": out.get("citations") or [],
            "reasoning": out.get("reasoning") or "",
        }

    # Deterministic candidate selection: if user inputs "1/2" after we presented candidates,
    # map it to the actual candidate and query config.
    idx = _extract_candidate_index(message)
    if idx is not None:
        cands = _get_last_bom_candidates(session_id)
        if cands and 1 <= idx <= len(cands):
            chosen = cands[idx - 1]
            chosen_ident = _candidate_identifier(chosen)
            rows = _query_config_for_bom_identifier(chosen_ident)
            used_ident = chosen_ident
            if not rows:
                # Auto-pick another candidate with config
                for j, cand in enumerate(cands):
                    if j == idx - 1:
                        continue
                    ident = _candidate_identifier(cand)
                    if not ident:
                        continue
                    r2 = _query_config_for_bom_identifier(ident)
                    if r2:
                        rows = r2
                        used_ident = ident
                        break
            if rows:
                citations = build_citations(rows)
                q = f"请解释 BOM {used_ident} 的产品配置"
                content = answer_nonstream(q, history, rows)
                return {
                    "sessionId": session_id,
                    "type": "answer",
                    "content": content,
                    "citations": citations,
                }
            # No config found for any candidate
            return {
                "sessionId": session_id,
                "type": "answer",
                "content": "已根据你选择的候选BOM尝试查询产品配置，但知识库中未找到任何候选的配置明细。你可以粘贴完整BOM号或换一个系列/物料编码继续。",
                "citations": [],
            }

    routed = route_intent(message, history=history, context=context)
    action = routed.get("action")
    args = routed.get("args") if isinstance(routed.get("args"), dict) else {}

    if action == "answer_smalltalk":
        return {
            "sessionId": session_id,
            "type": "answer",
            "content": answer_smalltalk_llm(message, history),
            "citations": [],
        }

    if action == "list_material_codes":
        limit = int(args.get("limit") or _material_codes_limit())
        limit = max(1, min(limit, _material_codes_limit()))
        cypher_count = "MATCH (m:Material) RETURN count(DISTINCT m.material_code) AS cnt"
        cypher_list = (
            "MATCH (m:Material) "
            "WHERE m.material_code IS NOT NULL AND trim(toString(m.material_code)) <> '' "
            "RETURN DISTINCT toString(m.material_code) AS code "
            "ORDER BY code ASC "
            "LIMIT $limit"
        )
        rows_cnt = run_cypher(cypher_count, {})
        total = None
        try:
            if rows_cnt and isinstance(rows_cnt[0], dict):
                total = int(rows_cnt[0].get("cnt"))
        except Exception:
            total = None
        rows = run_cypher(cypher_list, {"limit": limit})
        codes = [str(r.get("code")) for r in rows if isinstance(r, dict) and r.get("code")]
        return {
            "sessionId": session_id,
            "type": "answer",
            "content": answer_material_codes_list(message, history, codes, total=total),
            "citations": [],
        }

    if action == "list_products":
        limit = int(args.get("limit") or _list_products_limit())
        limit = max(1, min(limit, _list_products_limit()))
        cypher = (
            "MATCH (p:Product) "
            "RETURN p{.*} AS product "
            "ORDER BY coalesce(p.display_name_zh, p.name, p.display_name_en, p.product_id) ASC "
            "LIMIT $limit"
        )
        rows = run_cypher(cypher, {"limit": limit})
        citations = build_citations(rows, limit=min(limit, 50))
        return {
            "sessionId": session_id,
            "type": "answer",
            "content": answer_products_list(message, history, rows),
            "citations": citations,
        }

    if action == "list_boms_for_material":
        material_code = str(args.get("material_code") or "").strip()
        if material_code:
            limit = _bom_candidates_limit()
            rows = _query_boms_for_material(material_code, limit=limit)
            _set_last_bom_candidates(session_id, material_code, rows)
            if not rows:
                reflect_failure(message, stage="list_boms_for_material_empty", detail=f"material_code={material_code}", history=history)
                return {
                    "sessionId": session_id,
                    "type": "answer",
                    "content": _strict_no_candidates_text(material_code),
                    "citations": [],
                }
            return {
                "sessionId": session_id,
                "type": "answer",
                "content": answer_bom_candidates(message, history, material_code, rows, total=None),
                "citations": [],
            }

    try:
        need_clarify, clarify_text = decide_clarify(message, history, context=context)
    except Exception as exc:
        reflect_failure(message, stage="decide_clarify", detail=str(exc), history=history)
        raise HTTPException(status_code=502, detail=f"澄清判断失败: {exc}")
    if need_clarify:
        return {
            "sessionId": session_id,
            "type": "clarify",
            "content": clarify_text,
            "citations": [],
        }

    try:
        cypher, params = generate_cypher(message, history=history)
    except HTTPException:
        raise
    except Exception as exc:
        reflect_failure(message, stage="generate_cypher", detail=str(exc), history=history)
        raise HTTPException(status_code=502, detail=f"Cypher生成失败: {exc}")
    try:
        rows = run_cypher(cypher, params)
    except Exception as exc:
        reflect_failure(message, stage="run_cypher", detail=f"{exc}; cypher={cypher}; params={params}", history=history)
        new_cypher, new_params = repair_cypher(message, cypher, params, str(exc), history=history)
        try:
            rows = run_cypher(new_cypher, new_params)
        except Exception as exc2:
            reflect_failure(message, stage="run_cypher_after_repair", detail=f"{exc2}; cypher={new_cypher}; params={new_params}", history=history)
            raise HTTPException(status_code=502, detail=f"Neo4j查询失败: {exc2}")

    citations = build_citations(rows)
    try:
        content = answer_nonstream(message, history, rows)
    except Exception as exc:
        reflect_failure(message, stage="answer_nonstream", detail=str(exc), history=history)
        raise HTTPException(status_code=502, detail=f"LLM回答失败: {exc}")

    if _debug_llm_enabled() and rows == []:
        reflect_failure(message, stage="empty_rows", detail=f"cypher={cypher}; params={params}", history=history)
    return {
        "sessionId": session_id,
        "type": "answer",
        "content": content,
        "citations": citations,
    }


@router.post("/api/kb/chat/stream")
async def kb_chat_stream(
    request: Request,
    payload: Dict[str, Any] = Body(...),
):
    conversation_id = (payload.get("conversationId") or "").strip()
    message = (payload.get("message") or "").strip()
    context = payload.get("context") if isinstance(payload.get("context"), dict) else {}
    local_mode = bool(payload.get("local"))
    history_in = payload.get("history") if isinstance(payload.get("history"), list) else None

    owner_userid = _maybe_userid(request)
    if not local_mode:
        if not owner_userid:
            raise HTTPException(status_code=401, detail="not logged in")
        if not conversation_id:
            raise HTTPException(status_code=400, detail="conversationId 不能为空")
        conv = get_conversation(owner_userid, conversation_id)
        if not conv:
            raise HTTPException(status_code=404, detail="conversation not found")

        # Load history from DB
        db_msgs = list_messages(owner_userid, conversation_id, limit=24, offset=0)
        history = [
            {"role": m.get("role"), "content": m.get("content")}
            for m in db_msgs
            if m.get("role") in {"user", "assistant", "system"}
        ]
        # Keep legacy helper paths using session_id naming.
        session_id = conversation_id
    else:
        # Local mode: allow chatting without login and without persistence.
        history = []
        if isinstance(history_in, list):
            for it in history_in:
                if not isinstance(it, dict):
                    continue
                r = str(it.get("role") or "").strip()
                c = str(it.get("content") or "").strip()
                if r in {"user", "assistant", "system"} and c:
                    history.append({"role": r, "content": c})
        history = history[-24:]
        session_id = conversation_id or "local"

    if not message:
        raise HTTPException(status_code=400, detail="message 不能为空")

    def gen():
        # Many proxies buffer small chunks; send a padding comment first to force flush.
        yield _sse_comment("pad " + ("." * 2048))
        last_ping = time.time()

        yield _sse("meta", {"conversationId": conversation_id})

        if agent_mode_enabled():
            if not local_mode:
                append_message(owner_userid, conversation_id, role="user", content=message)
            out = agent_orchestrate(message, history=history, context=context, session_id=session_id)
            typ = out.get("type") or "answer"
            reasoning = out.get("reasoning") or ""
            if typ == "clarify":
                if reasoning:
                    yield _sse("reasoning_delta", {"delta": reasoning})
                yield _sse("clarify", {"content": out.get("content") or ""})
                if not local_mode:
                    append_message(
                        owner_userid,
                        conversation_id,
                        role="assistant",
                        content=out.get("content") or "",
                        reasoning=reasoning,
                        citations=out.get("citations") or [],
                    )
                yield _sse("done", {"ok": True})
                return
            if reasoning:
                yield _sse("reasoning_delta", {"delta": reasoning})
            yield _sse("answer_delta", {"delta": out.get("content") or ""})
            yield _sse("citations", {"citations": out.get("citations") or []})
            if not local_mode:
                append_message(
                    owner_userid,
                    conversation_id,
                    role="assistant",
                    content=out.get("content") or "",
                    reasoning=reasoning,
                    citations=out.get("citations") or [],
                )
            yield _sse("done", {"ok": True})
            return

        idx = _extract_candidate_index(message)
        if idx is not None:
            cands = _get_last_bom_candidates(session_id)
            if cands and 1 <= idx <= len(cands):
                chosen = cands[idx - 1]
                chosen_ident = _candidate_identifier(chosen)
                rows = _query_config_for_bom_identifier(chosen_ident)
                used_ident = chosen_ident
                if not rows:
                    for j, cand in enumerate(cands):
                        if j == idx - 1:
                            continue
                        ident = _candidate_identifier(cand)
                        if not ident:
                            continue
                        r2 = _query_config_for_bom_identifier(ident)
                        if r2:
                            rows = r2
                            used_ident = ident
                            break
                if rows:
                    yield _sse("retrieval", {"count": len(rows)})
                    stream = stream_answer(f"请解释 BOM {used_ident} 的产品配置", history, rows)
                    try:
                        for chunk in stream:
                            delta = ""
                            try:
                                delta = chunk["choices"][0]["delta"].get("content") or ""
                            except Exception:
                                try:
                                    delta = chunk.choices[0].delta.content or ""
                                except Exception:
                                    delta = ""
                            if delta:
                                yield _sse("answer_delta", {"delta": delta})
                    except Exception as exc:
                        reflect_failure(message, stage="stream_answer_selected_bom", detail=str(exc), history=history)
                        yield _sse("error", {"message": f"LLM输出失败: {exc}"})
                        yield _sse("done", {"ok": False})
                        return

                    citations = build_citations(rows)
                    yield _sse("citations", {"citations": citations})
                    yield _sse("done", {"ok": True})
                    return

                yield _sse("answer_delta", {"delta": "已根据你选择的候选BOM尝试查询产品配置，但知识库中未找到任何候选的配置明细。你可以粘贴完整BOM号或换一个系列/物料编码继续。"})
                yield _sse("done", {"ok": True})
                return

        routed = route_intent(message, history=history, context=context)
        action = routed.get("action")
        args = routed.get("args") if isinstance(routed.get("args"), dict) else {}

        if action == "answer_smalltalk":
            stream = stream_smalltalk_llm(message, history)
            try:
                for chunk in stream:
                    delta = ""
                    try:
                        delta = chunk["choices"][0]["delta"].get("content") or ""
                    except Exception:
                        try:
                            delta = chunk.choices[0].delta.content or ""
                        except Exception:
                            delta = ""
                    if delta:
                        yield _sse("answer_delta", {"delta": delta})
            except Exception as exc:
                yield _sse("error", {"message": f"LLM输出失败: {exc}"})
                yield _sse("done", {"ok": False})
                return
            yield _sse("done", {"ok": True})
            return

        if action == "list_material_codes":
            limit = _material_codes_limit()
            cypher_count = "MATCH (m:Material) RETURN count(DISTINCT m.material_code) AS cnt"
            cypher_list = (
                "MATCH (m:Material) "
                "WHERE m.material_code IS NOT NULL AND trim(toString(m.material_code)) <> '' "
                "RETURN DISTINCT toString(m.material_code) AS code "
                "ORDER BY code ASC "
                "LIMIT $limit"
            )
            rows_cnt = run_cypher(cypher_count, {})
            total = None
            try:
                if rows_cnt and isinstance(rows_cnt[0], dict):
                    total = int(rows_cnt[0].get("cnt"))
            except Exception:
                total = None
            rows = run_cypher(cypher_list, {"limit": limit})
            codes = [str(r.get("code")) for r in rows if isinstance(r, dict) and r.get("code")]
            yield _sse("retrieval", {"count": len(codes)})

            stream = stream_material_codes_list(message, history, codes, total=total)
            try:
                for chunk in stream:
                    delta = ""
                    try:
                        delta = chunk["choices"][0]["delta"].get("content") or ""
                    except Exception:
                        try:
                            delta = chunk.choices[0].delta.content or ""
                        except Exception:
                            delta = ""
                    if delta:
                        yield _sse("answer_delta", {"delta": delta})
            except Exception as exc:
                yield _sse("error", {"message": f"LLM输出失败: {exc}"})
                yield _sse("done", {"ok": False})
                return

            yield _sse("citations", {"citations": []})
            yield _sse("done", {"ok": True})
            return

        if action == "list_products":
            cypher = (
                "MATCH (p:Product) "
                "RETURN p{.*} AS product "
                "ORDER BY coalesce(p.display_name_zh, p.name, p.display_name_en, p.product_id) ASC "
                "LIMIT $limit"
            )
            limit = _list_products_limit()
            rows = run_cypher(cypher, {"limit": limit})
            yield _sse("retrieval", {"count": len(rows)})
            citations = build_citations(rows, limit=min(limit, 50))

            stream = stream_products_list(message, history, rows)
            try:
                for chunk in stream:
                    delta = ""
                    try:
                        delta = chunk["choices"][0]["delta"].get("content") or ""
                    except Exception:
                        try:
                            delta = chunk.choices[0].delta.content or ""
                        except Exception:
                            delta = ""
                    if delta:
                        yield _sse("answer_delta", {"delta": delta})
            except Exception as exc:
                yield _sse("error", {"message": f"LLM输出失败: {exc}"})
                yield _sse("done", {"ok": False})
                return

            yield _sse("citations", {"citations": citations})
            yield _sse("done", {"ok": True})
            return

        if action == "list_boms_for_material":
            material_code = str(args.get("material_code") or "").strip()
            if material_code:
                limit = _bom_candidates_limit()
                rows = _query_boms_for_material(material_code, limit=limit)
                _set_last_bom_candidates(session_id, material_code, rows)
                if not rows:
                    reflect_failure(message, stage="list_boms_for_material_empty", detail=f"material_code={material_code}", history=history)
                    yield _sse("answer_delta", {"delta": _strict_no_candidates_text(material_code)})
                    yield _sse("done", {"ok": True})
                    return
                yield _sse("retrieval", {"count": len(rows)})

                stream = stream_bom_candidates(message, history, material_code, rows, total=None)
                try:
                    for chunk in stream:
                        delta = ""
                        try:
                            delta = chunk["choices"][0]["delta"].get("content") or ""
                        except Exception:
                            try:
                                delta = chunk.choices[0].delta.content or ""
                            except Exception:
                                delta = ""
                        if delta:
                            yield _sse("answer_delta", {"delta": delta})
                except Exception as exc:
                    yield _sse("error", {"message": f"LLM输出失败: {exc}"})
                    yield _sse("done", {"ok": False})
                    return

                yield _sse("done", {"ok": True})
                return

        # Keep-alive ping (comment) in case upstream proxies close idle streams.
        if time.time() - last_ping > 10:
            yield _sse_comment("ping")
            last_ping = time.time()

        need_clarify, clarify_text = decide_clarify(message, history, context=context)
        if need_clarify:
            yield _sse("clarify", {"content": clarify_text})
            yield _sse("done", {"ok": True})
            return

        cypher = ""
        params: Dict[str, Any] = {}
        try:
            cypher, params = generate_cypher(message, history=history)
        except HTTPException as exc:
            reflect_failure(message, stage="generate_cypher", detail=str(exc.detail), history=history)
            yield _sse("error", {"message": str(exc.detail)})
            yield _sse("done", {"ok": False})
            return
        except Exception as exc:
            reflect_failure(message, stage="generate_cypher", detail=str(exc), history=history)
            yield _sse("error", {"message": f"Cypher生成失败: {exc}"})
            yield _sse("done", {"ok": False})
            return

        rows = []
        try:
            rows = run_cypher(cypher, params)
        except Exception as exc:
            try:
                reflect_failure(message, stage="run_cypher", detail=f"{exc}; cypher={cypher}; params={params}", history=history)
                new_cypher, new_params = repair_cypher(message, cypher, params, str(exc), history=history)
                rows = run_cypher(new_cypher, new_params)
                cypher, params = new_cypher, new_params
            except Exception as exc2:
                reflect_failure(message, stage="run_cypher_after_repair", detail=f"{exc2}; cypher={cypher}; params={params}", history=history)
                yield _sse("error", {"message": f"Neo4j查询失败: {exc2}"})
                yield _sse("done", {"ok": False})
                return

        yield _sse("retrieval", {"count": len(rows)})

        citations = build_citations(rows)
        stream = stream_answer(message, history, rows)
        buf = ""
        try:
            for chunk in stream:
                delta = ""
                try:
                    delta = chunk["choices"][0]["delta"].get("content") or ""
                except Exception:
                    try:
                        delta = chunk.choices[0].delta.content or ""
                    except Exception:
                        delta = ""

                if delta:
                    yield _sse("answer_delta", {"delta": delta})
                    if _debug_llm_enabled() and len(buf) < 4000:
                        buf += delta
        except Exception as exc:
            reflect_failure(message, stage="stream_answer", detail=str(exc), history=history)
            yield _sse("error", {"message": f"LLM输出失败: {exc}"})
            yield _sse("done", {"ok": False})
            return

        if _debug_llm_enabled():
            if rows == []:
                reflect_failure(message, stage="empty_rows", detail=f"cypher={cypher}; params={params}", history=history)
            if buf:
                print(f"[KBCHAT][LLM][answer_stream][OUT] {(buf[:4000] + ('...' if len(buf) > 4000 else ''))}")

        yield _sse("citations", {"citations": citations})
        yield _sse("done", {"ok": True})

    return _build_streaming_response(gen)


@router.get("/api/kb/chat/stream_get")
async def kb_chat_stream_get(
    request: Request,
    payload: str = Query(default=""),
    sessionId: str = Query(default=""),
    message: str = Query(default=""),
    moduleKey: str = Query(default="kbChat"),
):
    """GET-based SSE endpoint for environments where POST streaming is unreliable.

    You can pass either:
    - payload=<urlencoded JSON string> (recommended)
    or
    - message/sessionId/moduleKey
    """

    data: Dict[str, Any] = {}
    if payload:
        try:
            data = json.loads(payload)
        except Exception:
            raise HTTPException(status_code=400, detail="payload JSON 解析失败")
    else:
        data = {
            "sessionId": sessionId,
            "message": message,
            "history": [],
            "context": {"moduleKey": moduleKey},
        }

    # Reuse POST handler logic by calling it directly.
    return await kb_chat_stream(request, payload=data)

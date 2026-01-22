import json
import os
import uuid
from typing import Any, Dict, Optional
import time
import re

from fastapi import APIRouter, Body, HTTPException, Query
from fastapi.responses import StreamingResponse

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
    run_cypher,
    smalltalk_reply,
    stream_smalltalk_llm,
    stream_material_codes_list,
    stream_products_list,
    stream_bom_candidates,
    stream_answer,
)

router = APIRouter()


def _debug_llm_enabled() -> bool:
    v = (os.getenv("KBCHAT_DEBUG_LLM", "1") or "1").strip().lower()
    if v in {"0", "false", "no", "n", "off"}:
        return False
    return True


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
async def kb_chat(payload: Dict[str, Any] = Body(...)):
    """Non-streaming KB chat endpoint (JSON). Used as a fallback when SSE is blocked."""

    session_id = (payload.get("sessionId") or "").strip() or str(uuid.uuid4())
    message = (payload.get("message") or "").strip()
    history = payload.get("history")
    context = payload.get("context") if isinstance(payload.get("context"), dict) else {}

    if not message:
        raise HTTPException(status_code=400, detail="message 不能为空")

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
    payload: Dict[str, Any] = Body(...),
):
    session_id = (payload.get("sessionId") or "").strip() or str(uuid.uuid4())
    message = (payload.get("message") or "").strip()
    history = payload.get("history")
    context = payload.get("context") if isinstance(payload.get("context"), dict) else {}

    if not message:
        raise HTTPException(status_code=400, detail="message 不能为空")

    def gen():
        # Many proxies buffer small chunks; send a padding comment first to force flush.
        yield _sse_comment("pad " + ("." * 2048))
        last_ping = time.time()

        yield _sse("meta", {"sessionId": session_id})

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
    return await kb_chat_stream(payload=data)

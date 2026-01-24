import json
import os
import re
from typing import Any, Dict, Iterator, List, Optional, Tuple
import time

from fastapi import HTTPException

from src.api_queries import get_neo4j_config
from src.neo4j_file_add_neo4j import get_neo4j_driver

from .llm_client import chat_json, chat_stream
from .neo4j_schema import probe_schema
from .utils import extract_json_object


_AGENT_STATE: Dict[str, Dict[str, Any]] = {}


def _to_public_file_url(path: str) -> str:
    p = (path or "").strip()
    if not p:
        return ""
    if p.startswith("http://") or p.startswith("https://"):
        return p
    p = p.replace("\\", "/")
    if p.startswith("/api/files/"):
        return p
    p = p.lstrip("/")
    return f"/api/files/{p}" if p else ""


def _thinking_enabled() -> bool:
    v = (os.getenv("KBCHAT_ENABLE_THINKING", "0") or "0").strip().lower()
    return v in {"1", "true", "yes", "y", "on"}


def _chat_json_with_optional_thinking(messages: List[Dict[str, str]]) -> Tuple[Any, str, str]:
    """Return (resp, content, reasoning).

    Many thinking-capable models return reasoning_content only in streaming deltas.
    If thinking is enabled, we stream and accumulate.
    """

    if not _thinking_enabled():
        resp = chat_json(messages)
        content = (resp.get("choices", [{}])[0].get("message") or {}).get("content") or ""
        return resp, str(content), _extract_reasoning_from_resp(resp)

    reasoning_buf: List[str] = []
    content_buf: List[str] = []
    try:
        for chunk in chat_stream(messages):
            delta = {}
            try:
                delta = chunk["choices"][0].get("delta") or {}
            except Exception:
                try:
                    delta = chunk.choices[0].delta or {}
                except Exception:
                    delta = {}
            rc = None
            c = None
            try:
                rc = delta.get("reasoning_content")
                c = delta.get("content")
            except Exception:
                rc = None
                c = None
            if isinstance(rc, str) and rc:
                reasoning_buf.append(rc)
            if isinstance(c, str) and c:
                content_buf.append(c)
    except Exception:
        resp = chat_json(messages)
        content = (resp.get("choices", [{}])[0].get("message") or {}).get("content") or ""
        return resp, str(content), _extract_reasoning_from_resp(resp)

    reasoning = "".join(reasoning_buf).strip()
    content = "".join(content_buf).strip()
    resp = {"choices": [{"message": {"content": content, "reasoning_content": reasoning}}]}
    return resp, content, reasoning


def is_smalltalk(message: str) -> bool:
    text = (message or "").strip().lower()
    if not text:
        return True
    if len(text) <= 6 and re.fullmatch(r"[\s\W_]+", text):
        return True

    if len(text) <= 12:
        patterns = [
            r"^(你好|您好|hi|hello|hey|哈喽|嗨)$",
            r"^(在吗|在不在|有人吗)$",
            r"^(谢谢|多谢|感谢|thx|thanks)$",
            r"^(bye|再见|拜拜)$",
        ]
        return any(re.match(p, text, flags=re.IGNORECASE) for p in patterns)

    return False


def agent_mode_enabled() -> bool:
    v = (os.getenv("KBCHAT_AGENT_MODE", "1") or "1").strip().lower()
    if v in {"0", "false", "no", "n", "off"}:
        return False
    return True


def _agent_max_tool_calls() -> int:
    try:
        v = int(os.getenv("KBCHAT_AGENT_MAX_TOOL_CALLS", "8"))
        return max(1, min(v, 20))
    except Exception:
        return 8


def _agent_schema_scan_limits() -> Tuple[int, int]:
    try:
        node_limit = int(os.getenv("KBCHAT_AGENT_SCHEMA_SCAN_NODE_LIMIT", "50000"))
    except Exception:
        node_limit = 50000
    try:
        rel_limit = int(os.getenv("KBCHAT_AGENT_SCHEMA_SCAN_REL_LIMIT", "50000"))
    except Exception:
        rel_limit = 50000
    return max(1000, min(node_limit, 500000)), max(1000, min(rel_limit, 500000))


def _agent_schema_cache_ttl_seconds() -> int:
    try:
        v = int(os.getenv("KBCHAT_AGENT_SCHEMA_CACHE_TTL_SECONDS", "60"))
        return max(5, min(v, 3600))
    except Exception:
        return 60


_AGENT_SCHEMA_CACHE: Dict[str, Any] = {"ts": 0.0, "value": None}


def _build_agent_schema_snapshot_via_call() -> Dict[str, Any]:
    """Schema snapshot using Neo4j built-in db.schema procedures.

    This requires CALL support on the Neo4j instance, and is more complete than
    scanning existing data for keys.
    """
    out: Dict[str, Any] = {
        "source": "call",
        "labels": [],
        "relationshipTypes": [],
        "labelProperties": {},
        "relProperties": {},
    }

    # labels
    rows = run_cypher("CALL db.labels() YIELD label RETURN label ORDER BY label", {"limit": 5000})
    out["labels"] = [r.get("label") for r in rows if isinstance(r.get("label"), str)]

    # relationship types
    rows = run_cypher(
        "CALL db.relationshipTypes() YIELD relationshipType RETURN relationshipType ORDER BY relationshipType",
        {"limit": 5000},
    )
    out["relationshipTypes"] = [
        r.get("relationshipType") for r in rows if isinstance(r.get("relationshipType"), str)
    ]

    # node type properties
    # Neo4j returns: nodeType (e.g. ':Product'), propertyName, propertyTypes, mandatory
    rows = run_cypher(
        "CALL db.schema.nodeTypeProperties() YIELD nodeType, propertyName RETURN nodeType, propertyName ORDER BY nodeType, propertyName",
        {"limit": 200000},
    )
    label_props: Dict[str, List[str]] = {}
    for r in rows or []:
        nt = r.get("nodeType")
        pn = r.get("propertyName")
        if not (isinstance(nt, str) and isinstance(pn, str)):
            continue
        # ':Product' -> 'Product'
        lab = nt.lstrip(":")
        if not lab:
            continue
        label_props.setdefault(lab, []).append(pn)
    out["labelProperties"] = {k: sorted(list(set(v))) for k, v in label_props.items()}

    # rel type properties
    rows = run_cypher(
        "CALL db.schema.relTypeProperties() YIELD relType, propertyName RETURN relType, propertyName ORDER BY relType, propertyName",
        {"limit": 200000},
    )
    rel_props: Dict[str, List[str]] = {}
    for r in rows or []:
        rt = r.get("relType")
        pn = r.get("propertyName")
        if not (isinstance(rt, str) and isinstance(pn, str)):
            continue
        rel_props.setdefault(rt, []).append(pn)
    out["relProperties"] = {k: sorted(list(set(v))) for k, v in rel_props.items()}

    return out


def build_agent_schema_snapshot() -> Dict[str, Any]:
    """Best-effort schema snapshot without using CALL/apoc.

    We derive labels/relationship types and property keys by scanning existing data.
    This is data-driven: it reflects what exists in the graph right now.
    """

    ttl = _agent_schema_cache_ttl_seconds()
    now = time.time()
    cached = _AGENT_SCHEMA_CACHE.get("value")
    ts = float(_AGENT_SCHEMA_CACHE.get("ts") or 0.0)
    if cached and (now - ts) <= ttl:
        return cached

    node_limit, rel_limit = _agent_schema_scan_limits()
    out: Dict[str, Any] = {
        "source": "scan",
        "nodeLimit": node_limit,
        "relLimit": rel_limit,
        "labels": [],
        "relationshipTypes": [],
        "labelProperties": {},
        "relProperties": {},
        "sampleTriples": [],
    }

    # Prefer CALL-based schema if user allows (and Neo4j supports it).
    allow_call = (os.getenv("KBCHAT_AGENT_ALLOW_SCHEMA_CALL", "1") or "1").strip().lower()
    if allow_call not in {"0", "false", "no", "n", "off"}:
        try:
            out = _build_agent_schema_snapshot_via_call()
            _AGENT_SCHEMA_CACHE["ts"] = now
            _AGENT_SCHEMA_CACHE["value"] = out
            return out
        except Exception as exc:
            out["callSchemaError"] = str(exc)

    try:
        # Labels and per-label property keys.
        node_rows = run_cypher(
            "MATCH (n)\n"
            "WITH n LIMIT $limit\n"
            "UNWIND labels(n) AS l\n"
            "WITH l, keys(n) AS ks\n"
            "UNWIND ks AS k\n"
            "RETURN l AS label, collect(DISTINCT k) AS keys\n"
            "ORDER BY label\n"
            "LIMIT $limit",
            {"limit": node_limit},
        )
        label_props: Dict[str, List[str]] = {}
        labels: List[str] = []
        for r in node_rows or []:
            l = r.get("label")
            ks = r.get("keys")
            if isinstance(l, str) and l:
                labels.append(l)
                if isinstance(ks, list):
                    label_props[l] = [str(x) for x in ks if str(x).strip()]
        out["labels"] = sorted(list(set(labels)))
        out["labelProperties"] = {k: sorted(list(set(v))) for k, v in label_props.items()}
    except Exception as exc:
        out["nodeScanError"] = str(exc)

    try:
        # Relationship types and per-type property keys.
        rel_rows = run_cypher(
            "MATCH ()-[r]->()\n"
            "WITH r LIMIT $limit\n"
            "WITH type(r) AS t, keys(r) AS ks\n"
            "UNWIND ks AS k\n"
            "RETURN t AS type, collect(DISTINCT k) AS keys\n"
            "ORDER BY type\n"
            "LIMIT $limit",
            {"limit": rel_limit},
        )
        rel_props: Dict[str, List[str]] = {}
        rel_types: List[str] = []
        for r in rel_rows or []:
            t = r.get("type")
            ks = r.get("keys")
            if isinstance(t, str) and t:
                rel_types.append(t)
                if isinstance(ks, list):
                    rel_props[t] = [str(x) for x in ks if str(x).strip()]
        out["relationshipTypes"] = sorted(list(set(rel_types)))
        out["relProperties"] = {k: sorted(list(set(v))) for k, v in rel_props.items()}
    except Exception as exc:
        out["relScanError"] = str(exc)

    try:
        # Sample triples (label)-[:TYPE]->(label) to help path guessing.
        triple_rows = run_cypher(
            "MATCH (a)-[r]->(b)\n"
            "WITH a, r, b LIMIT $limit\n"
            "UNWIND labels(a) AS aLabel\n"
            "UNWIND labels(b) AS bLabel\n"
            "RETURN aLabel AS aLabel, type(r) AS rt, bLabel AS bLabel, count(*) AS cnt\n"
            "ORDER BY cnt DESC\n"
            "LIMIT $limit",
            {"limit": min(rel_limit, 2000)},
        )
        out["sampleTriples"] = triple_rows[:200] if isinstance(triple_rows, list) else []
    except Exception as exc:
        out["tripleScanError"] = str(exc)

    _AGENT_SCHEMA_CACHE["ts"] = now
    _AGENT_SCHEMA_CACHE["value"] = out
    return out


_CYTHER_DENY_PATTERNS = [
    r"\bCALL\b",
    r"\bAPOC\b",
    r"\bCREATE\b",
    r"\bMERGE\b",
    r"\bSET\b",
    r"\bDELETE\b",
    r"\bDETACH\b",
    r"\bREMOVE\b",
    r"\bDROP\b",
    r"\bLOAD\s+CSV\b",
]


def _sanitize_readonly_cypher(cypher: str, params: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
    c = (cypher or "").strip()
    if not c:
        raise HTTPException(status_code=400, detail="empty cypher")

    # Reject multi-statement.
    if ";" in c:
        raise HTTPException(status_code=400, detail="cypher must not contain ';'")

    upper = c.upper()
    for pat in _CYTHER_DENY_PATTERNS:
        if re.search(pat, upper, flags=re.IGNORECASE):
            raise HTTPException(status_code=400, detail=f"cypher contains forbidden operation: {pat}")

    # Enforce LIMIT.
    if re.search(r"\bLIMIT\b", upper) is None:
        c = c + "\nLIMIT $limit"

    safe_params: Dict[str, Any] = params if isinstance(params, dict) else {}
    # Clamp limit.
    max_limit = 200
    try:
        max_limit = int(os.getenv("KBCHAT_AGENT_MAX_ROWS", "200"))
    except Exception:
        max_limit = 200
    lim = safe_params.get("limit")
    try:
        lim_i = int(lim) if lim is not None else max_limit
    except Exception:
        lim_i = max_limit
    safe_params["limit"] = max(1, min(lim_i, max_limit))
    return c, safe_params


def run_cypher_readonly(cypher: str, params: Dict[str, Any]) -> List[Dict[str, Any]]:
    c, p = _sanitize_readonly_cypher(cypher, params)
    return run_cypher(c, p)


def _list_material_codes(keyword: str = "", limit: int = 50) -> List[Dict[str, Any]]:
    kw = (keyword or "").strip()
    lim = max(1, min(int(limit or 50), 200))
    where = ""
    params: Dict[str, Any] = {"limit": lim}
    if kw:
        where = (
            "WHERE (toLower(coalesce(m.material_code,'')) CONTAINS toLower($kw) "
            "   OR toLower(coalesce(m.name,'')) CONTAINS toLower($kw) "
            "   OR toLower(coalesce(m.name_zh,'')) CONTAINS toLower($kw))"
        )
        params["kw"] = kw
    cypher = (
        "MATCH (m:Material) "
        f"{where} "
        "RETURN m{.*} AS material "
        "ORDER BY coalesce(m.material_code, m.name, m.name_zh) ASC "
        "LIMIT $limit"
    )
    return run_cypher(cypher, params)


def _list_products(keyword: str = "", limit: int = 50) -> List[Dict[str, Any]]:
    kw = (keyword or "").strip()
    lim = max(1, min(int(limit or 50), 200))
    where = ""
    params: Dict[str, Any] = {"limit": lim}
    if kw:
        where = (
            "WHERE (toLower(coalesce(p.product_id,'')) CONTAINS toLower($kw) "
            "   OR toLower(coalesce(p.name,'')) CONTAINS toLower($kw) "
            "   OR toLower(coalesce(p.display_name_en,'')) CONTAINS toLower($kw) "
            "   OR toLower(coalesce(p.display_name_zh,'')) CONTAINS toLower($kw))"
        )
        params["kw"] = kw
    cypher = (
        "MATCH (p:Product) "
        f"{where} "
        "RETURN p{.*} AS product "
        "ORDER BY coalesce(p.product_id, p.name, p.display_name_en, p.display_name_zh) ASC "
        "LIMIT $limit"
    )
    return run_cypher(cypher, params)


def _list_boms_for_material(material_code: str, limit: int = 50) -> List[Dict[str, Any]]:
    mc = (material_code or "").strip()
    if not mc:
        return []
    lim = max(1, min(int(limit or 50), 200))

    # Try to resolve a Material node, then expand to BOM within 1-2 hops.
    cypher = (
        "MATCH (m:Material) "
        "WHERE m.material_code = $mc OR m.name = $mc OR m.name_zh = $mc "
        "   OR toLower(coalesce(m.material_code,'')) CONTAINS toLower($mc) "
        "   OR toLower(coalesce(m.name,'')) CONTAINS toLower($mc) "
        "   OR toLower(coalesce(m.name_zh,'')) CONTAINS toLower($mc) "
        "WITH m "
        "OPTIONAL MATCH (m)-[r1]-(b1:BOM) "
        "OPTIONAL MATCH (m)-[r2]-(x)-[r3]-(b2:BOM) "
        "WITH m, collect(DISTINCT {rel:type(r1), bom:b1{.*}}) + collect(DISTINCT {rel:type(r3), bom:b2{.*}}) AS cands "
        "UNWIND cands AS c "
        "WITH m, c WHERE c.bom IS NOT NULL "
        "RETURN m{.*} AS material, c AS candidate "
        "LIMIT $limit"
    )
    rows = run_cypher(cypher, {"mc": mc, "limit": lim})
    if rows:
        return rows

    # Fallback: many datasets model BOM via Product rather than directly on Material.
    # Try: material-ish string matches Product fields, then expand to BOM within 1-2 hops.
    cypher_p = (
        "MATCH (p:Product) "
        "WHERE p.material_code = $mc OR p.materialCode = $mc OR p.code = $mc "
        "   OR p.product_id = $mc OR p.name = $mc "
        "   OR toLower(coalesce(p.material_code,'')) CONTAINS toLower($mc) "
        "   OR toLower(coalesce(p.materialCode,'')) CONTAINS toLower($mc) "
        "   OR toLower(coalesce(p.code,'')) CONTAINS toLower($mc) "
        "   OR toLower(coalesce(p.product_id,'')) CONTAINS toLower($mc) "
        "   OR toLower(coalesce(p.name,'')) CONTAINS toLower($mc) "
        "WITH p "
        "OPTIONAL MATCH (p)-[r1]-(b1:BOM) "
        "OPTIONAL MATCH (p)-[r2]-(x)-[r3]-(b2:BOM) "
        "WITH p, collect(DISTINCT {rel:type(r1), bom:b1{.*}}) + collect(DISTINCT {rel:type(r3), bom:b2{.*}}) AS cands "
        "UNWIND cands AS c "
        "WITH p, c WHERE c.bom IS NOT NULL "
        "RETURN p{.*} AS product, c AS candidate "
        "LIMIT $limit"
    )
    rows = run_cypher(cypher_p, {"mc": mc, "limit": lim})
    if rows:
        return rows

    # Fallback: if Material->BOM is not modeled, try direct BOM id/code contains.
    cypher2 = (
        "MATCH (b:BOM) "
        "WHERE toLower(coalesce(b.bom_id,'')) CONTAINS toLower($mc) "
        "   OR toLower(coalesce(b.bom_code,'')) CONTAINS toLower($mc) "
        "   OR toLower(coalesce(b.name,'')) CONTAINS toLower($mc) "
        "RETURN b{.*} AS bom "
        "LIMIT $limit"
    )
    return run_cypher(cypher2, {"mc": mc, "limit": lim})


def _list_accessories(keyword: str = "", limit: int = 20) -> List[Dict[str, Any]]:
    kw = (keyword or "").strip()
    lim = max(1, min(int(limit or 20), 200))
    where = ""
    params: Dict[str, Any] = {"limit": lim}
    if kw:
        where = "WHERE toLower(coalesce(a.name,'')) CONTAINS toLower($kw) OR toLower(coalesce(a.name_zh,'')) CONTAINS toLower($kw)"
        params["kw"] = kw
    cypher = (
        "MATCH (a:Accessory) "
        f"{where} "
        "RETURN a{.*} AS accessory "
        "ORDER BY coalesce(a.name, a.name_zh) ASC "
        "LIMIT $limit"
    )
    return run_cypher(cypher, params)


def _list_products_for_accessory(accessory_name: str, limit: int = 50) -> List[Dict[str, Any]]:
    an = (accessory_name or "").strip()
    if not an:
        return []
    lim = max(1, min(int(limit or 50), 200))

    # Expand within 1-2 hops between Accessory and Product.
    cypher = (
        "MATCH (a:Accessory) "
        "WHERE a.name = $an OR a.name_zh = $an "
        "   OR toLower(coalesce(a.name,'')) CONTAINS toLower($an) "
        "   OR toLower(coalesce(a.name_zh,'')) CONTAINS toLower($an) "
        "WITH a "
        "OPTIONAL MATCH (a)-[r1]-(p1:Product) "
        "OPTIONAL MATCH (a)-[r2]-(x)-[r3]-(p2:Product) "
        "WITH a, collect(DISTINCT {rel:type(r1), product:p1{.*}}) + collect(DISTINCT {rel:type(r3), product:p2{.*}}) AS cands "
        "UNWIND cands AS c "
        "WITH a, c WHERE c.product IS NOT NULL "
        "RETURN a{.*} AS accessory, c AS usage "
        "LIMIT $limit"
    )
    rows = run_cypher(cypher, {"an": an, "limit": lim})
    if rows:
        return rows

    # Fallback: many “配件” are embedded as ProductConfig properties, not as graph edges.
    # We scan config properties and match if ANY property value contains the accessory name.
    cypher2 = (
        "MATCH (p:Product)-[:HAS_CONFIG]->(c:ProductConfig) "
        "WHERE any(k IN keys(c) WHERE toLower(toString(c[k])) CONTAINS toLower($an)) "
        "RETURN p{.*} AS product, c{.*} AS config "
        "LIMIT $limit"
    )
    rows2 = run_cypher(cypher2, {"an": an, "limit": lim})
    if rows2:
        return rows2

    # Last-resort: search across Product fields (sometimes accessory name is part of product_id/name).
    cypher3 = (
        "MATCH (p:Product) "
        "WHERE toLower(coalesce(p.product_id,'')) CONTAINS toLower($an) "
        "   OR toLower(coalesce(p.name,'')) CONTAINS toLower($an) "
        "RETURN p{.*} AS product "
        "LIMIT $limit"
    )
    return run_cypher(cypher3, {"an": an, "limit": lim})


def _find_products_with_specsheet(limit: int = 50) -> List[Dict[str, Any]]:
    lim = max(1, min(int(limit or 50), 200))
    # Heuristic: look for Document/Dataset with role/type/name containing 'spec' or '规格'.
    cypher = (
        "MATCH (p:Product)-[:HAS_DOC|HAS_DATASET]->(d) "
        "WHERE toLower(coalesce(d.role,'')) CONTAINS 'spec' "
        "   OR toLower(coalesce(d.type,'')) CONTAINS 'spec' "
        "   OR toLower(coalesce(d.name,'')) CONTAINS 'spec' "
        "   OR coalesce(d.role,'') CONTAINS '规格' "
        "   OR coalesce(d.type,'') CONTAINS '规格' "
        "   OR coalesce(d.name,'') CONTAINS '规格' "
        "RETURN p{.*} AS product, d{.*} AS doc "
        "LIMIT $limit"
    )
    return run_cypher(cypher, {"limit": lim})


def _list_product_files(product_key: str, limit: int = 50) -> List[Dict[str, Any]]:
    pk = (product_key or "").strip()
    if not pk:
        return []
    lim = max(1, min(int(limit or 50), 200))
    cypher = (
        "MATCH (p:Product) "
        "WHERE p.product_id = $pk OR p.name = $pk OR toLower(coalesce(p.product_id,'')) CONTAINS toLower($pk) OR toLower(coalesce(p.name,'')) CONTAINS toLower($pk) "
        "WITH p "
        "OPTIONAL MATCH (p)-[:HAS_DOC|HAS_DATASET]->(d) "
        "OPTIONAL MATCH (d)-[:HAS_FILE|CONTAINS|HAS_CHUNK]->(f) "
        "WITH p, collect(DISTINCT d{.*}) AS docs, collect(DISTINCT f{.*}) AS files "
        "RETURN p{.*} AS product, docs AS docs, files AS files "
        "LIMIT $limit"
    )
    return run_cypher(cypher, {"pk": pk, "limit": lim})


def _agent_state_get(session_id: str) -> Dict[str, Any]:
    sid = (session_id or "").strip()
    if not sid:
        return {}
    return _AGENT_STATE.get(sid, {})


def _agent_state_set(session_id: str, patch: Dict[str, Any]) -> Dict[str, Any]:
    sid = (session_id or "").strip()
    if not sid:
        return {}
    st = _AGENT_STATE.setdefault(sid, {})
    if isinstance(patch, dict):
        for k, v in patch.items():
            st[k] = v
    return st


def _extract_reasoning_from_resp(resp: Any) -> str:
    """Extract reasoning content from provider response if present.

    DashScope(Qwen) compatible-mode may return reasoning_content in message/delta.
    We keep it best-effort.
    """
    try:
        msg = resp.get("choices", [{}])[0].get("message") or {}
        rc = msg.get("reasoning_content")
        if isinstance(rc, str) and rc.strip():
            return rc.strip()
    except Exception:
        pass
    return ""


def _auto_update_agent_state_from_tool(session_id: str, tool: str, tool_result: Any) -> None:
    if not session_id:
        return
    try:
        if tool in {"list_products", "list_material_codes", "list_accessories"} and isinstance(tool_result, list):
            _agent_state_set(session_id, {f"last_{tool}": tool_result[:50]})
        if tool == "list_boms_for_material" and isinstance(tool_result, list):
            _agent_state_set(session_id, {"last_bom_candidates": tool_result[:50]})
        if tool == "list_products_for_accessory" and isinstance(tool_result, list):
            _agent_state_set(session_id, {"last_products_for_accessory": tool_result[:50]})
    except Exception:
        return


def _extract_identifier_candidates(text: str) -> List[str]:
    t = (text or "").strip()
    if not t:
        return []
    # Capture tokens like Atlantic18 / OtrantoSM15_11AA... / 11AA... etc.
    toks = re.findall(r"[A-Za-z][A-Za-z0-9_]{3,}|\b\d[A-Za-z0-9_]{5,}\b", t)
    # De-dup while keeping order.
    seen = set()
    out: List[str] = []
    for x in toks:
        k = x.strip()
        if not k:
            continue
        if k.lower() in seen:
            continue
        seen.add(k.lower())
        out.append(k)
    return out[:3]


def _keyword_variants(keyword: str) -> List[str]:
    kw = (keyword or "").strip()
    if not kw:
        return []
    vars: List[str] = [kw]
    # Strip trailing digits: Atlantic18 -> Atlantic
    m = re.match(r"^([A-Za-z_]+?)(\d{1,3})$", kw)
    if m:
        base = (m.group(1) or "").strip("_")
        if base and base.lower() != kw.lower():
            vars.append(base)
    # Strip suffix after underscore: Foo_ABC -> Foo
    if "_" in kw:
        base2 = kw.split("_", 1)[0].strip()
        if base2 and base2.lower() != kw.lower():
            vars.append(base2)
    # De-dup keep order
    seen = set()
    out: List[str] = []
    for x in vars:
        k = x.strip()
        if not k:
            continue
        lk = k.lower()
        if lk in seen:
            continue
        seen.add(lk)
        out.append(k)
    return out[:3]


def _agent_prefetch_entity_hints(session_id: str, user_message: str) -> None:
    """Best-effort prefetch to reduce 'not found' hallucinations.

    If the user mentions an identifier-like token (e.g. Atlantic18), we pre-search
    Product/Material and cache candidates into state so the agent can ground next steps.
    """
    if not session_id:
        return
    st = _agent_state_get(session_id)
    if st.get("_prefetch_for") == user_message:
        return
    ids = _extract_identifier_candidates(user_message)
    if not ids:
        return

    # Keep it cheap, but try a few variants for better hit rate.
    kw = ids[0]
    variants = _keyword_variants(kw)

    prod: List[Dict[str, Any]] = []
    mats: List[Dict[str, Any]] = []
    for v in variants:
        if not prod:
            try:
                prod = _list_products(keyword=v, limit=20)
            except Exception:
                prod = []
        if not mats:
            try:
                mats = _list_material_codes(keyword=v, limit=20)
            except Exception:
                mats = []
        if prod and mats:
            break

    patch: Dict[str, Any] = {
        "_prefetch_for": user_message,
        "prefetch_keyword": kw,
        "prefetch_products": prod[:20] if isinstance(prod, list) else [],
        "prefetch_materials": mats[:20] if isinstance(mats, list) else [],
    }

    # If user explicitly asks BOM for this token, also prefetch BOM candidates.
    if re.search(r"\bBOM\b|版本|物料清单", user_message, flags=re.IGNORECASE):
        try:
            # Use the best variant first.
            boms: List[Dict[str, Any]] = []
            for v in variants:
                boms = _list_boms_for_material(material_code=v, limit=20)
                if boms:
                    break
        except Exception:
            boms = []
        patch["prefetch_boms"] = boms[:20] if isinstance(boms, list) else []

        # Also prime last_bom_candidates so ordinal reference like "第5个" works.
        if isinstance(boms, list) and boms:
            _agent_state_set(session_id, {"last_bom_candidates": boms[:50]})

    _agent_state_set(session_id, patch)


def agent_orchestrate(user_message: str, history: Optional[List[Dict[str, str]]], context: Optional[Dict[str, Any]], session_id: str) -> Dict[str, Any]:
    """LLM-led agent loop.

    The model can propose tool calls (including Cypher) and update state.
    We execute in a read-only sandbox and feed results back.
    """

    schema = probe_schema()
    schema_full = build_agent_schema_snapshot()

    # Prefetch entity hints to avoid answering "not found" without any lookup.
    _agent_prefetch_entity_hints(session_id=session_id, user_message=user_message)
    tool_defs = {
        "tools": [
            {
                "name": "run_cypher_readonly",
                "args": {"cypher": "string", "params": "object"},
                "desc": "Execute a read-only Cypher query. CALL/CREATE/MERGE/SET/DELETE are forbidden. LIMIT is enforced.",
            },
            {"name": "probe_schema", "args": {}, "desc": "Return current Neo4j schema snapshot."},
            {"name": "state_get", "args": {}, "desc": "Get current session state JSON."},
            {"name": "state_set", "args": {"patch": "object"}, "desc": "Merge patch into session state."},
            {"name": "list_products", "args": {"keyword": "string", "limit": "number"}, "desc": "List Product nodes (best-effort fuzzy match by common fields)."},
            {"name": "list_material_codes", "args": {"keyword": "string", "limit": "number"}, "desc": "List Material nodes and material_code candidates (best-effort fuzzy)."},
            {"name": "list_boms_for_material", "args": {"material_code": "string", "limit": "number"}, "desc": "Given a material code/name, list related BOM candidates (1-2 hops) or BOM containing matches."},
            {"name": "list_accessories", "args": {"keyword": "string", "limit": "number"}, "desc": "List Accessory nodes (if present)."},
            {"name": "list_products_for_accessory", "args": {"accessory_name": "string", "limit": "number"}, "desc": "Find products that use a given accessory (1-2 hops), with fallbacks."},
            {"name": "find_products_with_specsheet", "args": {"limit": "number"}, "desc": "Find products with specsheet-like documents/datasets (heuristic by role/type/name contains spec/规格)."},
            {"name": "list_product_files", "args": {"product_key": "string", "limit": "number"}, "desc": "List docs/files connected to a product (best-effort)."},
        ]
    }

    scratch: List[Dict[str, Any]] = []
    sys = (
        "你是知识库问答系统的Agent（规划+执行）。你需要自主决定是否调用工具，并基于工具结果回答。\n"
        "你必须严格输出JSON，不要输出其他文字。\n"
        "JSON格式只能是以下之一：\n"
        "1) {\"action\":\"tool_call\", \"tool_name\":string, \"args\":object}\n"
        "2) {\"action\":\"final_answer\", \"content\":string}\n"
        "3) {\"action\":\"clarify\", \"content\":string}\n"
        "规则：\n"
        "- 需要事实时优先工具查询，不要编造BOM号/配置项。\n"
        "- 对于‘某某是否存在/某某的BOM/某某的配置’这类问题：如果 STATE 里没有可用候选，必须先调用 list_products/list_material_codes/list_boms_for_material 做检索，再基于结果回答；不要在未检索的情况下直接说‘数据库不存在’。\n"
        "- 系统会提供 PREFETCH(JSON)（基于用户输入自动检索的候选产品/物料/BOM）。优先使用这些候选继续查询与回答，并把候选列表写入 state_set（例如 last_bom_candidates），以便支持用户的‘第N个/这个/它’指代。\n"
        "- 只能使用提供的工具列表。\n"
        "- 查询必须只读；禁止 CALL / CREATE / MERGE / SET / DELETE / APOC。\n"
        "- 若用户要求‘从候选里选一个’，请先把候选列表写入 state_set（例如 selected_product/selected_material/last_candidates），再继续查询细节。\n"
        "- 若工具查询结果为空，也要用 final_answer 解释‘数据库未找到证据’，并给出下一步可查询的方向；不要陷入重复 tool_call。\n"
        f"可用工具: {json.dumps(tool_defs, ensure_ascii=False)}\n"
        f"schema.probed(labels/relationshipTypes): {json.dumps({'labels': schema.get('labels', []), 'relationshipTypes': schema.get('relationshipTypes', [])}, ensure_ascii=False, default=str)}\n"
        f"schema.full(data_scanned): {json.dumps(schema_full, ensure_ascii=False, default=str)}\n"
    )

    base_msgs: List[Dict[str, str]] = [{"role": "system", "content": sys}]
    base_msgs += _messages_from_history(history)[-12:]
    base_msgs.append({"role": "user", "content": user_message})

    max_steps = _agent_max_tool_calls()
    for step in range(max_steps):
        st_now = _agent_state_get(session_id)
        step_msgs: List[Dict[str, str]] = list(base_msgs)
        step_msgs.append({
            "role": "system",
            "content": f"STATE(JSON): {json.dumps(st_now, ensure_ascii=False, default=str)}",
        })

        prefetch_obj = {
            "keyword": st_now.get("prefetch_keyword"),
            "products": st_now.get("prefetch_products") or [],
            "materials": st_now.get("prefetch_materials") or [],
            "boms": st_now.get("prefetch_boms") or [],
            "last_bom_candidates": st_now.get("last_bom_candidates") or [],
        }
        step_msgs.append({
            "role": "system",
            "content": f"PREFETCH(JSON): {json.dumps(prefetch_obj, ensure_ascii=False, default=str)}",
        })
        if scratch:
            step_msgs.append({
                "role": "system",
                "content": f"TOOL_TRACE(JSON): {json.dumps(scratch[-8:], ensure_ascii=False, default=str)}",
            })

        resp, raw, reasoning = _chat_json_with_optional_thinking(step_msgs)
        raw = (raw or "").strip()
        _print_llm_io(f"agent_step_{step}", step_msgs, raw)
        obj = extract_json_object(raw)
        if not isinstance(obj, dict):
            return {"type": "clarify", "content": "我需要你再描述清楚一点你的查询目标（比如物料编码/型号/BOM号）。"}

        action = (obj.get("action") or "").strip()
        if action == "final_answer":
            return {
                "type": "answer",
                "content": (obj.get("content") or "").strip(),
                "citations": [],
                "reasoning": reasoning or _extract_reasoning_from_resp(resp),
            }
        if action == "clarify":
            return {
                "type": "clarify",
                "content": (obj.get("content") or "").strip(),
                "citations": [],
                "reasoning": reasoning or _extract_reasoning_from_resp(resp),
            }

        if action != "tool_call":
            scratch.append({"error": "unknown_action", "raw": obj})
            continue

        tool = (obj.get("tool_name") or "").strip()
        args = obj.get("args") if isinstance(obj.get("args"), dict) else {}
        tool_result: Any = None
        tool_error: str = ""

        try:
            if tool == "probe_schema":
                tool_result = probe_schema()
            elif tool == "state_get":
                tool_result = _agent_state_get(session_id)
            elif tool == "state_set":
                patch = args.get("patch") if isinstance(args.get("patch"), dict) else {}
                tool_result = _agent_state_set(session_id, patch)
            elif tool == "run_cypher_readonly":
                cypher = args.get("cypher") or ""
                params = args.get("params") if isinstance(args.get("params"), dict) else {}
                tool_result = run_cypher_readonly(str(cypher), params)
            elif tool == "list_products":
                tool_result = _list_products(str(args.get("keyword") or ""), int(args.get("limit") or 50))
            elif tool == "list_material_codes":
                tool_result = _list_material_codes(str(args.get("keyword") or ""), int(args.get("limit") or 50))
            elif tool == "list_boms_for_material":
                tool_result = _list_boms_for_material(str(args.get("material_code") or ""), int(args.get("limit") or 50))
            elif tool == "list_accessories":
                tool_result = _list_accessories(str(args.get("keyword") or ""), int(args.get("limit") or 20))
            elif tool == "list_products_for_accessory":
                tool_result = _list_products_for_accessory(str(args.get("accessory_name") or ""), int(args.get("limit") or 50))
            elif tool == "find_products_with_specsheet":
                tool_result = _find_products_with_specsheet(int(args.get("limit") or 50))
            elif tool == "list_product_files":
                tool_result = _list_product_files(str(args.get("product_key") or ""), int(args.get("limit") or 50))
            else:
                tool_error = f"unknown tool: {tool}"
        except Exception as exc:
            tool_error = str(exc)
            tool_result = None

        scratch.append({
            "step": step,
            "tool": tool,
            "args": args,
            "error": tool_error,
            "result": tool_result if tool_error == "" else None,
        })

        if tool_error == "":
            _auto_update_agent_state_from_tool(session_id, tool, tool_result)

    return {
        "type": "clarify",
        "content": "我尝试多步查询仍未得到稳定结果。请你提供更具体的物料编码/型号/BOM号，或说明你想看的配置字段。",
        "citations": [],
        "reasoning": "",
    }


def smalltalk_reply(message: str) -> str:
    text = (message or "").strip().lower()
    if re.search(r"(bye|再见|拜拜)", text, flags=re.IGNORECASE):
        return "再见。如需查询产品资料/配置/配件，直接告诉我物料编码或产品型号。"
    if re.search(r"(谢谢|多谢|感谢|thx|thanks)", text, flags=re.IGNORECASE):
        return "不客气。你可以直接提产品相关问题，我会基于知识库资料回答。"
    if re.search(r"(在吗|有人吗)", text, flags=re.IGNORECASE):
        return "在的。请直接描述问题（最好带物料编码/产品型号）。"
    return "你好。请直接提产品相关问题（建议带物料编码/产品型号），我会基于知识库资料回答。"


def answer_smalltalk_llm(user_message: str, history: Optional[List[Dict[str, str]]]) -> str:
    sys = (
        "你是产品知识库问答助手。用户发来的内容可能是寒暄、确认、或承接上文的简短回复。\n"
        "要求：\n"
        "- 用中文自然回复，优先承接上一轮对话语境；\n"
        "- 不要输出固定模板句；\n"
        "- 如果用户是在确认（例如‘可以/好的’），请继续推进上一步你提出的选项或请求用户补充必要信息；\n"
        "- 输出纯文本，不要Markdown。\n"
    )
    msgs = [{"role": "system", "content": sys}]
    msgs += _messages_from_history(history)[-10:]
    msgs.append({"role": "user", "content": user_message})
    resp = chat_json(msgs)
    return (resp["choices"][0]["message"]["content"] or "").strip()


def stream_smalltalk_llm(user_message: str, history: Optional[List[Dict[str, str]]]) -> Iterator[Any]:
    sys = (
        "你是产品知识库问答助手。用户发来的内容可能是寒暄、确认、或承接上文的简短回复。\n"
        "请用中文自然回复，优先承接上一轮对话语境，继续推进对话。\n"
        "输出纯文本，不要Markdown。\n"
    )
    msgs = [{"role": "system", "content": sys}]
    msgs += _messages_from_history(history)[-10:]
    msgs.append({"role": "user", "content": user_message})
    return chat_stream(msgs)


def _messages_from_history(history: Optional[List[Dict[str, str]]]) -> List[Dict[str, str]]:
    if not history:
        return []
    cleaned: List[Dict[str, str]] = []
    for item in history:
        if not isinstance(item, dict):
            continue
        role = (item.get("role") or "").strip()
        content = (item.get("content") or "").strip()
        if role in {"user", "assistant", "system"} and content:
            cleaned.append({"role": role, "content": content})
    return cleaned


def _debug_llm_enabled() -> bool:
    v = (os.getenv("KBCHAT_DEBUG_LLM", "1") or "1").strip().lower()
    if v in {"0", "false", "no", "n", "off"}:
        return False
    return True


def _reflection_enabled() -> bool:
    v = (os.getenv("KBCHAT_ENABLE_REFLECTION", "1") or "1").strip().lower()
    if v in {"0", "false", "no", "n", "off"}:
        return False
    return True


def _print_llm_io(tag: str, messages: List[Dict[str, Any]], output_text: str) -> None:
    if not _debug_llm_enabled():
        return
    try:
        in_txt = json.dumps(messages, ensure_ascii=False, default=str)
    except Exception:
        in_txt = str(messages)
    out_txt = (output_text or "").strip()
    if len(out_txt) > 3000:
        out_txt = out_txt[:3000] + "..."
    print(f"[KBCHAT][LLM][{tag}][IN] {in_txt}")
    print(f"[KBCHAT][LLM][{tag}][OUT] {out_txt}")


def reflect_failure(user_message: str, stage: str, detail: str, history: Optional[List[Dict[str, str]]] = None) -> str:
    if not _reflection_enabled():
        return ""
    sys = (
        "你是一个知识库问答系统的调试反思助手。\n"
        "给定用户问题、当前阶段(stage)和失败细节(detail)，请输出：\n"
        "(1) 你认为最可能的根因（1-3条）；\n"
        "(2) 下一步最小可行的排查动作（1-5条，尽量可操作）；\n"
        "(3) 如果要改代码，你建议改哪里（点到函数/模块级别即可）。\n"
        "输出纯文本，不要Markdown。不要输出与问题无关的长篇解释。\n"
    )
    msgs = [{"role": "system", "content": sys}]
    msgs += _messages_from_history(history)[-10:]
    msgs.append({"role": "user", "content": f"用户问题: {user_message}\nstage: {stage}\ndetail: {detail}"})
    resp = chat_json(msgs)
    text = (resp["choices"][0]["message"]["content"] or "").strip()
    _print_llm_io("reflection", msgs, text)
    return text


def route_intent(user_message: str, history: Optional[List[Dict[str, str]]] = None, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """LLM router that decides which tool/path to take.

    Returns JSON-like dict with at least: {"action": str, "args": object}
    """

    schema = probe_schema()
    labels = schema.get("labels", [])
    rels = schema.get("relationshipTypes", [])
    ctx = context or {}
    sys = (
        "你是知识库问答系统的路由器。你要根据用户输入与对话历史，决定下一步应该调用什么工具。\n"
        "你只能输出JSON，不要输出其他文字。\n"
        "可选 action：\n"
        "- answer_smalltalk：寒暄/承接（例如你好/谢谢/在吗/好的/可以），只需要自然回复，不查库\n"
        "- list_products：用户想列出有哪些产品/型号\n"
        "- list_material_codes：用户想列出有哪些物料编码\n"
        "- list_boms_for_material：用户想查看某个物料编码下有哪些BOM/版本（需要 material_code）\n"
        "- general_query：其它知识库问题，走通用 Text2Cypher\n"
        "输出格式：{\"action\": string, \"args\": object}\n"
        "args 规则：\n"
        "- 对于 list_boms_for_material，args 必须包含 material_code\n"
        "- 对于 list_* 可以包含 limit（默认200）\n"
        "判断规则：\n"
        "- 若用户使用指代（这个/它/上面那个），必须结合对话历史中的实体（产品名/物料编码/BOM号）推断\n"
        "- 不要编造实体；如果历史里没有实体且需要实体，请选择 general_query（让下游澄清）\n"
        f"可用Neo4j labels(部分): {labels[:30]}\n"
        f"可用Neo4j relationshipTypes(部分): {rels[:30]}\n"
        f"context.moduleKey: {(ctx.get('moduleKey') or 'kbChat')}\n"
    )

    msgs = [{"role": "system", "content": sys}]
    msgs += _messages_from_history(history)[-12:]
    msgs.append({"role": "user", "content": user_message})

    resp = chat_json(msgs)
    raw = (resp["choices"][0]["message"]["content"] or "").strip()
    _print_llm_io("route_intent", msgs, raw)
    obj = extract_json_object(raw)
    if not isinstance(obj, dict):
        return {"action": "general_query", "args": {}}
    action = (obj.get("action") or "").strip()
    args = obj.get("args") if isinstance(obj.get("args"), dict) else {}
    if action not in {
        "answer_smalltalk",
        "list_products",
        "list_material_codes",
        "list_boms_for_material",
        "general_query",
    }:
        return {"action": "general_query", "args": {}}
    return {"action": action, "args": args}


def answer_bom_candidates(user_message: str, history: Optional[List[Dict[str, str]]], material_code: str, rows: List[Dict[str, Any]], total: Optional[int] = None) -> str:
    payload = {
        "material_code": material_code,
        "total": total,
        "candidates": rows[:10],
    }
    evidence = json.dumps(payload, ensure_ascii=False, default=str)
    sys = (
        "你是产品知识库问答助手。你会得到某个物料编码的BOM候选列表(JSON)。\n"
        "请用纯文本输出：\n"
        "1) 说明该物料编码下存在BOM（若total为空就说‘已展示部分’）；\n"
        "2) 列出10个候选BOM（编号/版本/关键字段，按你拿到的JSON展示）；\n"
        "3) 最后问用户：请回复序号(1-10)或直接粘贴BOM号，我将解释该BOM配置。\n"
        "不要使用Markdown语法。不要编造BOM号。\n"
    )
    msgs = [{"role": "system", "content": sys}]
    msgs += _messages_from_history(history)[-8:]
    msgs.append({"role": "user", "content": f"用户问题: {user_message}\n\nBOM候选(JSON): {evidence}"})
    resp = chat_json(msgs)
    return (resp["choices"][0]["message"]["content"] or "").strip()


def stream_bom_candidates(user_message: str, history: Optional[List[Dict[str, str]]], material_code: str, rows: List[Dict[str, Any]], total: Optional[int] = None) -> Iterator[Any]:
    payload = {
        "material_code": material_code,
        "total": total,
        "candidates": rows[:10],
    }
    evidence = json.dumps(payload, ensure_ascii=False, default=str)
    sys = (
        "你是产品知识库问答助手。你会得到某个物料编码的BOM候选列表(JSON)。\n"
        "请用纯文本列出10个候选BOM并引导用户选择序号或粘贴BOM号。\n"
        "不要使用Markdown语法。不要编造BOM号。\n"
    )
    msgs = [{"role": "system", "content": sys}]
    msgs += _messages_from_history(history)[-8:]
    msgs.append({"role": "user", "content": f"用户问题: {user_message}\n\nBOM候选(JSON): {evidence}"})
    return chat_stream(msgs)


def decide_clarify(user_message: str, history: Optional[List[Dict[str, str]]], context: Optional[Dict[str, Any]] = None) -> Tuple[bool, str]:
    schema = probe_schema()
    sys = (
        "你是一个知识库问答助手。你需要判断用户的问题是否缺少关键实体信息。\n"
        "若需要澄清，输出简短的澄清问题（1-3个，用换行分隔）。\n"
        "若不需要澄清，只输出 'NO_CLARIFY'.\n"
        "不要输出多余解释。\n"
        f"可用的Neo4j标签: {', '.join(schema.get('labels', [])[:30])}\n"
    )
    msgs = [{"role": "system", "content": sys}]
    msgs += _messages_from_history(history)[-6:]
    msgs.append({"role": "user", "content": user_message})

    resp = chat_json(msgs)
    content = (resp["choices"][0]["message"]["content"] or "").strip()
    _print_llm_io("decide_clarify", msgs, content)
    if content == "NO_CLARIFY":
        return False, ""
    return True, content


def generate_suggestions(context: Optional[Dict[str, Any]] = None) -> List[str]:
    ctx = context or {}
    module_key = (ctx.get("moduleKey") or "kbChat").strip()
    product_name = (ctx.get("productName") or "").strip()
    material_code = (ctx.get("materialCode") or "").strip()
    bom_id = (ctx.get("bomId") or "").strip()

    sys = (
        "你是一个产品知识库问答助手。你的任务是生成‘能引导用户正确使用本系统能力’的推荐问题。\n"
        "系统能力包括：\n"
        "- 浏览全库：列出有哪些产品/型号；\n"
        "- 浏览全库：列出有哪些物料编码（并说明如何用物料编码继续提问）；\n"
        "- BOM/配置：解释BOM编号结构、查询某BOM配置；\n"
        "- 文档资料：列出某产品资料并提供可点击链接（/api/files/..），或基于文档摘要(summary_zh)做总结。\n"
        "请严格生成4条推荐问题（中文），每条不超过35字，且必须覆盖以下4类各1条：\n"
        "A. 产品列表/有哪些产品\n"
        "B. 物料编码列表/有哪些物料编码\n"
        "C. BOM编号解释/如何看BOM配置\n"
        "D. 文档资料/摘要+链接\n"
        "如果提供了产品名/物料编码/BOM编号，请优先把它融入问题，使问题更具体。\n"
        "输出严格为JSON：{\"suggestions\": [..]}，不要输出其他内容。\n"
        f"模块: {module_key}\n"
        f"产品名: {product_name}\n"
        f"物料编码: {material_code}\n"
        f"BOM编号: {bom_id}\n"
    )

    resp = chat_json([
        {"role": "system", "content": sys},
        {"role": "user", "content": "生成推荐问题"},
    ])
    raw = (resp["choices"][0]["message"]["content"] or "").strip()
    _print_llm_io("generate_suggestions", [{"role": "system", "content": sys}, {"role": "user", "content": "生成推荐问题"}], raw)
    obj = extract_json_object(raw)
    if isinstance(obj, dict) and isinstance(obj.get("suggestions"), list):
        out = []
        for s in obj["suggestions"]:
            if isinstance(s, str) and s.strip():
                out.append(s.strip())
        if out:
            return out[:6]

    return []


def _cypher_prompt(schema: Dict[str, Any], user_message: str, history: Optional[List[Dict[str, str]]] = None) -> List[Dict[str, str]]:
    triples = schema.get("sampleTriples") or []
    triples_txt = "\n".join(
        [
            f"- ({t.get('aLabel','')})-[:{t.get('rt','')}]->({t.get('bLabel','')}) x{t.get('cnt',0)}"
            for t in triples[:30]
            if isinstance(t, dict)
        ]
    )

    templates = """
你可以参考以下常见查询模板（按需改写）：

【T1 产品配置】
MATCH (p:Product)-[:HAS_CONFIG]->(c:ProductConfig)
WHERE p.product_id = $product_id OR p.material_code = $material_code
RETURN p{.*} AS product, c{.*} AS config
LIMIT $limit

【T2 产品/配件关联】
MATCH (p:Product)-[:HAS_ACCESSORY]->(a:Accessory)
WHERE p.product_id = $product_id OR p.material_code = $material_code
RETURN p{.*} AS product, a{.*} AS accessory
ORDER BY coalesce(a.order, 9999) ASC
LIMIT $limit

【T3 产品资料入口（手册/规格/海报/说明书/文档集）】
MATCH (p:Product)-[:HAS_DOC|HAS_DATASET]->(d)
WHERE p.product_id = $product_id OR p.material_code = $material_code
RETURN p{.*} AS product, d{.*} AS doc
LIMIT $limit

【T4 文档内容/Chunk 检索（如果存在 Chunk）】
MATCH (p:Product)-[:HAS_DATASET|HAS_DOC]->(d)-[:CONTAINS|HAS_CHUNK]->(c:Chunk)
WHERE p.product_id = $product_id OR p.material_code = $material_code
  AND (c.text CONTAINS $keyword OR c.content CONTAINS $keyword)
RETURN d{.*} AS doc, c{.*} AS chunk
LIMIT $limit

【T5 物料编码 -> 产品】
MATCH (m:Material)-[:HAS_PRODUCT]->(p:Product)
WHERE m.material_code = $material_code
RETURN m{.*} AS material, p{.*} AS product
LIMIT $limit

【T6 图片】
MATCH (x)-[:HAS_IMAGE]->(img)
WHERE (x:Product AND (x.product_id = $product_id OR x.material_code = $material_code))
   OR (x:Material AND x.material_code = $material_code)
RETURN x{.*} AS owner, img{.*} AS image
LIMIT $limit

注意：
- 如果用户没给足实体，请用最稳妥的“模糊字段包含”策略（CONTAINS）或先返回可选项。
- 返回字段尽量用 map 投影：node{.*}，并命名为 product/accessory/doc/chunk 等，方便后续 citations 提取。
 - **必须使用 LIMIT $limit 参数**；如果用户问“全部/所有”，也不要不加限制，先返回前 N 条并在回答中提示用户缩小范围。
"""

    sys = (
        "你是Neo4j知识图谱查询助手。根据用户问题生成可执行的Cypher查询。\n"
        "要求：\n"
        "- 只输出JSON：{\"cypher\": string, \"params\": object}\n"
        "- params必须是object（可为空），只包含字符串/数字/布尔/null\n"
        "- Cypher请使用参数化：$paramName，不要直接拼用户输入\n"
        "- 查询必须包含 LIMIT $limit，并在 params 中提供 limit（默认200）\n"
        "- 如果用户使用了指代（例如‘这个/它/上面那个/挑一个’），必须结合对话历史推断实体；如果历史不足请返回可选项而不是猜测。\n"
        "- 如果用户要求‘挑一个BOM号/任选一个版本’，必须先查询数据库中真实存在的 bom_id/bom_code，再基于查到的结果继续。不要编造BOM号。\n"
        "- 优先使用 schema 中真实存在的 label / relationship / property\n"
        "- 查询结果尽量包含 path/name/title/summary/content/text/material_code/bom_id 等字段\n"
        f"schema.labels: {schema.get('labels', [])}\n"
        f"schema.relationshipTypes: {schema.get('relationshipTypes', [])}\n"
        f"schema.labelProperties(sampled): {schema.get('labelProperties', {})}\n"
        f"schema.sampleTriples(top):\n{triples_txt}\n"
        f"{templates}\n"
    )
    msgs = [{"role": "system", "content": sys}]
    msgs += _messages_from_history(history)[-10:]
    msgs.append({"role": "user", "content": user_message})
    return msgs


def generate_cypher(user_message: str, history: Optional[List[Dict[str, str]]] = None) -> Tuple[str, Dict[str, Any]]:
    schema = probe_schema()
    resp = chat_json(_cypher_prompt(schema=schema, user_message=user_message, history=history))
    raw = (resp["choices"][0]["message"]["content"] or "").strip()
    obj = extract_json_object(raw)
    if not isinstance(obj, dict):
        raise HTTPException(status_code=500, detail="Cypher生成失败")

    cypher = (obj.get("cypher") or "").strip()
    params = obj.get("params") if isinstance(obj.get("params"), dict) else {}
    if not cypher:
        raise HTTPException(status_code=500, detail="Cypher生成失败")

    if "limit" not in params:
        try:
            params["limit"] = int(os.getenv("KBCHAT_DEFAULT_LIMIT", "200"))
        except Exception:
            params["limit"] = 200

    return cypher, params


def repair_cypher(user_message: str, cypher: str, params: Dict[str, Any], error: str, history: Optional[List[Dict[str, str]]] = None) -> Tuple[str, Dict[str, Any]]:
    schema = probe_schema()
    sys = (
        "你是Neo4j Cypher 修复助手。给定用户问题、schema、原cypher、错误信息，请修复cypher。\n"
        "只输出JSON：{\"cypher\": string, \"params\": object}，不要输出其他内容。\n"
        "如果用户使用了指代（例如‘这个/它/上面那个/挑一个’），必须结合对话历史推断实体；不要猜测。\n"
        f"schema.labels: {schema.get('labels', [])}\n"
        f"schema.relationshipTypes: {schema.get('relationshipTypes', [])}\n"
    )
    msgs = [{"role": "system", "content": sys}]
    msgs += _messages_from_history(history)[-10:]
    msgs.append({
        "role": "user",
        "content": f"用户问题: {user_message}\n\n原Cypher: {cypher}\n\nparams: {json.dumps(params, ensure_ascii=False, default=str)}\n\n错误: {error}",
    })
    resp = chat_json(msgs)
    raw = (resp["choices"][0]["message"]["content"] or "").strip()
    obj = extract_json_object(raw)
    if not isinstance(obj, dict):
        return cypher, params

    new_cypher = (obj.get("cypher") or "").strip() or cypher
    new_params = obj.get("params") if isinstance(obj.get("params"), dict) else params
    return new_cypher, new_params


def run_cypher(cypher: str, params: Dict[str, Any]) -> List[Dict[str, Any]]:
    cfg = get_neo4j_config()
    driver = get_neo4j_driver(cfg)
    try:
        with driver.session() as session:
            timeout_s = int(os.getenv("KBCHAT_NEO4J_QUERY_TIMEOUT_SECONDS", 10))
            try:
                res = session.run(cypher, params, timeout=timeout_s)
            except TypeError:
                # Older neo4j driver versions may not support `timeout` kwarg.
                res = session.run(cypher, params)
            rows = []
            for r in res:
                rows.append(r.data())
            return rows
    finally:
        driver.close()


def build_citations(rows: List[Dict[str, Any]], limit: int = 6) -> List[Dict[str, str]]:
    out: List[Dict[str, str]] = []
    for row in rows[: max(limit, 1)]:
        title = ""
        snippet = ""
        path = ""
        node_id = ""

        for _k, v in row.items():
            if isinstance(v, dict):
                if not title and isinstance(v.get("name"), str):
                    title = v.get("name")
                if not title and isinstance(v.get("title"), str):
                    title = v.get("title")
                if not path and isinstance(v.get("path"), str):
                    path = v.get("path")
                if not snippet and isinstance(v.get("summary"), str):
                    snippet = v.get("summary")
                if not snippet and isinstance(v.get("content"), str):
                    snippet = v.get("content")
                if not node_id and ("id" in v or "node_id" in v):
                    node_id = str(v.get("id") or v.get("node_id") or "")

        if not title:
            title = "Neo4j Record"
        if snippet:
            snippet = snippet.strip().replace("\n", " ")
            if len(snippet) > 160:
                snippet = snippet[:160] + "..."

        public_path = _to_public_file_url(path)

        out.append({
            "title": title,
            "snippet": snippet,
            "path": public_path,
            "nodeId": node_id,
        })

    return out


def stream_answer(user_message: str, history: Optional[List[Dict[str, str]]], rows: List[Dict[str, Any]]) -> Iterator[Any]:
    evidence = json.dumps(rows[:8], ensure_ascii=False, default=str)
    sys = (
        "你是产品知识库问答助手。你必须仅基于提供的证据回答，若证据不足要明确说明知识库中未找到。\n"
        "回答使用中文，结构清晰，纯文本即可。\n"
        "不要使用任何Markdown语法（例如###标题、**加粗**、```代码块、|表格|、- 无序列表也不要用Markdown符号）。\n"
        "请用普通文本排版：用中文序号(1)(2)或'•'开头的条目，字段用'键: 值'形式，必要时用缩进。\n"
        "严禁猜测或编造：\n"
        "- 不要凭常识生成BOM号/版本号/配置项；\n"
        "- 如果用户要求‘挑一个BOM号解释配置’，但证据里没有任何BOM号或配置明细，请先说明需要查询到具体BOM号，提示用户提供BOM号/或让系统先列出若干可选BOM号。\n"
        "不要编造。\n"
    )

    msgs = [{"role": "system", "content": sys}]
    msgs += _messages_from_history(history)[-8:]
    msgs.append({"role": "user", "content": f"问题: {user_message}\n\n证据(JSON): {evidence}"})

    return chat_stream(msgs)


def answer_nonstream(user_message: str, history: Optional[List[Dict[str, str]]], rows: List[Dict[str, Any]]) -> str:
    evidence = json.dumps(rows[:8], ensure_ascii=False, default=str)
    sys = (
        "你是产品知识库问答助手。你必须仅基于提供的证据回答，若证据不足要明确说明知识库中未找到。\n"
        "回答使用中文，结构清晰，纯文本即可。\n"
        "不要使用任何Markdown语法（例如###标题、**加粗**、```代码块、|表格|、- 无序列表也不要用Markdown符号）。\n"
        "请用普通文本排版：用中文序号(1)(2)或'•'开头的条目，字段用'键: 值'形式，必要时用缩进。\n"
        "不要编造。\n"
    )

    msgs = [{"role": "system", "content": sys}]
    msgs += _messages_from_history(history)[-8:]
    msgs.append({"role": "user", "content": f"问题: {user_message}\n\n证据(JSON): {evidence}"})

    resp = chat_json(msgs)
    return (resp["choices"][0]["message"]["content"] or "").strip()


def answer_products_list(user_message: str, history: Optional[List[Dict[str, str]]], rows: List[Dict[str, Any]]) -> str:
    evidence = json.dumps(rows[:200], ensure_ascii=False, default=str)
    sys = (
        "你是产品知识库问答助手。你会得到一组产品记录(JSON)。\n"
        "请完成：\n"
        "1) 用自然中文回答用户问题；\n"
        "2) 给出总体规模（如果无法确定总数就说明是展示的数量）；\n"
        "3) 优先按产品类型归类概括，并列出若干示例；\n"
        "4) 最后给出1-2句引导问题（例如让用户输入关键词/物料编码/选择某类产品）。\n"
        "输出纯文本，不要输出JSON。\n"
        "不要使用任何Markdown语法（例如###标题、**加粗**、```代码块、|表格|）。\n"
    )
    msgs = [{"role": "system", "content": sys}]
    msgs += _messages_from_history(history)[-8:]
    msgs.append({"role": "user", "content": f"用户问题: {user_message}\n\n产品记录(JSON): {evidence}"})
    resp = chat_json(msgs)
    return (resp["choices"][0]["message"]["content"] or "").strip()


def stream_products_list(user_message: str, history: Optional[List[Dict[str, str]]], rows: List[Dict[str, Any]]) -> Iterator[Any]:
    evidence = json.dumps(rows[:200], ensure_ascii=False, default=str)
    sys = (
        "你是产品知识库问答助手。你会得到一组产品记录(JSON)。\n"
        "请用自然中文回答用户问题，并按产品类型归类概括、列示例，最后给出引导问题。\n"
        "输出纯文本。\n"
        "不要使用任何Markdown语法（例如###标题、**加粗**、```代码块、|表格|）。\n"
    )
    msgs = [{"role": "system", "content": sys}]
    msgs += _messages_from_history(history)[-8:]
    msgs.append({"role": "user", "content": f"用户问题: {user_message}\n\n产品记录(JSON): {evidence}"})
    return chat_stream(msgs)


def answer_material_codes_list(user_message: str, history: Optional[List[Dict[str, str]]], codes: List[str], total: Optional[int] = None) -> str:
    payload = {
        "total": total if isinstance(total, int) else len(codes),
        "codes": codes[:500],
    }
    evidence = json.dumps(payload, ensure_ascii=False, default=str)
    sys = (
        "你是产品知识库问答助手。你会得到物料编码列表(JSON)。\n"
        "请直接回答用户，并把物料编码尽量完整列出（如果超过500条，只列前500条并提示用户用关键词筛选）。\n"
        "输出纯文本。不要使用任何Markdown语法（例如###、**、```、|表格|）。\n"
        "排版要求：\n"
        "- 第一行给出总数；\n"
        "- 后续逐行输出物料编码，每行一个；\n"
        "- 最后给1句引导：用户可输入某个编码继续查询产品/BOM/资料。\n"
    )
    msgs = [{"role": "system", "content": sys}]
    msgs += _messages_from_history(history)[-6:]
    msgs.append({"role": "user", "content": f"用户问题: {user_message}\n\n物料编码列表(JSON): {evidence}"})
    resp = chat_json(msgs)
    return (resp["choices"][0]["message"]["content"] or "").strip()


def stream_material_codes_list(user_message: str, history: Optional[List[Dict[str, str]]], codes: List[str], total: Optional[int] = None) -> Iterator[Any]:
    payload = {
        "total": total if isinstance(total, int) else len(codes),
        "codes": codes[:500],
    }
    evidence = json.dumps(payload, ensure_ascii=False, default=str)
    sys = (
        "你是产品知识库问答助手。你会得到物料编码列表(JSON)。\n"
        "请用纯文本输出：先给总数，然后逐行列出物料编码（每行一个），最后给引导语。\n"
        "不要使用任何Markdown语法（例如###、**、```、|表格|）。\n"
    )
    msgs = [{"role": "system", "content": sys}]
    msgs += _messages_from_history(history)[-6:]
    msgs.append({"role": "user", "content": f"用户问题: {user_message}\n\n物料编码列表(JSON): {evidence}"})
    return chat_stream(msgs)

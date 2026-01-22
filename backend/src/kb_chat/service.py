import json
import os
import re
from typing import Any, Dict, Iterator, List, Optional, Tuple

from fastapi import HTTPException

from src.api_queries import get_neo4j_config
from src.neo4j_file_add_neo4j import get_neo4j_driver

from .llm_client import chat_json, chat_stream
from .neo4j_schema import probe_schema
from .utils import extract_json_object


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

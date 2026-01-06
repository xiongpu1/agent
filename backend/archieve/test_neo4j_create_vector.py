import os
import re
import sys
import json
import hashlib
import difflib
from datetime import datetime
from typing import Iterable, List, Tuple, Optional, Dict
from dataclasses import dataclass
import base64

from neo4j import GraphDatabase
from litellm import embedding, completion
def normalize_whitespace(text: str) -> str:
    text = re.sub(r"\r\n?", "\n", text)
    text = re.sub(r"\t", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()

# Local model configuration
try:
    from src.models_litellm import Ollama_MODEL  # chat model default
except Exception:
    Ollama_MODEL = "ollama/qwen3-vl:30b-a3b-instruct-bf16"  # reasonable default if not provided

# -------- Helpers --------

def read_text_file(path: str, max_bytes: int = 2_000_000) -> str:
    with open(path, 'rb') as f:
        data = f.read(max_bytes)
    try:
        return data.decode('utf-8', errors='ignore')
    except Exception:
        return data.decode('latin-1', errors='ignore')


# -------- Markdown & JSON parsing (text/tables/images) --------

@dataclass
class ParsedMD:
    text_only_md: str
    tables: List[Dict]
    images: List[Dict]


def parse_markdown_assets(md: str) -> ParsedMD:
    # Extract base64 images first
    img_pattern = re.compile(r"!\[(?P<alt>[^\]]*)\]\(data:image\/(?P<mime>[a-zA-Z0-9+.-]+);base64,(?P<data>[^)]+)\)", re.IGNORECASE)
    images: List[Dict] = []
    def img_repl(m):
        idx = len(images)
        alt = m.group('alt') or ''
        mime = m.group('mime').lower()
        data_b64 = m.group('data').strip()
        ext_map = {
            'png': 'png', 'jpeg': 'jpg', 'jpg': 'jpg', 'webp': 'webp', 'svg+xml': 'svg', 'gif': 'gif'
        }
        ext = ext_map.get(mime, mime.split('+')[0].split('.')[0])
        try:
            raw = base64.b64decode(data_b64, validate=False)
        except Exception:
            raw = b''
        images.append({
            'image_index': idx,
            'mime': mime,
            'ext': ext,
            'bytes': raw,
            'alt': alt,
        })
        return ''  # remove from text
    md_wo_images = img_pattern.sub(img_repl, md)

    # Split lines for table detection
    lines = md_wo_images.split('\n')
    tables: List[Dict] = []
    out_lines: List[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        # detect table header line: contains | and next line is separator like | --- |
        if '|' in line:
            j = i + 1
            if j < len(lines) and re.match(r"^\s*\|?\s*:?\-[-:\s|]*\|\s*$", lines[j]):
                # consume table block until a blank line or non-table pattern
                tbl_lines = [line, lines[j]]
                k = j + 1
                while k < len(lines) and ('|' in lines[k]) and not re.match(r"^\s*$", lines[k]):
                    tbl_lines.append(lines[k])
                    k += 1
                tbl_md = "\n".join(tbl_lines).strip()
                tables.append({'table_index': len(tables), 'table_markdown': tbl_md})
                i = k
                continue
        out_lines.append(line)
        i += 1

    text_only_md = normalize_whitespace("\n".join(out_lines))
    return ParsedMD(text_only_md=text_only_md, tables=tables, images=images)


# ---- JSON parsing to produce text, tables, and images ----

def _is_data_url(s: str) -> bool:
    return bool(re.match(r"^data:image/[a-zA-Z0-9+.-]+;base64,", s or ""))


def _decode_data_url(data_url: str) -> Dict:
    try:
        m = re.match(r"^data:image/([a-zA-Z0-9+.-]+);base64,(.*)$", data_url)
        if not m:
            return {}
        mime = m.group(1).lower()
        data_b64 = m.group(2)
        raw = base64.b64decode(data_b64, validate=False)
        ext_map = {'png':'png','jpeg':'jpg','jpg':'jpg','webp':'webp','svg+xml':'svg','gif':'gif'}
        ext = ext_map.get(mime, mime.split('+')[0].split('.')[0])
        return {'mime': mime, 'bytes': raw, 'ext': ext}
    except Exception:
        return {}


def _render_table_markdown(rows: List[Dict]) -> Optional[str]:
    if not rows or not isinstance(rows, list):
        return None
    # ensure rows are dict-like
    if not all(isinstance(r, dict) for r in rows):
        return None
    # collect columns
    cols = []
    seen = set()
    for r in rows:
        for k in r.keys():
            if k not in seen:
                seen.add(k)
                cols.append(k)
    if not cols:
        return None
    # header
    header = "|" + "|".join(cols) + "|"
    sep = "|" + "|".join(["---"] * len(cols)) + "|"
    body_lines = []
    for r in rows:
        vals = [str(r.get(c, "")) for c in cols]
        body_lines.append("|" + "|".join(vals) + "|")
    return "\n".join([header, sep] + body_lines)


def parse_json_assets(obj: Dict) -> ParsedMD:
    tables: List[Dict] = []
    images: List[Dict] = []
    out_lines: List[str] = []

    def walk(node, path: List[str]):
        nonlocal tables, images, out_lines
        # Detect arrays of dicts as tables
        if isinstance(node, list):
            if node and all(isinstance(x, dict) for x in node):
                tbl_md = _render_table_markdown(node)
                if tbl_md:
                    tables.append({'table_index': len(tables), 'table_markdown': tbl_md})
                return
            else:
                # traverse list elements
                for idx, item in enumerate(node):
                    walk(item, path + [str(idx)])
                return
        if isinstance(node, dict):
            for k, v in node.items():
                key = str(k)
                # image detection by common field names and data URLs
                if isinstance(v, str) and _is_data_url(v):
                    meta = _decode_data_url(v)
                    if meta:
                        images.append({
                            'image_index': len(images),
                            'mime': meta['mime'],
                            'ext': meta['ext'],
                            'bytes': meta['bytes'],
                            'alt': "/".join(path + [key])
                        })
                        continue
                # scalar text
                if isinstance(v, (str, int, float, bool)) and not isinstance(v, bytes):
                    text = str(v)
                    if text.strip():
                        heading = "# " + "/".join(path + [key])
                        out_lines.append(heading)
                        out_lines.append("")
                        out_lines.append(text)
                        out_lines.append("")
                    continue
                # recurse
                walk(v, path + [key])
            return
        # other scalar at root/list elements
        if isinstance(node, (str, int, float, bool)):
            text = str(node)
            if text.strip():
                out_lines.append(text)

    walk(obj, [])
    text_only_md = normalize_whitespace("\n".join(out_lines))
    return ParsedMD(text_only_md=text_only_md, tables=tables, images=images)


# -------- Summarizers --------

def _completion_messages(model: str, messages: List[Dict], api_base: Optional[str] = None, temperature: float = 0):
    kwargs = {"model": model, "messages": messages, "temperature": temperature}
    if api_base and model.startswith("ollama/"):
        kwargs["api_base"] = api_base
    return completion(**kwargs)


def summarize_text_index(text_md: str, model: str, api_base: Optional[str]) -> str:
    system = "你是技术文档的索引生成器。请以不超过 30 个中文字，总结该文档的关键信息，输出单句，不要标点后的解释。"
    user = text_md[:3000]
    resp = _completion_messages(model, [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ], api_base, temperature=0)
    return (resp["choices"][0]["message"]["content"].strip() if resp else "").splitlines()[0][:60]


def summarize_table(table_md: str, model: str, api_base: Optional[str]) -> str:
    system = (
        "你是一个专业的技术文档分析助手。\n"
        "请用要点形式完整概括下表的关键信息：指标/维度、范围、异常、对比与结论。\n"
        "最多 16 行，每行不超过 120 字。"
    )
    user = f"表格内容如下（markdown）：\n\n{table_md}"
    resp = _completion_messages(model, [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ], api_base, temperature=0)
    return resp["choices"][0]["message"]["content"].strip()


def summarize_image_vlm(image_bytes: bytes, mime: str, alt: str, model: str, api_base: Optional[str]) -> str:
    if not image_bytes:
        # fallback to alt text
        return f"图片：{alt or '无描述'}"
    data_url = f"data:image/{mime};base64,{base64.b64encode(image_bytes).decode('utf-8')}"
    messages = [
        {"role": "system", "content": "你是一个视觉分析助手，请简洁总结图片内容（中文，<= 100 字）。"},
        {"role": "user", "content": [
            {"type": "text", "text": f"请总结这张图片的关键内容。若有 ALT：{alt}"},
            {"type": "image_url", "image_url": {"url": data_url}},
        ]},
    ]
    # Some backends may not support multimodal; catch and fallback
    try:
        resp = _completion_messages(model, messages, api_base, temperature=0)
        return resp["choices"][0]["message"]["content"].strip()
    except Exception:
        # fallback textual prompt
        return f"图片（基于 ALT 估计）：{alt or '未提供'}"


def progress_bar(current: int, total: int, prefix: str = "", width: int = 30) -> None:
    """Lightweight progress bar printed on a single line.
    Only for TTY stdout; otherwise, prints nothing to avoid cluttering logs.
    """
    if total <= 0:
        return
    if not sys.stdout.isatty():
        # non-interactive environment: skip dynamic bar
        return
    current = max(0, min(current, total))
    ratio = current / total
    filled = int(width * ratio)
    bar = "█" * filled + "-" * (width - filled)
    end = "\n" if current >= total else "\r"
    print(f"{prefix} [{bar}] {current}/{total} ({ratio*100:.1f}%)", end=end, flush=True)


def md_chunker(md: str, max_chars: int = 3000, overlap: int = 300) -> List[str]:
    """Simple markdown chunker: split on headings/paragraphs, accumulate up to max_chars with overlap."""
    lines = md.split('\n')
    blocks: List[str] = []
    buf: List[str] = []
    size = 0

    def flush():
        nonlocal buf, size
        if buf:
            block = '\n'.join(buf).strip()
            if block:
                blocks.append(block)
        buf = []
        size = 0

    for ln in lines:
        # Start new block on ATX heading or long horizontal rule
        if re.match(r"^\s*#{1,6}\s+", ln) or re.match(r"^\s*(-{3,}|\*{3,}|_{3,})\s*$", ln):
            # force flush before heading if current buffer sizable
            if size > max_chars * 0.6:
                flush()
        buf.append(ln)
        size += len(ln) + 1
        if size >= max_chars:
            flush()
            # add overlap from previous block
            if blocks:
                tail = blocks[-1][-overlap:]
                if tail:
                    buf = [tail]
                    size = len(tail)
    flush()
    # Further split extremely long blocks by sentence if needed
    out: List[str] = []
    for b in blocks:
        if len(b) <= max_chars:
            out.append(b)
        else:
            # naive sentence split
            parts = re.split(r"(?<=[。！？.!?])\s+", b)
            cur = ''
            for p in parts:
                if len(cur) + len(p) + 1 <= max_chars:
                    cur = (cur + ' ' + p).strip()
                else:
                    if cur:
                        out.append(cur)
                    cur = p
            if cur:
                out.append(cur)
    return out


def stable_chunk_id(file_path: str, chunk_index: int, text: str) -> str:
    h = hashlib.sha256()
    h.update(file_path.encode('utf-8'))
    h.update(b'\x00')
    h.update(str(chunk_index).encode('utf-8'))
    h.update(b'\x00')
    # include a small digest of text to reflect content differences
    h.update(hashlib.sha1(text.encode('utf-8')).digest())
    return h.hexdigest()


# -------- Neo4j --------

def get_neo4j_driver(uri: str, user: str, password: str):
    return GraphDatabase.driver(uri, auth=(user, password))


def ensure_constraints(session) -> None:
    # Ensure Chunk.id unique and new nodes unique by path
    session.run("""
    CREATE CONSTRAINT chunk_id IF NOT EXISTS
    FOR (c:Chunk) REQUIRE c.id IS UNIQUE
    """)
    session.run("""
    CREATE CONSTRAINT document_path IF NOT EXISTS
    FOR (d:Document) REQUIRE d.path IS UNIQUE
    """)
    session.run("""
    CREATE CONSTRAINT table_path IF NOT EXISTS
    FOR (t:Table) REQUIRE t.table_path IS UNIQUE
    """)
    session.run("""
    CREATE CONSTRAINT image_path IF NOT EXISTS
    FOR (i:Image) REQUIRE i.image_path IS UNIQUE
    """)


def load_all_node_names(session) -> Tuple[List[str], List[str]]:
    # Return product names and accessory names
    res_p = session.run("MATCH (p:Product) RETURN p.name AS name")
    products = [r["name"] for r in res_p]
    res_a = session.run("MATCH (a:Accessory) RETURN a.name AS name")
    accessories = [r["name"] for r in res_a]
    return products, accessories


def is_document_ingested(session, document_path: str) -> bool:
    """Return True if this document already has any chunk ingested.
    We purposely check for chunks to avoid skipping half-done documents that only have metadata.
    """
    rec = session.run(
        """
        MATCH (d:Document {path:$path})-[:HAS_CONTENT]->(:Chunk)
        RETURN count(*) > 0 AS ingested
        """,
        {"path": document_path},
    ).single()
    return bool(rec and rec["ingested"]) 


essential_skip_note = (
    "已存在内容分块，跳过重建（断点续传）"
)


def mark_content_ingested(session, content_id: str) -> None:
    now = datetime.utcnow().isoformat()
    session.run(
        """
        MERGE (c:Content {id:$id})
        SET c.ingested=true, c.ingested_at=datetime($now)
        """,
        {"id": content_id, "now": now},
    )


def resolve_node(
    filepath: str,
    content: str,
    products: List[str],
    accessories: List[str],
    chat_model: str,
    ollama_base: Optional[str],
) -> Optional[Tuple[str, str]]:
    """
    使用大模型直接匹配归属节点。
    """
    filename = os.path.basename(filepath)

    # 增加内容长度以获得更好的理解
    snippet = content[:8000]

    # 将候选名称列表提供给 LLM
    products_list = "\n".join([f"  - {p}" for p in products[:50]])  # 限制数量避免提示过长
    accessories_list = "\n".join([f"  - {a}" for a in accessories[:50]])

    system_prompt = (
        "你是一个严格的文档分类助手。\n"
        "任务：根据给定的文件名与内容片段，判断该文档最可能归属于哪一个产品(Product)或配件(Accessory)。\n"
        "要求：\n"
        "1) 你必须从下面提供的候选名称列表中选择一个，不能自己创造新名称。\n"
        "2) 只能选择 Product 或 Accessory 其中一类。\n"
        "3) 如果不够确定或找不到匹配的，请输出 UNKNOWN。\n"
        "4) 仅输出 JSON 格式：{\"label\": \"Product|Accessory|UNKNOWN\", \"name\": \"精确名称\"}。\n"
        "5) 不要输出解释或多余文本。\n\n"
        f"可选的 Product 名称列表：\n{products_list}\n\n"
        f"可选的 Accessory 名称列表：\n{accessories_list}"
    )

    user_prompt = (
        f"文件名: {filename}\n\n"
        f"内容片段:\n{snippet}\n\n"
        "请从上述候选列表中选择最匹配的节点，仅输出 JSON。"
    )

    kwargs = {
        "model": chat_model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0,
    }
    if ollama_base and chat_model.startswith("ollama/"):
        kwargs["api_base"] = ollama_base

    try:
        resp = completion(**kwargs)
        text = resp["choices"][0]["message"]["content"].strip()
        # 解析 JSON
        try:
            data = json.loads(text)
        except Exception:
            m = re.search(r"\{[\s\S]*\}", text)
            if not m:
                return None
            data = json.loads(m.group(0))

        label = data.get("label")
        name = data.get("name")
        if not isinstance(name, str):
            return None

        # 验证名称是否在候选列表中
        if label == "Product" and name in products:
            return ("Product", name)
        if label == "Accessory" and name in accessories:
            return ("Accessory", name)

        return None
    except Exception as e:
        print(f"    LLM resolve error: {e}")
        return None


def is_progress_enabled() -> bool:
    val = os.getenv("PROGRESS", "1").strip().lower()
    return val not in ("0", "false", "no")


def env_bool(name: str, default: bool = False) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    val = val.strip().lower()
    return val in ("1", "true", "yes", "y", "on")


# -------- Embeddings --------

def embed_texts(texts: List[str], model: str, ollama_base: Optional[str]) -> List[List[float]]:
    res: List[List[float]] = []
    total = len(texts)
    for idx, t in enumerate(texts, start=1):
        kwargs = {"model": model, "input": t}
        if ollama_base and model.startswith("ollama/"):
            kwargs["api_base"] = ollama_base
        er = embedding(**kwargs)
        vec = er["data"][0]["embedding"]
        res.append(vec)
        if is_progress_enabled():
            progress_bar(idx, total, prefix=f"Embedding ({model})")
    return res


# -------- Upsert to Neo4j --------

def _content_id_from_doc_path(path: str) -> str:
    h = hashlib.sha256()
    h.update(b"content:")
    h.update(path.encode("utf-8"))
    return h.hexdigest()


def get_owner_dir_name(session, owner_label: str, owner_name: str) -> str:
    # product -> product_identifier; accessory -> accessory_name; fallback to name
    if owner_label == "Product":
        rec = session.run("""
            MATCH (p:Product {name:$name}) RETURN coalesce(p.product_identifier, p.name) AS d
        """, {"name": owner_name}).single()
        return rec["d"] if rec and rec["d"] else owner_name
    else:
        rec = session.run("""
            MATCH (a:Accessory {name:$name}) RETURN coalesce(a.accessory_name, a.name) AS d
        """, {"name": owner_name}).single()
        return rec["d"] if rec and rec["d"] else owner_name


def ensure_document_and_content(session,
                                owner_label: str,
                                owner_name: str,
                                document_path: str,
                                document_name: str,
                                document_index: Optional[str],
                                text_saved: bool,
                                text_path: Optional[str]) -> str:
    content_id = _content_id_from_doc_path(document_path)
    now = datetime.utcnow().isoformat()
    session.run(
        (
            """
            MATCH (o:%s {name:$owner_name})
            MERGE (d:Document {path:$document_path})
            ON CREATE SET d.name=$document_name, d.document_index=$document_index, d.created_at=datetime($now)
            ON MATCH SET  d.document_index=coalesce($document_index, d.document_index), d.updated_at=datetime($now)
            MERGE (o)-[:HAS_DOCUMENT]->(d)
            MERGE (c:Content {id:$content_id})
            ON CREATE SET c.created_at=datetime($now)
            ON MATCH SET c.updated_at=datetime($now)
            MERGE (d)-[:HAS_CONTENT]->(c)
            SET c.text_saved=$text_saved, c.text_path=$text_path
            """
            % owner_label
        ),
        {
            "owner_name": owner_name,
            "document_path": document_path,
            "document_name": document_name,
            "document_index": document_index,
            "now": now,
            "content_id": content_id,
            "text_saved": bool(text_saved),
            "text_path": text_path,
        },
    )
    return content_id

def upsert_chunks(
    session,
    owner_label: str,
    owner_name: str,
    file_path: str,
    chunks: List[str],
    vectors: List[List[float]],
    embedding_model: str,
    kind: str = "text",
    document_path: Optional[str] = None,
    content_id: Optional[str] = None,
) -> Tuple[int, int]:
    created_nodes = 0
    created_rels = 0

    total = len(chunks)
    for idx, (text, vec) in enumerate(zip(chunks, vectors)):
        cid = stable_chunk_id(file_path, idx, text)
        params = {
            "id": cid,
            "text": text,
            "file_path": file_path,
            "index": idx,
            "embedding": vec,
            "embedding_model": embedding_model,
            "created_at": datetime.utcnow().isoformat(),
            "owner_name": owner_name,
            "kind": kind,
            "document_path": document_path,
        }
        cypher = (
            """
            MERGE (c:Chunk {id: $id})
            ON CREATE SET c.text = $text, c.file_path = $file_path, c.index = $index,
                          c.embedding = $embedding, c.embedding_model = $embedding_model,
                          c.kind=$kind,
                          c.created_at = datetime($created_at)
            ON MATCH SET  c.text = $text, c.file_path = $file_path, c.index = $index,
                          c.embedding = $embedding, c.embedding_model = $embedding_model,
                          c.kind=$kind,
                          c.updated_at = datetime($created_at)
            WITH c
            MATCH (o:%s {name: $owner_name})
            MERGE (o)-[:HAS_CONTENT]->(c)
            """
            % owner_label
        )
        if document_path:
            cypher += "\nMERGE (d:Document {path:$document_path}) WITH c,d MERGE (d)-[:HAS_CONTENT]->(c)"
        if content_id:
            cypher += "\nMERGE (cs:Content {id:$content_id}) WITH c,cs MERGE (cs)-[:HAS_CHUNK]->(c)"
        cypher += "\nRETURN c"
        result = session.run(cypher, params)
        summary = result.consume()
        stats = summary.counters
        if stats.nodes_created > 0:
            created_nodes += stats.nodes_created
        if stats.relationships_created > 0:
            created_rels += stats.relationships_created
        if is_progress_enabled():
            progress_bar(idx + 1, total, prefix=f"Upsert {os.path.basename(file_path)}")

    return created_nodes, created_rels


# -------- Asset upserts for Table and Image --------

def upsert_table_node(session, content_id: str, table_index: int, table_path: str, summary: str,
                      summary_vec: List[float], summary_model: str) -> None:
    now = datetime.utcnow().isoformat()
    session.run(
        """
        MERGE (t:Table {table_path:$table_path})
        ON CREATE SET t.index=$index, t.created_at=datetime($now)
        ON MATCH SET  t.index=$index, t.updated_at=datetime($now)
        SET t.summary=$summary, t.summary_embedding=$summary_embedding, t.summary_model=$summary_model
        WITH t
        MERGE (c:Content {id:$content_id})
        MERGE (c)-[:HAS_TABLE]->(t)
        """,
        {
            "table_path": table_path,
            "index": table_index,
            "now": now,
            "summary": summary,
            "summary_embedding": summary_vec,
            "summary_model": summary_model,
            "content_id": content_id,
        }
    )


def upsert_image_node(session, content_id: str, image_index: int, image_path: str, mime: str, alt: str,
                      summary: str, summary_vec: List[float], summary_model: str) -> None:
    now = datetime.utcnow().isoformat()
    session.run(
        """
        MERGE (i:Image {image_path:$image_path})
        ON CREATE SET i.index=$index, i.mime=$mime, i.alt=$alt, i.created_at=datetime($now)
        ON MATCH SET  i.index=$index, i.mime=$mime, i.alt=$alt, i.updated_at=datetime($now)
        SET i.summary=$summary, i.summary_embedding=$summary_embedding, i.summary_model=$summary_model
        WITH i
        MERGE (c:Content {id:$content_id})
        MERGE (c)-[:HAS_IMAGE]->(i)
        """,
        {
            "image_path": image_path,
            "index": image_index,
            "mime": mime,
            "alt": alt,
            "now": now,
            "summary": summary,
            "summary_embedding": summary_vec,
            "summary_model": summary_model,
            "content_id": content_id,
        }
    )


# -------- Main pipeline --------

from src.io_manager import ensure_owner_artifact_dirs, save_table_markdown, save_base64_image, save_text_markdown

def ingest(
    root_dir: str,
    neo4j_uri: str,
    neo4j_user: str,
    neo4j_password: str,
    ollama_base: Optional[str],
    classifier_model: str,
    embedding_model: str,
    text_index_model: Optional[str] = None,
    table_summary_model: Optional[str] = None,
    vision_model: Optional[str] = None,
    classifier_api_base: Optional[str] = None,
    text_index_api_base: Optional[str] = None,
    table_summary_api_base: Optional[str] = None,
    vision_api_base: Optional[str] = None,
    artifacts_root: Optional[str] = None,
    limit_files: Optional[int] = None,
    dry_run: bool = False,
    resume: bool = True,
    force_reingest: bool = False,
) -> None:
    driver = get_neo4j_driver(neo4j_uri, neo4j_user, neo4j_password)
    processed = 0
    total_chunks = 0
    total_new = 0
    total_rels = 0

    try:
        if not artifacts_root:
            artifacts_root_resolved = os.path.abspath(os.path.join(os.getcwd(), "data_storage"))
        else:
            artifacts_root_resolved = os.path.abspath(artifacts_root)
        os.makedirs(artifacts_root_resolved, exist_ok=True)
        with driver.session() as session:
            ensure_constraints(session)
            products, accessories = load_all_node_names(session)
            print(f"Loaded {len(products)} products, {len(accessories)} accessories from Neo4j")

            src_files: List[str] = []
            for base, _, files in os.walk(root_dir):
                for f in files:
                    fl = f.lower()
                    if fl.endswith('.md') or fl.endswith('.json'):
                        src_files.append(os.path.join(base, f))
            src_files.sort()
            if limit_files is not None:
                src_files = src_files[:limit_files]
            print(f"Found {len(src_files)} source files (.md, .json) under {root_dir}")

            total_files = len(src_files)
            if is_progress_enabled() and total_files:
                progress_bar(0, total_files, prefix="Files")

            for i, path in enumerate(src_files, start=1):
                try:
                    # Resume support: skip files that already have chunks in Neo4j
                    if not dry_run and resume and not force_reingest and is_document_ingested(session, path):
                        print(f"[{i}/{total_files}] Skip (resume): {path} | {essential_skip_note}")
                        if is_progress_enabled():
                            progress_bar(i, total_files, prefix="Files")
                        continue

                    raw = read_text_file(path)
                    ext = os.path.splitext(path)[1].lower()
                    parsed: ParsedMD
                    if ext == '.json':
                        try:
                            obj = json.loads(raw)
                        except Exception as je:
                            print(f"[{i}/{total_files}] Invalid JSON, skip: {path} | {je}")
                            if is_progress_enabled():
                                progress_bar(i, total_files, prefix="Files")
                            continue
                        parsed = parse_json_assets(obj)
                    else:
                        parsed = parse_markdown_assets(raw)
                    cleaned = normalize_whitespace(parsed.text_only_md)
                    if not cleaned or len(cleaned) < 20:
                        print(f"[{i}/{total_files}] Skip (empty/short): {path}")
                        if is_progress_enabled():
                            progress_bar(i, total_files, prefix="Files")
                        continue

                    resolved = resolve_node(path, cleaned, products, accessories, classifier_model, classifier_api_base or ollama_base)
                    if not resolved:
                        print(f"[{i}/{total_files}] Unresolved node for file: {path}")
                        if is_progress_enabled():
                            progress_bar(i, total_files, prefix="Files")
                        continue
                    owner_label, owner_name = resolved

                    owner_dir_name = get_owner_dir_name(session, owner_label, owner_name)
                    dirs = ensure_owner_artifact_dirs(artifacts_root_resolved, owner_dir_name)
                    base_name = os.path.splitext(os.path.basename(path))[0]

                    # Save text markdown
                    text_path = save_text_markdown(dirs["text_dir"], base_name, cleaned)

                    # Prepare index sentence placeholder
                    table_summaries: List[str] = []
                    image_summaries: List[str] = []

                    # Summarize tables and save original table markdown
                    table_vecs: List[List[float]] = []
                    for t in parsed.tables:
                        t_md = t["table_markdown"]
                        t_path = save_table_markdown(dirs["table_dir"], base_name, t["table_index"], t_md)
                        if not dry_run and table_summary_model:
                            t_sum = summarize_table(t_md, table_summary_model, table_summary_api_base or ollama_base)
                        else:
                            t_sum = f"表格摘要（占位）: {os.path.basename(t_path)}"
                        table_summaries.append(t_sum)
                        # embed table summary
                        vec = embed_texts([t_sum], embedding_model, ollama_base)[0]
                        table_vecs.append(vec)

                    # Save and summarize images
                    image_meta = []
                    for img in parsed.images:
                        img_path = save_base64_image(dirs["image_dir"], base_name, img["image_index"], img["ext"], img["bytes"]) 
                        if not dry_run and vision_model:
                            img_sum = summarize_image_vlm(img["bytes"], img["mime"], img.get("alt", ""), vision_model, vision_api_base or ollama_base)
                        else:
                            img_sum = f"图片摘要（占位）: {os.path.basename(img_path)}"
                        image_summaries.append(img_sum)
                        image_meta.append((img_path, img["mime"], img.get("alt", "")))
                    image_vecs = [embed_texts([s], embedding_model, ollama_base)[0] for s in image_summaries]

                    # Chunk text
                    chunks = md_chunker(cleaned)
                    if not chunks:
                        print(f"[{i}/{total_files}] No chunks produced: {path}")
                        if is_progress_enabled():
                            progress_bar(i, total_files, prefix="Files")
                        continue

                    if dry_run:
                        print(f"[{i}/{total_files}] DRY-RUN: {owner_label} '{owner_name}' <- {path} | text_chunks={len(chunks)}, tables={len(parsed.tables)}, images={len(parsed.images)}")
                        processed += 1
                        total_chunks += len(chunks)
                        if is_progress_enabled():
                            progress_bar(i, total_files, prefix="Files")
                        continue

                    # Decide document index sentence
                    document_index: Optional[str] = None
                    if table_summaries or image_summaries:
                        top_parts = []
                        if table_summaries:
                            top_parts.append(table_summaries[0])
                        if image_summaries:
                            top_parts.append(image_summaries[0])
                        merged = "；".join([p.splitlines()[0][:60] for p in top_parts])
                        document_index = merged[:60]
                    else:
                        model_idx = text_index_model or classifier_model
                        api_idx = text_index_api_base or classifier_api_base or ollama_base
                        document_index = summarize_text_index(cleaned, model_idx, api_idx)

                    # Create Document & Content
                    content_id = ensure_document_and_content(
                        session,
                        owner_label,
                        owner_name,
                        document_path=path,
                        document_name=os.path.basename(path),
                        document_index=document_index,
                        text_saved=True,
                        text_path=text_path,
                    )

                    # Upsert one-sentence index as a retrievable chunk
                    if document_index:
                        idx_vec = embed_texts([document_index], embedding_model, ollama_base)[0]
                        upsert_chunks(
                            session,
                            owner_label,
                            owner_name,
                            f"{path}#index",
                            [document_index],
                            [idx_vec],
                            embedding_model,
                            kind="index",
                            document_path=path,
                            content_id=content_id,
                        )

                    # Upsert text chunks
                    text_vectors = embed_texts(chunks, embedding_model, ollama_base)
                    c_nodes, c_rels = upsert_chunks(
                        session,
                        owner_label,
                        owner_name,
                        path,
                        chunks,
                        text_vectors,
                        embedding_model,
                        kind="text",
                        document_path=path,
                        content_id=content_id,
                    )

                    # Upsert tables and their summary chunks
                    for (t, vec) in zip(parsed.tables, table_vecs):
                        t_md = t["table_markdown"]
                        t_path = os.path.join(dirs["table_dir"], f"{base_name}_table{t['table_index']}.md")
                        t_sum = table_summaries[t["table_index"]]
                        upsert_table_node(session, content_id, t["table_index"], t_path, t_sum, vec, table_summary_model or "")
                        upsert_chunks(
                            session,
                            owner_label,
                            owner_name,
                            f"{path}#table{t['table_index']}",
                            [t_sum],
                            [vec],
                            embedding_model,
                            kind="table_summary",
                            document_path=path,
                            content_id=content_id,
                        )

                    # Upsert images and their summary chunks
                    for idx_img, (meta, vec, summary) in enumerate(zip(image_meta, image_vecs, image_summaries)):
                        img_path, mime, alt = meta
                        upsert_image_node(session, content_id, idx_img, img_path, mime, alt, summary, vec, vision_model or "")
                        upsert_chunks(
                            session,
                            owner_label,
                            owner_name,
                            f"{path}#image{idx_img}",
                            [summary],
                            [vec],
                            embedding_model,
                            kind="image_summary",
                            document_path=path,
                            content_id=content_id,
                        )

                    # Mark content as fully ingested (checkpoint)
                    try:
                        mark_content_ingested(session, content_id)
                    except Exception as _:
                        # Non-fatal: proceed even if marking fails
                        pass

                    processed += 1
                    total_chunks += len(chunks)
                    # created counts unknown here due to multiple runs; keep zeros or omit
                    print(f"[{i}/{total_files}] Ingested {len(chunks)} text chunks, {len(parsed.tables)} tables, {len(parsed.images)} images for {owner_label} '{owner_name}'")
                except KeyboardInterrupt:
                    print("Interrupted by user.")
                    break
                except Exception as e:
                    print(f"[{i}/{total_files}] ERROR processing {path}: {e}")
                finally:
                    if is_progress_enabled():
                        progress_bar(i, total_files, prefix="Files")

    finally:
        driver.close()
        print("\nCleaned up resources.")


# argparse removed: configure values directly here or via environment variables

if __name__ == "__main__":
    # Hardcoded folder path to scan for Markdown files
    root_dir = os.path.join(os.getcwd(), "structured_processed_files")

    # Other settings can still come from environment variables (fallback to sensible defaults)
    neo4j_uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    neo4j_user = os.getenv("NEO4J_USER", "neo4j")
    neo4j_password = os.getenv("NEO4J_PASSWORD", "Root@12345678@")
    ollama_base = os.getenv("OLLAMA_BASE", "http://localhost:11434")

    # Separated models for different roles
    classifier_model = os.getenv("CLASSIFIER_MODEL", os.getenv("CHAT_MODEL", Ollama_MODEL))
    text_index_model = os.getenv("TEXT_INDEX_MODEL", classifier_model)
    table_summary_model = os.getenv("TABLE_SUMMARY_MODEL", classifier_model)
    vision_model = os.getenv("VISION_MODEL", Ollama_MODEL)
    embedding_model = os.getenv("EMBED_MODEL", "ollama/qwen3-embedding:latest")

    # Optional per-model API base (default to OLLAMA_BASE)
    classifier_api_base = os.getenv("CLASSIFIER_API_BASE", ollama_base)
    text_index_api_base = os.getenv("TEXT_INDEX_API_BASE", ollama_base)
    table_summary_api_base = os.getenv("TABLE_SUMMARY_API_BASE", ollama_base)
    vision_api_base = os.getenv("VISION_API_BASE", ollama_base)

    # Artifacts root (folder_path)
    artifacts_root = os.getenv("ARTIFACTS_ROOT", os.path.abspath(os.path.join(os.getcwd(), "data_storage")))

    # Optional controls
    limit_files = None  # set to an integer to limit files processed
    dry_run = False     # set True to skip writing to Neo4j

    # Resume/Checkpoint controls
    resume = env_bool("RESUME", True)              # if true, skip files that already have chunks in Neo4j
    force_reingest = env_bool("FORCE_REINGEST", False)  # if true, reprocess even if already ingested

    ingest(
        root_dir=root_dir,
        neo4j_uri=neo4j_uri,
        neo4j_user=neo4j_user,
        neo4j_password=neo4j_password,
        ollama_base=ollama_base,
        classifier_model=classifier_model,
        embedding_model=embedding_model,
        text_index_model=text_index_model,
        table_summary_model=table_summary_model,
        vision_model=vision_model,
        classifier_api_base=classifier_api_base,
        text_index_api_base=text_index_api_base,
        table_summary_api_base=table_summary_api_base,
        vision_api_base=vision_api_base,
        artifacts_root=artifacts_root,
        limit_files=limit_files,
        dry_run=dry_run,
        resume=resume,
        force_reingest=force_reingest,
    )

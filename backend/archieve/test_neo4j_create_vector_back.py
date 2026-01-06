import os
import re
import sys
import json
import time
import hashlib
import difflib
from datetime import datetime
from typing import Iterable, List, Tuple, Optional, Dict

from neo4j import GraphDatabase
from litellm import embedding, completion

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


def strip_data_urls(md: str) -> str:
    # Remove inline base64 images: ![...](data:image/...)
    return re.sub(r"!\[[^\]]*\]\(data:image[^)]+\)", "", md, flags=re.IGNORECASE)


def normalize_whitespace(text: str) -> str:
    text = re.sub(r"\r\n?", "\n", text)
    text = re.sub(r"\t", " ", text)
    # collapse 3+ newlines to 2
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


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
    # Ensure Chunk.id unique
    session.run("""
    CREATE CONSTRAINT chunk_id IF NOT EXISTS
    FOR (c:Chunk) REQUIRE c.id IS UNIQUE
    """)


def load_all_node_names(session) -> Tuple[List[str], List[str]]:
    # Return product names and accessory names
    res_p = session.run("MATCH (p:Product) RETURN p.name AS name")
    products = [r["name"] for r in res_p]
    res_a = session.run("MATCH (a:Accessory) RETURN a.name AS name")
    accessories = [r["name"] for r in res_a]
    return products, accessories


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

def upsert_chunks(
    session,
    owner_label: str,
    owner_name: str,
    file_path: str,
    chunks: List[str],
    vectors: List[List[float]],
    embedding_model: str,
) -> Tuple[int, int]:
    created_nodes = 0
    created_rels = 0

    total = len(chunks)
    for idx, (text, vec) in enumerate(zip(chunks, vectors)):
        cid = stable_chunk_id(file_path, idx, text)
        result = session.run(
            """
            MERGE (c:Chunk {id: $id})
            ON CREATE SET c.text = $text, c.file_path = $file_path, c.index = $index,
                          c.embedding = $embedding, c.embedding_model = $embedding_model,
                          c.created_at = datetime($created_at)
            ON MATCH SET  c.text = $text, c.file_path = $file_path, c.index = $index,
                          c.embedding = $embedding, c.embedding_model = $embedding_model,
                          c.updated_at = datetime($created_at)
            WITH c
            MATCH (o:%s {name: $owner_name})
            MERGE (o)-[r:HAS_CONTENT]->(c)
            RETURN c, r
            """ % owner_label,
            {
                "id": cid,
                "text": text,
                "file_path": file_path,
                "index": idx,
                "embedding": vec,
                "embedding_model": embedding_model,
                "created_at": datetime.utcnow().isoformat(),
                "owner_name": owner_name,
            },
        )
        summary = result.consume()
        stats = summary.counters
        if stats.nodes_created > 0:
            created_nodes += stats.nodes_created
        if stats.relationships_created > 0:
            created_rels += stats.relationships_created
        if is_progress_enabled():
            progress_bar(idx + 1, total, prefix=f"Upsert {os.path.basename(file_path)}")

    return created_nodes, created_rels


# -------- Main pipeline --------

def ingest(
    root_dir: str,
    neo4j_uri: str,
    neo4j_user: str,
    neo4j_password: str,
    ollama_base: Optional[str],
    chat_model: str,
    embedding_model: str,
    limit_files: Optional[int] = None,
    dry_run: bool = False,
) -> None:
    driver = get_neo4j_driver(neo4j_uri, neo4j_user, neo4j_password)
    processed = 0
    total_chunks = 0
    total_new = 0
    total_rels = 0

    try:
        with driver.session() as session:
            ensure_constraints(session)
            products, accessories = load_all_node_names(session)
            print(f"Loaded {len(products)} products, {len(accessories)} accessories from Neo4j")

            md_files: List[str] = []
            for base, _, files in os.walk(root_dir):
                for f in files:
                    if f.lower().endswith('.md'):
                        md_files.append(os.path.join(base, f))
            md_files.sort()
            if limit_files is not None:
                md_files = md_files[:limit_files]
            print(f"Found {len(md_files)} markdown files under {root_dir}")

            total_files = len(md_files)
            if is_progress_enabled() and total_files:
                progress_bar(0, total_files, prefix="Files")

            for i, path in enumerate(md_files, start=1):
                try:
                    raw = read_text_file(path)
                    cleaned = normalize_whitespace(strip_data_urls(raw))
                    if not cleaned or len(cleaned) < 20:
                        print(f"[{i}/{total_files}] Skip (empty/short): {path}")
                        if is_progress_enabled():
                            progress_bar(i, total_files, prefix="Files")
                        continue

                    resolved = resolve_node(path, cleaned, products, accessories, chat_model, ollama_base)
                    if not resolved:
                        print(f"[{i}/{total_files}] Unresolved node for file: {path}")
                        if is_progress_enabled():
                            progress_bar(i, total_files, prefix="Files")
                        continue
                    owner_label, owner_name = resolved

                    chunks = md_chunker(cleaned)
                    if not chunks:
                        print(f"[{i}/{total_files}] No chunks produced: {path}")
                        if is_progress_enabled():
                            progress_bar(i, total_files, prefix="Files")
                        continue

                    if dry_run:
                        print(f"[{i}/{total_files}] DRY-RUN: {owner_label} '{owner_name}' <- {path} with {len(chunks)} chunks")
                        processed += 1
                        total_chunks += len(chunks)
                        if is_progress_enabled():
                            progress_bar(i, total_files, prefix="Files")
                        continue

                    vectors = embed_texts(chunks, embedding_model, ollama_base)
                    created_nodes, created_rels = upsert_chunks(
                        session,
                        owner_label,
                        owner_name,
                        path,
                        chunks,
                        vectors,
                        embedding_model,
                    )
                    processed += 1
                    total_chunks += len(chunks)
                    total_new += created_nodes
                    total_rels += created_rels
                    print(f"[{i}/{total_files}] Linked {len(chunks)} chunks to {owner_label} '{owner_name}' | nodes+{created_nodes}, rels+{created_rels}")
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
    chat_model = os.getenv("CHAT_MODEL", Ollama_MODEL)
    embedding_model = os.getenv("EMBED_MODEL", "ollama/qwen3-embedding:latest")

    # Optional controls
    limit_files = None  # set to an integer to limit files processed
    dry_run = False     # set True to skip writing to Neo4j

    ingest(
        root_dir=root_dir,
        neo4j_uri=neo4j_uri,
        neo4j_user=neo4j_user,
        neo4j_password=neo4j_password,
        ollama_base=ollama_base,
        chat_model=chat_model,
        embedding_model=embedding_model,
        limit_files=limit_files,
        dry_run=dry_run,
    )

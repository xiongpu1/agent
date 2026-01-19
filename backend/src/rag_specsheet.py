import os
import sys
import json
import re
import signal
import base64
import mimetypes
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple, Union
from dotenv import load_dotenv
from neo4j import GraphDatabase
from litellm import completion, embedding
import numpy as np


# 若设为 <=0 则不截断上下文，默认不截断
SPEC_CONTEXT_MAX_CHARS = int(os.getenv("SPEC_CONTEXT_MAX_CHARS", "0"))
SPEC_PLAYBOOK_RULES_LIMIT = int(os.getenv("SPEC_PLAYBOOK_RULES_LIMIT", "0"))
SPEC_SHEET_SYSTEM_PROMPT = """你是一个数据提取助手。请从提供的信息中提取产品规格，并且只返回符合下方 Schema 的有效 JSON：

{
  "productTitle": "string",                 // 产品名
  "features": {                             // 核心规格
    "capacity": "string",                   // 适合人数（数字转字符串）
    "jets": "string",                       // 喷嘴总数（数字转字符串）
    "pumps": "string"                       // 水泵总数（数字转字符串，只能根据产品配置指令中的水泵配置文本逐项求和，不得使用其他上下文/表格推断）
  },
  "measurements": "string",                 // 产品尺寸，如 '70\" × 33\" × 37\"'
  "premiumFeatures": ["string", ...],       // 照明系统列表，可由产品配置中的灯光位得出；若 ACE 规则补充了“必须逐项完整提取/不得省略或改写”，则以 ACE 为准
  "insulationFeatures": ["string", ...],    // 保温系统列表，可由产品配置中的底保温、侧保温、缸体保温、外加热位得出；若 ACE 规则要求术语精准，则必须遵守
  "extraFeatures": ["string", ...],         // 额外功能列表，可由产品配置中的喷嘴、多媒体、台阶、裙边位得出；若 ACE 规则要求“不得省略/不得概括/不得改写”，则必须逐项完整列出
  "Specifications": [                       // 固定顺序的规格
    {"Cabinet Color": ["#c4c4c4", "#666666"]}, // 内缸颜色，可由产品配置中的缸体/外壳颜色位推断；若描述“内缸黑+外缸白”，Cabinet=黑色十六进制（如 #000000），Shell=白色十六进制（如 #ffffff）；若描述单一颜色（如“进口云彩黑/进口云彩白”等），Cabinet 和 Shell 都填同一颜色的十六进制。可为字符串或字符串数组。
    {"Shell Color": "#c4c4c4"},                 // 外缸颜色，可由产品配置提示中的缸体/外壳颜色位推断，规则同上，值用十六进制色值
    {"Dry Weight": "293 lbs"},                  // 干重
    {"Water Capacity": "79 gallons"},           // 储水量
    {"Pump": "1 x Chiller"},                    // 水泵具体组成，直接采用产品配置指令中的水泵配置文本（不改写）；pumps 总数另行求和
    {"Controls": "Joyonway Touch Screen"}       // 控制面板
  ],
  "smartWater": ["string", ...],            // 智能净水系统列表，可由产品配置中的消毒系统位得出；若 ACE 规则要求术语/枚举项保持原文，则必须遵守
  "images": {                               // 图片链接
    "product": "/back/product.png",         // 产品图片
    "background": "/back/back.png"          // 背景图片
  }
}

说明：
1. 【最高优先级】所有提取行为必须严格遵守 ACE Playbook Rules，ACE 规则凌驾于任何其他信息来源之上；若 BOM（产品配置指令）、上下文信息与 ACE 规则冲突，以 ACE 规则为准。
2. 信息优先级（ACE 规则除外）：产品配置指令/解析文本（BOM） > 产品文件概览中文本内容（上下文/OCR） > 合理缺省值。
3. 术语提取要求：严格遵循 ACE 规则中“保留精确表述、不得缩写/改写/概括”的要求，例如：
   - 若 BOM 中出现“满泡”，需先校验 ACE 规则是否要求完整术语（如“满泡沫保温”），若 ACE 明确“不得缩写”，则需修正为完整术语；
   - 所有从 BOM/上下文提取的特征（如保温、照明、额外功能），必须逐一审验是否符合 ACE 术语规范，不符合则按 ACE 要求调整。
4. 字段提取细则（均需先遵守 ACE 规则）：
   - Pump：必须用产品配置指令中的水泵配置文本原样填充（不改写、不重组），仅在产品配置指令缺失时，从产品文件概览文本推断；pumps 数值字段需据产品配置指令中的泵数量逐项求和。
   - Cabinet Color / Shell Color：若产品配置指令提供缸体/外壳颜色位，解析并填充；按 ACE 规则映射为规范十六进制色值，若 ACE 有明确颜色映射标准，必须严格遵循；若描述“内缸 X + 外缸 Y”，则 Cabinet=X，Shell=Y；单一颜色则两者均填该颜色，可为单色或数组。
   - premiumFeatures/insulationFeatures/extraFeatures/smartWater：提取后需校验是否符合 ACE 规则中“逐项完整列出、不得省略”的要求，确保无遗漏、无改写。
5. Specifications 必须是按以上顺序的对象数组，每个对象仅有 1 个键值对。
6. Cabinet Color / Shell Color 可接受单字符串或字符串数组；其他规格字段必须为字符串。
7. 所有数组需非空（至少给出一个合理值）。
8. 仅返回 JSON，不要输出额外文本。

【语言输出要求（必须遵守）】
1. JSON 的 key 必须保持为 Schema 中的英文 key（如 productTitle/features/Specifications 等），不要翻译 key。
2. 除 JSON key 以外，所有可读文本字段的值必须为英文（包括 productTitle、premiumFeatures/insulationFeatures/extraFeatures/smartWater 列表项、Specifications 中的 Dry Weight/Water Capacity/Pump/Controls 等字段值）。
3. 若上下文/BOM/OCR 为中文，请先理解其含义并翻译为自然英文后填入 JSON。
4. 品牌/型号/技术名词/缩写等专有名词尽量保留原文（例如 Joyonway、Bluetooth、Ozonator 等），仅翻译其周边描述。
"""


def _get_spec_playbook_rules_text(limit: int = 0) -> str:
    snapshot: List[Dict[str, Any]] = []
    try:
        from src.ace_integration import get_ace_manager  # type: ignore

        snapshot = get_ace_manager("spec").get_playbook_snapshot()
    except Exception:
        snapshot = []

    # Fallback: read playbook directly from disk (helps when in-process manager
    # fails to load checkpoint for any reason)
    if not snapshot:
        try:
            ace_root = Path(__file__).resolve().parents[2] / "agentic-context-engineering-main"
            playbook_path = ace_root / "results" / "spec" / "ace_playbook.json"
            if playbook_path.exists():
                payload = json.loads(playbook_path.read_text(encoding="utf-8"))
                bullets = payload.get("bullets") if isinstance(payload, dict) else None
                if isinstance(bullets, list):
                    snapshot = [b for b in bullets if isinstance(b, dict)]
        except Exception:
            snapshot = []

    if not snapshot:
        return ""

    if limit and limit > 0:
        snapshot = snapshot[-limit:]

    lines: List[str] = []
    for bullet in snapshot:
        bullet_id = (bullet or {}).get("id")
        content = (bullet or {}).get("content")
        if bullet_id and content:
            lines.append(f"- [{bullet_id}] {content}")

    if not lines:
        return ""

    return "【ACE Playbook Rules（必须遵守）】\n" + "\n".join(lines) + "\n\n"


def _run_completion_with_timeout(kwargs: Dict[str, Any], timeout: int) -> Any:
    """Run litellm completion with a hard timeout (POSIX only)."""

    if timeout is None or timeout <= 0:
        return completion(**kwargs)

    def _timeout_handler(_signum, _frame):
        raise TimeoutError("LLM specsheet generation timed out")

    old_handler = signal.signal(signal.SIGALRM, _timeout_handler)
    signal.alarm(max(timeout, 1))
    try:
        return completion(**kwargs)
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old_handler)
"""
RAG query module for retrieving specsheet content from Neo4j.
Uses vector search to find relevant chunks and LLM to extract structured data.
"""
import os
import sys
import json
import signal
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple, Union
from dotenv import load_dotenv
from neo4j import GraphDatabase
from litellm import completion, embedding
import numpy as np

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.dataclass import Neo4jConfig, LLMConfig
from src.neo4j_file_add_neo4j import embed_texts, get_neo4j_driver
from src.models_litellm import (
    Qwen_API_KEY,
    Qwen_URL_BASE,
    Qwen_MODEL,
    Ollama_QWEN3_VL_MODEL,
    Ollama_QWEN3_EMBEDDING,
    Ollama_BASE_URL
)
from src.specsheet_models import (
    SpecsheetData,
    SpecsheetFromDocsRequest,
    SpecsheetFromOcrRequest,
    SpecsheetOcrDocument,
    DocumentReference,
    AccessoryDocumentGroup,
)
from src.bom_config import BOM_TYPES, get_bom_sections

_REF_BOM_ACCESSORIES_CACHE: Optional[Dict[str, List[str]]] = None
_REF_BOM_ACCESSORIES_MTIME: Optional[float] = None

load_dotenv()

BACKEND_ROOT = Path(__file__).resolve().parent.parent
TEXT_FILE_EXTS = {
    ".txt",
    ".md",
    ".markdown",
    ".csv",
    ".tsv",
    ".json",
    ".yaml",
    ".yml",
    ".ini",
    ".cfg",
    ".log",
}


def _parse_specsheet_json(raw_json: Optional[str]) -> Optional[SpecsheetData]:
    if not raw_json:
        return None

    try:
        data = json.loads(raw_json)
        return SpecsheetData(**data)
    except Exception as exc:
        print(f"Warning: Failed to parse saved specsheet JSON: {exc}")
        return None


def get_neo4j_config() -> Neo4jConfig:
    """Get Neo4j configuration from environment variables."""
    return Neo4jConfig(
        uri=os.getenv("NEO4J_URI"),
        user=os.getenv("NEO4J_USER"),
        password=os.getenv("NEO4J_PASSWORD")
    )


def get_embedding_config() -> LLMConfig:
    """Get embedding model configuration."""
    return LLMConfig(
        model=Ollama_QWEN3_EMBEDDING,
        base_url=Ollama_BASE_URL
    )


def get_llm_config(
    llm_provider: Optional[str] = None,
    llm_model: Optional[str] = None,
) -> LLMConfig:
    provider = (llm_provider or "").strip().lower()
    model = (llm_model or "").strip()

    dashscope_api_key = os.getenv("DASHSCOPE_API_KEY")

    if not model:
        model = os.getenv("DEFAULT_LLM_MODEL", "").strip()

    if model.startswith("ollama/"):
        provider = "ollama"
    elif model.startswith("dashscope/"):
        provider = "dashscope"

    if provider == "dashscope":
        if not model:
            model = Qwen_MODEL
        elif not model.startswith("dashscope/") and "/" not in model:
            model = f"dashscope/{model}"
        if not dashscope_api_key:
            raise ValueError("DASHSCOPE_API_KEY 未配置，无法使用 dashscope 模型")
        return LLMConfig(
            model=model,
            api_key=dashscope_api_key,
            base_url=Qwen_URL_BASE,
        )

    if not model:
        model = Ollama_QWEN3_VL_MODEL
    elif provider == "ollama" and not model.startswith("ollama/") and "/" not in model:
        model = f"ollama/{model}"

    return LLMConfig(
        model=model,
        api_key=None,
        base_url=Ollama_BASE_URL,
    )


def retrieve_chunks_by_product_bom(
    session,
    product_name: str,
    bom_version: str,
    query_vector: List[float],
    top_k: int = 10,
    similarity_threshold: float = 0
) -> List[Dict[str, Any]]:
    """
    Retrieve relevant chunks for a product and BOM version using vector search.
    
    Args:
        session: Neo4j session
        product_name: Product English name
        bom_version: BOM version
        query_vector: Query vector for similarity search
        top_k: Number of top results to return
        similarity_threshold: Minimum similarity score
        
    Returns:
        List of chunk dictionaries with text, source_path, and similarity score
    """
    try:
        # Try using vector index query (Neo4j 5.x+)
        result = session.run(
            """
            MATCH (p:Product {english_name: $product_name, bom_version: $bom_version})
            OPTIONAL MATCH (p)-[:HAS_DOCUMENT]->(doc_p:Document)
            OPTIONAL MATCH (p)-[:HAS]->(a:Accessory)-[:HAS_DOCUMENT]->(doc_a:Document)
            WITH collect(DISTINCT doc_p) + collect(DISTINCT doc_a) AS all_docs
            UNWIND all_docs AS doc
            MATCH (doc)-[:HAS_TEXT_DESCRIPTION|HAS_IMAGE_DESCRIPTION|HAS_TABLE_DESCRIPTION]->(desc)
            MATCH (desc)-[:HAS_CHUNK]->(c:Chunk)
            WITH collect(DISTINCT c) AS product_chunks
            CALL db.index.vector.queryNodes('chunk_embedding', $topK, $queryVector)
            YIELD node AS chunk, score
            WHERE chunk IN product_chunks AND score >= $threshold
            RETURN chunk.text AS text, 
                   chunk.source_path AS source_path,
                   score AS similarity
            ORDER BY score DESC
            LIMIT $topK
            """,
            {
                "product_name": product_name,
                "bom_version": bom_version,
                "topK": top_k * 2,  # Query more to filter by product
                "queryVector": query_vector,
                "threshold": similarity_threshold
            }
        )
        
        chunks = []
        for record in result:
            chunks.append({
                "text": record["text"],
                "source_path": record.get("source_path", "unknown"),
                "similarity": float(record["similarity"])
            })
        
        if chunks:
            return chunks[:top_k]
    except Exception as e:
        print(f"Warning: Vector index query failed ({e}), using Python-based similarity calculation")
    
    # Fallback: Python-based similarity calculation
    try:
        # First, get all chunks for this product
        result = session.run(
            """
            MATCH (p:Product {english_name: $product_name, bom_version: $bom_version})
            OPTIONAL MATCH (p)-[:HAS_DOCUMENT]->(doc_p:Document)
            OPTIONAL MATCH (p)-[:HAS]->(a:Accessory)-[:HAS_DOCUMENT]->(doc_a:Document)
            WITH collect(DISTINCT doc_p) + collect(DISTINCT doc_a) AS all_docs
            UNWIND all_docs AS doc
            MATCH (doc)-[:HAS_TEXT_DESCRIPTION|HAS_IMAGE_DESCRIPTION|HAS_TABLE_DESCRIPTION]->(desc)
            MATCH (desc)-[:HAS_CHUNK]->(c:Chunk)
            WHERE c.embedding IS NOT NULL AND c.text IS NOT NULL
            RETURN c.text AS text,
                   c.source_path AS source_path,
                   c.embedding AS embedding
            """,
            {
                "product_name": product_name,
                "bom_version": bom_version
            }
        )
        
        query_vec = np.array(query_vector)
        candidates = []
        
        for record in result:
            chunk_vec = np.array(record["embedding"])
            # Calculate cosine similarity
            similarity = np.dot(query_vec, chunk_vec) / (np.linalg.norm(query_vec) * np.linalg.norm(chunk_vec))
            
            if similarity >= similarity_threshold:
                candidates.append({
                    "text": record["text"],
                    "source_path": record.get("source_path", "unknown"),
                    "similarity": float(similarity)
                })
        
        # Sort by similarity and return top_k
        candidates.sort(key=lambda x: x["similarity"], reverse=True)
        return candidates[:top_k]
    except Exception as e:
        print(f"Warning: Python-based similarity calculation failed: {e}")
        return []


def format_context(chunks: List[Dict[str, Any]]) -> str:
    """Format retrieved chunks into a context string."""
    if not chunks:
        return "未找到相关上下文信息。"
    
    context_parts = []
    for idx, chunk in enumerate(chunks, 1):
        source = chunk.get("source_path", "未知来源")
        text = chunk.get("text", "")
        similarity = chunk.get("similarity", 0.0)
        context_parts.append(
            f"[上下文 {idx}] (来源: {source}, 相似度: {similarity:.3f})\n{text}\n"
        )
    
    return "\n".join(context_parts)


def _summarize_bom(bom_context: Optional[Dict[str, Any]]) -> Optional[str]:
    """Convert BOM 解码结果为简洁句子，侧重配件含义。"""
    if not bom_context:
        return None
    segs = bom_context.get("segments") or []
    if not segs:
        return None
    parts: List[str] = []
    for seg in segs:
        label = seg.get("label") or ""
        meaning = seg.get("meaning") or seg.get("value") or ""
        if label and meaning:
            # 去掉前缀“第x位”等数字标识，保留配置名称
            prefix_clean = re.sub(r"第?\s*\d+[+位]*\s*[:：]?\s*", "", label)
            clean_label = prefix_clean.split("（")[0].strip() or label
            parts.append(f"{clean_label}：{meaning}")
    if not parts:
        return None
    return "；".join(parts)


def _summarize_docs(documents: Optional[List[SpecsheetOcrDocument]]) -> Optional[str]:
    """
    现根据需求：不再罗列文件名，只说明数量，正文已在上下文展开。
    """
    if not documents:
        return None
    total = len(documents)
    return f"共 {total} 个文件，全文已在上下文展开"


def _normalize_ref_key(value: Optional[str]) -> str:
    return (value or "").strip().lower()


def _load_ref_bom_accessories_cache() -> Dict[str, List[str]]:
    global _REF_BOM_ACCESSORIES_CACHE  # noqa: PLW0603
    global _REF_BOM_ACCESSORIES_MTIME  # noqa: PLW0603

    ref_path = (Path(__file__).resolve().parent.parent / "data_test" / "ref_BOM_accessories.json").resolve()
    try:
        stat = ref_path.stat()
    except Exception:
        _REF_BOM_ACCESSORIES_CACHE = {}
        _REF_BOM_ACCESSORIES_MTIME = None
        return _REF_BOM_ACCESSORIES_CACHE

    if _REF_BOM_ACCESSORIES_CACHE is not None and _REF_BOM_ACCESSORIES_MTIME == stat.st_mtime:
        return _REF_BOM_ACCESSORIES_CACHE

    try:
        with open(ref_path, "r", encoding="utf-8") as f:
            raw = json.load(f)
    except Exception:
        _REF_BOM_ACCESSORIES_CACHE = {}
        _REF_BOM_ACCESSORIES_MTIME = stat.st_mtime
        return _REF_BOM_ACCESSORIES_CACHE

    mapping: Dict[str, List[str]] = {}
    if isinstance(raw, list):
        for item in raw:
            if not isinstance(item, dict):
                continue
            name = _normalize_ref_key(item.get("product_english_name"))
            bom = _normalize_ref_key(item.get("bom_version"))
            if not name or not bom:
                continue
            accessories = item.get("accessories")
            if not isinstance(accessories, list) or not accessories:
                continue
            key = f"{name}||{bom}"
            if key not in mapping:
                mapping[key] = []
            for acc in accessories:
                if not isinstance(acc, str):
                    continue
                acc_s = acc.strip()
                if not acc_s:
                    continue
                if acc_s in mapping[key]:
                    continue
                mapping[key].append(acc_s)

    _REF_BOM_ACCESSORIES_CACHE = mapping
    _REF_BOM_ACCESSORIES_MTIME = stat.st_mtime
    return mapping


def _get_ref_accessories_prompt_text(product_name: Optional[str], bom_code: Optional[str]) -> Optional[str]:
    name = _normalize_ref_key(product_name)
    bom = _normalize_ref_key(bom_code)
    if not name or not bom:
        return None
    cache = _load_ref_bom_accessories_cache()
    accessories = cache.get(f"{name}||{bom}")
    if not accessories:
        return None

    lines: List[str] = []
    for idx, acc in enumerate(accessories[:60], 1):
        lines.append(f"- {acc}")
    if len(accessories) > 60:
        lines.append(f"- ...（共 {len(accessories)} 条，已截断）")

    text = "\n".join(lines).strip()
    if len(text) > 2400:
        text = text[:2400] + "..."
    return text


def _get_product_config_and_accessory_glossary(
    product_name: Optional[str],
    bom_code: Optional[str],
) -> Tuple[str, str]:
    name = (product_name or "").strip()
    bom = (bom_code or "").strip()
    if not name or not bom:
        return "", ""

    pid = f"{name}_{bom}".strip()

    neo4j_config = get_neo4j_config()
    driver = get_neo4j_driver(neo4j_config)

    config_text_zh = ""
    glossary_lines: List[str] = []
    try:
        with driver.session() as session:
            cfg = session.run(
                """
                OPTIONAL MATCH (p1:Product {product_id: $product_id})-[:HAS_CONFIG]->(pc1:ProductConfig)
                OPTIONAL MATCH (p2:Product {material_code: $material_code, bom_id: $bom_id})-[:HAS_CONFIG]->(pc2:ProductConfig)
                OPTIONAL MATCH (p3:Product {english_name: $english_name, bom_version: $bom_version})-[:HAS_CONFIG]->(pc3:ProductConfig)
                WITH coalesce(pc1.config_text_zh, pc2.config_text_zh, pc3.config_text_zh, '') AS config_text_zh
                RETURN config_text_zh AS config_text_zh
                """,
                {
                    "product_id": pid,
                    "material_code": name,
                    "bom_id": bom,
                    "english_name": name,
                    "bom_version": bom,
                },
            ).single()
            if cfg:
                config_text_zh = (cfg.get("config_text_zh") or "").strip()

            acc_rows = session.run(
                """
                OPTIONAL MATCH (p1:Product {product_id: $product_id})
                OPTIONAL MATCH (p2:Product {material_code: $material_code, bom_id: $bom_id})
                OPTIONAL MATCH (p3:Product {english_name: $english_name, bom_version: $bom_version})
                WITH [p1, p2, p3] AS ps
                UNWIND ps AS p
                WITH DISTINCT p
                WHERE p IS NOT NULL
                OPTIONAL MATCH (p)-[:USES_BOM]->(b:BOM {bom_id: $bom_id})-[r1:HAS_ACCESSORY]->(a1:Accessory)
                OPTIONAL MATCH (p)-[r2:HAS_ACCESSORY]->(a2:Accessory)
                WITH collect({ord: r1.order, zh: coalesce(a1.name_zh, ''), en: coalesce(a1.name_en, '')})
                     + collect({ord: r2.order, zh: coalesce(a2.name_zh, ''), en: coalesce(a2.name_en, '')}) AS rows
                UNWIND rows AS row
                WITH row
                WHERE row.zh IS NOT NULL AND row.zh <> ''
                RETURN row.ord AS ord,
                       row.zh AS name_zh,
                       row.en AS name_en
                ORDER BY ord ASC, name_zh ASC
                """,
                {
                    "product_id": pid,
                    "material_code": name,
                    "bom_id": bom,
                    "english_name": name,
                    "bom_version": bom,
                },
            )

            seen = set()
            for record in acc_rows:
                name_zh = (record.get("name_zh") or "").strip()
                if not name_zh:
                    continue
                key = name_zh.lower()
                if key in seen:
                    continue
                seen.add(key)
                name_en = (record.get("name_en") or "").strip()
                if name_en:
                    glossary_lines.append(f"- {name_zh} -> {name_en}")
                else:
                    glossary_lines.append(f"- {name_zh} -> (translate yourself)")
    finally:
        driver.close()

    glossary_text = "\n".join(glossary_lines).strip()
    if len(glossary_text) > 2400:
        glossary_text = glossary_text[:2400] + "..."

    return config_text_zh, glossary_text


def _build_llm_prompt_text(
    context_text: str,
    title_hint: Optional[str],
    multimodal_segments: Optional[List[Dict[str, str]]] = None,
    bom_summary: Optional[str] = None,
    doc_summary: Optional[str] = None,
    ref_accessories_text: Optional[str] = None,
    config_text_zh: Optional[str] = None,
    accessory_glossary_text: Optional[str] = None,
) -> str:
    """Build the user prompt text sent to LLM, given context and images."""
    multimodal_segments = multimodal_segments or []

    # 构造候选图片列表（路径 + 反推描述），帮助模型选择最合适的产品主图
    image_candidates: List[str] = []
    for idx, seg in enumerate(multimodal_segments):
        path = seg.get("image_path") or seg.get("image") or f"image_{idx}"
        desc = seg.get("description") or ""
        mime = seg.get("mime_type") or "image/*"
        source = (seg.get("source") or "").strip().lower()
        source_tag = ""
        if source == "original_upload":
            source_tag = " [ORIGINAL_UPLOAD]"
        elif source == "ocr_artifact":
            source_tag = " [OCR_ARTIFACT]"
        # 截断描述避免过长
        if len(desc) > 500:
            desc = desc[:500] + "..."
        image_candidates.append(f"{idx + 1}. path: {path} ({mime}){source_tag}\n   reverse_prompt: {desc}".strip())

    multimodal_brief = ""
    if image_candidates:
        multimodal_brief = "\n\n候选产品图片（请从中选出最适合作为 images.product 的一张）：\n" + "\n".join(image_candidates)

    bom_text = f"\n产品配置指令：{bom_summary}" if bom_summary else ""
    ref_text = ""
    doc_text = f"\n产品文件概览（上下文/OCR）：{doc_summary}" if doc_summary else ""

    cfg_text = (config_text_zh or "").strip()
    glossary_text = (accessory_glossary_text or "").strip()
    header = ""
    if cfg_text or glossary_text:
        header = (
            "You are extracting product specification information and MUST return STRICT JSON ONLY.\n\n"
            "# Priority of sources (very important)\n"
            "1) Product configuration original text (Chinese) is authoritative.\n"
            "2) Accessory bilingual glossary (ZH -> EN) is authoritative for English naming.\n"
            "3) The rest of the context (OCR/diagrams) is secondary.\n\n"
        )
        if cfg_text:
            header += (
                "# Product Configuration (Chinese, authoritative)\n"
                "[CONFIG_TEXT_ZH]\n"
                f"{cfg_text}\n"
                "[/CONFIG_TEXT_ZH]\n\n"
            )
        if glossary_text:
            header += (
                "# Accessory Glossary (ZH -> EN, use EXACT English if provided)\n"
                "[ACCESSORY_GLOSSARY]\n"
                f"{glossary_text}\n"
                "[/ACCESSORY_GLOSSARY]\n\n"
            )

    image_choice_rule = (
        "- 若提供了候选产品图片列表，必须从列表中选择一条路径填入 images.product（不得保留默认或填写列表外路径）。\n"
        "- 若候选列表中包含 [ORIGINAL_UPLOAD]，优先从这些原始上传图片中选择（避免 OCR 产物带黑边/裁切/压缩）。\n"
        "- 若列表为空或无候选图片，则使用默认 \"/back/product.png\"。\n"
    )

    return f"""{header}Extract product specification information from the following context. If某些字段缺失或无法确定，请使用\"待填写\"作为占位。严格返回 JSON。{bom_text}{ref_text}{doc_text}

上下文：
{context_text}
{multimodal_brief}

要求：
- All human-readable string values in the JSON must be in English. If the source context is Chinese, translate to natural English before filling the JSON.
- Preserve brand/model/proper nouns and technical terms as-is whenever possible (e.g., Joyonway, Bluetooth, Ozonator). Only translate surrounding descriptions.
- 在 Specifications/字段提取的基础上，若提供了候选产品图片，请选择最能代表产品的图片，将其路径填入 images.product；若无合适图片，保持默认 "/back/product.png"。
- {image_choice_rule.strip()}
- 对于表示“缺失/不包含/没有”的配置项（例如：无台阶、无缸盖、无外接加热管路、无风泵、Without steps/No cover/Without XXX 等），不要把它们写入规格页的功能列表字段（premiumFeatures/insulationFeatures/extraFeatures/smartWater 等）；这些字段只写“实际包含/具备”的卖点与配置。
- 若字段无法从上下文确定，请统一填写 "待填写"（不得返回 "未知"/"Unknown"/"N/A" 等）。
- 仅返回 JSON。若推断到产品称呼，可使用该称呼作为 productTitle；否则使用 "{title_hint or 'OCR Generated Specsheet'}"。"""


def _normalize_unknown_placeholders(value: Any) -> Any:
    if isinstance(value, str):
        raw = value.strip()
        lowered = raw.lower()
        if raw in {"未知"}:
            return "待填写"
        if lowered in {"unknown", "n/a", "na"}:
            return "待填写"
        return value
    if isinstance(value, list):
        return [_normalize_unknown_placeholders(item) for item in value]
    if isinstance(value, dict):
        return {k: _normalize_unknown_placeholders(v) for k, v in value.items()}
    return value


def _extract_specsheet_from_context(
    context_text: str,
    chunks: Optional[List[Dict[str, Any]]] = None,
    title_hint: Optional[str] = None,
    multimodal_segments: Optional[List[Dict[str, str]]] = None,
    bom_summary: Optional[str] = None,
    doc_summary: Optional[str] = None,
    ref_accessories_text: Optional[str] = None,
    config_text_zh: Optional[str] = None,
    accessory_glossary_text: Optional[str] = None,
    llm_provider: Optional[str] = None,
    llm_model: Optional[str] = None,
) -> Tuple[SpecsheetData, List[Dict[str, Any]], str, str]:
    """Run LLM over provided context text to obtain specsheet data."""

    llm_config = get_llm_config(llm_provider=llm_provider, llm_model=llm_model)

    title_text = title_hint or "OCR Generated Specsheet"

    original_context_len = len(context_text or "")
    truncated = False
    if SPEC_CONTEXT_MAX_CHARS > 0 and original_context_len > SPEC_CONTEXT_MAX_CHARS:
        context_text = context_text[:SPEC_CONTEXT_MAX_CHARS]
        truncated = True

    print(
        "[SpecsheetLLM] model=%s base_url=%s context_chars=%s truncated=%s multimodal_segments=%s"
        % (
            llm_config.model,
            llm_config.base_url,
            original_context_len,
            truncated,
            len(multimodal_segments or []),
        )
    )

    user_prompt = _build_llm_prompt_text(
        context_text,
        title_text,
        multimodal_segments,
        bom_summary=bom_summary,
        doc_summary=doc_summary,
        ref_accessories_text=ref_accessories_text,
        config_text_zh=config_text_zh,
        accessory_glossary_text=accessory_glossary_text,
    )

    playbook_rules_text = _get_spec_playbook_rules_text(SPEC_PLAYBOOK_RULES_LIMIT)
    system_prompt = SPEC_SHEET_SYSTEM_PROMPT + ("\n\n" + playbook_rules_text if playbook_rules_text else "")

    kwargs = {
        "model": llm_config.model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": 0.1,
    }

    if multimodal_segments:
        image_payloads = [seg.get("image") for seg in multimodal_segments if seg.get("image")]
        if image_payloads:
            kwargs["images"] = image_payloads

    if llm_config.api_key:
        kwargs["api_key"] = llm_config.api_key
    if llm_config.base_url:
        kwargs["api_base"] = llm_config.base_url

    try:
        response = _run_completion_with_timeout(kwargs, None)
    except TimeoutError:
        print("Warning: Specsheet generation exceeded timeout, returning default data")
        return get_default_specsheet(title_hint), chunks or [], user_prompt, system_prompt
    except Exception as exc:  # noqa: BLE001
        print(f"Warning: LLM call failed: {exc}")
        return get_default_specsheet(title_hint), chunks or [], user_prompt, system_prompt

    llm_output = response.choices[0].message.content.strip()

    if "```json" in llm_output:
        llm_output = llm_output.split("```json")[1].split("```")[0].strip()
    elif "```" in llm_output:
        llm_output = llm_output.split("```")[1].split("```")[0].strip()

    try:
        extracted_data = json.loads(llm_output)
    except json.JSONDecodeError as e:
        print(f"Warning: Failed to parse LLM JSON output: {e}")
        print(f"LLM output: {llm_output}")
        return get_default_specsheet(title_hint), chunks or [], user_prompt, system_prompt

    try:
        extracted_data = _normalize_unknown_placeholders(extracted_data)
        if "images" not in extracted_data:
            extracted_data["images"] = {
                "product": "/back/product.png",
                "background": "/back/back.png"
            }

        specsheet_data = SpecsheetData(**extracted_data)
        return specsheet_data, chunks or [], user_prompt, system_prompt
    except Exception as e:
        print(f"Warning: Pydantic validation failed: {e}")
        print(f"Extracted data: {extracted_data}")
        return get_default_specsheet(title_hint), chunks or [], user_prompt, system_prompt


def _get_specsheet_and_chunks_by_product_bom(
    product_name: str,
    bom_version: str,
    top_k: int = 10,
    similarity_threshold: float = 0,
):
    """Core implementation that returns both specsheet data and retrieved chunks.

    This is used by the public helpers to either return only specsheet data
    (for backward compatibility) or specsheet data together with chunks.
    """
    neo4j_config = get_neo4j_config()
    embedding_config = get_embedding_config()
    
    driver = get_neo4j_driver(neo4j_config)
    try:
        with driver.session() as session:
            product_record = session.run(
                """
                MATCH (p:Product {english_name: $product_name, bom_version: $bom_version})
                RETURN p.specsheet_json AS specsheet_json
                LIMIT 1
                """,
                {
                    "product_name": product_name,
                    "bom_version": bom_version,
                },
            ).single()

            if not product_record:
                raise ValueError(f"Product '{product_name}' with BOM '{bom_version}' not found")

            saved_specsheet = _parse_specsheet_json(product_record.get("specsheet_json"))
            if saved_specsheet:
                return saved_specsheet, []

            # Step 1: Build query text for vector search
            query_text = (
                f"{product_name} {bom_version} specification capacity jets pumps measurements "
                "features premium lighting insulation smart water purification system"
            )

            # Step 2: Generate query vector
            query_vectors = embed_texts([query_text], embedding_config)
            if not query_vectors:
                raise ValueError("Failed to generate query vector")
            query_vector = query_vectors[0]

            # Step 3: Retrieve relevant chunks
            chunks = retrieve_chunks_by_product_bom(
                session,
                product_name,
                bom_version,
                query_vector,
                top_k=top_k,
                similarity_threshold=similarity_threshold,
            )

            # Step 4: Format context
            if not chunks:
                print(f"Warning: No relevant chunks found for {product_name} {bom_version}")
                print("Attempting to generate specsheet from product name only...")
                context_text = (
                    f"产品名称: {product_name}, BOM版本: {bom_version}\n"
                    "未找到相关文档内容，请基于产品名称生成合理的默认规格页内容。"
                )
            else:
                context_text = format_context(chunks)

            specsheet_data, _chunks_unused, _prompt_text_unused, _system_prompt_unused = _extract_specsheet_from_context(
                context_text,
                chunks,
                title_hint=f"{product_name} {bom_version}".strip(),
                multimodal_segments=None,
            )
            return specsheet_data, chunks
    finally:
        driver.close()


def get_specsheet_by_product_bom(
    product_name: str,
    bom_version: str,
    top_k: int = 10,
    similarity_threshold: float = 0
) -> SpecsheetData:
    """Backward compatible helper that returns only specsheet data.

    This preserves the original behavior for existing callers.
    """
    specsheet_data, _chunks = _get_specsheet_and_chunks_by_product_bom(
        product_name=product_name,
        bom_version=bom_version,
        top_k=top_k,
        similarity_threshold=similarity_threshold,
    )
    return specsheet_data



def get_specsheet_with_chunks_by_product_bom(
    product_name: str,
    bom_version: str,
    top_k: int = 10000,
    similarity_threshold: float = 0,
):
    """Return both specsheet data and the retrieved top-k chunks for a product BOM.

    Returns a tuple of (SpecsheetData, List[Dict[str, Any]]).
    """
    specsheet_data, chunks = _get_specsheet_and_chunks_by_product_bom(
        product_name=product_name,
        bom_version=bom_version,
        top_k=top_k,
        similarity_threshold=similarity_threshold,
    )
    return specsheet_data, chunks


def _read_text_from_backend(path: Optional[str], max_chars: int = 4000) -> str:
    if not path:
        return ""
    try:
        resolved = (BACKEND_ROOT / path).resolve()
        resolved.relative_to(BACKEND_ROOT)
    except Exception:
        return ""

    if not resolved.exists() or not resolved.is_file():
        return ""

    ext = resolved.suffix.lower()
    if ext not in TEXT_FILE_EXTS:
        # attempt reading small files even if unknown extension but limit size
        if resolved.stat().st_size > 1024 * 1024:  # >1MB skip
            return ""

    try:
        with open(resolved, "r", encoding="utf-8", errors="ignore") as f:
            data = f.read(max_chars + 500)
            if len(data) > max_chars:
                data = data[:max_chars] + "..."
            return data
    except Exception as e:
        print(f"Warning: failed reading file {path}: {e}")
        return ""


def _build_context_from_docs(
    product_docs: List[DocumentReference],
    accessory_docs: List[AccessoryDocumentGroup],
) -> Tuple[str, List[Dict[str, Any]]]:
    context_parts: List[str] = []
    pseudo_chunks: List[Dict[str, Any]] = []

    def append_entry(owner: str, doc: DocumentReference):
        header = f"[{owner}] {doc.name or doc.path or 'Unnamed'}"
        summary_text = doc.summary or ""
        file_text = _read_text_from_backend(doc.path)
        body_parts = []
        if summary_text:
            body_parts.append(f"摘要: {summary_text}")
        if file_text:
            body_parts.append(file_text)
        if not body_parts:
            body_parts.append("（无可用文本内容，保留文件引用。）")
        chunk_text = header + "\n" + "\n".join(body_parts)
        context_parts.append(chunk_text)
        pseudo_chunks.append(
            {
                "text": chunk_text,
                "source_path": doc.path or doc.name or owner,
                "similarity": 1.0,
            }
        )

    for doc in product_docs:
        append_entry("产品文档", doc)

    for group in accessory_docs:
        owner = f"配件:{group.accessory}"
        for doc in group.documents:
            append_entry(owner, doc)

    context_text = "\n\n".join(context_parts)
    return context_text, pseudo_chunks


def _read_image_base64_from_backend(path: Optional[str]) -> Optional[Tuple[str, str]]:
    if not path:
        return None
    try:
        resolved = (BACKEND_ROOT / path).resolve()
        resolved.relative_to(BACKEND_ROOT)
    except Exception:
        return None

    if not resolved.exists() or not resolved.is_file():
        return None

    mime_map = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
        ".bmp": "image/bmp",
    }
    mime_type = mime_map.get(resolved.suffix.lower())
    if not mime_type:
        return None

    try:
        with open(resolved, "rb") as f:
            encoded = base64.b64encode(f.read()).decode("utf-8")
            return encoded, mime_type
    except Exception as exc:
        print(f"Warning: failed reading image {path}: {exc}")
        return None


def decode_bom_code(bom_code: str, bom_type: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    将 22 位 BOM 编码解析成可读的段位信息与上下文文本。
    返回示例：
    {
        "bom_type": "outdoor",
        "segments": [
            {"key": "shellColor", "label": "第1位：缸体颜色", "value": "A", "meaning": "珍珠白"},
            ...
        ],
        "context_text": "第1位：缸体颜色: A（珍珠白）\n..."
    }
    """
    if not bom_code:
        return None
    code = bom_code.strip()
    if not code:
        return None

    candidate_types = [bom_type] if bom_type in BOM_TYPES else BOM_TYPES

    for candidate in candidate_types:
        sections = get_bom_sections(candidate)
        idx = 0
        segments: List[Dict[str, Any]] = []
        success = True

        for section in sections:
            if section.get("children"):
                for child in section["children"]:
                    digits = child.get("digits") or 0
                    if digits <= 0 or idx + digits > len(code):
                        success = False
                        break
                    value = code[idx : idx + digits]
                    idx += digits
                    options = child.get("options") or {}
                    meaning = options.get(value)
                    segments.append(
                        {
                            "key": child["key"],
                            "label": child["label"],
                            "value": value,
                            "meaning": meaning,
                        }
                    )
                if not success:
                    break
            else:
                digits = section.get("digits") or 0
                if digits <= 0 or idx + digits > len(code):
                    success = False
                    break
                value = code[idx : idx + digits]
                idx += digits
                options = section.get("options") or {}
                meaning = options.get(value)
                segments.append(
                    {
                        "key": section["key"],
                        "label": section["label"],
                        "value": value,
                        "meaning": meaning,
                    }
                )

        if not success:
            continue

        context_lines = []
        for seg in segments:
            line = f"{seg['label']}: {seg['value']}"
            if seg.get("meaning"):
                line += f"（{seg['meaning']}）"
            context_lines.append(line)

        return {
            "bom_type": candidate,
            "segments": segments,
            "context_text": "\n".join(context_lines),
        }

    return None


def _strip_resource_index_block(text: str) -> str:
    if not text:
        return text
    match = re.search(r"(?m)^\s*\[image_embedded\]\s", text)
    if not match:
        return text
    return text[: match.start()].rstrip()


def _sanitize_ocr_markdown_text(text: str) -> str:
    if not text:
        return text
    text = _strip_resource_index_block(text)

    lines = text.splitlines()
    out_lines: List[str] = []
    last_file_marker: Optional[str] = None
    has_content_since_last_file_marker = True

    file_line_re = re.compile(r"^\s*\[file\]\s+(.+?)\s*$")
    md_image_line_re = re.compile(r"^\s*!\[[^\]]*\]\([^)]+\)\s*$")

    for raw_line in lines:
        line = raw_line.rstrip()
        if not line.strip():
            out_lines.append("")
            continue

        if md_image_line_re.match(line) or re.search(r"<\s*img\b", line, flags=re.IGNORECASE):
            continue

        m = file_line_re.match(line)
        if m:
            marker = m.group(1).strip()
            if marker == last_file_marker and not has_content_since_last_file_marker:
                continue
            out_lines.append(f"[file] {marker}")
            last_file_marker = marker
            has_content_since_last_file_marker = False
            continue

        out_lines.append(line)
        has_content_since_last_file_marker = True

    sanitized = "\n".join(out_lines)
    sanitized = re.sub(r"\n{3,}", "\n\n", sanitized)
    return sanitized.strip()


def _build_context_from_ocr_documents(
    documents: List[SpecsheetOcrDocument],
) -> Tuple[str, List[Dict[str, Any]], List[Dict[str, str]]]:
    context_parts: List[str] = []
    pseudo_chunks: List[Dict[str, Any]] = []
    multimodal_segments: List[Dict[str, str]] = []

    # 保留 .mmd 和图片（用于候选产品图），其余过滤
    def is_allowed(doc: SpecsheetOcrDocument) -> bool:
        path = (doc.path or "").lower()
        name = (doc.name or "").lower()
        target = path or name
        return target.endswith(".mmd") or target.endswith((".png", ".jpg", ".jpeg", ".webp"))

    def is_raw_upload(doc: SpecsheetOcrDocument) -> bool:
        path = (doc.path or "").replace("\\", "/")
        return path.startswith("manual_uploads/")

    def is_prompt_reversed_image(doc_path: str | None) -> bool:
        if not doc_path:
            return False
        normalized = doc_path.replace("\\", "/")
        if "/images/" not in normalized:
            return False
        p = Path(normalized)
        if p.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp"}:
            return False
        reverse_txt = _read_text_from_backend((p.parent / f"{p.stem}.txt").as_posix())
        return bool(reverse_txt and reverse_txt.strip())

    for idx, doc in enumerate(documents, 1):
        if not is_allowed(doc):
            continue
        if is_raw_upload(doc):
            continue
        owner = doc.type or f"OCR文档{idx}"
        header = f"[{owner}] {doc.name or doc.path or owner}"
        mime_type = doc.mime_type or (mimetypes.guess_type(doc.path or "")[0] if doc.path else None)
        is_image = bool(mime_type and mime_type.startswith("image/"))

        if is_image:
            if doc.path and is_prompt_reversed_image(doc.path):
                p = Path(doc.path.replace("\\", "/"))
                reverse_txt = _read_text_from_backend((p.parent / f"{p.stem}.txt").as_posix())
                if reverse_txt and len(reverse_txt) > 800:
                    reverse_txt = reverse_txt[:800] + "..."
                candidate_desc = (reverse_txt or "").strip()
                public_path = doc.path if doc.path.startswith("/api/files/") else f"/api/files/{doc.path}"
                multimodal_segments.append(
                    {
                        "description": candidate_desc,
                        "image_path": public_path,
                        "mime_type": mime_type,
                    }
                )
            continue

        # 构造上下文文本：图片不再读二进制，仅引用占位
        summary_text = doc.summary or ("" if is_image else doc.text) or ""
        file_text = "" if is_image else (doc.text or _read_text_from_backend(doc.path))
        summary_text = _sanitize_ocr_markdown_text(summary_text)
        file_text = _sanitize_ocr_markdown_text(file_text)
        body_parts = []
        if summary_text:
            body_parts.append(summary_text)
        if file_text and file_text != summary_text:
            body_parts.append(file_text)
        if not body_parts:
            body_parts.append(f"[{mime_type or 'file'}] {doc.path or doc.name or owner}")

        chunk_text = header + "\n" + "\n".join(body_parts)
        context_parts.append(chunk_text)
        pseudo_chunks.append(
            {
                "text": chunk_text,
                "source_path": doc.path or doc.name or owner,
                "similarity": 1.0,
            }
        )

    return "\n\n".join(context_parts), pseudo_chunks, multimodal_segments


def get_specsheet_from_provided_docs(
    product_name: str,
    bom_version: str,
    request: SpecsheetFromDocsRequest,
):
    context_text, pseudo_chunks = _build_context_from_docs(
        request.product_docs,
        request.accessory_docs,
    )

    if not context_text.strip():
        raise ValueError("未提供可用于生成的文档内容")

    config_text_zh, accessory_glossary_text = _get_product_config_and_accessory_glossary(
        product_name,
        bom_version,
    )

    specsheet_data, chunks, _prompt_text, _system_prompt_unused = _extract_specsheet_from_context(
        context_text,
        pseudo_chunks,
        title_hint=f"{product_name} {bom_version}".strip(),
        config_text_zh=config_text_zh,
        accessory_glossary_text=accessory_glossary_text,
    )
    return specsheet_data, chunks


def generate_specsheet_from_ocr_request(
    request: SpecsheetFromOcrRequest,
) -> Tuple[SpecsheetData, List[Dict[str, Any]], str, str, str]:
    context_text, pseudo_chunks, multimodal_segments = _build_context_from_ocr_documents(request.documents)

    # Prepend original uploaded product images as better candidates than OCR artifacts.
    if getattr(request, "session_id", None):
        try:
            from src.manual_ocr import load_session_record, session_dir  # local import to avoid heavy deps at import-time

            record = load_session_record(request.session_id)
            if record:
                base_dir = session_dir(request.session_id)
                out_dir = base_dir / "reverse_prompts" / "products"
                orig_segments: List[Dict[str, str]] = []
                seen = set()
                for f in (record.get("product_files") or []):
                    try:
                        rel = (f.get("path") or "").strip()
                        if not rel:
                            continue
                        suffix = Path(rel).suffix.lower()
                        if suffix not in {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"}:
                            continue
                        public_path = rel if rel.startswith("/api/files/") else f"/api/files/{rel}"
                        if public_path in seen:
                            continue
                        seen.add(public_path)
                        desc = ""
                        try:
                            txt_path = out_dir / f"{Path(rel).stem}.txt"
                            if txt_path.exists() and txt_path.is_file():
                                desc = (txt_path.read_text(encoding="utf-8") or "").strip()
                        except Exception:
                            desc = ""
                        mime = (f.get("type") or "").strip() or mimetypes.guess_type(rel)[0] or "image/*"
                        orig_segments.append(
                            {
                                "description": desc,
                                "image_path": public_path,
                                "mime_type": mime,
                                "source": "original_upload",
                            }
                        )
                    except Exception:
                        continue
                if orig_segments:
                    multimodal_segments = orig_segments + [
                        {**seg, "source": seg.get("source") or "ocr_artifact"}
                        for seg in (multimodal_segments or [])
                    ]
        except Exception:
            # Best-effort only; keep existing OCR-derived candidates.
            pass

    # 将 BOM 解析信息也加入上下文，帮助 LLM 获得配件配置
    bom_context = None
    bom_context_text = ""
    if request.bom_code:
        bom_context = decode_bom_code(request.bom_code, getattr(request, "bom_type", None))
        if bom_context:
            bom_context_text = bom_context.get("context_text") or ""
            if bom_context_text.strip():
                pseudo_chunks.append(
                    {
                        "text": bom_context_text,
                        "source_path": f"BOM-{bom_context.get('bom_type') or 'unknown'}",
                        "similarity": 1.0,
                    }
                )

    # 无 OCR 文档时允许仅凭 BOM 生成
    if not context_text.strip():
        if bom_context_text.strip():
            context_text = bom_context_text
        else:
            raise ValueError("未提供可用于生成的 OCR 文档内容")

    bom_summary = _summarize_bom(bom_context if request.bom_code else None)
    doc_summary = _summarize_docs(request.documents)
    if not (request.documents or []):
        doc_summary = "未提供 OCR 文档，仅使用 BOM 配置生成"

    ref_accessories_text = None

    config_text_zh, accessory_glossary_text = _get_product_config_and_accessory_glossary(
        request.product_name,
        request.bom_code,
    )

    # 使用产品名/BOM 号作为标题提示，帮助 LLM 生成更贴近的称呼
    title_hint = request.product_name or request.bom_code or "Generated Specsheet"

    specsheet_data, chunks, prompt_text, system_prompt = _extract_specsheet_from_context(
        context_text,
        pseudo_chunks,
        title_hint=title_hint,
        multimodal_segments=multimodal_segments,
        bom_summary=bom_summary,
        doc_summary=doc_summary,
        ref_accessories_text=ref_accessories_text,
        config_text_zh=config_text_zh,
        accessory_glossary_text=accessory_glossary_text,
        llm_provider=getattr(request, "llm_provider", None),
        llm_model=getattr(request, "llm_model", None),
    )
    # 强制使用传入的产品名作为 productTitle
    if request.product_name:
        specsheet_data.productTitle = request.product_name

    return specsheet_data, chunks, prompt_text, system_prompt, context_text


def save_specsheet_for_product_bom(
    product_name: str,
    bom_version: str,
    specsheet_payload: Union[SpecsheetData, Dict[str, Any]],
) -> SpecsheetData:
    """Persist a validated specsheet JSON onto the product node."""

    if isinstance(specsheet_payload, SpecsheetData):
        specsheet_data = specsheet_payload
    else:
        specsheet_data = SpecsheetData(**specsheet_payload)

    serialized = json.dumps(specsheet_data.dict(), ensure_ascii=False)

    neo4j_config = get_neo4j_config()
    driver = get_neo4j_driver(neo4j_config)

    try:
        with driver.session() as session:
            record = session.run(
                """
                MATCH (p:Product {english_name: $product_name, bom_version: $bom_version})
                SET p.specsheet_json = $specsheet_json,
                    p.specsheet_updated_at = datetime({timezone: 'UTC'})
                RETURN p.english_name AS english_name
                """,
                {
                    "product_name": product_name,
                    "bom_version": bom_version,
                    "specsheet_json": serialized,
                },
            ).single()

            if not record:
                raise ValueError(
                    f"Product '{product_name}' with BOM '{bom_version}' not found"
                )
    finally:
        driver.close()

    return specsheet_data


def get_default_specsheet(product_title: Optional[str] = None) -> SpecsheetData:
    """Get default specsheet data when RAG query fails or returns no results."""
    title = product_title or "OCR Generated Specsheet"
    return SpecsheetData(
        productTitle=title,
        features={
            "capacity": "1",
            "jets": "0",
            "pumps": "2"
        },
        measurements='70" × 33" × 37"',
        premiumFeatures=["LED Jet Illumination", "Underwater Mood Lighting"],
        insulationFeatures=["Polyfoam Insulation", "Triple-Layered Side Insulation"],
        extraFeatures=["Bluetooth Audio System", "Heater/Chiller Ready"],
        Specifications=[
            {"Cabinet Color": ["#c4c4c4", "#666666"]},
            {"Shell Color": "#c4c4c4"},
            {"Dry Weight": "293 lbs"},
            {"Water Capacity": "79 gallons"},
            {"Pump": "1 x Chiller"},
            {"Controls": "Joyonway Touch Screen"}
        ],
        smartWater=["Ozonator", "Filtration System", "Circulation Pump *"],
        images={
            "product": "/back/product.png",
            "background": "/back/back.png"
        }
    )


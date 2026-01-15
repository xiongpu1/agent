"""
Neo4j query helper functions for API endpoints.
References existing functions from main.py and neo4j_file_add_neo4j.py.
"""
import hashlib
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import quote
from typing import List, Dict, Optional, Any, Iterable
from dotenv import load_dotenv
from neo4j import GraphDatabase

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.dataclass import Neo4jConfig, LLMConfig
from src.models_litellm import Ollama_BASE_URL, Ollama_QWEN3_EMBEDDING
from src.neo4j_file_add_neo4j import (
    get_neo4j_driver,
    md_chunker,
    embed_texts,
    create_chunk_nodes,
    create_unknown_node,
)

load_dotenv()

# Backend root directory for resolving stored document paths
BACKEND_ROOT = Path(__file__).resolve().parent.parent

MATERIAL_IMAGES_DIR = BACKEND_ROOT / "material_images"


def _encode_url_path(p: str) -> str:
    segs = [quote(s) for s in str(p).split("/")]
    return "/".join(segs)


def _material_image_url_from_path(stored_path: str | None) -> str:
    raw = (stored_path or "").strip()
    if not raw:
        return ""

    if raw.startswith("/static/material_images/"):
        return _encode_url_path(raw)

    normalized = raw.replace("\\", "/")
    marker = "/material_images/"
    if marker in normalized:
        idx = normalized.rfind(marker)
        rel = normalized[idx + len(marker) :].lstrip("/")
        if rel:
            return _encode_url_path(f"/static/material_images/{rel}")

    try:
        p = Path(raw)
        if p.is_absolute() and MATERIAL_IMAGES_DIR in p.parents:
            rel = p.relative_to(MATERIAL_IMAGES_DIR)
            return _encode_url_path(f"/static/material_images/{rel.as_posix()}")
    except Exception:
        pass

    return ""


def get_material_image_by_material_code(material_code: str) -> Dict[str, Any]:
    mc = (material_code or "").strip()
    if not mc:
        return {"material_code": "", "found": False, "image_url": "", "score": None, "sheet": ""}

    neo4j_config = get_neo4j_config()
    driver = get_neo4j_driver(neo4j_config)
    try:
        with driver.session() as session:
            res = session.run(
                """
                MATCH (m:Material {material_code: $material_code})
                OPTIONAL MATCH (m)-[r:HAS_IMAGE]->(img:MaterialImage)
                RETURN img.path AS rel_path, m.image AS legacy_path, r.score AS score, r.sheet AS sheet
                ORDER BY coalesce(r.score, 0.0) DESC
                LIMIT 1
                """,
                {"material_code": mc},
            )
            record = res.single()
            if not record:
                return {"material_code": mc, "found": False, "image_url": "", "score": None, "sheet": ""}

            rel_path = record.get("rel_path")
            legacy_path = record.get("legacy_path")
            chosen_path = rel_path if rel_path else legacy_path
            url = _material_image_url_from_path(str(chosen_path) if chosen_path else "")
            if not url:
                fallback_score = record.get("score")
                if fallback_score is None and legacy_path:
                    fallback_score = 1.0
                return {
                    "material_code": mc,
                    "found": False,
                    "image_url": "",
                    "score": fallback_score,
                    "sheet": str(record.get("sheet") or ""),
                }

            return {
                "material_code": mc,
                "found": True,
                "image_url": url,
                "score": record.get("score") if rel_path else (1.0 if legacy_path else None),
                "sheet": str(record.get("sheet") or ""),
            }
    finally:
        driver.close()


def get_product_image_by_product_name(product_name: str) -> Dict[str, Any]:
    pn = (product_name or "").strip()
    if not pn:
        return {"product_name": "", "found": False, "image_url": ""}

    if not MATERIAL_IMAGES_DIR.exists() or not MATERIAL_IMAGES_DIR.is_dir():
        return {"product_name": pn, "found": False, "image_url": ""}

    allowed_exts = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".svg"}
    ext_priority = {
        ".png": 0,
        ".jpg": 1,
        ".jpeg": 2,
        ".webp": 3,
        ".gif": 4,
        ".bmp": 5,
        ".svg": 6,
    }

    target = pn.casefold()
    best_path: Path | None = None
    best_rank = 10**9
    for p in MATERIAL_IMAGES_DIR.rglob("*"):
        if not p.is_file():
            continue
        ext = p.suffix.lower()
        if ext not in allowed_exts:
            continue
        if p.stem.casefold() != target:
            continue
        rank = ext_priority.get(ext, 10**8)
        if rank < best_rank:
            best_rank = rank
            best_path = p
            if best_rank == 0:
                break

    if not best_path:
        return {"product_name": pn, "found": False, "image_url": ""}

    try:
        rel = best_path.relative_to(MATERIAL_IMAGES_DIR).as_posix()
    except Exception:
        return {"product_name": pn, "found": False, "image_url": ""}

    url = _encode_url_path(f"/static/material_images/{rel}")
    return {"product_name": pn, "found": True, "image_url": url}


def upsert_manual_dataset(
    *,
    product_id: str,
    dataset_id: str,
    source: str,
    created_at: str | None = None,
) -> None:
    pid = (product_id or "").strip()
    did = (dataset_id or "").strip()
    if not pid or not did:
        return

    neo4j_config = get_neo4j_config()
    driver = get_neo4j_driver(neo4j_config)
    try:
        with driver.session() as session:
            session.run(
                """
                MATCH (p:Product {product_id: $product_id})
                MERGE (ds:Dataset {dataset_id: $dataset_id})
                ON CREATE SET ds.created_at = CASE WHEN $created_at IS NULL OR $created_at = '' THEN datetime({timezone: 'UTC'}) ELSE datetime($created_at) END
                SET ds.source = $source
                MERGE (p)-[:HAS_DATASET]->(ds)
                """,
                {
                    "product_id": pid,
                    "dataset_id": did,
                    "source": source,
                    "created_at": created_at,
                },
            )
    finally:
        driver.close()


def upsert_manual_folder(*, dataset_id: str, folder_path: str, kind: str) -> None:
    did = (dataset_id or "").strip()
    fpath = (folder_path or "").strip()
    if not did or not fpath:
        return

    neo4j_config = get_neo4j_config()
    driver = get_neo4j_driver(neo4j_config)
    try:
        with driver.session() as session:
            session.run(
                """
                MATCH (ds:Dataset {dataset_id: $dataset_id})
                MERGE (f:Folder {path: $folder_path})
                SET f.kind = $kind
                MERGE (ds)-[:HAS_FOLDER]->(f)
                """,
                {
                    "dataset_id": did,
                    "folder_path": fpath,
                    "kind": kind,
                },
            )
    finally:
        driver.close()


def upsert_manual_document(
    *,
    doc_path: str,
    name: str | None = None,
    mime_type: str | None = None,
    doc_kind: str | None = None,
    created_at: str | None = None,
    parent_raw_path: str | None = None,
    source_name: str | None = None,
    page_number: int | None = None,
) -> None:
    dpath = (doc_path or "").strip()
    if not dpath:
        return

    neo4j_config = get_neo4j_config()
    driver = get_neo4j_driver(neo4j_config)
    try:
        with driver.session() as session:
            session.run(
                """
                MERGE (d:Document {path: $path})
                ON CREATE SET d.created_at = CASE WHEN $created_at IS NULL OR $created_at = '' THEN datetime({timezone: 'UTC'}) ELSE datetime($created_at) END
                SET d.name = coalesce($name, d.name),
                    d.mime_type = coalesce($mime_type, d.mime_type),
                    d.doc_kind = coalesce($doc_kind, d.doc_kind),
                    d.parent_raw_path = CASE WHEN $parent_raw_path IS NULL OR $parent_raw_path = '' THEN d.parent_raw_path ELSE $parent_raw_path END,
                    d.source_name = CASE WHEN $source_name IS NULL OR $source_name = '' THEN d.source_name ELSE $source_name END,
                    d.page_number = CASE WHEN $page_number IS NULL THEN d.page_number ELSE $page_number END
                """,
                {
                    "path": dpath,
                    "name": name,
                    "mime_type": mime_type,
                    "doc_kind": doc_kind,
                    "created_at": created_at,
                    "parent_raw_path": parent_raw_path,
                    "source_name": source_name,
                    "page_number": page_number,
                },
            )
    finally:
        driver.close()


def upsert_manual_contains(*, folder_path: str, doc_path: str) -> None:
    fpath = (folder_path or "").strip()
    dpath = (doc_path or "").strip()
    if not fpath or not dpath:
        return

    neo4j_config = get_neo4j_config()
    driver = get_neo4j_driver(neo4j_config)
    try:
        with driver.session() as session:
            session.run(
                """
                MATCH (f:Folder {path: $folder_path})
                MATCH (d:Document {path: $doc_path})
                MERGE (f)-[:CONTAINS]->(d)
                """,
                {"folder_path": fpath, "doc_path": dpath},
            )
    finally:
        driver.close()


def delete_manual_contains_and_gc_document(*, folder_path: str, doc_path: str) -> None:
    """Remove CONTAINS edge and delete Document if it has no remaining CONTAINS refs."""

    fpath = (folder_path or "").strip()
    dpath = (doc_path or "").strip()
    if not fpath or not dpath:
        return

    neo4j_config = get_neo4j_config()
    driver = get_neo4j_driver(neo4j_config)
    try:
        with driver.session() as session:
            session.run(
                """
                MATCH (f:Folder {path: $folder_path})-[r:CONTAINS]->(d:Document {path: $doc_path})
                DELETE r
                """,
                {"folder_path": fpath, "doc_path": dpath},
            )

            session.run(
                """
                MATCH (d:Document {path: $doc_path})
                WITH d, size([(f:Folder)-[:CONTAINS]->(d) | f]) AS ref_count
                WHERE ref_count = 0
                DETACH DELETE d
                """,
                {"doc_path": dpath},
            )
    finally:
        driver.close()


def get_neo4j_config() -> Neo4jConfig:
    """Get Neo4j configuration from environment variables."""
    return Neo4jConfig(
        uri=os.getenv("NEO4J_URI"),
        user=os.getenv("NEO4J_USER"),
        password=os.getenv("NEO4J_PASSWORD")
    )


def get_all_product_names() -> List[Dict[str, Any]]:
    """
    Get all unique product English names from Neo4j.
    
    Returns:
        List of unique product English names, sorted alphabetically.
    """
    neo4j_config = get_neo4j_config()
    driver = get_neo4j_driver(neo4j_config)
    
    products: List[Dict[str, Any]] = []
    try:
        with driver.session() as session:
            result = session.run(
                """
                MATCH (p:Product)
                WHERE p.product_id IS NOT NULL AND p.product_id <> ''
                RETURN DISTINCT
                    p.product_id AS product_id,
                    coalesce(p.display_name_en, '') AS display_name_en,
                    coalesce(p.display_name_zh, '') AS display_name_zh,
                    coalesce(p.material_code, '') AS material_code,
                    coalesce(p.bom_id, '') AS bom_id,
                    coalesce(p.product_type_zh, '') AS product_type_zh
                ORDER BY p.product_id
                """
            )
            
            for record in result:
                product_id = record["product_id"]
                if not product_id:
                    continue
                products.append(
                    {
                        "product_id": product_id,
                        "display_name_en": record.get("display_name_en") or "",
                        "display_name_zh": record.get("display_name_zh") or "",
                        "material_code": record.get("material_code") or "",
                        "bom_id": record.get("bom_id") or "",
                        "product_type_zh": record.get("product_type_zh") or "",
                    }
                )
    finally:
        driver.close()

    return products


def get_boms_by_product_id(product_id: str) -> List[str]:
    """Get BOM ids for a specific product_id."""
    neo4j_config = get_neo4j_config()
    driver = get_neo4j_driver(neo4j_config)

    boms: List[str] = []
    pid = (product_id or "").strip()
    if not pid:
        return []

    try:
        with driver.session() as session:
            result = session.run(
                """
                MATCH (p:Product {product_id: $product_id})
                RETURN DISTINCT p.bom_id AS bom_id
                ORDER BY bom_id
                """,
                {"product_id": pid},
            )
            for record in result:
                bom_id = record.get("bom_id")
                if bom_id:
                    boms.append(str(bom_id))
    finally:
        driver.close()

    return boms


def get_all_material_codes() -> List[str]:
    """Get all unique material_code values."""
    neo4j_config = get_neo4j_config()
    driver = get_neo4j_driver(neo4j_config)

    materials: List[str] = []
    try:
        with driver.session() as session:
            result = session.run(
                """
                MATCH (m:Material)
                WHERE m.material_code IS NOT NULL AND m.material_code <> ''
                RETURN DISTINCT m.material_code AS material_code
                ORDER BY material_code
                """
            )
            for record in result:
                code = record.get("material_code")
                if code:
                    materials.append(str(code))
    finally:
        driver.close()

    return materials


def get_boms_by_material_code(material_code: str) -> List[str]:
    """List bom_id values for a given material_code."""
    mc = (material_code or "").strip()
    if not mc:
        return []

    neo4j_config = get_neo4j_config()
    driver = get_neo4j_driver(neo4j_config)

    boms: List[str] = []
    try:
        with driver.session() as session:
            result = session.run(
                """
                MATCH (m:Material {material_code: $material_code})-[:HAS_PRODUCT]->(p:Product)
                WHERE p.bom_id IS NOT NULL AND p.bom_id <> ''
                RETURN DISTINCT p.bom_id AS bom_id
                ORDER BY bom_id
                """,
                {"material_code": mc},
            )
            for record in result:
                bom_id = record.get("bom_id")
                if bom_id:
                    boms.append(str(bom_id))
    finally:
        driver.close()

    return boms


def get_accessories_zh_by_material_bom(material_code: str, bom_id: str) -> List[str]:
    """List accessory Chinese names for a given material_code + bom_id."""
    mc = (material_code or "").strip()
    bid = (bom_id or "").strip()
    if not mc or not bid:
        return []

    neo4j_config = get_neo4j_config()
    driver = get_neo4j_driver(neo4j_config)

    names: List[str] = []
    try:
        with driver.session() as session:
            result = session.run(
                """
                MATCH (p:Product {material_code: $material_code, bom_id: $bom_id})-[:USES_BOM]->(b:BOM {bom_id: $bom_id})
                MATCH (b)-[r:HAS_ACCESSORY]->(a:Accessory)
                RETURN r.order AS ord, a.name_zh AS name_zh
                ORDER BY ord ASC, name_zh ASC
                """,
                {"material_code": mc, "bom_id": bid},
            )
            seen = set()
            for record in result:
                zh = record.get("name_zh")
                if not zh:
                    continue
                zh_s = str(zh)
                if zh_s in seen:
                    continue
                seen.add(zh_s)
                names.append(zh_s)

            if not names:
                fallback = session.run(
                    """
                    MATCH (p:Product {material_code: $material_code, bom_id: $bom_id})
                    MATCH (p)-[r:HAS_ACCESSORY]->(a:Accessory)
                    RETURN r.order AS ord, a.name_zh AS name_zh
                    ORDER BY ord ASC, name_zh ASC
                    """,
                    {"material_code": mc, "bom_id": bid},
                )
                seen = set()
                for record in fallback:
                    zh = record.get("name_zh")
                    if not zh:
                        continue
                    zh_s = str(zh)
                    if zh_s in seen:
                        continue
                    seen.add(zh_s)
                    names.append(zh_s)
    finally:
        driver.close()

    return names


def get_accessories_by_product_bom_id(product_id: str, bom_id: str) -> List[str]:
    """Get accessories connected to a product_id. bom_id is used as a safety filter."""
    neo4j_config = get_neo4j_config()
    driver = get_neo4j_driver(neo4j_config)

    pid = (product_id or "").strip()
    bid = (bom_id or "").strip()
    if not pid or not bid:
        return []

    accessories: List[str] = []
    try:
        with driver.session() as session:
            result = session.run(
                """
                MATCH (p:Product {product_id: $product_id, bom_id: $bom_id})-[:USES_BOM]->(b:BOM {bom_id: $bom_id})
                MATCH (b)-[r:HAS_ACCESSORY]->(a:Accessory)
                RETURN r.order AS ord, coalesce(a.name, a.name_zh, '') AS name
                ORDER BY ord ASC, name ASC
                """,
                {"product_id": pid, "bom_id": bid},
            )
            seen = set()
            for record in result:
                name = record.get("name")
                if not name:
                    continue
                name_s = str(name)
                if name_s in seen:
                    continue
                seen.add(name_s)
                accessories.append(name_s)

            if not accessories:
                fallback = session.run(
                    """
                    MATCH (p:Product {product_id: $product_id, bom_id: $bom_id})
                    MATCH (p)-[r:HAS_ACCESSORY]->(a:Accessory)
                    RETURN r.order AS ord, coalesce(a.name, a.name_zh, '') AS name
                    ORDER BY ord ASC, name ASC
                    """,
                    {"product_id": pid, "bom_id": bid},
                )
                seen = set()
                for record in fallback:
                    name = record.get("name")
                    if not name:
                        continue
                    name_s = str(name)
                    if name_s in seen:
                        continue
                    seen.add(name_s)
                    accessories.append(name_s)
    finally:
        driver.close()

    return accessories


def get_kb_overview_by_product_id(product_id: str) -> Dict[str, Any]:
    """Return grouped documents for KB overview using new Dataset/Folder/Document schema."""

    pid = (product_id or "").strip()
    if not pid:
        return {"product": {"product_id": ""}, "special_docs": {}, "datasets": []}

    neo4j_config = get_neo4j_config()
    driver = get_neo4j_driver(neo4j_config)

    special_docs: Dict[str, Dict[str, Any]] = {}
    datasets_by_id: Dict[str, Dict[str, Any]] = {}
    product_meta: Dict[str, Any] = {"product_id": pid}
    product_config: Dict[str, Any] = {"config_text_zh": ""}

    try:
        with driver.session() as session:
            prod = session.run(
                """
                MATCH (p:Product {product_id: $product_id})
                RETURN p.product_id AS product_id,
                       coalesce(p.material_code, '') AS material_code,
                       coalesce(p.bom_id, '') AS bom_id,
                       coalesce(p.display_name_en, '') AS display_name_en,
                       coalesce(p.display_name_zh, '') AS display_name_zh,
                       coalesce(p.product_type_zh, '') AS product_type_zh
                """,
                {"product_id": pid},
            ).single()
            if prod:
                product_meta = {
                    "product_id": prod.get("product_id") or pid,
                    "material_code": prod.get("material_code") or "",
                    "bom_id": prod.get("bom_id") or "",
                    "display_name_en": prod.get("display_name_en") or "",
                    "display_name_zh": prod.get("display_name_zh") or "",
                    "product_type_zh": prod.get("product_type_zh") or "",
                }

            cfg = session.run(
                """
                MATCH (p:Product {product_id: $product_id})
                OPTIONAL MATCH (p)-[:HAS_CONFIG]->(pc:ProductConfig)
                RETURN coalesce(pc.config_text_zh, '') AS config_text_zh
                """,
                {"product_id": pid},
            ).single()
            if cfg:
                product_config = {"config_text_zh": cfg.get("config_text_zh") or ""}

            docs = session.run(
                """
                MATCH (p:Product {product_id: $product_id})
                OPTIONAL MATCH (p)-[hd:HAS_DOC]->(d:Document)
                WITH hd, d
                WHERE d IS NOT NULL
                RETURN coalesce(hd.role, '') AS role,
                       d.path AS path,
                       coalesce(d.name, '') AS name,
                       coalesce(d.mime_type, '') AS mime_type,
                       coalesce(d.doc_kind, '') AS doc_kind,
                       d.created_at AS created_at
                """,
                {"product_id": pid},
            )
            for record in docs:
                role = (record.get("role") or "").strip()
                if role not in {"specsheet", "manual", "poster"}:
                    continue
                path = record.get("path")
                if not path:
                    continue
                special_docs[role] = {
                    "role": role,
                    "path": path,
                    "name": record.get("name") or os.path.basename(str(path)),
                    "mime_type": record.get("mime_type") or "",
                    "doc_kind": record.get("doc_kind") or "",
                    "created_at": record.get("created_at"),
                }

            # Fallback: if special docs are not yet linked in Neo4j, load from on-disk truth outputs.
            # This supports workflows where manual/specsheet JSON is stored under manual_ocr_results/<product_id>/truth.
            try:
                truth_dir = (BACKEND_ROOT / "manual_ocr_results" / pid / "truth").resolve()
                truth_dir.relative_to(BACKEND_ROOT.resolve())
            except Exception:
                truth_dir = None

            if truth_dir and truth_dir.exists() and truth_dir.is_dir():
                if "manual" not in special_docs:
                    manual_truth = truth_dir / "manual_book.json"
                    if manual_truth.exists() and manual_truth.is_file():
                        rel = manual_truth.resolve().relative_to(BACKEND_ROOT.resolve()).as_posix()
                        special_docs["manual"] = {
                            "role": "manual",
                            "path": rel,
                            "name": manual_truth.name,
                            "mime_type": "application/json",
                            "doc_kind": "manual_book",
                            "created_at": None,
                        }

                if "specsheet" not in special_docs:
                    spec_truth = truth_dir / "specsheet.json"
                    if spec_truth.exists() and spec_truth.is_file():
                        rel = spec_truth.resolve().relative_to(BACKEND_ROOT.resolve()).as_posix()
                        special_docs["specsheet"] = {
                            "role": "specsheet",
                            "path": rel,
                            "name": spec_truth.name,
                            "mime_type": "application/json",
                            "doc_kind": "specsheet",
                            "created_at": None,
                        }

            rows = session.run(
                """
                MATCH (p:Product {product_id: $product_id})
                OPTIONAL MATCH (p)-[:HAS_DATASET]->(ds:Dataset)
                OPTIONAL MATCH (ds)-[:HAS_FOLDER]->(f:Folder)
                OPTIONAL MATCH (f)-[:CONTAINS]->(doc:Document)
                RETURN coalesce(ds.dataset_id, '') AS dataset_id,
                       coalesce(ds.source, '') AS source,
                       ds.created_at AS dataset_created_at,
                       coalesce(f.path, '') AS folder_path,
                       coalesce(f.kind, '') AS folder_kind,
                       coalesce(doc.path, '') AS doc_path,
                       coalesce(doc.name, '') AS doc_name,
                       coalesce(doc.mime_type, '') AS doc_mime_type,
                       coalesce(doc.doc_kind, '') AS doc_kind,
                       doc.created_at AS doc_created_at,
                       coalesce(doc.parent_raw_path, '') AS parent_raw_path,
                       coalesce(doc.source_name, '') AS source_name,
                       coalesce(doc.page_number, 0) AS page_number
                """,
                {"product_id": pid},
            )

            for record in rows:
                dataset_id = (record.get("dataset_id") or "").strip()
                if not dataset_id:
                    continue

                ds_entry = datasets_by_id.get(dataset_id)
                if not ds_entry:
                    ds_entry = {
                        "dataset_id": dataset_id,
                        "source": record.get("source") or "",
                        "created_at": record.get("dataset_created_at"),
                        "folders": {
                            "product_raw": [],
                            "accessory_raw": [],
                            "product_ocr": [],
                            "accessory_ocr": [],
                        },
                    }
                    datasets_by_id[dataset_id] = ds_entry

                folder_kind = (record.get("folder_kind") or "").strip()
                if folder_kind not in ds_entry["folders"]:
                    continue

                doc_path = record.get("doc_path")
                if not doc_path:
                    continue
                ds_entry["folders"][folder_kind].append(
                    {
                        "path": doc_path,
                        "name": record.get("doc_name") or os.path.basename(str(doc_path)),
                        "mime_type": record.get("doc_mime_type") or "",
                        "doc_kind": record.get("doc_kind") or "",
                        "created_at": record.get("doc_created_at"),
                        "folder_path": record.get("folder_path") or "",
                        "parent_raw_path": record.get("parent_raw_path") or "",
                        "source_name": record.get("source_name") or "",
                        "page_number": int(record.get("page_number") or 0),
                    }
                )
    finally:
        driver.close()

    return {
        "product": product_meta,
        "product_config": product_config,
        "special_docs": special_docs,
        "datasets": list(datasets_by_id.values()),
    }


def update_product_config_text_zh(product_id: str, config_text_zh: str) -> Dict[str, Any]:
    pid = (product_id or "").strip()
    if not pid:
        raise ValueError("product_id 不能为空")

    text = (config_text_zh or "").strip()

    neo4j_config = get_neo4j_config()
    driver = get_neo4j_driver(neo4j_config)
    try:
        with driver.session() as session:
            record = session.run(
                """
                MATCH (p:Product {product_id: $product_id})
                MERGE (pc:ProductConfig {product_id: $product_id})
                SET pc.config_text_zh = $config_text_zh,
                    pc.updated_at = datetime({timezone: 'UTC'})
                MERGE (p)-[:HAS_CONFIG]->(pc)
                RETURN pc.config_text_zh AS config_text_zh
                """,
                {"product_id": pid, "config_text_zh": text},
            ).single()

            if not record:
                raise ValueError(f"Product '{pid}' not found")

            return {"product_id": pid, "config_text_zh": record.get("config_text_zh") or ""}
    finally:
        driver.close()


def upsert_product_has_doc(
    *,
    product_id: str,
    role: str,
    doc_path: str,
    name: str | None = None,
    mime_type: str | None = None,
    doc_kind: str | None = None,
) -> Dict[str, Any]:
    pid = (product_id or "").strip()
    if not pid:
        raise ValueError("product_id 不能为空")

    dpath = (doc_path or "").strip().replace("\\", "/").lstrip("/")
    if dpath.startswith("/api/files/"):
        dpath = dpath[len("/api/files/") :].lstrip("/")
    if not dpath:
        raise ValueError("doc_path 不能为空")

    r = (role or "").strip()
    if r not in {"specsheet", "manual", "poster"}:
        raise ValueError("role 必须是 specsheet/manual/poster")

    doc_name = (name or "").strip() or os.path.basename(dpath)
    mt = (mime_type or "").strip()
    dk = (doc_kind or "").strip()

    neo4j_config = get_neo4j_config()
    driver = get_neo4j_driver(neo4j_config)
    try:
        with driver.session() as session:
            record = session.run(
                """
                MATCH (p:Product {product_id: $product_id})
                OPTIONAL MATCH (p)-[old:HAS_DOC {role: $role}]->(:Document)
                DELETE old
                MERGE (d:Document {path: $path})
                SET d.name = $name,
                    d.mime_type = $mime_type,
                    d.doc_kind = $doc_kind,
                    d.updated_at = datetime({timezone: 'UTC'})
                MERGE (p)-[r:HAS_DOC {role: $role}]->(d)
                SET r.updated_at = datetime({timezone: 'UTC'})
                RETURN d.path AS path
                """,
                {
                    "product_id": pid,
                    "role": r,
                    "path": dpath,
                    "name": doc_name,
                    "mime_type": mt,
                    "doc_kind": dk,
                },
            ).single()

            if not record:
                raise ValueError(f"Product '{pid}' not found")

            return {"product_id": pid, "role": r, "path": record.get("path") or dpath}
    finally:
        driver.close()


def _normalize_document_path(path: Optional[str]) -> str:
    if not path:
        return ""
    if isinstance(path, str):
        normalized = path.replace("\\", "/")
    else:
        normalized = str(path)
    if normalized.startswith("/api/files/"):
        normalized = normalized[len("/api/files/") :]
    return normalized.lstrip("/")


def _normalize_document_payload(doc: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if not isinstance(doc, dict):
        return None

    path = (
        doc.get("path")
        or doc.get("relative_path")
        or doc.get("file_path")
        or doc.get("document_path")
    )
    if not path:
        url = doc.get("url")
        if isinstance(url, str):
            path = url
    normalized_path = _normalize_document_path(path)
    if not normalized_path:
        return None

    name = doc.get("name") or doc.get("source_name") or os.path.basename(normalized_path) or "未命名文件"
    summary = doc.get("summary") or doc.get("caption") or ""
    mime_type = (
        doc.get("mime_type")
        or doc.get("mime")
        or (doc.get("type") if isinstance(doc.get("type"), str) and "/" in doc.get("type") else "")
        or ""
    )
    declared = doc.get("type") or doc.get("kind") or doc.get("mime_type") or ""
    doc_type = _classify_document_type(declared, mime_type, normalized_path)

    category = doc.get("category")
    session_id = doc.get("session_id")
    parent_path = _normalize_document_path(doc.get("parent_path")) if doc.get("parent_path") else ""
    page_number = doc.get("page_number")

    payload: Dict[str, Any] = {
        "name": name,
        "path": normalized_path,
        "type": doc_type,
        "summary": summary,
        "mime_type": mime_type,
    }
    if category:
        payload["category"] = category
    if session_id:
        payload["session_id"] = session_id
    if parent_path:
        payload["parent_path"] = parent_path
    if page_number is not None:
        payload["page_number"] = page_number
    return payload


def _classify_document_type(declared: Any, mime_type: str, path: str) -> str:
    declared_str = str(declared or "").strip().lower()
    mime = str(mime_type or "").strip().lower()
    ext = os.path.splitext(path or "")[1].lower()

    office_exts = {
        ".pdf",
        ".doc",
        ".docx",
        ".ppt",
        ".pptx",
        ".xls",
        ".xlsx",
    }

    if declared_str in {"image", "image_embedded", "specsheet", "document", "file"}:
        return declared_str

    if mime.startswith("image/") or ext in {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".svg"}:
        return "image"
    if mime.startswith("application/pdf") or ext in office_exts:
        return "file"
    if mime.startswith("text/") or ext in {".md", ".markdown", ".txt", ".json"}:
        return "document"
    if declared_str == "markdown":
        return "document"
    return "file"


def _sanitize_session_folder(value: str | None) -> str:
    v = (value or "").strip()
    if not v:
        return ""
    cleaned = re.sub(r"[^A-Za-z0-9]+", "_", v)
    cleaned = re.sub(r"_+", "_", cleaned).strip("_")
    return cleaned


def extract_truth_documents(session_id: str) -> List[Dict[str, Any]]:
    """Collect truth files from manual_ocr_results/<session_id>/truth."""

    sid = (session_id or "").strip()
    if not sid:
        return []

    sanitized = _sanitize_session_folder(sid)
    base = BACKEND_ROOT / "manual_ocr_results"
    candidate_dirs = []
    if sanitized:
        candidate_dirs.append(base / sanitized)
    if sid != sanitized:
        candidate_dirs.append(base / sid)

    truth_dir: Path | None = None
    for candidate in candidate_dirs:
        td = candidate / "truth"
        if td.exists() and td.is_dir():
            truth_dir = td
            break
    if not truth_dir:
        return []

    docs: List[Dict[str, Any]] = []
    for entry in sorted(truth_dir.iterdir()):
        if not entry.is_file():
            continue
        try:
            rel = entry.resolve().relative_to(BACKEND_ROOT.resolve()).as_posix()
        except ValueError:
            continue
        normalized = _normalize_document_payload(
            {
                "name": entry.name,
                "path": rel,
                "category": "manual_truth",
                "session_id": sid,
            }
        )
        if normalized:
            docs.append(normalized)
    return docs


def extract_documents_from_session(session_record: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Collect normalized document payloads from a saved manual OCR session."""
    if not session_record:
        return []

    documents: List[Dict[str, Any]] = []

    session_id = (session_record.get("session_id") or "").strip()
    product_files = session_record.get("product_files", []) or []
    accessory_files = session_record.get("accessory_files", []) or []

    def build_parent_lookup(files: List[Dict[str, Any]]) -> Dict[str, str]:
        lookup: Dict[str, str] = {}
        for entry in files:
            if not isinstance(entry, dict):
                continue
            name = (entry.get("name") or entry.get("source_name") or "").strip()
            raw_path = entry.get("path") or entry.get("url")
            normalized_path = _normalize_document_path(raw_path)
            if not name or not normalized_path:
                continue
            lookup[name] = normalized_path
            lookup[name.lower()] = normalized_path
            stem = os.path.splitext(name)[0]
            if stem:
                lookup[stem] = normalized_path
                lookup[stem.lower()] = normalized_path
        return lookup

    product_file_by_name = build_parent_lookup(product_files)
    accessory_file_by_name = build_parent_lookup(accessory_files)

    def push(item: Optional[Dict[str, Any]]) -> None:
        normalized = _normalize_document_payload(item or {})
        if normalized:
            documents.append(normalized)

    def push_with_meta(
        item: Optional[Dict[str, Any]],
        *,
        category: str,
        parent_path: str = "",
        page_number: int | None = None,
    ) -> None:
        if not isinstance(item, dict):
            return
        payload = dict(item)
        payload["category"] = category
        if session_id:
            payload["session_id"] = session_id
        if parent_path:
            payload["parent_path"] = parent_path
        if page_number is not None:
            payload["page_number"] = page_number
        push(payload)

    for entry in product_files:
        push_with_meta(entry, category="manual_upload")
    for entry in accessory_files:
        push_with_meta(entry, category="manual_accessory_upload")

    def flatten_groups(groups: Optional[Iterable[Dict[str, Any]]], *, parent_lookup: Dict[str, str], category: str) -> None:
        if not groups:
            return
        for group in groups:
            source_name = ((group or {}).get("source_name") or "").strip()
            parent_path = ""
            if source_name:
                parent_path = (
                    parent_lookup.get(source_name)
                    or parent_lookup.get(source_name.lower())
                    or parent_lookup.get(os.path.splitext(source_name)[0])
                    or parent_lookup.get(os.path.splitext(source_name)[0].lower())
                    or ""
                )
            for page in (group or {}).get("pages", []) or []:
                page_number = page.get("page_number")
                for artifact in (page or {}).get("artifacts", []) or []:
                    push_with_meta(
                        artifact,
                        category=category,
                        parent_path=parent_path,
                        page_number=page_number,
                    )

    flatten_groups(
        session_record.get("product_ocr_groups"),
        parent_lookup=product_file_by_name,
        category="manual_ocr_artifact",
    )
    flatten_groups(
        session_record.get("accessory_ocr_groups"),
        parent_lookup=accessory_file_by_name,
        category="manual_accessory_ocr_artifact",
    )

    return documents


def _deduplicate_documents(documents: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    by_path: Dict[str, Dict[str, Any]] = {}

    def merge(base: Dict[str, Any], incoming: Dict[str, Any]) -> Dict[str, Any]:
        merged = dict(base)
        for key in (
            "name",
            "type",
            "summary",
            "mime_type",
            "category",
            "parent_path",
            "session_id",
            "page_number",
        ):
            cur = merged.get(key)
            nxt = incoming.get(key)
            if (cur is None or cur == "") and (nxt is not None and nxt != ""):
                merged[key] = nxt
        return merged

    for doc in documents or []:
        normalized = _normalize_document_payload(doc)
        if not normalized:
            continue
        path = normalized["path"]
        existing = by_path.get(path)
        if not existing:
            by_path[path] = normalized
        else:
            by_path[path] = merge(existing, normalized)

    return list(by_path.values())


def insert_product_with_documents(
    product_name: str,
    *,
    display_name: Optional[str] = None,
    bom_code: Optional[str] = None,
    session_id: Optional[str] = None,
    documents: Optional[Iterable[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Create/merge a Product node and attach Document nodes to it."""

    if not product_name:
        raise ValueError("product_name is required")

    normalized_documents = _deduplicate_documents(documents or [])
    product_identifier = f"{product_name}_{bom_code}" if bom_code else product_name

    neo4j_config = get_neo4j_config()
    driver = get_neo4j_driver(neo4j_config)

    attached = 0
    try:
        with driver.session() as session:
            session.run(
                """
                MERGE (p:Product {name: $identifier})
                ON CREATE SET p.created_at = datetime({timezone: 'UTC'})
                SET p.english_name = $product_name,
                    p.chinese_name = $display_name,
                    p.bom_version = $bom_code,
                    p.manual_session_id = $session_id,
                    p.updated_at = datetime({timezone: 'UTC'})
                """,
                {
                    "identifier": product_identifier,
                    "product_name": product_name,
                    "display_name": display_name,
                    "bom_code": bom_code,
                    "session_id": session_id,
                },
            )

            for doc in normalized_documents:
                session.run(
                    """
                    MATCH (p:Product {name: $identifier})
                    MERGE (doc:Document {path: $path})
                    ON CREATE SET doc.created_at = datetime({timezone: 'UTC'}),
                                  doc.name = $name
                    SET doc.name = coalesce($name, doc.name),
                        doc.type = coalesce($doc_type, doc.type),
                        doc.category = coalesce($category, doc.category),
                        doc.parent_path = coalesce($parent_path, doc.parent_path),
                        doc.page_number = coalesce($page_number, doc.page_number),
                        doc.session_id = coalesce($session_id, doc.session_id),
                        doc.summary = coalesce($summary, doc.summary),
                        doc.mime_type = coalesce($mime_type, doc.mime_type),
                        doc.updated_at = datetime({timezone: 'UTC'})
                    MERGE (p)-[:HAS_DOCUMENT]->(doc)
                    """,
                    {
                        "identifier": product_identifier,
                        "path": doc["path"],
                        "name": doc.get("name"),
                        "doc_type": doc.get("type"),
                        "category": doc.get("category"),
                        "parent_path": doc.get("parent_path"),
                        "page_number": doc.get("page_number"),
                        "session_id": doc.get("session_id") or session_id,
                        "summary": doc.get("summary"),
                        "mime_type": doc.get("mime_type"),
                    },
                )
                attached += 1
    finally:
        driver.close()

    return {
        "product_identifier": product_identifier,
        "product_name": product_name,
        "display_name": display_name,
        "bom_code": bom_code,
        "session_id": session_id,
        "documents_submitted": len(normalized_documents),
        "documents_attached": attached,
    }


def get_boms_by_product_name(product_name: str) -> List[str]:
    """
    Get all BOM versions for a specific product by English name.
    
    Args:
        product_name: Product English name
        
    Returns:
        List of BOM versions for the product, sorted.
    """
    neo4j_config = get_neo4j_config()
    driver = get_neo4j_driver(neo4j_config)
    
    boms = []
    try:
        with driver.session() as session:
            result = session.run(
                """
                MATCH (p:Product)
                WHERE p.product_id = $product_id
                AND p.bom_id IS NOT NULL AND p.bom_id <> ''
                RETURN DISTINCT p.bom_id AS bom_version
                ORDER BY bom_version
                """,
                {"product_id": product_name}
            )
            
            for record in result:
                bom_version = record["bom_version"]
                if bom_version:
                    boms.append(bom_version)
    finally:
        driver.close()
    
    return sorted(boms)


def get_all_accessory_names() -> List[Dict[str, Any]]:
    """Get all unique accessory names from Neo4j."""
    neo4j_config = get_neo4j_config()
    driver = get_neo4j_driver(neo4j_config)

    accessory_items: List[Dict[str, Any]] = []
    try:
        with driver.session() as session:
            result = session.run(
                """
                MATCH (a:Accessory)
                WHERE a.name_zh IS NOT NULL AND a.name_zh <> ''
                RETURN DISTINCT
                    a.name_zh AS name_zh,
                    coalesce(a.name_en, '') AS name_en,
                    coalesce(a.name, '') AS name
                ORDER BY a.name_zh
                """
            )
            for record in result:
                name_zh = record.get("name_zh")
                if not name_zh:
                    continue
                accessory_items.append(
                    {
                        "name_zh": name_zh,
                        "name_en": record.get("name_en") or "",
                        "name": record.get("name") or "",
                    }
                )
    finally:
        driver.close()

    return accessory_items


def get_accessories_by_product_bom(product_name: str, bom_version: str) -> List[str]:
    """Get accessory names connected to a specific product BOM."""
    neo4j_config = get_neo4j_config()
    driver = get_neo4j_driver(neo4j_config)

    accessories: List[str] = []
    try:
        with driver.session() as session:
            result = session.run(
                """
                MATCH (p:Product)
                WHERE p.product_id = $product_id AND p.bom_id = $bom_id
                MATCH (p)-[r:HAS_ACCESSORY]->(a:Accessory)
                RETURN r.order AS ord, coalesce(a.name, a.name_zh, '') AS name
                ORDER BY ord ASC, name ASC
                """,
                {"product_id": product_name, "bom_id": bom_version},
            )
            seen = set()
            for record in result:
                name = record["name"]
                if not name:
                    continue
                name_s = str(name)
                if name_s in seen:
                    continue
                seen.add(name_s)
                accessories.append(name_s)
    finally:
        driver.close()

    return accessories


def get_documents_by_product_bom(product_name: str, bom_version: str) -> List[Dict[str, Any]]:
    """Get files linked directly to a product (documents + images, exclude accessory files)."""
    neo4j_config = get_neo4j_config()
    driver = get_neo4j_driver(neo4j_config)

    documents: List[Dict[str, Any]] = []
    try:
        with driver.session() as session:
            doc_result = session.run(
                """
                MATCH (p:Product {english_name: $product_name, bom_version: $bom_version})
                MATCH (p)-[:HAS_DOCUMENT]->(doc:Document)
                RETURN DISTINCT doc.name AS name,
                                doc.path AS path,
                                doc.created_at AS created_at,
                                doc.updated_at AS updated_at,
                                doc.type AS doc_type,
                                doc.mime_type AS mime_type,
                                doc.summary AS summary,
                                doc.category AS category,
                                doc.parent_path AS parent_path,
                                doc.page_number AS page_number
                ORDER BY category, name
                """,
                {"product_name": product_name, "bom_version": bom_version},
            )

            for record in doc_result:
                documents.append(
                    {
                        "name": record.get("name") or record.get("path") or "Unknown",
                        "path": record.get("path", ""),
                        "created_at": record.get("created_at"),
                        "updated_at": record.get("updated_at"),
                        "type": record.get("doc_type") or "document",
                        "mime_type": record.get("mime_type") or "",
                        "summary": record.get("summary") or "",
                        "category": record.get("category") or "",
                        "parent_path": record.get("parent_path") or "",
                        "page_number": record.get("page_number"),
                    }
                )

            image_result = session.run(
                """
                MATCH (p:Product {english_name: $product_name, bom_version: $bom_version})
                MATCH (p)-[:HAS_IMAGE]->(img:Image)
                OPTIONAL MATCH (img)-[:HAS_DESCRIPTION]->(desc:ImageDescription)
                RETURN DISTINCT img.path AS source_path,
                                COALESCE(desc.image_path, img.path) AS stored_path,
                                img.created_at AS created_at,
                                desc.summary AS summary
                ORDER BY stored_path
                """,
                {"product_name": product_name, "bom_version": bom_version},
            )

            for record in image_result:
                stored_path = record.get("stored_path") or record.get("source_path") or ""
                fallback_source = record.get("source_path") or ""
                stored_name = os.path.basename(stored_path) if stored_path else None
                documents.append(
                    {
                        "name": stored_name
                        or (os.path.basename(fallback_source) if fallback_source else None)
                        or "Image",
                        "path": stored_path,
                        "created_at": record.get("created_at"),
                        "type": "image",
                        "source_path": fallback_source,
                        "summary": record.get("summary"),
                    }
                )

            embedded_result = session.run(
                """
                MATCH (p:Product {english_name: $product_name, bom_version: $bom_version})
                MATCH (p)-[:HAS_DOCUMENT]->(doc:Document)
                OPTIONAL MATCH (doc)-[:HAS_IMAGE_DESCRIPTION]->(desc:ImageDescription)
                RETURN DISTINCT desc.image_path AS stored_path,
                                doc.path AS doc_path,
                                doc.name AS doc_name,
                                desc.summary AS summary,
                                desc.created_at AS created_at
                ORDER BY stored_path
                """,
                {"product_name": product_name, "bom_version": bom_version},
            )

            for record in embedded_result:
                stored_path = record.get("stored_path") or ""
                stored_name = os.path.basename(stored_path) if stored_path else None
                documents.append(
                    {
                        "name": stored_name or record.get("doc_name") or "Document Image",
                        "path": stored_path,
                        "created_at": record.get("created_at"),
                        "type": "image_embedded",
                        "doc_path": record.get("doc_path"),
                        "doc_name": record.get("doc_name"),
                        "summary": record.get("summary"),
                    }
                )

            specsheet_record = session.run(
                """
                MATCH (p:Product {english_name: $product_name, bom_version: $bom_version})
                RETURN p.specsheet_json AS specsheet_json,
                       p.specsheet_updated_at AS specsheet_updated_at
                """,
                {
                    "product_name": product_name,
                    "bom_version": bom_version,
                },
            ).single()

            if specsheet_record and specsheet_record.get("specsheet_json"):
                updated_at = specsheet_record.get("specsheet_updated_at")
                documents.append(
                    {
                        "name": "规格页 JSON",  # front-end friendly label
                        "path": "__specsheet_json__",
                        "type": "specsheet",
                        "summary": "点击查看已保存的规格页 JSON",
                        "updated_at": updated_at,
                    }
                )
    finally:
        driver.close()

    return documents


def move_document_owner(
    doc_path: str,
    target_type: str,
    product_name: Optional[str] = None,
    bom_version: Optional[str] = None,
    accessory_name: Optional[str] = None,
) -> Dict[str, Any]:
    """Move a document under a new product or accessory owner."""

    if target_type not in {"product", "accessory"}:
        raise ValueError("target_type 必须是 'product' 或 'accessory'")

    metadata = _fetch_document_metadata(doc_path)

    neo4j_config = get_neo4j_config()
    driver = get_neo4j_driver(neo4j_config)

    try:
        with driver.session() as session:
            if target_type == "product":
                if not product_name or not bom_version:
                    raise ValueError("移动到产品节点需要提供 product_name 与 bom_version")

                target_record = session.run(
                    """
                    MATCH (p:Product {english_name: $product_name, bom_version: $bom_version})
                    RETURN p.english_name AS english_name, p.bom_version AS bom_version
                    """,
                    {"product_name": product_name, "bom_version": bom_version},
                ).single()

                if not target_record:
                    raise ValueError(f"未找到指定产品：{product_name} - {bom_version}")

                session.run(
                    """
                    MATCH (doc:Document {path: $path})
                    OPTIONAL MATCH (doc)<-[rel:HAS_DOCUMENT]-()
                    DELETE rel
                    WITH doc
                    MATCH (target:Product {english_name: $product_name, bom_version: $bom_version})
                    MERGE (target)-[:HAS_DOCUMENT]->(doc)
                    SET doc.updated_at = datetime({timezone: 'UTC'})
                    """,
                    {
                        "path": doc_path,
                        "product_name": product_name,
                        "bom_version": bom_version,
                    },
                )

                metadata.update(
                    {
                        "owner_type": "Product",
                        "owner_name": target_record["english_name"],
                        "bom_version": target_record["bom_version"],
                    }
                )

            else:
                if not accessory_name:
                    raise ValueError("移动到配件节点需要提供 accessory_name")

                target_record = session.run(
                    """
                    MATCH (a:Accessory {name: $accessory_name})
                    RETURN a.name AS name
                    """,
                    {"accessory_name": accessory_name},
                ).single()

                if not target_record:
                    raise ValueError(f"未找到指定配件：{accessory_name}")

                session.run(
                    """
                    MATCH (doc:Document {path: $path})
                    OPTIONAL MATCH (doc)<-[rel:HAS_DOCUMENT]-()
                    DELETE rel
                    WITH doc
                    MATCH (target:Accessory {name: $accessory_name})
                    MERGE (target)-[:HAS_DOCUMENT]->(doc)
                    SET doc.updated_at = datetime({timezone: 'UTC'})
                    """,
                    {"path": doc_path, "accessory_name": accessory_name},
                )

                metadata.update(
                    {
                        "owner_type": "Accessory",
                        "owner_name": target_record["name"],
                        "bom_version": None,
                    }
                )

        return metadata
    finally:
        driver.close()


def get_unmatched_documents() -> List[Dict[str, Any]]:
    """Return documents that do not have any owner relationship."""

    neo4j_config = get_neo4j_config()
    driver = get_neo4j_driver(neo4j_config)

    documents: List[Dict[str, Any]] = []
    try:
        with driver.session() as session:
            doc_result = session.run(
                """
                MATCH (doc:Document)
                WHERE NOT (doc)<-[:HAS_DOCUMENT]-()
                RETURN doc.name AS name,
                       doc.path AS path,
                       doc.created_at AS created_at,
                       doc.updated_at AS updated_at
                ORDER BY doc.name
                """
            )

            for record in doc_result:
                documents.append(
                    {
                        "name": record.get("name") or record.get("path") or "Unknown",
                        "path": record.get("path", ""),
                        "created_at": record.get("created_at"),
                        "updated_at": record.get("updated_at"),
                        "source": "document",
                    }
                )

            unknown_result = session.run(
                """
                MATCH (u:Unknown)
                RETURN u.file_path AS path,
                       u.file_type AS file_type,
                       u.created_at AS created_at,
                       u.updated_at AS updated_at
                ORDER BY u.created_at DESC
                """
            )

            for record in unknown_result:
                path_value = record.get("path", "")
                documents.append(
                    {
                        "name": os.path.basename(path_value) or path_value or "Unknown",
                        "path": path_value,
                        "created_at": record.get("created_at"),
                        "updated_at": record.get("updated_at"),
                        "file_type": record.get("file_type"),
                        "source": "unknown",
                    }
                )
    finally:
        driver.close()

    return documents


def attach_document_to_owner(
    doc_path: str,
    target_type: str,
    product_name: Optional[str] = None,
    bom_version: Optional[str] = None,
    accessory_name: Optional[str] = None,
) -> Dict[str, Any]:
    """Attach an owner to a previously unmatched document."""

    if target_type not in {"product", "accessory"}:
        raise ValueError("target_type 必须是 'product' 或 'accessory'")

    try:
        metadata = _fetch_document_metadata(doc_path)
    except ValueError:
        metadata = None

    if metadata and metadata.get("owner_type"):
        raise ValueError("该文件已关联到其它节点，无需再次增加")

    neo4j_config = get_neo4j_config()
    driver = get_neo4j_driver(neo4j_config)

    try:
        with driver.session() as session:
            _ensure_document_node(session, doc_path)

            if metadata is None:
                metadata = _fetch_document_metadata(doc_path)

            if target_type == "product":
                if not product_name or not bom_version:
                    raise ValueError("关联到产品需要提供 product_name 与 bom_version")

                target_record = session.run(
                    """
                    MATCH (p:Product {english_name: $product_name, bom_version: $bom_version})
                    RETURN p.english_name AS english_name, p.bom_version AS bom_version
                    """,
                    {"product_name": product_name, "bom_version": bom_version},
                ).single()

                if not target_record:
                    raise ValueError(f"未找到指定产品：{product_name} - {bom_version}")

                session.run(
                    """
                    MATCH (doc:Document {path: $path})
                    MATCH (target:Product {english_name: $product_name, bom_version: $bom_version})
                    MERGE (target)-[:HAS_DOCUMENT]->(doc)
                    SET doc.updated_at = datetime({timezone: 'UTC'})
                    """,
                    {
                        "path": doc_path,
                        "product_name": product_name,
                        "bom_version": bom_version,
                    },
                )

                metadata.update(
                    {
                        "owner_type": "Product",
                        "owner_name": target_record["english_name"],
                        "bom_version": target_record["bom_version"],
                    }
                )

            else:
                if not accessory_name:
                    raise ValueError("关联到配件需要提供 accessory_name")

                target_record = session.run(
                    """
                    MATCH (a:Accessory {name: $accessory_name})
                    RETURN a.name AS name
                    """,
                    {"accessory_name": accessory_name},
                ).single()

                if not target_record:
                    raise ValueError(f"未找到指定配件：{accessory_name}")

                session.run(
                    """
                    MATCH (doc:Document {path: $path})
                    MATCH (target:Accessory {name: $accessory_name})
                    MERGE (target)-[:HAS_DOCUMENT]->(doc)
                    SET doc.updated_at = datetime({timezone: 'UTC'})
                    """,
                    {
                        "path": doc_path,
                        "accessory_name": accessory_name,
                    },
                )

                metadata.update(
                    {
                        "owner_type": "Accessory",
                        "owner_name": target_record["name"],
                        "bom_version": None,
                    }
                )

        return metadata
    finally:
        driver.close()


def get_unmatched_document_detail(doc_path: str) -> Dict[str, Any]:
    """Return file content for an unmatched document (Document or Unknown)."""

    try:
        return get_document_detail(doc_path)
    except ValueError:
        pass

    neo4j_config = get_neo4j_config()
    driver = get_neo4j_driver(neo4j_config)

    try:
        with driver.session() as session:
            record = session.run(
                """
                MATCH (u:Unknown {file_path: $path})
                RETURN u.file_path AS path,
                       u.file_type AS file_type,
                       u.created_at AS created_at,
                       u.updated_at AS updated_at
                """,
                {"path": doc_path},
            ).single()

            if not record:
                raise ValueError(f"Document '{doc_path}' not found")

            resolved_path = _resolve_document_path(doc_path)
            if not resolved_path.exists():
                raise FileNotFoundError(f"File '{doc_path}' not found on disk")

            content = _read_file_text(resolved_path)

            return {
                "name": resolved_path.name,
                "path": doc_path,
                "created_at": record.get("created_at"),
                "updated_at": record.get("updated_at"),
                "file_type": record.get("file_type"),
                "content": content,
            }
    finally:
        driver.close()


def update_unmatched_document_content(
    doc_path: str,
    content: str,
    new_name: Optional[str] = None,
) -> Dict[str, Any]:
    """Update an unmatched document (Document or Unknown) without requiring ownership."""

    try:
        return update_document_content(doc_path, content, new_name)
    except ValueError:
        pass

    if new_name:
        raise ValueError("暂不支持重命名 Unknown 类型文件")

    neo4j_config = get_neo4j_config()
    driver = get_neo4j_driver(neo4j_config)

    try:
        with driver.session() as session:
            record = session.run(
                """
                MATCH (u:Unknown {file_path: $path})
                RETURN u.file_path AS path,
                       u.file_type AS file_type,
                       u.created_at AS created_at,
                       u.updated_at AS updated_at
                """,
                {"path": doc_path},
            ).single()

            if not record:
                raise ValueError(f"Document '{doc_path}' not found")

            resolved_path = _resolve_document_path(doc_path)
            if not resolved_path.exists():
                raise FileNotFoundError(f"File '{doc_path}' not found on disk")

            resolved_path.write_text(content, encoding="utf-8")
            updated_record = session.run(
                """
                MATCH (u:Unknown {file_path: $path})
                SET u.updated_at = datetime({timezone: 'UTC'})
                RETURN u.file_path AS path,
                       u.file_type AS file_type,
                       u.created_at AS created_at,
                       u.updated_at AS updated_at
                """,
                {"path": doc_path},
            ).single()

            return {
                "name": resolved_path.name,
                "path": doc_path,
                "created_at": updated_record.get("created_at"),
                "updated_at": updated_record.get("updated_at"),
                "file_type": updated_record.get("file_type"),
                "content": content,
                "source": "unknown",
            }
    finally:
        driver.close()


def _resolve_document_path(doc_path: str) -> Path:
    """Resolve a stored document path to an absolute path on disk."""
    path_obj = Path(doc_path)
    if not path_obj.is_absolute():
        path_obj = (BACKEND_ROOT / path_obj).resolve()
    return path_obj


def _relative_to_backend(path_obj: Path) -> str:
    """Convert an absolute path to a backend-root-relative POSIX string if possible."""
    try:
        return path_obj.relative_to(BACKEND_ROOT).as_posix()
    except ValueError:
        return path_obj.as_posix()


def _read_file_text(path_obj: Path) -> str:
    """Read text content from disk using utf-8 fallback encodings."""
    encodings = ["utf-8", "utf-8-sig", "gb18030"]
    last_exc: Optional[Exception] = None
    for enc in encodings:
        try:
            return path_obj.read_text(encoding=enc)
        except Exception as exc:  # pragma: no cover - fallback handling
            last_exc = exc
    if last_exc:
        raise last_exc
    return path_obj.read_text()


def _get_embedding_config() -> LLMConfig:
    """Return embedding config for updating chunk vectors."""
    model = os.getenv("EMBEDDING_MODEL", Ollama_QWEN3_EMBEDDING)
    base_url = os.getenv("EMBEDDING_BASE_URL", Ollama_BASE_URL)
    api_key = os.getenv("EMBEDDING_API_KEY")
    return LLMConfig(model=model, api_key=api_key, base_url=base_url)


def _fetch_document_metadata(doc_path: str) -> Dict[str, Any]:
    """Fetch document metadata and owner info from Neo4j."""
    neo4j_config = get_neo4j_config()
    driver = get_neo4j_driver(neo4j_config)

    try:
        with driver.session() as session:
            record = session.run(
                """
                MATCH (doc:Document {path: $path})
                OPTIONAL MATCH (doc)<-[:HAS_DOCUMENT]-(owner)
                RETURN doc.name AS name,
                       doc.path AS path,
                       doc.created_at AS created_at,
                       doc.updated_at AS updated_at,
                       labels(owner)[0] AS owner_type,
                       COALESCE(owner.english_name, owner.name) AS owner_name
                """,
                {"path": doc_path},
            ).single()

            if not record:
                raise ValueError(f"Document '{doc_path}' not found")

            return {
                "name": record.get("name"),
                "path": record.get("path"),
                "created_at": record.get("created_at"),
                "updated_at": record.get("updated_at"),
                "owner_type": record.get("owner_type"),
                "owner_name": record.get("owner_name"),
            }
    finally:
        driver.close()


def get_document_detail(doc_path: str) -> Dict[str, Any]:
    """Return document metadata together with its file content."""
    resolved_path = _resolve_document_path(doc_path)
    if not resolved_path.exists():
        raise FileNotFoundError(f"File '{doc_path}' not found on disk")

    try:
        metadata = _fetch_document_metadata(doc_path)
    except ValueError:
        normalized = _normalize_document_path(doc_path)
        if normalized.startswith("manual_ocr_results/") or normalized.startswith("manual_uploads/"):
            metadata = {
                "name": resolved_path.name,
                "path": normalized,
                "created_at": None,
                "updated_at": None,
                "owner_type": None,
                "owner_name": None,
            }
        else:
            raise

    content = _read_file_text(resolved_path)
    metadata["content"] = content
    return metadata


def update_document_content(doc_path: str, content: str, new_name: Optional[str] = None) -> Dict[str, Any]:
    """Update a stored document's content (and optionally rename it)."""
    if new_name:
        new_name = new_name.strip()
        if not new_name:
            raise ValueError("新的文件名不能为空")
        if any(sep in new_name for sep in ("/", "\\")):
            raise ValueError("文件名不能包含路径分隔符")

    resolved_path = _resolve_document_path(doc_path)
    if not resolved_path.exists():
        raise FileNotFoundError(f"File '{doc_path}' not found on disk")

    normalized_doc_path = _normalize_document_path(doc_path)
    allow_disk_only = normalized_doc_path.startswith("manual_ocr_results/") or normalized_doc_path.startswith(
        "manual_uploads/"
    )

    try:
        metadata = _fetch_document_metadata(doc_path)
        has_graph_node = True
    except ValueError:
        if not allow_disk_only:
            raise
        metadata = {
            "name": resolved_path.name,
            "path": normalized_doc_path,
            "created_at": None,
            "updated_at": None,
            "owner_type": None,
            "owner_name": None,
        }
        has_graph_node = False

    final_path = resolved_path
    updated_path_value = doc_path

    if new_name and new_name != resolved_path.name:
        final_path = resolved_path.with_name(new_name)
        final_path.parent.mkdir(parents=True, exist_ok=True)
        if final_path.exists():
            raise FileExistsError(f"目标文件 {final_path} 已存在")
        resolved_path.rename(final_path)
        resolved_path = final_path
        updated_path_value = _relative_to_backend(final_path)

    resolved_path.write_text(content, encoding="utf-8")

    if allow_disk_only and not has_graph_node:
        metadata.update(
            {
                "content": content,
                "path": updated_path_value,
                "name": new_name or metadata.get("name") or resolved_path.name,
                "updated_at": datetime.utcnow().isoformat(),
            }
        )
        return metadata

    neo4j_config = get_neo4j_config()
    driver = get_neo4j_driver(neo4j_config)

    try:
        with driver.session() as session:
            record = session.run(
                """
                MATCH (doc:Document {path: $original_path})
                SET doc.name = $new_name,
                    doc.path = $new_path,
                    doc.updated_at = datetime({timezone: 'UTC'})
                RETURN doc.name AS name,
                       doc.path AS path,
                       doc.created_at AS created_at,
                       doc.updated_at AS updated_at
                """,
                {
                    "original_path": doc_path,
                    "new_name": new_name or metadata.get("name") or resolved_path.name,
                    "new_path": updated_path_value,
                },
            ).single()

            _refresh_text_description(session, updated_path_value, content)

        metadata.update(record or {})
        metadata["content"] = content
        metadata["path"] = updated_path_value
        metadata["name"] = metadata.get("name") or resolved_path.name
        return metadata
    finally:
        driver.close()


def _refresh_text_description(session, doc_path: str, content: str) -> None:
    """Refresh TextDescription summary and chunk embeddings for a document."""
    normalized_content = content or ""
    summary = _build_summary(normalized_content)

    chunks = md_chunker(normalized_content) if normalized_content.strip() else []
    if not chunks and normalized_content:
        chunks = [normalized_content[:3000]]

    vectors: List[List[float]] = []
    embedding_config = None
    if chunks:
        embedding_config = _get_embedding_config()
        try:
            vectors = embed_texts(chunks, embedding_config)
        except Exception as exc:  # pragma: no cover - runtime safeguard
            print(f"Warning: Failed to embed document '{doc_path}': {exc}")
            chunks = []
            vectors = []

    record = session.run(
        """
        MATCH (doc:Document {path: $path})
        OPTIONAL MATCH (doc)-[:HAS_TEXT_DESCRIPTION]->(td)
        RETURN td.id AS td_id
        """,
        {"path": doc_path},
    ).single()

    text_desc_id = record["td_id"] if record else None
    if not text_desc_id:
        text_desc_id = hashlib.sha256(f"text_desc:{doc_path}".encode("utf-8")).hexdigest()
        session.run(
            """
            MATCH (doc:Document {path: $path})
            MERGE (td:TextDescription {id: $td_id})
            ON CREATE SET td.created_at = datetime({timezone: 'UTC'})
            MERGE (doc)-[:HAS_TEXT_DESCRIPTION]->(td)
            """,
            {"path": doc_path, "td_id": text_desc_id},
        )

    session.run(
        """
        MATCH (td:TextDescription {id: $td_id})
        SET td.summary = $summary,
            td.text_path = $text_path,
            td.updated_at = datetime({timezone: 'UTC'})
        """,
        {
            "td_id": text_desc_id,
            "summary": summary,
            "text_path": doc_path,
        },
    )

    session.run(
        """
        MATCH (td:TextDescription {id: $td_id})-[:HAS_CHUNK]->(chunk:Chunk)
        DETACH DELETE chunk
        """,
        {"td_id": text_desc_id},
    )

    if chunks and vectors and embedding_config:
        create_chunk_nodes(
            session,
            text_desc_id,
            "TextDescription",
            chunks,
            vectors,
            embedding_config.model,
            doc_path,
        )


def _build_summary(content: str) -> str:
    stripped = content.strip()
    if not stripped:
        return ""
    first_line = stripped.splitlines()[0]
    return first_line[:120]


def _ensure_document_node(session, doc_path: str) -> None:
    """Ensure a Document node exists for the given path, promoting Unknown if needed."""

    existing = session.run(
        """
        MATCH (doc:Document {path: $path})
        RETURN doc.path AS path
        """,
        {"path": doc_path},
    ).single()

    if existing:
        return

    unknown_record = session.run(
        """
        MATCH (u:Unknown {file_path: $path})
        RETURN u.file_type AS file_type,
               u.created_at AS created_at,
               u.updated_at AS updated_at
        """,
        {"path": doc_path},
    ).single()

    resolved_path = _resolve_document_path(doc_path)

    if not resolved_path.exists():
        raise FileNotFoundError(f"File '{doc_path}' not found on disk")

    if not unknown_record:
        raise ValueError(f"Document '{doc_path}' not found in graph")

    now = datetime.utcnow().isoformat()
    session.run(
        """
        MERGE (doc:Document {path: $path})
        ON CREATE SET doc.name = $name,
                      doc.created_at = COALESCE($created_at, datetime($now)),
                      doc.updated_at = datetime($now)
        """,
        {
            "path": doc_path,
            "name": resolved_path.name,
            "created_at": unknown_record.get("created_at"),
            "now": now,
        },
    )

    session.run(
        """
        MATCH (u:Unknown {file_path: $path})
        DETACH DELETE u
        """,
        {"path": doc_path},
    )


def _cleanup_saved_paths(paths: List[Optional[str]]) -> None:
    for raw in paths:
        if not raw:
            continue
        resolved = _resolve_document_path(raw)
        if resolved.exists():
            try:
                resolved.unlink()
            except Exception:
                pass


def delete_document(doc_path: str) -> Dict[str, Any]:
    """Detach a document from owners and downgrade it to an Unknown node."""
    normalized_doc_path = _normalize_document_path(doc_path)
    allow_disk_only = normalized_doc_path.startswith("manual_ocr_results/") or normalized_doc_path.startswith(
        "manual_uploads/"
    )

    try:
        metadata = _fetch_document_metadata(doc_path)
    except ValueError:
        if not allow_disk_only:
            raise
        resolved = _resolve_document_path(doc_path)
        if not resolved.exists():
            raise FileNotFoundError(f"File '{doc_path}' not found on disk")
        resolved.unlink()
        return {
            "name": resolved.name,
            "path": normalized_doc_path,
            "created_at": None,
            "updated_at": datetime.utcnow().isoformat(),
            "owner_type": None,
            "owner_name": None,
        }

    neo4j_config = get_neo4j_config()
    driver = get_neo4j_driver(neo4j_config)

    try:
        with driver.session() as session:
            extra_paths_record = session.run(
                """
                MATCH (doc:Document {path: $path})
                OPTIONAL MATCH (doc)-[:HAS_TEXT_DESCRIPTION]->(td)
                OPTIONAL MATCH (doc)-[:HAS_IMAGE_DESCRIPTION]->(imgd)
                OPTIONAL MATCH (doc)-[:HAS_TABLE_DESCRIPTION]->(tabled)
                RETURN collect(DISTINCT td.text_path) AS text_paths,
                       collect(DISTINCT imgd.image_path) AS image_paths,
                       collect(DISTINCT tabled.table_path) AS table_paths
                """,
                {"path": doc_path},
            ).single()

            if extra_paths_record:
                _cleanup_saved_paths(extra_paths_record.get("text_paths", []))
                _cleanup_saved_paths(extra_paths_record.get("image_paths", []))
                _cleanup_saved_paths(extra_paths_record.get("table_paths", []))

            session.run(
                """
                MATCH (doc:Document {path: $path})
                OPTIONAL MATCH (doc)-[:HAS_TEXT_DESCRIPTION]->(td)
                OPTIONAL MATCH (td)-[:HAS_CHUNK]->(textChunk)
                OPTIONAL MATCH (doc)-[:HAS_IMAGE_DESCRIPTION]->(imgd)
                OPTIONAL MATCH (imgd)-[:HAS_CHUNK]->(imgChunk)
                OPTIONAL MATCH (doc)-[:HAS_TABLE_DESCRIPTION]->(tabled)
                OPTIONAL MATCH (tabled)-[:HAS_CHUNK]->(tableChunk)
                DETACH DELETE textChunk, imgChunk, tableChunk, td, imgd, tabled, doc
                """,
                {"path": doc_path},
            )

            create_unknown_node(session, doc_path, "document")
            session.run(
                """
                MATCH (u:Unknown {file_path: $path})
                SET u.created_at = COALESCE($created_at, u.created_at),
                    u.updated_at = datetime({timezone: 'UTC'})
                """,
                {
                    "path": doc_path,
                    "created_at": metadata.get("created_at"),
                },
            )

        return metadata
    finally:
        driver.close()


def get_documents_by_accessory(accessory_name: str) -> List[Dict[str, Any]]:
    """Get documents and images linked to a specific accessory."""
    neo4j_config = get_neo4j_config()
    driver = get_neo4j_driver(neo4j_config)

    documents: List[Dict[str, Any]] = []
    try:
        with driver.session() as session:
            doc_result = session.run(
                """
                MATCH (a:Accessory {name: $accessory_name})
                OPTIONAL MATCH (a)-[:HAS_DOCUMENT]->(doc:Document)
                WITH DISTINCT doc WHERE doc IS NOT NULL
                RETURN doc.name AS name,
                       doc.path AS path,
                       doc.created_at AS created_at,
                       doc.updated_at AS updated_at,
                       doc.type AS doc_type,
                       doc.mime_type AS mime_type,
                       doc.summary AS summary,
                       doc.category AS category,
                       doc.parent_path AS parent_path,
                       doc.page_number AS page_number
                ORDER BY doc.name
                """,
                {"accessory_name": accessory_name},
            )

            for record in doc_result:
                documents.append(
                    {
                        "name": record.get("name") or record.get("path") or "Unknown",
                        "path": record.get("path", ""),
                        "created_at": record.get("created_at"),
                        "updated_at": record.get("updated_at"),
                        "type": record.get("doc_type") or "document",
                        "mime_type": record.get("mime_type") or "",
                        "summary": record.get("summary") or "",
                        "category": record.get("category") or "",
                        "parent_path": record.get("parent_path") or "",
                        "page_number": record.get("page_number"),
                    }
                )

            image_result = session.run(
                """
                MATCH (a:Accessory {name: $accessory_name})
                MATCH (a)-[:HAS_IMAGE]->(img:Image)
                OPTIONAL MATCH (img)-[:HAS_DESCRIPTION]->(desc:ImageDescription)
                RETURN DISTINCT img.path AS source_path,
                                COALESCE(desc.image_path, img.path) AS stored_path,
                                img.created_at AS created_at,
                                desc.summary AS summary
                ORDER BY stored_path
                """,
                {"accessory_name": accessory_name},
            )

            for record in image_result:
                stored_path = record.get("stored_path") or record.get("source_path") or ""
                fallback_source = record.get("source_path") or ""
                stored_name = os.path.basename(stored_path) if stored_path else None
                documents.append(
                    {
                        "name": stored_name
                        or (os.path.basename(fallback_source) if fallback_source else None)
                        or "Image",
                        "path": stored_path,
                        "created_at": record.get("created_at"),
                        "type": "image",
                        "source_path": fallback_source,
                        "summary": record.get("summary"),
                    }
                )

            embedded_result = session.run(
                """
                MATCH (a:Accessory {name: $accessory_name})
                OPTIONAL MATCH (a)-[:HAS_DOCUMENT]->(doc:Document)
                OPTIONAL MATCH (doc)-[:HAS_IMAGE_DESCRIPTION]->(desc:ImageDescription)
                WITH desc, doc WHERE desc IS NOT NULL
                RETURN DISTINCT desc.image_path AS stored_path,
                                doc.path AS doc_path,
                                doc.name AS doc_name,
                                desc.summary AS summary,
                                desc.created_at AS created_at
                ORDER BY stored_path
                """,
                {"accessory_name": accessory_name},
            )

            for record in embedded_result:
                stored_path = record.get("stored_path") or ""
                stored_name = os.path.basename(stored_path) if stored_path else None
                documents.append(
                    {
                        "name": stored_name or record.get("doc_name") or "Document Image",
                        "path": stored_path,
                        "created_at": record.get("created_at"),
                        "type": "image_embedded",
                        "doc_path": record.get("doc_path"),
                        "doc_name": record.get("doc_name"),
                        "summary": record.get("summary"),
                    }
                )
    finally:
        driver.close()

    return documents

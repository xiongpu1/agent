import argparse
import csv
import json
import os
import re
import sys
import importlib.util
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np
from dotenv import load_dotenv
from litellm import completion

project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.api_queries import get_neo4j_config
from src.dataclass import LLMConfig
from src.neo4j_file_add_neo4j import embed_texts, get_neo4j_driver
from src.rag_specsheet import get_embedding_config, get_llm_config


UNITS_RE = re.compile(r"\b(lbs?|gallons?|hp|kg|mm|cm|inch|in\.|v|hz|w|kw)\b", flags=re.IGNORECASE)
BULLET_PREFIX_RE = re.compile(r"^\s*(?:[-*+]|[•·])\s+")


@dataclass
class CandidateAccessory:
    element_id: str
    name_zh: str


@dataclass
class MatchResult:
    material_code: str
    accessory_element_id: str
    accessory_name_zh: str
    matched_en: str
    score: float
    match_scope: str
    source_pdf: str
    llm_used: bool
    llm_confidence: Optional[float]
    llm_reason: str


def _now_tag() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def iter_pdf_files(root: Path) -> Iterable[Path]:
    if root.is_file() and root.suffix.lower() == ".pdf":
        yield root
        return

    if not root.exists() or not root.is_dir():
        return

    for p in root.rglob("*.pdf"):
        if p.is_file():
            yield p


def _normalize_phrase(text: str) -> str:
    t = (text or "").strip()
    t = t.replace("\u00a0", " ")
    t = re.sub(r"\s+", " ", t)
    t = t.strip("*-_•· ")
    t = t.strip()
    return t


def _is_englishish(line: str) -> bool:
    if not line:
        return False
    if len(line) < 3 or len(line) > 120:
        return False

    letters = sum(1 for c in line if "A" <= c <= "Z" or "a" <= c <= "z")
    if letters < 3:
        return False

    digits = sum(1 for c in line if c.isdigit())
    if digits / max(len(line), 1) > 0.25:
        return False

    if UNITS_RE.search(line):
        return False

    return True


def extract_en_phrases_from_markdown(md: str) -> List[str]:
    if not md:
        return []

    out: List[str] = []

    for raw in md.splitlines():
        line = raw.strip()
        if not line:
            continue

        line = BULLET_PREFIX_RE.sub("", line)
        line = _normalize_phrase(line)

        if not line:
            continue

        if line.startswith("[") and line.endswith("]"):
            continue

        if ":" in line and any(ch.isdigit() for ch in line):
            continue

        if _is_englishish(line):
            out.append(line)

    uniq: List[str] = []
    seen = set()
    for x in out:
        k = x.lower()
        if k in seen:
            continue
        seen.add(k)
        uniq.append(x)
    return uniq


def extract_en_phrases_from_text(text: str) -> List[str]:
    if not text:
        return []
    # Reuse markdown extractor by treating each line as a markdown line.
    # This is a pragmatic fallback for pure text extraction.
    return extract_en_phrases_from_markdown(text)


def _has_module(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except Exception:
        return False


def _pdf_backend_status() -> Dict[str, bool]:
    return {
        "mineru": _has_module("mineru"),
        "pymupdf": _has_module("fitz"),
        "pypdf": _has_module("pypdf"),
        "pypdf2": _has_module("PyPDF2"),
    }


def _try_parse_pdf_with_mineru(pdf_path: Path, lang: str) -> Optional[str]:
    try:
        # Optional dependency: mineru
        from src.data_pdf import parse_doc  # type: ignore

        return parse_doc(pdf_path, lang=lang, backend="pipeline", method="auto")
    except ModuleNotFoundError:
        return None
    except Exception:
        return None


def _try_extract_text_with_fitz(pdf_path: Path) -> Optional[str]:
    try:
        import fitz  # PyMuPDF

        doc = fitz.open(str(pdf_path))
        parts: List[str] = []
        for page in doc:
            parts.append(page.get_text("text"))
        doc.close()
        out = "\n".join(parts).strip()
        return out or None
    except Exception:
        return None


def _try_extract_text_with_pypdf(pdf_path: Path) -> Optional[str]:
    try:
        from pypdf import PdfReader  # type: ignore

        reader = PdfReader(str(pdf_path))
        parts: List[str] = []
        for page in reader.pages:
            parts.append(page.extract_text() or "")
        out = "\n".join(parts).strip()
        return out or None
    except Exception:
        return None


def _try_extract_text_with_pypdf2(pdf_path: Path) -> Optional[str]:
    try:
        from PyPDF2 import PdfReader  # type: ignore

        reader = PdfReader(str(pdf_path))
        parts: List[str] = []
        for page in reader.pages:
            parts.append(page.extract_text() or "")
        out = "\n".join(parts).strip()
        return out or None
    except Exception:
        return None


def parse_pdf_to_phrases(pdf_path: Path, lang: str = "en") -> List[str]:
    # 1) Best-effort: mineru pipeline (handles OCR + structure) if available
    md = _try_parse_pdf_with_mineru(pdf_path, lang=lang)
    if md:
        phrases = extract_en_phrases_from_markdown(md)
        if phrases:
            return phrases

    # 2) Fallback: text extraction from PDF text layer
    text = _try_extract_text_with_fitz(pdf_path)
    if not text:
        text = _try_extract_text_with_pypdf(pdf_path)
    if not text:
        text = _try_extract_text_with_pypdf2(pdf_path)

    if not text:
        return []
    return extract_en_phrases_from_text(text)



def _fetch_candidates_scope(driver, material_code: str) -> List[CandidateAccessory]:
    mc = (material_code or "").strip()
    if not mc:
        return []

    query = """
    CALL {
      MATCH (m:Material {material_code: $material_code})-[:HAS_PRODUCT]->(p:Product)
      MATCH (p)-[:USES_BOM]->(b:BOM {bom_id: p.bom_id})
      MATCH (b)-[:HAS_ACCESSORY]->(a:Accessory)
      RETURN DISTINCT a
      UNION
      MATCH (m:Material {material_code: $material_code})-[:HAS_PRODUCT]->(p:Product)
      MATCH (p)-[:HAS_ACCESSORY]->(a:Accessory)
      RETURN DISTINCT a
    }
    WITH DISTINCT a
    WHERE a IS NOT NULL
      AND a.name_zh IS NOT NULL AND trim(a.name_zh) <> ''
      AND (a.name_en IS NULL OR trim(a.name_en) = '')
    RETURN elementId(a) AS element_id,
           a.name_zh AS name_zh
    ORDER BY name_zh
    """

    items: List[CandidateAccessory] = []
    with driver.session() as session:
        res = session.run(query, {"material_code": mc})
        for r in res:
            eid = r.get("element_id")
            name_zh = r.get("name_zh")
            if not eid or not name_zh:
                continue
            items.append(CandidateAccessory(element_id=str(eid), name_zh=str(name_zh)))
    return items


def _fetch_candidates_global(driver) -> List[CandidateAccessory]:
    query = """
    MATCH (a:Accessory)
    WHERE a.name_zh IS NOT NULL AND trim(a.name_zh) <> ''
      AND (a.name_en IS NULL OR trim(a.name_en) = '')
    RETURN elementId(a) AS element_id,
           a.name_zh AS name_zh
    ORDER BY name_zh
    """

    items: List[CandidateAccessory] = []
    with driver.session() as session:
        res = session.run(query)
        for r in res:
            eid = r.get("element_id")
            name_zh = r.get("name_zh")
            if not eid or not name_zh:
                continue
            items.append(CandidateAccessory(element_id=str(eid), name_zh=str(name_zh)))
    return items


def _unit_normalize_rows(vecs: Sequence[Sequence[float]]) -> np.ndarray:
    mat = np.array(vecs, dtype=np.float32)
    norms = np.linalg.norm(mat, axis=1, keepdims=True)
    norms = np.where(norms == 0, 1.0, norms)
    return mat / norms


def _embed_texts(texts: List[str], cfg: LLMConfig) -> List[List[float]]:
    if not texts:
        return []
    return embed_texts(texts, cfg)


def _top_k_sim(
    query_vec: np.ndarray,
    cand_unit: np.ndarray,
    k: int,
) -> List[Tuple[int, float]]:
    scores = cand_unit @ query_vec
    k_eff = min(k, scores.shape[0])
    if k_eff <= 0:
        return []

    idx = np.argpartition(-scores, k_eff - 1)[:k_eff]
    idx_sorted = idx[np.argsort(-scores[idx])]
    return [(int(i), float(scores[i])) for i in idx_sorted]


def _extract_json_object(text: str) -> Optional[dict]:
    if not text:
        return None
    m = re.search(r"\{[\s\S]*\}", text)
    if not m:
        return None
    raw = m.group(0)
    try:
        return json.loads(raw)
    except Exception:
        return None


def _llm_choose_candidate(
    en_phrase: str,
    candidates: List[Tuple[CandidateAccessory, float]],
    llm_cfg: LLMConfig,
    timeout_s: int = 60,
) -> Tuple[Optional[str], Optional[float], str]:
    items = [
        {"id": c.element_id, "name_zh": c.name_zh, "score": round(score, 4)}
        for c, score in candidates
    ]
    prompt = (
        "你是一个中英文对齐助手。\n"
        "给定一个英文功能/配件短语，以及若干候选的中文配件名称，请选择最匹配的一项。\n"
        "如果都不匹配，请返回 chosen_id 为 null。\n"
        "请只输出 JSON，对应字段：chosen_id, confidence, reason。\n\n"
        f"英文短语: {en_phrase}\n"
        f"候选列表: {json.dumps(items, ensure_ascii=False)}\n"
    )

    kwargs: Dict[str, Any] = {
        "model": llm_cfg.model,
        "messages": [
            {"role": "system", "content": "只输出 JSON，不要输出多余文字。"},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.0,
    }
    if llm_cfg.api_key:
        kwargs["api_key"] = llm_cfg.api_key
    if llm_cfg.base_url:
        kwargs["api_base"] = llm_cfg.base_url

    resp = completion(**kwargs)
    content = resp["choices"][0]["message"]["content"]
    obj = _extract_json_object(content)
    if not obj:
        return None, None, (content or "").strip()

    chosen = obj.get("chosen_id")
    conf = obj.get("confidence")
    reason = (obj.get("reason") or "").strip()

    if chosen is None:
        return None, float(conf) if isinstance(conf, (int, float)) else None, reason

    chosen_s = str(chosen).strip()
    if not chosen_s:
        return None, float(conf) if isinstance(conf, (int, float)) else None, reason

    if not isinstance(conf, (int, float)):
        conf_val: Optional[float] = None
    else:
        conf_val = float(conf)

    return chosen_s, conf_val, reason


def _should_use_llm(best: float, second: float, threshold: float) -> bool:
    if best < threshold:
        return False
    if best - second < 0.03:
        return True
    if best - threshold < 0.03:
        return True
    return False


def match_phrases_to_candidates(
    material_code: str,
    phrases: List[Tuple[str, str]],
    scope_candidates: List[CandidateAccessory],
    global_candidates: List[CandidateAccessory],
    embedding_cfg: LLMConfig,
    llm_cfg: Optional[LLMConfig],
    threshold_scope: float,
    threshold_global: float,
    top_k: int,
    llm_conf_threshold: float,
) -> Tuple[List[MatchResult], List[Dict[str, Any]]]:
    if not phrases:
        return [], []

    scope_texts = [c.name_zh for c in scope_candidates]
    scope_vecs = _embed_texts(scope_texts, embedding_cfg)
    scope_unit = _unit_normalize_rows(scope_vecs) if scope_vecs else np.zeros((0, 1), dtype=np.float32)

    phrase_texts = [p[1] for p in phrases]
    phrase_vecs = _embed_texts(phrase_texts, embedding_cfg)
    phrase_unit = _unit_normalize_rows(phrase_vecs) if phrase_vecs else np.zeros((0, 1), dtype=np.float32)

    matches_by_accessory: Dict[str, MatchResult] = {}
    unmatched: List[Dict[str, Any]] = []

    # Collect phrases that fail scope match for potential global fallback.
    pending_global: List[Tuple[int, str, str, List[Tuple[int, float]]]] = []

    global_unit: Optional[np.ndarray] = None

    for idx, (pdf_path, en_phrase) in enumerate(phrases):
        if idx >= phrase_unit.shape[0]:
            break

        q = phrase_unit[idx]

        best_scope = None
        scope_rank = []
        if scope_candidates:
            scope_rank = _top_k_sim(q, scope_unit, top_k)
            if scope_rank:
                best_i, best_s = scope_rank[0]
                second_s = scope_rank[1][1] if len(scope_rank) > 1 else -1.0
                if best_s >= threshold_scope:
                    chosen = scope_candidates[best_i]
                    chosen_score = best_s
                    llm_used = False
                    llm_conf = None
                    llm_reason = ""

                    if llm_cfg and _should_use_llm(best_s, second_s, threshold_scope):
                        llm_used = True
                        cand_for_llm = [(scope_candidates[i], s) for i, s in scope_rank]
                        chosen_id, llm_conf, llm_reason = _llm_choose_candidate(en_phrase, cand_for_llm, llm_cfg)
                        if chosen_id and llm_conf is not None and llm_conf >= llm_conf_threshold:
                            if chosen_id in {c.element_id for c, _ in cand_for_llm}:
                                chosen = next(c for c, _ in cand_for_llm if c.element_id == chosen_id)
                                chosen_score = next(s for c, s in cand_for_llm if c.element_id == chosen_id)
                            else:
                                chosen = None
                        else:
                            chosen = None

                    if chosen:
                        mr = MatchResult(
                            material_code=material_code,
                            accessory_element_id=chosen.element_id,
                            accessory_name_zh=chosen.name_zh,
                            matched_en=en_phrase,
                            score=float(chosen_score),
                            match_scope="material_code",
                            source_pdf=pdf_path,
                            llm_used=llm_used,
                            llm_confidence=llm_conf,
                            llm_reason=llm_reason,
                        )
                        prev = matches_by_accessory.get(chosen.element_id)
                        if prev is None or mr.score > prev.score:
                            matches_by_accessory[chosen.element_id] = mr
                        continue

        # Defer global embedding and search until we confirm at least one phrase needs fallback.
        pending_global.append((idx, pdf_path, en_phrase, scope_rank[:top_k]))
        continue

    if pending_global and global_candidates:
        global_texts = [c.name_zh for c in global_candidates]
        global_vecs = _embed_texts(global_texts, embedding_cfg) if global_texts else []
        global_unit = _unit_normalize_rows(global_vecs) if global_vecs else np.zeros((0, 1), dtype=np.float32)

    for idx, pdf_path, en_phrase, scope_rank_short in pending_global:
        if idx >= phrase_unit.shape[0]:
            continue

        q = phrase_unit[idx]
        global_rank: List[Tuple[int, float]] = []

        if global_candidates and global_unit is not None and global_unit.size:
            global_rank = _top_k_sim(q, global_unit, top_k)
            if global_rank:
                best_i, best_s = global_rank[0]
                second_s = global_rank[1][1] if len(global_rank) > 1 else -1.0
                if best_s >= threshold_global:
                    chosen = global_candidates[best_i]
                    chosen_score = best_s
                    llm_used = False
                    llm_conf = None
                    llm_reason = ""

                    if llm_cfg and _should_use_llm(best_s, second_s, threshold_global):
                        llm_used = True
                        cand_for_llm = [(global_candidates[i], s) for i, s in global_rank]
                        chosen_id, llm_conf, llm_reason = _llm_choose_candidate(en_phrase, cand_for_llm, llm_cfg)
                        if chosen_id and llm_conf is not None and llm_conf >= llm_conf_threshold:
                            if chosen_id in {c.element_id for c, _ in cand_for_llm}:
                                chosen = next(c for c, _ in cand_for_llm if c.element_id == chosen_id)
                                chosen_score = next(s for c, s in cand_for_llm if c.element_id == chosen_id)
                            else:
                                chosen = None
                        else:
                            chosen = None

                    if chosen:
                        mr = MatchResult(
                            material_code=material_code,
                            accessory_element_id=chosen.element_id,
                            accessory_name_zh=chosen.name_zh,
                            matched_en=en_phrase,
                            score=float(chosen_score),
                            match_scope="global_fallback",
                            source_pdf=pdf_path,
                            llm_used=llm_used,
                            llm_confidence=llm_conf,
                            llm_reason=llm_reason,
                        )
                        prev = matches_by_accessory.get(chosen.element_id)
                        if prev is None or mr.score > prev.score:
                            matches_by_accessory[chosen.element_id] = mr
                        continue

        unmatched.append(
            {
                "material_code": material_code,
                "pdf": pdf_path,
                "en_phrase": en_phrase,
                "scope_top": [
                    {
                        "accessory_element_id": scope_candidates[i].element_id,
                        "name_zh": scope_candidates[i].name_zh,
                        "score": s,
                    }
                    for i, s in scope_rank_short
                ],
                "global_top": [
                    {
                        "accessory_element_id": global_candidates[i].element_id,
                        "name_zh": global_candidates[i].name_zh,
                        "score": s,
                    }
                    for i, s in global_rank[:top_k]
                ],
            }
        )

    return list(matches_by_accessory.values()), unmatched


def _write_csv(path: Path, rows: List[MatchResult]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "material_code",
                "accessory_element_id",
                "accessory_name_zh",
                "name_en",
                "score",
                "match_scope",
                "source_pdf",
                "llm_used",
                "llm_confidence",
                "llm_reason",
            ]
        )
        for r in rows:
            w.writerow(
                [
                    r.material_code,
                    r.accessory_element_id,
                    r.accessory_name_zh,
                    r.matched_en,
                    f"{r.score:.6f}",
                    r.match_scope,
                    r.source_pdf,
                    str(bool(r.llm_used)),
                    "" if r.llm_confidence is None else f"{r.llm_confidence:.4f}",
                    r.llm_reason,
                ]
            )


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_lines(path: Path, lines: List[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def _apply_updates(driver, matches: List[MatchResult]) -> int:
    if not matches:
        return 0

    query = """
    MATCH (a:Accessory)
    WHERE elementId(a) = $element_id
    SET a.name_en = $name_en,
        a.name_en_source_pdf = $source_pdf,
        a.name_en_source_phrase = $source_phrase,
        a.name_en_match_score = $score,
        a.name_en_match_scope = $scope,
        a.name_en_match_method = $method,
        a.name_en_updated_at = $updated_at
    RETURN elementId(a) AS element_id
    """

    updated_at = datetime.now().isoformat(timespec="seconds")

    count = 0
    with driver.session() as session:
        for m in matches:
            method = "embedding+llm" if m.llm_used else "embedding"
            res = session.run(
                query,
                {
                    "element_id": m.accessory_element_id,
                    "name_en": m.matched_en,
                    "source_pdf": m.source_pdf,
                    "source_phrase": m.matched_en,
                    "score": float(m.score),
                    "scope": m.match_scope,
                    "method": method,
                    "updated_at": updated_at,
                },
            )
            if res.single():
                count += 1
    return count


def main() -> int:
    load_dotenv()

    ap = argparse.ArgumentParser()
    ap.add_argument("--material-code", required=True)
    ap.add_argument("--translate-dir", default=str(Path(__file__).resolve().parent.parent / "translate"))
    ap.add_argument("--report-dir", default=str(Path(__file__).resolve().parent.parent / "translate_reports"))

    ap.add_argument("--threshold-scope", type=float, default=0.78)
    ap.add_argument("--threshold-global", type=float, default=0.82)
    ap.add_argument("--top-k", type=int, default=5)
    ap.add_argument("--llm-conf-threshold", type=float, default=0.6)

    ap.add_argument("--use-llm", action="store_true")
    ap.add_argument("--llm-provider", default=None)
    ap.add_argument("--llm-model", default=None)

    ap.add_argument("--limit-pdfs", type=int, default=0)
    ap.add_argument("--limit-phrases", type=int, default=0)

    ap.add_argument("--apply", action="store_true")

    args = ap.parse_args()

    material_code = (args.material_code or "").strip()
    translate_dir = Path(args.translate_dir).resolve()
    report_dir = Path(args.report_dir).resolve() / f"{material_code}_{_now_tag()}"

    backend_status = _pdf_backend_status()

    neo4j_cfg = get_neo4j_config()
    driver = get_neo4j_driver(neo4j_cfg)

    try:
        scope_candidates = _fetch_candidates_scope(driver, material_code)
        if not scope_candidates:
            raise RuntimeError(f"material_code={material_code} 范围内未找到缺少 name_en 的 Accessory")

        global_candidates: List[CandidateAccessory] = []
        llm_cfg: Optional[LLMConfig] = None
        if args.use_llm:
            llm_cfg = get_llm_config(llm_provider=args.llm_provider, llm_model=args.llm_model)

        embedding_cfg = get_embedding_config()

        pdfs = list(iter_pdf_files(translate_dir))
        if args.limit_pdfs and args.limit_pdfs > 0:
            pdfs = pdfs[: args.limit_pdfs]

        phrases: List[Tuple[str, str]] = []
        pdf_parse_failures: List[str] = []
        for pdf in pdfs:
            en_items = parse_pdf_to_phrases(pdf, lang="en")
            if not en_items:
                pdf_parse_failures.append(pdf.as_posix())
            for item in en_items:
                phrases.append((pdf.as_posix(), item))

        extracted_payload = {
            "material_code": material_code,
            "translate_dir": str(translate_dir),
            "pdfs_total": len(pdfs),
            "pdfs_failed": len(pdf_parse_failures),
            "backends": backend_status,
            "phrases": [
                {
                    "pdf": pdf,
                    "en_phrase": phrase,
                }
                for pdf, phrase in phrases
            ],
        }
        _write_json(report_dir / "extracted_phrases.json", extracted_payload)
        _write_lines(report_dir / "extracted_phrases.txt", [p[1] for p in phrases])

        if not phrases:
            detail = {
                "translate_dir": str(translate_dir),
                "pdfs_total": len(pdfs),
                "pdfs_failed": len(pdf_parse_failures),
                "backends": backend_status,
                "hint": "当前环境缺少 mineru 或 PDF 文本提取库时，扫描型 PDF 将无法解析。可以安装 pymupdf 或 pypdf，或安装/启用 mineru。",
                "suggest": [
                    "pip install pymupdf",
                    "pip install pypdf",
                    "或在项目的 uv/venv 环境中安装 mineru 并使用同一环境运行脚本",
                ],
            }
            raise RuntimeError(
                "未从 translate_dir 提取到任何英文短语。\n" + json.dumps(detail, ensure_ascii=False, indent=2)
            )

        if args.limit_phrases and args.limit_phrases > 0:
            phrases = phrases[: args.limit_phrases]

        global_candidates = _fetch_candidates_global(driver)

        matched, unmatched = match_phrases_to_candidates(
            material_code=material_code,
            phrases=phrases,
            scope_candidates=scope_candidates,
            global_candidates=global_candidates,
            embedding_cfg=embedding_cfg,
            llm_cfg=llm_cfg,
            threshold_scope=float(args.threshold_scope),
            threshold_global=float(args.threshold_global),
            top_k=int(args.top_k),
            llm_conf_threshold=float(args.llm_conf_threshold),
        )

        _write_csv(report_dir / "matched.csv", matched)
        _write_json(report_dir / "unmatched.json", unmatched)

        if args.apply:
            updated = _apply_updates(driver, matched)
            _write_json(
                report_dir / "apply_summary.json",
                {
                    "material_code": material_code,
                    "updated": updated,
                    "matched": len(matched),
                    "unmatched_phrases": len(unmatched),
                },
            )
            print(f"Updated {updated} accessories. Report: {report_dir}")
        else:
            print(f"Dry run complete. Matched={len(matched)} UnmatchedPhrases={len(unmatched)} Report: {report_dir}")

        return 0
    finally:
        driver.close()


if __name__ == "__main__":
    raise SystemExit(main())

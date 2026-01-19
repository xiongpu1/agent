import argparse
import csv
import json
import re
import sys
import time
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
from src.bom_config import get_bom_sections
from src.dataclass import LLMConfig
from src.neo4j_file_add_neo4j import embed_texts, get_neo4j_driver
from src.rag_specsheet import get_embedding_config, get_llm_config
from src.translate_accessory_name_en_from_pdfs import (  # type: ignore
    _pdf_backend_status,
    iter_pdf_files,
    parse_pdf_to_phrases,
)


def _split_filename_tokens(p: Path) -> List[str]:
    base = p.stem
    base = re.sub(r"\s+", " ", base).strip()
    parts = re.split(r"[^0-9A-Za-z\u4e00-\u9fff]+", base)
    out: List[str] = []
    for x in [base, *parts]:
        s = (x or "").strip()
        if not s:
            continue
        if len(s) < 3:
            continue
        if s not in out:
            out.append(s)
    return out


def _fuzzy_match_material_codes(driver, query: str, limit: int = 20) -> List[str]:
    q = (query or "").strip()
    if not q:
        return []

    cypher = """
    MATCH (m:Material)
    WHERE m.material_code IS NOT NULL AND trim(m.material_code) <> ''
      AND (
        toLower(m.material_code) = toLower($q)
        OR toLower(m.material_code) STARTS WITH toLower($q)
        OR toLower(m.material_code) CONTAINS toLower($q)
        OR toLower($q) CONTAINS toLower(m.material_code)
      )
    RETURN DISTINCT m.material_code AS material_code
    LIMIT $limit
    """

    hits: List[str] = []
    with driver.session() as session:
        res = session.run(cypher, {"q": q, "limit": int(limit)})
        for r in res:
            mc = r.get("material_code")
            if mc:
                hits.append(str(mc))
    return hits


def _rank_material_code_hits(raw_query: str, hits: List[str]) -> List[Tuple[str, int]]:
    q = (raw_query or "").strip().lower()
    ranked: List[Tuple[str, int]] = []
    for mc in hits:
        m = (mc or "").strip()
        ml = m.lower()
        if not q or not m:
            continue
        score = 0
        if ml == q:
            score += 100
        if ml.startswith(q):
            score += 40
        if q and q in ml:
            score += 20
        if ml and ml in q:
            score += 10
        score += min(len(m), 50) // 5
        ranked.append((m, score))
    ranked.sort(key=lambda x: (-x[1], x[0]))
    return ranked


def _infer_material_code_from_pdfs(driver, pdfs: List[Path]) -> str:
    if not pdfs:
        raise RuntimeError("translate_dir 下没有找到任何 PDF，无法推断 material_code")

    # aggregate hits across filenames
    agg: Dict[str, int] = {}
    for p in pdfs[:200]:
        for token in _split_filename_tokens(p):
            hits = _fuzzy_match_material_codes(driver, token, limit=30)
            ranked = _rank_material_code_hits(token, hits)
            for mc, score in ranked:
                agg[mc] = agg.get(mc, 0) + score

    if not agg:
        sample = "\n".join([x.name for x in pdfs[:5]])
        raise RuntimeError(
            "无法从 PDF 文件名推断 material_code；请手动传 --material-code。"
            f"\n示例文件名:\n{sample}"
        )

    ranked_all = sorted(agg.items(), key=lambda x: (-x[1], x[0]))
    best_code, best_score = ranked_all[0]
    second_score = ranked_all[1][1] if len(ranked_all) > 1 else -1

    # If ambiguous, fail fast with candidates for manual selection.
    if best_score <= 0 or (second_score >= 0 and best_score - second_score < 30):
        top = ranked_all[:10]
        raise RuntimeError(
            "material_code 推断结果不唯一，请手动传 --material-code。\n"
            "候选(按得分降序):\n"
            + "\n".join([f"- {c} ({s})" for c, s in top])
        )

    return best_code


@dataclass
class CandidateBomOption:
    section_key: str
    section_label: str
    code: str
    name_zh: str


@dataclass
class MatchRow:
    material_code: str
    bom_type: str
    section_key: str
    section_label: str
    code: str
    name_zh: str
    en_phrase: str
    score: float
    source_pdf: str
    llm_used: bool
    llm_confidence: Optional[float]
    llm_reason: str


@dataclass
class CandidateCache:
    bom_type: str
    candidates: List[CandidateBomOption]
    cand_unit: np.ndarray


PRODUCT_TYPE_ZH_TO_BOM_TYPE: Dict[str, str] = {
    "户外缸": "outdoor",
    "泳池": "pool",
    "冰水缸": "iceTub",
}


def _now_tag() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_lines(path: Path, lines: List[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def _write_csv(path: Path, rows: List[MatchRow]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "material_code",
                "bom_type",
                "section_key",
                "section_label",
                "code",
                "name_zh",
                "en_phrase",
                "score",
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
                    r.bom_type,
                    r.section_key,
                    r.section_label,
                    r.code,
                    r.name_zh,
                    r.en_phrase,
                    f"{r.score:.6f}",
                    r.source_pdf,
                    str(bool(r.llm_used)),
                    "" if r.llm_confidence is None else f"{r.llm_confidence:.4f}",
                    r.llm_reason,
                ]
            )


def _write_csv_readable(path: Path, rows: List[MatchRow]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "source_pdf",
                "en_phrase",
                "name_zh",
                "section_label",
                "section_key",
                "code",
                "llm_confidence",
                "score",
                "llm_reason",
            ]
        )
        for r in rows:
            w.writerow(
                [
                    r.source_pdf,
                    r.en_phrase,
                    r.name_zh,
                    r.section_label,
                    r.section_key,
                    r.code,
                    "" if r.llm_confidence is None else f"{r.llm_confidence:.4f}",
                    f"{r.score:.6f}",
                    r.llm_reason,
                ]
            )


def _unit_normalize_rows(vecs: Sequence[Sequence[float]]) -> np.ndarray:
    mat = np.array(vecs, dtype=np.float32)
    norms = np.linalg.norm(mat, axis=1, keepdims=True)
    norms = np.where(norms == 0, 1.0, norms)
    return mat / norms


def _top_k_sim(query_vec: np.ndarray, cand_unit: np.ndarray, k: int) -> List[Tuple[int, float]]:
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


def _should_use_llm(best: float, second: float, threshold: float) -> bool:
    if best < threshold:
        return False
    if best - second < 0.03:
        return True
    if best - threshold < 0.03:
        return True
    return False


def _llm_choose_bom_option(
    en_phrase: str,
    candidates: List[Tuple[CandidateBomOption, float]],
    llm_cfg: LLMConfig,
) -> Tuple[Optional[str], Optional[float], str]:
    items = [
        {
            "section_key": c.section_key,
            "code": c.code,
            "name_zh": c.name_zh,
            "score": round(score, 4),
        }
        for c, score in candidates
    ]

    prompt = (
        "你是一个英文短语到产品配置项的对齐助手。\n"
        "给定一个英文配置/功能短语，以及若干候选的中文配置项（带 section_key 和 code），请选择最匹配的一项。\n"
        "如果都不匹配，请返回 chosen 为 null。\n"
        "请只输出 JSON，对应字段：chosen, confidence, reason。\n\n"
        "字段说明：chosen 必须是候选中的 {section_key, code} 组合，或者为 null。\n\n"
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

    chosen = obj.get("chosen")
    conf = obj.get("confidence")
    reason = (obj.get("reason") or "").strip()

    if chosen is None:
        return None, float(conf) if isinstance(conf, (int, float)) else None, reason

    if not isinstance(chosen, dict):
        return None, float(conf) if isinstance(conf, (int, float)) else None, reason

    sk = str(chosen.get("section_key") or "").strip()
    code = str(chosen.get("code") or "").strip()
    if not sk or not code:
        return None, float(conf) if isinstance(conf, (int, float)) else None, reason

    conf_val: Optional[float]
    if isinstance(conf, (int, float)):
        conf_val = float(conf)
    else:
        conf_val = None

    return f"{sk}::{code}", conf_val, reason


def _llm_choose_bom_option_batch(
    items: List[Tuple[str, List[Tuple[CandidateBomOption, float]]]],
    llm_cfg: LLMConfig,
    timeout_s: Optional[float] = None,
) -> List[Tuple[Optional[str], Optional[float], str]]:
    tasks = []
    for i, (en_phrase, candidates) in enumerate(items):
        tasks.append(
            {
                "i": i,
                "en_phrase": en_phrase,
                "candidates": [
                    {
                        "section_key": c.section_key,
                        "code": c.code,
                        "name_zh": c.name_zh,
                        "score": round(score, 4),
                    }
                    for c, score in candidates
                ],
            }
        )

    prompt = (
        "你将收到一个 tasks JSON 数组。\n"
        "对每个任务，从 candidates 中选择最匹配的一项；如果都不匹配，chosen 为 null。\n"
        "你必须只输出一个 JSON 数组（不能有任何多余文字/解释/markdown）。\n"
        "数组中每个元素必须包含字段：i, chosen, confidence, reason。\n"
        "chosen 必须是候选中的 {section_key, code} 组合，或者为 null。\n\n"
        f"tasks={json.dumps(tasks, ensure_ascii=False)}\n"
        "\n输出示例："
        "[{\"i\":0,\"chosen\":{\"section_key\":\"lighting\",\"code\":\"A\"},\"confidence\":0.83,\"reason\":\"...\"},"
        "{\"i\":1,\"chosen\":null,\"confidence\":0.2,\"reason\":\"...\"}]"
    )

    kwargs: Dict[str, Any] = {
        "model": llm_cfg.model,
        "messages": [
            {
                "role": "system",
                "content": "严格输出 JSON。不要输出任何解释、标题、markdown 或多余文字。",
            },
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.0,
    }
    # Ollama supports JSON mode via `format: json`. litellm will forward it.
    # Some models may still return an object; we handle both list and dict.
    if str(llm_cfg.model).startswith("ollama/"):
        kwargs["format"] = "json"
    if llm_cfg.api_key:
        kwargs["api_key"] = llm_cfg.api_key
    if llm_cfg.base_url:
        kwargs["api_base"] = llm_cfg.base_url

    def _extract_array_from_json_payload(payload: Any) -> Optional[list]:
        if isinstance(payload, list):
            return payload
        if isinstance(payload, dict):
            for k in ("results", "items", "data", "output"):
                v = payload.get(k)
                if isinstance(v, list):
                    return v
        return None

    def _call_and_parse(call_kwargs: Dict[str, Any]) -> Tuple[Optional[list], str]:
        try:
            resp = completion(**call_kwargs)
            content = resp["choices"][0]["message"]["content"]
            raw = (content or "").strip()

            # 1) If JSON mode works, content is usually directly parseable.
            try:
                payload = json.loads(raw)
                arr = _extract_array_from_json_payload(payload)
                if arr is not None and len(arr) > 0:
                    return arr, raw
                # {} or empty array treated as failure
            except Exception:
                pass

            # 2) Fallback: try to extract a JSON array substring.
            m = re.search(r"\[[\s\S]*\]", raw)
            if not m:
                return None, raw
            try:
                payload = json.loads(m.group(0))
                arr = _extract_array_from_json_payload(payload)
                if arr is not None and len(arr) > 0:
                    return arr, raw
                return None, raw
            except Exception:
                return None, raw
        except Exception as e:
            return None, f"LLM_CALL_ERROR: {type(e).__name__}: {e}"

    if timeout_s is not None:
        try:
            t = float(timeout_s)
            if t > 0:
                kwargs["timeout"] = t
                kwargs["request_timeout"] = t
        except Exception:
            pass

    arr, raw = _call_and_parse(kwargs)
    if arr is None:
        # One retry with an even stricter instruction.
        retry_kwargs = dict(kwargs)
        retry_kwargs["messages"] = [
            {
                "role": "system",
                "content": "只输出 JSON 数组本体（以 [ 开头，以 ] 结尾）。输出任何其他字符都会被判错。",
            },
            {"role": "user", "content": prompt},
        ]
        # Retry without format=json, because some models return `{}` under JSON mode.
        if "format" in retry_kwargs:
            retry_kwargs.pop("format", None)

        print("[bom-match] LLM parse failed; retrying once without JSON mode...", flush=True)
        arr, raw2 = _call_and_parse(retry_kwargs)
        if arr is None:
            return [(None, None, raw2 or raw) for _ in items]

    out: List[Tuple[Optional[str], Optional[float], str]] = [(None, None, "") for _ in items]
    if not isinstance(arr, list):
        return [(None, None, raw) for _ in items]

    for obj in arr:
        if not isinstance(obj, dict):
            continue
        i = obj.get("i")
        if not isinstance(i, int) or i < 0 or i >= len(items):
            continue
        chosen = obj.get("chosen")
        conf = obj.get("confidence")
        reason = (obj.get("reason") or "").strip()

        conf_val: Optional[float]
        if isinstance(conf, (int, float)):
            conf_val = float(conf)
        else:
            conf_val = None

        if chosen is None:
            out[i] = (None, conf_val, reason)
            continue

        if not isinstance(chosen, dict):
            out[i] = (None, conf_val, reason)
            continue

        sk = str(chosen.get("section_key") or "").strip()
        code = str(chosen.get("code") or "").strip()
        if not sk or not code:
            out[i] = (None, conf_val, reason)
            continue
        out[i] = (f"{sk}::{code}", conf_val, reason)

    return out


def _fetch_product_type_zh(driver, material_code: str) -> str:
    mc = (material_code or "").strip()
    if not mc:
        raise ValueError("material_code 不能为空")

    query = """
    MATCH (m:Material {material_code: $material_code})
    RETURN m.product_type_zh AS product_type_zh
    LIMIT 1
    """
    with driver.session() as session:
        r = session.run(query, {"material_code": mc}).single()
        if not r:
            raise RuntimeError(f"未找到 material_code={mc} 的 Material 节点")
        t = r.get("product_type_zh")
        if not t:
            raise RuntimeError(f"material_code={mc} 缺少 product_type_zh")
        return str(t)


def _safe_dirname(s: str) -> str:
    x = (s or "").strip()
    x = re.sub(r"\s+", "_", x)
    x = re.sub(r"[^0-9A-Za-z_\-\u4e00-\u9fff]+", "_", x)
    x = re.sub(r"_+", "_", x).strip("_")
    return x or "item"


def _get_candidate_cache(
    *,
    bom_type: str,
    embedding_cfg: Any,
    cache: Dict[str, CandidateCache],
) -> CandidateCache:
    hit = cache.get(bom_type)
    if hit is not None:
        return hit

    candidates = _build_candidates(bom_type)
    if not candidates:
        raise RuntimeError(f"bom_type={bom_type} 未找到任何候选配置项")

    cand_texts = [f"{c.section_label} {c.name_zh}" for c in candidates]
    cand_vecs = embed_texts(cand_texts, embedding_cfg)
    cand_unit = _unit_normalize_rows(cand_vecs) if cand_vecs else np.zeros((0, 1), dtype=np.float32)

    out = CandidateCache(bom_type=bom_type, candidates=candidates, cand_unit=cand_unit)
    cache[bom_type] = out
    return out


def _match_phrases_to_candidates(
    *,
    material_code: str,
    product_type_zh: str,
    bom_type: str,
    pdf_path: Path,
    phrases: List[str],
    cand_cache: CandidateCache,
    embedding_cfg: Any,
    threshold: float,
    top_k: int,
    llm_top_k: int,
    llm_batch_size: int,
    llm_cfg: Optional[LLMConfig],
    llm_conf_threshold: float,
    llm_timeout_s: Optional[float] = None,
) -> Tuple[List[MatchRow], List[Dict[str, Any]], List[Dict[str, Any]]]:
    if not phrases:
        return [], [], []

    phrase_vecs = embed_texts(list(phrases), embedding_cfg)
    phrase_unit = _unit_normalize_rows(phrase_vecs) if phrase_vecs else np.zeros((0, 1), dtype=np.float32)

    matched_rows: List[MatchRow] = []
    unmatched: List[Dict[str, Any]] = []
    llm_decisions: List[Dict[str, Any]] = []

    candidates = cand_cache.candidates
    cand_unit = cand_cache.cand_unit

    ranks: List[List[Tuple[int, float]]] = []
    for idx, _en_phrase in enumerate(phrases):
        if idx >= phrase_unit.shape[0] or cand_unit.size == 0:
            break
        q = phrase_unit[idx]
        ranks.append(_top_k_sim(q, cand_unit, int(max(top_k, llm_top_k))))

    if not llm_cfg:
        for idx, en_phrase in enumerate(phrases[: len(ranks)]):
            rank = ranks[idx]
            if not rank:
                unmatched.append({"material_code": material_code, "pdf": pdf_path.as_posix(), "en_phrase": en_phrase, "top": []})
                continue

            best_i, best_s = rank[0]
            if best_s < float(threshold):
                unmatched.append(
                    {
                        "material_code": material_code,
                        "product_type_zh": product_type_zh,
                        "bom_type": bom_type,
                        "pdf": pdf_path.as_posix(),
                        "en_phrase": en_phrase,
                        "top": [
                            {
                                "section_key": candidates[i].section_key,
                                "section_label": candidates[i].section_label,
                                "code": candidates[i].code,
                                "name_zh": candidates[i].name_zh,
                                "score": s,
                            }
                            for i, s in rank[: int(top_k)]
                        ],
                    }
                )
                continue

            chosen = candidates[best_i]
            matched_rows.append(
                MatchRow(
                    material_code=material_code,
                    bom_type=bom_type,
                    section_key=chosen.section_key,
                    section_label=chosen.section_label,
                    code=chosen.code,
                    name_zh=chosen.name_zh,
                    en_phrase=en_phrase,
                    score=float(best_s),
                    source_pdf=pdf_path.as_posix(),
                    llm_used=False,
                    llm_confidence=None,
                    llm_reason="",
                )
            )
        return matched_rows, unmatched, llm_decisions

    batch_size = max(1, int(llm_batch_size))
    total_batches = (len(ranks) + batch_size - 1) // batch_size
    for start in range(0, len(ranks), batch_size):
        end = min(start + batch_size, len(ranks))
        batch_items: List[Tuple[str, List[Tuple[CandidateBomOption, float]]]] = []
        batch_meta: List[Dict[str, Any]] = []
        for j in range(start, end):
            en_phrase = phrases[j]
            rank = ranks[j]
            cand_for_llm = [(candidates[i], s) for i, s in rank[: int(llm_top_k)]]
            batch_items.append((en_phrase, cand_for_llm))
            batch_meta.append(
                {
                    "material_code": material_code,
                    "product_type_zh": product_type_zh,
                    "bom_type": bom_type,
                    "pdf": pdf_path.as_posix(),
                    "en_phrase": en_phrase,
                    "top": [
                        {
                            "section_key": c.section_key,
                            "section_label": c.section_label,
                            "code": c.code,
                            "name_zh": c.name_zh,
                            "score": s,
                        }
                        for c, s in cand_for_llm
                    ],
                }
            )

        batch_idx = (start // batch_size) + 1
        print(
            f"[bom-match] LLM batch {batch_idx}/{total_batches} phrases={len(batch_items)} model={llm_cfg.model} pdf={pdf_path.name}",
            flush=True,
        )
        t0 = time.perf_counter()
        decisions = _llm_choose_bom_option_batch(batch_items, llm_cfg, timeout_s=llm_timeout_s)
        dt = time.perf_counter() - t0
        print(
            f"[bom-match] LLM batch {batch_idx}/{total_batches} done in {dt:.1f}s",
            flush=True,
        )
        for off, (chosen_key, llm_conf, llm_reason) in enumerate(decisions):
            meta = batch_meta[off]
            llm_decisions.append(
                {
                    **meta,
                    "llm_model": llm_cfg.model,
                    "llm_chosen": chosen_key,
                    "llm_confidence": llm_conf,
                    "llm_reason": llm_reason,
                }
            )

            chosen: Optional[CandidateBomOption] = None
            chosen_score = None
            if chosen_key:
                sk, code = chosen_key.split("::", 1)
                chosen = next((c for c, _s in batch_items[off][1] if c.section_key == sk and c.code == code), None)
                if chosen:
                    chosen_score = next(_s for c, _s in batch_items[off][1] if c.section_key == sk and c.code == code)

            if chosen and llm_conf is not None and float(llm_conf) >= float(llm_conf_threshold):
                matched_rows.append(
                    MatchRow(
                        material_code=material_code,
                        bom_type=bom_type,
                        section_key=chosen.section_key,
                        section_label=chosen.section_label,
                        code=chosen.code,
                        name_zh=chosen.name_zh,
                        en_phrase=str(meta["en_phrase"]),
                        score=float(chosen_score if chosen_score is not None else 0.0),
                        source_pdf=pdf_path.as_posix(),
                        llm_used=True,
                        llm_confidence=llm_conf,
                        llm_reason=llm_reason,
                    )
                )
            else:
                unmatched.append(
                    {
                        **meta,
                        "llm_used": True,
                        "llm_chosen": chosen_key,
                        "llm_confidence": llm_conf,
                        "llm_reason": llm_reason,
                    }
                )

    return matched_rows, unmatched, llm_decisions


def _build_candidates(bom_type: str) -> List[CandidateBomOption]:
    sections = get_bom_sections(bom_type)
    items: List[CandidateBomOption] = []

    for sec in sections:
        sk = str(sec.get("key") or "").strip()
        sl = str(sec.get("label") or "").strip()
        options = sec.get("options")
        if not sk or not sl or not isinstance(options, dict):
            continue

        for code, name_zh in options.items():
            c = str(code).strip()
            nz = str(name_zh).strip()
            if not c or not nz:
                continue
            items.append(CandidateBomOption(section_key=sk, section_label=sl, code=c, name_zh=nz))

    return items


def main() -> int:
    load_dotenv()

    ap = argparse.ArgumentParser()
    ap.add_argument("--material-code", required=False, default=None)
    ap.add_argument("--translate-dir", default=str(Path(__file__).resolve().parent.parent / "translate"))
    ap.add_argument("--report-dir", default=str(Path(__file__).resolve().parent.parent / "translate_reports"))

    ap.add_argument("--threshold", type=float, default=0.80)
    ap.add_argument("--top-k", type=int, default=8)
    ap.add_argument("--llm-conf-threshold", type=float, default=0.6)

    ap.add_argument("--use-llm", action="store_true")
    ap.add_argument("--llm-provider", default="ollama")
    ap.add_argument("--llm-model", default="qwen2.5:14b-instruct")
    ap.add_argument("--llm-top-k", type=int, default=20)
    ap.add_argument("--llm-batch-size", type=int, default=10)
    ap.add_argument("--llm-timeout-s", type=float, default=300.0)

    ap.add_argument("--limit-pdfs", type=int, default=0)
    ap.add_argument("--limit-phrases", type=int, default=0)

    args = ap.parse_args()

    translate_dir = Path(args.translate_dir).resolve()

    neo4j_cfg = get_neo4j_config()
    driver = get_neo4j_driver(neo4j_cfg)

    try:
        pdfs = list(iter_pdf_files(translate_dir))
        if args.limit_pdfs and args.limit_pdfs > 0:
            pdfs = pdfs[: args.limit_pdfs]

        material_code = (args.material_code or "").strip() if args.material_code else ""
        per_pdf_mode = not bool(material_code)

        llm_cfg: Optional[LLMConfig] = None
        if args.use_llm:
            if str(args.llm_provider).strip().lower() == "ollama":
                llm_cfg = LLMConfig(model=f"ollama/{str(args.llm_model).strip()}")
                llm_cfg.base_url = "http://localhost:11434"
            else:
                llm_cfg = get_llm_config(llm_provider=args.llm_provider, llm_model=args.llm_model)

        embedding_cfg = get_embedding_config()

        run_root = Path(args.report_dir).resolve() / f"bom_match_{_now_tag()}"
        run_root.mkdir(parents=True, exist_ok=True)
        candidate_cache: Dict[str, CandidateCache] = {}

        all_matched: List[MatchRow] = []
        all_unmatched: List[Dict[str, Any]] = []
        per_pdf_index: List[Dict[str, Any]] = []
        pdf_errors: List[Dict[str, Any]] = []

        if not pdfs:
            raise RuntimeError("translate_dir 下没有找到任何 PDF")

        if not per_pdf_mode:
            # Legacy behavior: all PDFs treated as one material_code
            product_type_zh = _fetch_product_type_zh(driver, material_code)
            bom_type = PRODUCT_TYPE_ZH_TO_BOM_TYPE.get(product_type_zh)
            if not bom_type:
                raise RuntimeError(f"product_type_zh={product_type_zh} 无法映射到 bom_type")

            cand_cache = _get_candidate_cache(bom_type=bom_type, embedding_cfg=embedding_cfg, cache=candidate_cache)

            phrases: List[Tuple[str, str]] = []
            pdf_parse_failures: List[str] = []
            for pdf in pdfs:
                en_items = parse_pdf_to_phrases(pdf, lang="en")
                if not en_items:
                    pdf_parse_failures.append(pdf.as_posix())
                for item in en_items:
                    phrases.append((pdf.as_posix(), item))

            phrase_only = [p[1] for p in phrases]
            if args.limit_phrases and args.limit_phrases > 0:
                phrase_only = phrase_only[: args.limit_phrases]

            report_dir = run_root / f"{_safe_dirname(material_code)}_bom"
            extracted_payload = {
                "material_code": material_code,
                "material_code_inferred": False,
                "product_type_zh": product_type_zh,
                "bom_type": bom_type,
                "translate_dir": str(translate_dir),
                "pdfs_total": len(pdfs),
                "pdfs_failed": len(pdf_parse_failures),
                "backends": _pdf_backend_status(),
                "phrases": [{"pdf": p, "en_phrase": x} for p, x in phrases],
            }
            _write_json(report_dir / "extracted_phrases.json", extracted_payload)
            _write_lines(report_dir / "extracted_phrases.txt", phrase_only)

            matched_rows, unmatched, llm_decisions = _match_phrases_to_candidates(
                material_code=material_code,
                product_type_zh=product_type_zh,
                bom_type=bom_type,
                pdf_path=Path("ALL_PDFS"),
                phrases=phrase_only,
                cand_cache=cand_cache,
                embedding_cfg=embedding_cfg,
                threshold=float(args.threshold),
                top_k=int(args.top_k),
                llm_top_k=int(args.llm_top_k),
                llm_batch_size=int(args.llm_batch_size),
                llm_cfg=llm_cfg,
                llm_conf_threshold=float(args.llm_conf_threshold),
                llm_timeout_s=float(args.llm_timeout_s) if args.use_llm else None,
            )
            _write_csv(report_dir / "matched.csv", matched_rows)
            _write_csv_readable(report_dir / "matched_readable.csv", matched_rows)
            _write_json(report_dir / "unmatched.json", unmatched)
            if llm_cfg:
                _write_lines(
                    report_dir / "llm_decisions.jsonl",
                    [json.dumps(x, ensure_ascii=False) for x in llm_decisions],
                )

            best_by_section: Dict[str, Dict[str, Any]] = {}
            for r in matched_rows:
                cur = best_by_section.get(r.section_key)
                if cur is None or float(r.score) > float(cur.get("score", -1)):
                    best_by_section[r.section_key] = {
                        "section_key": r.section_key,
                        "section_label": r.section_label,
                        "code": r.code,
                        "name_zh": r.name_zh,
                        "score": r.score,
                        "source_pdf": r.source_pdf,
                        "en_phrase": r.en_phrase,
                        "llm_used": r.llm_used,
                        "llm_confidence": r.llm_confidence,
                        "llm_reason": r.llm_reason,
                    }
            _write_json(
                report_dir / "best_by_section.json",
                {
                    "material_code": material_code,
                    "product_type_zh": product_type_zh,
                    "bom_type": bom_type,
                    "threshold": float(args.threshold),
                    "top_k": int(args.top_k),
                    "matched": len(matched_rows),
                    "unmatched": len(unmatched),
                    "best_by_section": list(best_by_section.values()),
                },
            )

            print(
                f"Complete(single). material_code={material_code} product_type_zh={product_type_zh} bom_type={bom_type} "
                f"Matched={len(matched_rows)} Unmatched={len(unmatched)} Report={report_dir}"
            )
            return 0

        # per-pdf mode
        for pdf in pdfs:
            try:
                inferred_code = _infer_material_code_from_pdfs(driver, [pdf])
                product_type_zh = _fetch_product_type_zh(driver, inferred_code)
                bom_type = PRODUCT_TYPE_ZH_TO_BOM_TYPE.get(product_type_zh)
                if not bom_type:
                    raise RuntimeError(f"product_type_zh={product_type_zh} 无法映射到 bom_type")

                en_items = parse_pdf_to_phrases(pdf, lang="en")
                if not en_items:
                    per_pdf_index.append(
                        {
                            "pdf": pdf.as_posix(),
                            "material_code": inferred_code,
                            "product_type_zh": product_type_zh,
                            "bom_type": bom_type,
                            "matched": 0,
                            "unmatched": 0,
                            "note": "no_phrases",
                        }
                    )
                    continue

                if args.limit_phrases and args.limit_phrases > 0:
                    en_items = en_items[: args.limit_phrases]

                cand_cache = _get_candidate_cache(bom_type=bom_type, embedding_cfg=embedding_cfg, cache=candidate_cache)

                matched_rows, unmatched, llm_decisions = _match_phrases_to_candidates(
                    material_code=inferred_code,
                    product_type_zh=product_type_zh,
                    bom_type=bom_type,
                    pdf_path=pdf,
                    phrases=en_items,
                    cand_cache=cand_cache,
                    embedding_cfg=embedding_cfg,
                    threshold=float(args.threshold),
                    top_k=int(args.top_k),
                    llm_top_k=int(args.llm_top_k),
                    llm_batch_size=int(args.llm_batch_size),
                    llm_cfg=llm_cfg,
                    llm_conf_threshold=float(args.llm_conf_threshold),
                    llm_timeout_s=float(args.llm_timeout_s) if args.use_llm else None,
                )

                pdf_dir = run_root / f"{_safe_dirname(pdf.stem)}_{_safe_dirname(inferred_code)}_bom"
                extracted_payload = {
                    "pdf": pdf.as_posix(),
                    "material_code": inferred_code,
                    "material_code_inferred": True,
                    "product_type_zh": product_type_zh,
                    "bom_type": bom_type,
                    "translate_dir": str(translate_dir),
                    "backends": _pdf_backend_status(),
                    "phrases": [{"pdf": pdf.as_posix(), "en_phrase": x} for x in en_items],
                }
                _write_json(pdf_dir / "extracted_phrases.json", extracted_payload)
                _write_lines(pdf_dir / "extracted_phrases.txt", list(en_items))
                _write_csv(pdf_dir / "matched.csv", matched_rows)
                _write_csv_readable(pdf_dir / "matched_readable.csv", matched_rows)
                _write_json(pdf_dir / "unmatched.json", unmatched)
                if llm_cfg:
                    _write_lines(
                        pdf_dir / "llm_decisions.jsonl",
                        [json.dumps(x, ensure_ascii=False) for x in llm_decisions],
                    )

                best_by_section: Dict[str, Dict[str, Any]] = {}
                for r in matched_rows:
                    cur = best_by_section.get(r.section_key)
                    if cur is None or float(r.score) > float(cur.get("score", -1)):
                        best_by_section[r.section_key] = {
                            "section_key": r.section_key,
                            "section_label": r.section_label,
                            "code": r.code,
                            "name_zh": r.name_zh,
                            "score": r.score,
                            "source_pdf": r.source_pdf,
                            "en_phrase": r.en_phrase,
                            "llm_used": r.llm_used,
                            "llm_confidence": r.llm_confidence,
                            "llm_reason": r.llm_reason,
                        }
                _write_json(
                    pdf_dir / "best_by_section.json",
                    {
                        "pdf": pdf.as_posix(),
                        "material_code": inferred_code,
                        "product_type_zh": product_type_zh,
                        "bom_type": bom_type,
                        "threshold": float(args.threshold),
                        "top_k": int(args.top_k),
                        "matched": len(matched_rows),
                        "unmatched": len(unmatched),
                        "best_by_section": list(best_by_section.values()),
                    },
                )

                all_matched.extend(matched_rows)
                all_unmatched.extend(unmatched)
                per_pdf_index.append(
                    {
                        "pdf": pdf.as_posix(),
                        "material_code": inferred_code,
                        "product_type_zh": product_type_zh,
                        "bom_type": bom_type,
                        "matched": len(matched_rows),
                        "unmatched": len(unmatched),
                        "report_dir": pdf_dir.as_posix(),
                    }
                )
            except Exception as e:
                pdf_errors.append({"pdf": pdf.as_posix(), "error": str(e)})

        agg_dir = run_root / "aggregate"
        _write_csv(agg_dir / "matched.csv", all_matched)
        _write_json(agg_dir / "unmatched.json", all_unmatched)
        if llm_cfg:
            llm_all = []
            for item in per_pdf_index:
                rd = item.get("report_dir")
                if not rd:
                    continue
                p = Path(str(rd)) / "llm_decisions.jsonl"
                if not p.exists():
                    continue
                try:
                    llm_all.extend([x for x in p.read_text(encoding="utf-8").splitlines() if x.strip()])
                except Exception:
                    pass
            if llm_all:
                _write_lines(agg_dir / "llm_decisions.jsonl", llm_all)
        _write_json(agg_dir / "index.json", {"items": per_pdf_index, "errors": pdf_errors})

        print(
            f"Complete(per-pdf). PDFs={len(pdfs)} Matched={len(all_matched)} Unmatched={len(all_unmatched)} "
            f"Errors={len(pdf_errors)} ReportRoot={run_root} Aggregate={agg_dir}"
        )
        return 0
    finally:
        driver.close()


if __name__ == "__main__":
    raise SystemExit(main())

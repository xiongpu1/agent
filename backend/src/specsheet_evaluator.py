from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from pydantic import ValidationError

from src.specsheet_models import SpecsheetData


def _normalize_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value)
    text = text.strip().lower()
    text = re.sub(r"\s+", " ", text)
    return text


def _as_list(value: Any) -> List[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _jaccard(a: List[str], b: List[str]) -> float:
    sa = {x for x in a if x}
    sb = {x for x in b if x}
    if not sa and not sb:
        return 1.0
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def _safe_json_loads(text: str) -> Optional[Any]:
    if not text:
        return None
    raw = text.strip()
    if not raw:
        return None
    try:
        return json.loads(raw)
    except Exception:
        return None


@dataclass
class SpecsheetEvalResult:
    score: float
    is_correct: bool
    schema_valid: bool
    required_ok: bool
    errors: List[Dict[str, Any]]
    diffs: List[Dict[str, Any]]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "score": self.score,
            "is_correct": self.is_correct,
            "schema_valid": self.schema_valid,
            "required_ok": self.required_ok,
            "errors": self.errors,
            "diffs": self.diffs,
        }


def evaluate_specsheet(predicted_text: str, ground_truth_text: str) -> SpecsheetEvalResult:
    errors: List[Dict[str, Any]] = []
    diffs: List[Dict[str, Any]] = []

    predicted_obj = _safe_json_loads(predicted_text)
    gt_obj = _safe_json_loads(ground_truth_text)

    if predicted_obj is None:
        return SpecsheetEvalResult(
            score=0.0,
            is_correct=False,
            schema_valid=False,
            required_ok=False,
            errors=[{"type": "parse", "message": "predicted 不是合法 JSON"}],
            diffs=[],
        )

    if gt_obj is None:
        return SpecsheetEvalResult(
            score=0.0,
            is_correct=False,
            schema_valid=False,
            required_ok=False,
            errors=[{"type": "parse", "message": "ground_truth 不是合法 JSON"}],
            diffs=[],
        )

    schema_valid = True
    try:
        SpecsheetData(**predicted_obj)
    except ValidationError as exc:
        schema_valid = False
        errors.extend(
            [{"type": "schema", "loc": list(e.get("loc", [])), "msg": e.get("msg")} for e in exc.errors()]
        )

    def get_path(obj: Any, path: Tuple[str, ...]) -> Any:
        cur = obj
        for key in path:
            if not isinstance(cur, dict) or key not in cur:
                return None
            cur = cur[key]
        return cur

    # Required fields check (for correctness condition b)
    required_paths = [
        ("productTitle",),
        ("features", "capacity"),
        ("features", "jets"),
        ("features", "pumps"),
        ("measurements",),
        ("Specifications",),
        ("premiumFeatures",),
        ("insulationFeatures",),
        ("extraFeatures",),
        ("smartWater",),
        ("images", "product"),
        ("images", "background"),
    ]

    required_missing: List[Tuple[str, ...]] = []
    for p in required_paths:
        val = get_path(predicted_obj, p)
        if val is None:
            required_missing.append(p)
            continue
        if isinstance(val, str) and not val.strip():
            required_missing.append(p)
        if isinstance(val, list) and len(val) == 0:
            required_missing.append(p)

    required_ok = len(required_missing) == 0
    if not required_ok:
        errors.append({"type": "required", "missing": [".".join(p) for p in required_missing]})

    # Scoring
    score = 0.0

    def exact_field(path: Tuple[str, ...], weight: float):
        nonlocal score
        pv = _normalize_text(get_path(predicted_obj, path))
        gv = _normalize_text(get_path(gt_obj, path))
        matched = pv == gv and pv != ""
        if not matched:
            diffs.append({"path": ".".join(path), "pred": pv, "gt": gv})
        score += weight if matched else 0.0

    def jaccard_field(path: Tuple[str, ...], weight: float):
        nonlocal score
        pv_raw = _as_list(get_path(predicted_obj, path))
        gv_raw = _as_list(get_path(gt_obj, path))
        pv = [_normalize_text(x) for x in pv_raw]
        gv = [_normalize_text(x) for x in gv_raw]
        sim = _jaccard(pv, gv)
        if sim < 1.0:
            diffs.append({"path": ".".join(path), "pred": pv_raw, "gt": gv_raw, "sim": sim})
        score += weight * sim

    # Features (high weight)
    exact_field(("features", "capacity"), 0.10)
    exact_field(("features", "jets"), 0.10)
    exact_field(("features", "pumps"), 0.10)

    # Measurements
    exact_field(("measurements",), 0.15)

    # Specifications: check order + compare each entry value as normalized string/list
    specs_p = get_path(predicted_obj, ("Specifications",))
    specs_g = get_path(gt_obj, ("Specifications",))

    specs_weight = 0.35
    specs_score = 0.0
    if isinstance(specs_p, list) and isinstance(specs_g, list) and specs_p and specs_g:
        # compare by index; each element should be {key: value}
        common_len = min(len(specs_p), len(specs_g))
        per_item_weight = specs_weight / 6.0
        for i in range(common_len):
            kp = list(specs_p[i].keys())[0] if isinstance(specs_p[i], dict) and specs_p[i] else None
            kg = list(specs_g[i].keys())[0] if isinstance(specs_g[i], dict) and specs_g[i] else None
            if kp != kg:
                diffs.append({"path": f"Specifications[{i}]", "pred_key": kp, "gt_key": kg})
                continue
            vp = specs_p[i].get(kp)
            vg = specs_g[i].get(kg)
            # value may be string or list
            if isinstance(vp, list) or isinstance(vg, list):
                sim = _jaccard([_normalize_text(x) for x in _as_list(vp)], [_normalize_text(x) for x in _as_list(vg)])
                specs_score += per_item_weight * sim
                if sim < 1.0:
                    diffs.append({"path": f"Specifications[{i}].{kp}", "pred": vp, "gt": vg, "sim": sim})
            else:
                sp = _normalize_text(vp)
                sg = _normalize_text(vg)
                matched = sp == sg and sp != ""
                specs_score += per_item_weight if matched else 0.0
                if not matched:
                    diffs.append({"path": f"Specifications[{i}].{kp}", "pred": vp, "gt": vg})

        # penalize length mismatch
        if len(specs_p) != len(specs_g):
            diffs.append({"path": "Specifications.length", "pred": len(specs_p), "gt": len(specs_g)})
        if len(specs_p) < 6 or len(specs_g) < 6:
            errors.append({"type": "specifications", "message": "Specifications 长度不足 6"})
    else:
        errors.append({"type": "specifications", "message": "Specifications 缺失或不是数组"})

    score += min(specs_weight, specs_score)

    # Lists similarity
    jaccard_field(("premiumFeatures",), 0.06)
    jaccard_field(("insulationFeatures",), 0.06)
    jaccard_field(("extraFeatures",), 0.04)
    jaccard_field(("smartWater",), 0.04)

    # Images (low weight)
    exact_field(("images", "product"), 0.005)
    exact_field(("images", "background"), 0.005)

    # Clamp
    score = max(0.0, min(1.0, score))

    # Correctness condition (b): required_ok + score>=0.99
    is_correct = required_ok and score >= 0.99

    return SpecsheetEvalResult(
        score=score,
        is_correct=is_correct,
        schema_valid=schema_valid,
        required_ok=required_ok,
        errors=errors,
        diffs=diffs,
    )

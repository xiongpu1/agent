import ast
import json
import logging
from typing import Any, Dict, List, Tuple

from litellm import completion

from src.bom_config import (
    BOM_TYPES,
    get_bom_sections,
)
from src.bom_models import (
    BomGenerationRequest,
    BomGenerationResponse,
    BomSelection,
)
from src.rag_specsheet import (
    SPEC_CONTEXT_MAX_CHARS,
    _build_context_from_ocr_documents,
    _run_completion_with_timeout,
    get_llm_config,
)


def _flatten_sections(
    sections: List[Dict[str, Any]],
) -> Dict[str, Dict[str, Any]]:
    flattened: Dict[str, Dict[str, Any]] = {}
    for section in sections:
        if section.get("children"):
            for child in section["children"]:
                flattened[child["key"]] = {
                    "label": child["label"],
                    "digits": child.get("digits"),
                    "options": child.get("options") or {},
                }
        else:
            flattened[section["key"]] = {
                "label": section["label"],
                "digits": section.get("digits"),
                "options": section.get("options") or {},
            }
    return flattened


def _format_options(options: Dict[str, str]) -> str:
    if not options:
        return "任意字符"
    pairs = [f"{code}={label}" for code, label in options.items()]
    return ", ".join(pairs)


def _build_sections_prompt(sections: List[Dict[str, Any]]) -> str:
    lines: List[str] = []
    for section in sections:
        if section.get("children"):
            for child in section["children"]:
                line = (
                    f"- {child['key']}（{child['label']}，{child['digits']}位）："
                    f"{_format_options(child.get('options', {}))}"
                )
                lines.append(line)
        else:
            digits = section.get("digits")
            digit_text = f"{digits}位" if digits else "可选长度"
            line = (
                f"- {section['key']}（{section['label']}，{digit_text}）："
                f"{_format_options(section.get('options', {}))}"
            )
            lines.append(line)
    return "\n".join(lines)


def _truncate_context(context_text: str) -> Tuple[str, bool]:
    if SPEC_CONTEXT_MAX_CHARS > 0 and len(context_text) > SPEC_CONTEXT_MAX_CHARS:
        return context_text[:SPEC_CONTEXT_MAX_CHARS], True
    return context_text, False


def _repair_json_text(text: str) -> str:
    fixed = text.strip()
    if not fixed:
        return fixed
    open_curly = fixed.count("{")
    close_curly = fixed.count("}")
    if close_curly < open_curly:
        fixed = f"{fixed}{'}' * (open_curly - close_curly)}"
    open_bracket = fixed.count("[")
    close_bracket = fixed.count("]")
    if close_bracket < open_bracket:
        fixed = f"{fixed}{']' * (open_bracket - close_bracket)}"
    return fixed


def _parse_llm_json(llm_output: str) -> Dict[str, Any]:
    def try_load(value: str):
        if not value:
            return None
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            try:
                return ast.literal_eval(value)
            except Exception:
                return None

    parsed = try_load(llm_output)
    if parsed is not None:
        return parsed

    repaired = _repair_json_text(llm_output)
    parsed = try_load(repaired)
    if parsed is not None:
        return parsed

    raise ValueError("LLM 输出不可解析")


def _normalize_option_value(value: str, options: Dict[str, str]) -> Tuple[str, bool]:
    if not value:
        return value, False
    if not options:
        return value, False
    upper_value = value.upper()
    if upper_value in options:
        return upper_value, True
    stripped_value = value.strip()
    for code, label in options.items():
        label = label or ""
        if stripped_value == label:
            return code, True
        if stripped_value in label or label in stripped_value:
            return code, True
    # try case-insensitive compare
    lower_value = stripped_value.lower()
    for code, label in options.items():
        label_lower = (label or "").lower()
        if lower_value == label_lower or lower_value in label_lower or label_lower in lower_value:
            return code, True
    return value, False


def decode_bom_code(bom_code: str, bom_type: str | None = None) -> Dict[str, Any] | None:
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


def generate_bom_from_ocr_request(
    request: BomGenerationRequest,
) -> BomGenerationResponse:
    bom_type = request.bom_type or request.bomType
    if bom_type not in BOM_TYPES:
        raise ValueError("Unsupported BOM 类型，请选择户外缸(outdoor)或泳池(pool)")

    if request.sections:
        sections = [section.dict() for section in request.sections]
    else:
        sections = get_bom_sections(bom_type)

    context_text, pseudo_chunks, multimodal_segments = _build_context_from_ocr_documents(
        request.documents
    )
    if not context_text.strip():
        raise ValueError("未提供可用于生成 BOM 的 OCR 文档内容")

    context_text, truncated = _truncate_context(context_text)
    llm_config = get_llm_config()
    sections_prompt = _build_sections_prompt(sections)

    system_prompt = """你是一个资深的 BOM 编码工程师。你的任务是阅读提供的 OCR 文档，根据实际内容推断 22 位 BOM 中各段的编码，并输出结构化 JSON。"""

    user_prompt = f"""BOM 类型：{bom_type}
段位要求与可选编码（请逐一覆盖每个段位，最多返回一个最可能的编码）：
{sections_prompt}

请严格遵守以下规则：
1. 只能从给定选项里选择编码，不要发明新的代码。
2. reason 字段必须引用触发该判断的 OCR 句子（或片段），格式如“依据《文档名》: ……”。如果完全无法找到依据，请明确写明“默认/推测”并解释原因。
3. 即使文档没有明确提及，也要结合上下文、常识和默认配置，选择“最可能的编码”。只有在完全没有任何线索时才跳过该字段。
4. 如果同一个字段出现多个可能值，优先选择与文本匹配度最高的那一个，并在 reason 中说明依据。
5. 优先保证输出的段位数量尽量多，至少覆盖 3 个字段。
6. JSON 结构必须严格等于：
{{
  "segments": [
    {{"key": "shellColor", "value": "A", "reason": "依据"}},
    ...
  ]
}}

下面是 OCR 文本（{'已截断' if truncated else '完整'}）：
{context_text}
"""

    kwargs = {
        "model": llm_config.model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.1,
    }
    if llm_config.api_key:
        kwargs["api_key"] = llm_config.api_key
    if llm_config.base_url:
        kwargs["api_base"] = llm_config.base_url

    response = _run_completion_with_timeout(kwargs, None)
    llm_output = response.choices[0].message.content.strip()

    if "```json" in llm_output:
        llm_output = llm_output.split("```json", 1)[1].split("```", 1)[0].strip()
    elif "```" in llm_output:
        llm_output = llm_output.split("```", 1)[1].split("```", 1)[0].strip()

    try:
        result_json = _parse_llm_json(llm_output)
    except ValueError as exc:
        raise ValueError(f"LLM 输出不可解析：{exc}") from exc

    flat_sections = _flatten_sections(sections)
    raw_segments = result_json.get("segments") or []
    segment_reason_map = {item.get("key"): item.get("reason") for item in raw_segments if item.get("key")}

    valid_segments: List[BomSelection] = []
    selections: Dict[str, str] = {}

    for item in raw_segments:
        key = (item.get("key") or "").strip()
        value = (item.get("value") or "").strip().upper()
        if not key or not value:
            continue
        config = flat_sections.get(key)
        if not config:
            continue
        digits = config.get("digits")
        options = config.get("options") or {}

        if options:
            normalized_value, matched = _normalize_option_value(value, options)
            if matched:
                value = normalized_value

        if digits and len(value) != digits:
            continue
        if options and value not in options:
            continue
        selections[key] = value
        valid_segments.append(
            BomSelection(
                key=key,
                label=config["label"],
                value=value,
                digits=digits,
                meaning=options.get(value),
                reason=item.get("reason"),
            )
        )

    # Ensure each configurable segment appears once (fill blank selections with default/first option if needed)
    for key, config in flat_sections.items():
        if key in selections:
            continue
        options = config.get("options") or {}
        fallback_value = ""
        if options:
            fallback_value = next(iter(options.keys()))
        if not fallback_value:
            continue
        selections[key] = fallback_value
        valid_segments.append(
            BomSelection(
                key=key,
                label=config["label"],
                value=fallback_value,
                digits=config.get("digits"),
                meaning=options.get(fallback_value),
                reason=segment_reason_map.get(key) or "LLM 未给出，使用默认配置",
            )
        )

    matched_count = len(valid_segments)
    logger = logging.getLogger("rag_bom")
    if matched_count:
        logger.info(
            "[BOM] Matched %s segments for %s: %s",
            matched_count,
            bom_type,
            {
                segment.key: segment.value for segment in valid_segments
            },
        )
    else:
        logger.warning(
            "[BOM] No segments matched for %s. LLM output (trimmed): %s",
            bom_type,
            llm_output[:500],
        )

    return BomGenerationResponse(
        type=bom_type,
        selections=selections,
        segments=valid_segments,
    )

import base64
import json
import mimetypes
import os
import re
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import HTTPException
from litellm import completion

from src.api_queries import BACKEND_ROOT


POSTER_ANALYSIS_DEFAULT_FONT_CANDIDATES: List[str] = [
    "Inter",
    "Roboto",
    "Montserrat",
    "Poppins",
    "Oswald",
    "Bebas Neue",
    "Noto Sans",
    "Noto Serif",
    "Noto Sans SC",
    "Noto Serif SC",
    "Source Han Sans SC",
    "Source Han Serif SC",
    "Alibaba PuHuiTi",
]


POSTER_ANALYSIS_DEFAULT_PROMPT = (
    "你是专业的海报视觉布局分析助手。"
    "请根据参考图进行分析，并且只输出一个严格合法的 JSON 对象（RFC8259）。"
    "不要输出 markdown、代码块、注释或任何额外文本。"
    "所有坐标必须归一化到 0-1000，格式为 [ymin,xmin,ymax,xmax]。"
)


POSTER_COPY_DEFAULT_PROMPT = (
    "你是专业的电商营销海报文案与风格策划助手。"
    "默认产品品类为：按摩浴缸/浴缸（Massage Bathtub / Hot Tub / Jacuzzi）。"
    "你会基于已解析的海报结构（元素 id 与 bbox）产出适配的营销文案与风格建议，用于替换原海报文字。"
    "目标语言请根据用户 requirements 自行判断并在输出 JSON 的 target_language 字段中给出（zh/en/ru/ja/ko/other）。"
    "只输出一个严格合法的 JSON 对象（RFC8259），不要输出任何额外文本。"
)


def build_step1_prompt(extra_requirements: Optional[str], font_candidates: List[str]) -> str:
    extra = (extra_requirements or "").strip()
    candidates = [c.strip() for c in (font_candidates or []) if (c or "").strip()]
    if not candidates:
        candidates = POSTER_ANALYSIS_DEFAULT_FONT_CANDIDATES

    candidates_str = ", ".join([json.dumps(c, ensure_ascii=False) for c in candidates])

    schema = (
        "请返回一个顶层 JSON 对象，包含这些 key：width,height,elements,font_guess,style,evidence。\n"
        "- width,height：如果你能可靠推断出输入图像像素尺寸，则输出整数；否则可以省略或置为 null。\n"
        "- elements：数组（2..10 个），每个元素是一个对象，字段为 id,type,label,bbox,confidence,text。\n"
        "  重要：elements 不要求固定为 6 个，必须忠实于图片内容，但总数不超过 10 个。\n"
        "  本任务只关心：背景、产品主体、以及文字布局（主标题/副标题/卖点）。请严格只输出这些元素，不要输出任何装饰性/信息性小图片。\n"
        "  必须至少包含：background、main_product 两个元素。\n"
        "  文字元素仅允许包含（如图中确实存在）：title、subtitle、sellpoint_1、sellpoint_2、sellpoint_3、sellpoint_4、sellpoint_5。\n"
        "  不要输出：角标/徽章/价格贴纸/平台 logo/按钮/认证图标/配图小图标/场景小图/装饰贴纸/水印 等任何非必要图片类元素（即使它们真实存在也不要输出）。\n"
        "  已约定 id：background, main_product, title, subtitle, sellpoint_1..sellpoint_5（如不存在就不要输出该元素）。\n"
        "  type：background / product / text。background 的 type 必须是 background；main_product 的 type 必须是 product；其余为 text。\n"
        "  bbox：格式为 [ymin,xmin,ymax,xmax]，整数 0..1000，且必须满足 ymin<ymax 且 xmin<xmax。\n"
        "  在输出前请自检：\n"
        "  - title/subtitle/sellpoint 这类文字区域通常更宽更矮；main_product 通常更高更大；角标/徽章/icon 通常更小且偏宽。\n"
        "  - 若发现某个 bbox 变成了明显的竖条/横条（与元素形态不符），说明你可能把坐标顺序写成了 [xmin,ymin,xmax,ymax]，请纠正为 [ymin,xmin,ymax,xmax]。\n"
        "  label：简短中文标签。\n"
        "  text：仅对 text 元素输出；其它类型输出 null。\n"
        "  confidence：0..1。若无法确定或无法从图中读出文本/区域，请降低 confidence。\n"
        "- font_guess：对象，包含 key：title, subtitle, sellpoint_1, sellpoint_2。每个值为 {name, confidence}。\n"
        "  name 必须从候选列表中选择：["
        + candidates_str
        + "]。若对应元素不存在或无法判断字体，请输出 name 为 null，confidence 为 0。\n"
        "- style：对象，包含 key：main_light_direction, theme_colors（hex 字符串数组）, notes。\n"
        "- evidence：对象，包含 key：language_guess, ocr_snippets, main_product_guess。\n"
        "  language_guess：zh/en/ru/ja/ko/other 之一。\n"
        "  ocr_snippets：6-12 个短字符串，必须是图片中出现的原文（verbatim）。\n"
        "  如果你输出了某个 text 元素的 text，尽量让 ocr_snippets 包含该 text 的原文片段；做不到则在 style.notes 说明原因并降低该元素 confidence。\n"
        "  main_product_guess：简短名词（如“保温水壶/保温杯/背包/护肤品”）。\n"
        "规则：\n"
        "- 只能输出 JSON 对象本身，不要输出任何额外文字。\n"
        "- JSON 必须严格 RFC8259：双引号、不能有尾逗号、不能有注释。\n"
        "- 所有文本必须来自图片；不要编造与图片无关的内容。\n"
    )

    if extra:
        return POSTER_ANALYSIS_DEFAULT_PROMPT + "\n" + schema + "\nAdditional user requirements:\n" + extra
    return POSTER_ANALYSIS_DEFAULT_PROMPT + "\n" + schema


def build_step2_prompt(
    *,
    step1_result: Dict[str, Any],
    requirements: Optional[str],
    target_language: str,
    forced_product_category: Optional[str] = None,
) -> str:
    req = (requirements or "").strip()
    lang = (target_language or "").strip().lower() or "zh"

    step1_json = json.dumps(step1_result or {}, ensure_ascii=False)

    elements = step1_result.get("elements") if isinstance(step1_result, dict) else None
    sellpoint_ids: List[str] = []
    if isinstance(elements, list):
        for el in elements:
            if not isinstance(el, dict):
                continue
            el_id = str(el.get("id") or "").strip()
            if re.match(r"^sellpoint_\d+$", el_id):
                sellpoint_ids.append(el_id)
    sellpoint_ids = sorted(sellpoint_ids, key=lambda s: int(s.split("_", 1)[1]) if "_" in s and s.split("_", 1)[1].isdigit() else 999)
    sp_count = len(sellpoint_ids)

    sellpoint_rule = (
        f"- copy.sellpoints：数组，长度必须为 {sp_count}（严格与 step1_result 中存在的卖点框数量一致）。\n"
        if sp_count > 0
        else "- copy.sellpoints：数组，若 step1_result 中不存在 sellpoint_\"n\" 区域，可输出空数组。\n"
    )

    forced_cat = (forced_product_category or "").strip()
    forced_rule = (
        "\n重要：用户已在 requirements 中明确指定产品品类，本次文案必须严格围绕该品类生成，并忽略 step1_result.evidence.main_product_guess：\n"
        + f"- 强制产品品类 = {forced_cat}\n"
        + "- title/subtitle/sellpoints 不允许出现与该品类明显不一致的词（例如把浴缸写成水壶/保温杯等）。\n"
        if forced_cat
        else ""
    )

    default_cat_rule = (
        "\n默认产品品类：按摩浴缸/浴缸（Massage Bathtub / Hot Tub / Jacuzzi）。\n"
        "- 如果 step1_result.evidence.main_product_guess 与该品类冲突（例如 Thermal Flask / Bottle），必须忽略 step1_result 的品类猜测，仍按浴缸产品生成文案。\n"
        if not forced_cat
        else ""
    )

    schema = "".join(
        [
            "请根据输入的 step1_result（已解析的 bbox/元素信息）生成文案与风格建议。\n",
            "你的任务是用新的营销文案替换海报中的原始文字（OCR 可能为外语），并保持与原布局区域数量一致。\n",
            "目标语言 target_language 可为 zh/en/ru/ja/ko/other，请根据 requirements 自行判断并在输出中填写。\n",
            "若用户需求明确面向美国/经销商/Dealer/Distributor，请优先输出英文（en）。\n",
            default_cat_rule,
            forced_rule,
            "强约束（很重要）：\n",
            "- 不能编造具体参数/数值/认证/材质/保修/专利/医学疗效等信息，除非 requirements 明确给出。\n",
            "- 可以使用不含具体数值的营销表述（如 energy-efficient / smart / spa-like relaxation 等）。\n",
            "- 若面向渠道（经销商/分销商），语气偏 B2B：专业、可信、可合作。\n",
            "返回 JSON schema：\n",
            "{\n",
            "  target_language: \"zh\",\n",
            "  copy: { title, subtitle, sellpoints, cta, footer },\n",
            "  layout_map: { title, subtitle, sellpoints, cta, footer },\n",
            "  style_guidance: { theme_colors, tone_keywords, notes },\n",
            "  font_plan: { title_font, subtitle_font, sellpoint_font, cta_font }\n",
            "}\n",
            "字段要求：\n",
            "- copy.title/subtitle/cta/footer：字符串；允许为空字符串但不建议。\n",
            sellpoint_rule,
            "- layout_map：将文案映射到 step1 的元素 id。\n",
            "  layout_map.title 必须为 \"title\"；layout_map.subtitle 为 \"subtitle\"（若 step1 不存在可为 null）。\n",
            "  layout_map.sellpoints 为数组，对应映射到 \"sellpoint_1\"/\"sellpoint_2\"/\"sellpoint_3\"...（按 step1 中存在的顺序）。\n",
            "  layout_map.cta 可映射到 \"cta\"（若 step1 存在该元素）否则为 null。\n",
            "  layout_map.footer 可映射到 \"footer\"（若 step1 存在该元素）否则为 null。\n",
            "- style_guidance.theme_colors：3-6 个 hex 颜色字符串。\n",
            "- font_plan：必须使用 step1_result.font_guess 中的字体名称进行选择，不要发明新字体。\n",
            "规则：\n",
            "- 只能输出 JSON 对象本身，不要输出任何额外文字。\n",
            "- JSON 必须严格 RFC8259：双引号、不能有尾逗号、不能有注释。\n",
            "- 不要编造产品参数（容量/材质/时长/认证等），除非 requirements 明确给出。\n",
        ]
    )

    extra = f"\n用户需求：\n{req}\n" if req else ""
    return (
        POSTER_COPY_DEFAULT_PROMPT
        + "\n"
        + "step1_result:\n"
        + step1_json
        + "\n"
        + schema
        + extra
    )


def _data_url_from_bytes(data: bytes, mime_type: Optional[str]) -> str:
    mime = (mime_type or "").strip() or "image/png"
    b64 = base64.b64encode(data).decode("utf-8")
    return f"data:{mime};base64,{b64}"


def _data_url_from_file(path: Path) -> str:
    data = path.read_bytes()
    mime, _ = mimetypes.guess_type(str(path))
    return _data_url_from_bytes(data, mime)


def resolve_image_url_to_data_url(image_url: str) -> str:
    u = (image_url or "").strip()
    if not u:
        raise ValueError("image_url 不能为空")

    if u.startswith("data:"):
        return u

    if u.startswith("/api/files/"):
        rel = u[len("/api/files/") :]
        resolved = (Path(BACKEND_ROOT) / rel).resolve()
        if not str(resolved).startswith(str(Path(BACKEND_ROOT).resolve())):
            raise ValueError("非法文件路径")
        if not resolved.exists() or not resolved.is_file():
            raise FileNotFoundError(f"文件不存在: {resolved}")
        return _data_url_from_file(resolved)

    return u


def extract_json(text: str) -> Dict[str, Any]:
    raw = (text or "").strip()
    if not raw:
        raise ValueError("LLM 输出为空")

    if "```json" in raw:
        raw = raw.split("```json", 1)[1].split("```", 1)[0].strip()
    elif "```" in raw:
        raw = raw.split("```", 1)[1].split("```", 1)[0].strip()

    def _cleanup_jsonish(s: str) -> str:
        out = (s or "").strip()
        if not out:
            return out
        out = re.sub(r"/\*[\s\S]*?\*/", "", out)
        out = re.sub(r"//.*?$", "", out, flags=re.MULTILINE)
        out = re.sub(r",\s*([}\]])", r"\1", out)
        return out.strip()

    try:
        return json.loads(_cleanup_jsonish(raw))
    except Exception:
        pass

    m = re.search(r"\{[\s\S]*\}", raw)
    if not m:
        raise ValueError("无法从 LLM 输出中提取 JSON")
    return json.loads(_cleanup_jsonish(m.group(0)))


def _validate_bbox(bbox: Any) -> bool:
    if not isinstance(bbox, list) or len(bbox) != 4:
        return False
    try:
        y0, x0, y1, x1 = [int(round(float(v))) for v in bbox]
    except Exception:
        return False
    if not (0 <= y0 <= 1000 and 0 <= x0 <= 1000 and 0 <= y1 <= 1000 and 0 <= x1 <= 1000):
        return False
    if y1 <= y0 or x1 <= x0:
        return False
    return True


def _validate_step1(payload: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("分析结果必须为 JSON object")

    def _has_cyrillic(s: str) -> bool:
        return bool(re.search(r"[\u0400-\u04FF]", s or ""))

    required_ids = {"background", "main_product"}

    def _maybe_swap_bbox_order(el: Dict[str, Any]) -> None:
        bbox = el.get("bbox")
        if not isinstance(bbox, list) or len(bbox) != 4:
            return
        try:
            a0, a1, a2, a3 = [float(v) for v in bbox]
        except Exception:
            return

        # Interpret as [ymin,xmin,ymax,xmax]
        h_yx = a2 - a0
        w_yx = a3 - a1
        # Interpret as [xmin,ymin,xmax,ymax]
        w_xy = a2 - a0
        h_xy = a3 - a1

        if h_yx <= 0 or w_yx <= 0 or h_xy <= 0 or w_xy <= 0:
            return

        el_type = str(el.get("type") or "").strip().lower()
        el_id = str(el.get("id") or "").strip().lower()
        el_label = str(el.get("label") or "").strip().lower()
        key_text = f"{el_id} {el_label}"
        icon_like = any(
            k in key_text
            for k in (
                "icon",
                "badge",
                "logo",
                "stamp",
                "tag",
                "label",
                "drone",
                "角标",
                "徽章",
                "标识",
                "标签",
                "图标",
                "配图",
            )
        )

        # Heuristics:
        # - text regions are typically wide and short
        # - product regions in posters are typically tall
        if el_type == "text" or icon_like:
            if w_yx < h_yx and w_xy > h_xy:
                el["bbox"] = [int(round(a1)), int(round(a0)), int(round(a3)), int(round(a2))]
        elif el_type in {"product", "image"}:
            if h_yx < w_yx and h_xy > w_xy:
                el["bbox"] = [int(round(a1)), int(round(a0)), int(round(a3)), int(round(a2))]

    elements = payload.get("elements")
    if not isinstance(elements, list):
        raise ValueError("elements 必须为数组")

    if len(elements) < 2:
        raise ValueError("elements 过少，至少需要 background 与 main_product")
    if len(elements) > 10:
        raise ValueError("elements 过多，最多允许 10 个")

    seen = set()
    for el in elements:
        if not isinstance(el, dict):
            continue

        _maybe_swap_bbox_order(el)

        el_id = (el.get("id") or "").strip()
        if el_id:
            seen.add(el_id)
        bbox = el.get("bbox")
        if bbox is None:
            continue
        if not _validate_bbox(bbox):
            raise ValueError(f"bbox 非法: {bbox}")

    missing = sorted(list(required_ids - seen))
    if missing:
        raise ValueError(f"elements 缺少必选 id: {missing}")

    evidence = payload.get("evidence")
    if not isinstance(evidence, dict):
        raise ValueError("evidence 必须为 object")

    lang_guess = str(evidence.get("language_guess") or "").strip().lower()

    ocr_snippets = evidence.get("ocr_snippets")
    if not isinstance(ocr_snippets, list) or len([s for s in ocr_snippets if str(s).strip()]) < 2:
        raise ValueError("evidence.ocr_snippets 过少，疑似未读取到图片文字")

    cleaned_snips = [str(s).strip() for s in ocr_snippets if str(s).strip()]
    joined_snips = "\n".join(cleaned_snips)

    any_cyr = _has_cyrillic(joined_snips)

    def _text_has_evidence(txt: str) -> bool:
        t = (txt or "").strip()
        if not t:
            return True
        for sn in cleaned_snips:
            if not sn:
                continue
            if t in sn:
                return True
            if len(sn) >= 4 and sn in t:
                return True
        return False
    for el in elements:
        if not isinstance(el, dict):
            continue
        if (el.get("type") or "") != "text":
            continue
        txt = (el.get("text") or "").strip()
        if not txt:
            continue
        if _has_cyrillic(txt):
            any_cyr = True
        if not _text_has_evidence(txt):
            # Repair: ensure evidence includes all text fields verbatim.
            cleaned_snips.append(txt)
            joined_snips = "\n".join(cleaned_snips)

    if any_cyr and lang_guess in {"zh", ""}:
        raise ValueError("language_guess 与识别到的西里尔文字不一致（疑似兼容/降级或幻觉）")

    evidence["ocr_snippets"] = cleaned_snips
    payload["evidence"] = evidence

    return payload


def _validate_step2(payload: Dict[str, Any], *, step1_result: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("Step2 输出必须为 JSON object")

    lang = str(payload.get("target_language") or "").strip().lower()
    if not lang:
        payload["target_language"] = "zh"
    elif lang != "zh":
        payload["target_language"] = lang

    copy = payload.get("copy")
    if not isinstance(copy, dict):
        raise ValueError("copy 必须为 object")

    sellpoints = copy.get("sellpoints")
    if not isinstance(sellpoints, list):
        raise ValueError("copy.sellpoints 必须为数组")
    cleaned_sp = [str(s).strip() for s in sellpoints if str(s).strip()]

    elements = step1_result.get("elements") if isinstance(step1_result, dict) else None
    sellpoint_ids: List[str] = []
    if isinstance(elements, list):
        for el in elements:
            if not isinstance(el, dict):
                continue
            el_id = str(el.get("id") or "").strip()
            if re.match(r"^sellpoint_\d+$", el_id):
                sellpoint_ids.append(el_id)
    expected_sp = len(sellpoint_ids)

    if expected_sp > 0:
        if len(cleaned_sp) != expected_sp:
            raise ValueError(f"copy.sellpoints 长度必须为 {expected_sp}（与 step1 卖点框数量一致）")
    else:
        # No sellpoint regions in layout: allow empty sellpoints.
        if len(cleaned_sp) > 0:
            # Keep it tolerant, but trim to 0 to avoid UI mismatch.
            cleaned_sp = []

    if len(cleaned_sp) > 5:
        raise ValueError("copy.sellpoints 长度最多为 5")
    copy["sellpoints"] = cleaned_sp

    for k in ("title", "subtitle", "cta", "footer"):
        if k in copy and copy[k] is not None:
            copy[k] = str(copy[k])

    payload["copy"] = copy

    style = payload.get("style_guidance")
    if style is not None and not isinstance(style, dict):
        raise ValueError("style_guidance 必须为 object")

    font_guess = step1_result.get("font_guess") if isinstance(step1_result, dict) else None
    fg_title = None
    fg_sub = None
    fg_sp = None
    try:
        if isinstance(font_guess, dict):
            fg_title = (font_guess.get("title") or {}).get("name")
            fg_sub = (font_guess.get("subtitle") or {}).get("name")
            fg_sp = (font_guess.get("sellpoint_1") or {}).get("name") or (font_guess.get("sellpoint_2") or {}).get("name")
    except Exception:
        pass

    enforced_font_plan = {
        "title_font": fg_title or None,
        "subtitle_font": fg_sub or None,
        "sellpoint_font": fg_sp or None,
        "cta_font": fg_title or fg_sub or fg_sp or None,
    }
    payload["font_plan"] = enforced_font_plan

    layout_map = payload.get("layout_map")
    if layout_map is not None and not isinstance(layout_map, dict):
        raise ValueError("layout_map 必须为 object")

    return payload


def _looks_like_no_image_reply(text: str) -> bool:
    t = (text or "").lower()
    if not t:
        return False
    signals = [
        "无法直接查看",
        "无法查看",
        "无法接收",
        "cannot view",
        "can't view",
        "cannot see",
        "can't see",
        "i can't access",
        "i cannot access",
    ]
    return any(s in t for s in signals)


def _dashscope_native_vl_call(
    *,
    api_key: str,
    model: str,
    image_url_value: str,
    prompt_text: str,
    temperature: float = 0.1,
) -> Dict[str, Any]:
    """Call DashScope native multimodal-generation endpoint.

    This avoids OpenAI-compatible routing issues where the image may be dropped.
    Returns the decoded JSON response.
    """

    m = (model or "").strip()
    if m.startswith("dashscope/"):
        m = m.split("/", 1)[1]

    url = "https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation"

    payload = {
        "model": m,
        "input": {
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"image": image_url_value},
                        {"text": prompt_text},
                    ],
                }
            ]
        },
        "parameters": {
            "temperature": temperature,
            "enable_thinking": False,
        },
    }

    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url=url,
        data=data,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=120) as resp:  # noqa: S310
            body = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:  # noqa: BLE001
        body = ""
        try:
            body = e.read().decode("utf-8", errors="replace")
        except Exception:
            pass
        raise RuntimeError(f"DashScope native HTTPError {e.code}: {body[:500]}") from e
    except Exception as e:  # noqa: BLE001
        raise RuntimeError(f"DashScope native request failed: {e}") from e

    try:
        return json.loads(body)
    except Exception as e:  # noqa: BLE001
        raise RuntimeError(f"DashScope native response is not JSON: {body[:500]}") from e


def _dashscope_native_extract_text(resp_json: Dict[str, Any]) -> str:
    """Extract assistant text from DashScope native response."""
    if not isinstance(resp_json, dict):
        return ""

    output = resp_json.get("output")
    if isinstance(output, dict):
        choices = output.get("choices")
        if isinstance(choices, list) and choices:
            msg = choices[0].get("message") if isinstance(choices[0], dict) else None
            if isinstance(msg, dict):
                content = msg.get("content")
                if isinstance(content, str):
                    return content.strip()
                if isinstance(content, list):
                    texts: List[str] = []
                    for part in content:
                        if isinstance(part, dict) and isinstance(part.get("text"), str):
                            texts.append(part["text"])
                        elif isinstance(part, str):
                            texts.append(part)
                    return "\n".join([t for t in texts if t]).strip()

    for key in ("output_text", "text", "result"):
        v = resp_json.get(key)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return ""


def _dashscope_openai_fallback(image_url_value: str, prompt_text: str, api_key: str, api_base: str, model: str) -> str:
    try:
        from openai import OpenAI
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"OpenAI SDK 未安装或不可用: {exc}") from exc

    client = OpenAI(api_key=api_key, base_url=api_base)
    m = model
    if isinstance(m, str) and m.startswith("dashscope/"):
        m = m.split("/", 1)[1]
    resp = client.chat.completions.create(
        model=m,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": image_url_value}},
                    {"type": "text", "text": prompt_text},
                ],
            }
        ],
        temperature=0.1,
        extra_body={"enable_thinking": False},
    )
    return (resp.choices[0].message.content or "").strip()


async def analyze_reference(
    *,
    image_url: str,
    prompt_extra: Optional[str],
    model: Optional[str],
    font_candidates: Optional[List[str]],
) -> Dict[str, Any]:
    payload_model = (model or "").strip() or None
    vision_model = (payload_model or os.getenv("POSTER_VISION_MODEL") or "dashscope/qwen3-vl-plus-2025-12-19").strip()
    if not vision_model.startswith("dashscope/") and "/" not in vision_model:
        vision_model = f"dashscope/{vision_model}"

    api_key = os.getenv("DASHSCOPE_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="DASHSCOPE_API_KEY 未配置")

    api_base = os.getenv("DASHSCOPE_BASE_URL") or "https://dashscope.aliyuncs.com/compatible-mode/v1"

    resolved = resolve_image_url_to_data_url(image_url)
    data_url = resolved if isinstance(resolved, str) and resolved.startswith("data:") else None
    content_url = None if data_url else resolved

    image_for_model = data_url or content_url
    if not image_for_model:
        raise HTTPException(status_code=400, detail="请提供 image_url")

    fc = font_candidates or []
    resolved_prompt = build_step1_prompt(prompt_extra, fc)

    debug: Dict[str, Any] = {
        "model": vision_model,
        "image_kind": "data_url" if data_url else "url",
        "image_url_prefix": (image_for_model[:32] + "...") if isinstance(image_for_model, str) else "",
        "font_candidates_count": len([c for c in fc if (c or "").strip()]),
    }
    if data_url and isinstance(data_url, str):
        debug["data_url_len"] = len(data_url)
        try:
            b64_part = data_url.split(",", 1)[1]
            debug["data_bytes"] = len(base64.b64decode(b64_part, validate=False))
        except Exception:
            debug["data_bytes"] = None

    user_content: List[Dict[str, Any]] = [
        {"type": "image_url", "image_url": {"url": image_for_model}},
        {"type": "text", "text": resolved_prompt},
    ]

    kwargs: Dict[str, Any] = {
        "model": vision_model,
        "messages": [{"role": "user", "content": user_content}],
        "api_key": api_key,
        "api_base": api_base,
        "temperature": 0.1,
        "extra_body": {"enable_thinking": False},
    }

    def _try_parse(raw_text: str) -> Dict[str, Any]:
        parsed = extract_json(raw_text)
        return _validate_step1(parsed)

    def _has_cyrillic_text(s: str) -> bool:
        return bool(re.search(r"[\u0400-\u04FF]", s or ""))

    # 1) Prefer DashScope native multimodal endpoint to reduce "image dropped" issues.
    try:
        native_json = _dashscope_native_vl_call(
            api_key=api_key,
            model=vision_model,
            image_url_value=image_for_model,
            prompt_text=resolved_prompt,
        )
        debug_native = {
            **debug,
            "primary": "dashscope_native",
            "native_request_id": native_json.get("request_id") if isinstance(native_json, dict) else None,
        }
        native_raw = _dashscope_native_extract_text(native_json)
        if native_raw:
            try:
                validated = _try_parse(native_raw)
                return {"ok": True, "model": vision_model, "result": validated, "raw": native_raw, "debug": debug_native}
            except Exception as native_parse_exc:  # noqa: BLE001
                # Keep native raw for diagnosis; it is often more faithful than compatible-mode fallback.
                debug = {
                    **debug_native,
                    "native_error": str(native_parse_exc),
                    "native_raw_prefix": native_raw[:240],
                }
        else:
            debug = {**debug_native, "native_error": "empty native text"}
    except Exception as native_exc:  # noqa: BLE001
        debug = {**debug, "primary": "dashscope_native", "native_error": str(native_exc)}

    # 2) Fallback to compatible-mode via litellm.
    try:
        resp = completion(**kwargs)
        raw = (resp.choices[0].message.content or "").strip()
    except Exception as exc:  # noqa: BLE001
        raw = ""
        debug = {**debug, "compatible_error": str(exc)}

    if raw:
        try:
            # If native path already surfaced Cyrillic in error/prefix, do not accept a zh fallback.
            if _has_cyrillic_text(str(debug.get("native_error") or "")) or _has_cyrillic_text(str(debug.get("native_raw_prefix") or "")):
                fb_parsed = extract_json(raw)
                fb_ev = fb_parsed.get("evidence") if isinstance(fb_parsed, dict) else None
                fb_lang = str(fb_ev.get("language_guess") or "") if isinstance(fb_ev, dict) else ""
                if str(fb_lang).strip().lower() == "zh":
                    return {
                        "ok": False,
                        "model": vision_model,
                        "error": "检测到原生输出含俄文特征，但 fallback 结果为中文，疑似未正确走视觉通道；已拒绝 fallback。",
                        "raw": raw,
                        "debug": {**debug, "fallback": "litellm"},
                    }

            validated = _try_parse(raw)
            return {"ok": True, "model": vision_model, "result": validated, "raw": raw, "debug": {**debug, "fallback": "litellm"}}
        except Exception as parse_exc:  # noqa: BLE001
            debug_parse = {**debug, "parse_error": str(parse_exc), "fallback": "litellm"}
            if _looks_like_no_image_reply(raw):
                try:
                    fb_raw = _dashscope_openai_fallback(image_for_model, resolved_prompt, api_key, api_base, vision_model)
                    debug_fb = {**debug_parse, "fallback": "openai_sdk"}
                    try:
                        fb_validated = _try_parse(fb_raw)
                        return {"ok": True, "model": vision_model, "result": fb_validated, "raw": fb_raw, "debug": debug_fb}
                    except Exception as fb_parse_exc:  # noqa: BLE001
                        return {"ok": False, "model": vision_model, "error": str(fb_parse_exc), "raw": fb_raw, "debug": debug_fb}
                except Exception as fb_exc:  # noqa: BLE001
                    return {"ok": False, "model": vision_model, "error": str(fb_exc), "raw": raw, "debug": debug_parse}

            return {"ok": False, "model": vision_model, "error": str(parse_exc), "raw": raw, "debug": debug_parse}

    return {"ok": False, "model": vision_model, "error": "模型无有效输出", "raw": raw, "debug": debug}


async def generate_copy(
    *,
    step1_result: Dict[str, Any],
    requirements: Optional[str],
    target_language: Optional[str],
    model: Optional[str],
    product_image_url: Optional[str],
    background_image_url: Optional[str],
) -> Dict[str, Any]:
    api_key = os.getenv("DASHSCOPE_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="DASHSCOPE_API_KEY 未配置")

    copy_model = (model or os.getenv("POSTER_COPY_MODEL") or "dashscope/qwen3-max").strip()
    if not copy_model.startswith("dashscope/") and "/" not in copy_model:
        copy_model = f"dashscope/{copy_model}"

    def _infer_lang(req_text: Optional[str]) -> str:
        r = (req_text or "").strip().lower()
        if not r:
            return "zh"
        signals_en = (
            "us",
            "usa",
            "united states",
            "america",
            "american",
            "dealer",
            "distributor",
            "wholesale",
            "b2b",
            "经销商",
            "美国",
            "北美",
        )
        if any(s in r for s in signals_en):
            return "en"
        return "zh"

    def _infer_forced_category(req_text: Optional[str], *, resolved_lang: str) -> Optional[str]:
        r = (req_text or "").strip().lower()
        if not r:
            return None
        # Massage bathtub / whirlpool / hot tub cues.
        tub_signals = (
            "按摩浴缸",
            "浴缸",
            "jacuzzi",
            "hot tub",
            "whirlpool",
            "spa tub",
            "spa bath",
            "massage tub",
            "bathtub",
        )
        if any(s in r for s in tub_signals):
            return "massage bathtub" if (resolved_lang == "en") else "按摩浴缸"
        return None

    def _infer_forced_category_from_product_image(image_url_value: str, *, resolved_lang: str) -> Optional[str]:
        """Best-effort category inference from the uploaded product image.

        This is used when the reference poster is unrelated (e.g., thermal flask), but the
        user uploads a new product image (e.g., massage bathtub). We only return a category
        when high-confidence cues appear; otherwise return None.
        """

        u = (image_url_value or "").strip()
        if not u:
            return None

        try:
            # Ensure it's a resolvable image url/data url.
            image_for_model = resolve_image_url_to_data_url(u)
        except Exception:
            return None

        vision_model = (os.getenv("POSTER_VISION_MODEL") or "dashscope/qwen3-vl-plus-2025-12-19").strip()
        if not vision_model.startswith("dashscope/") and "/" not in vision_model:
            vision_model = f"dashscope/{vision_model}"

        prompt_text = "".join(
            [
                "请识别图片中的产品品类（只输出一个简短英文名词或短语，不要解释）。\n",
                "若无法确定，输出 unknown。\n",
                "示例输出：massage bathtub / hot tub / bathtub / thermal flask / bottle / unknown\n",
            ]
        )

        try:
            resp_json = _dashscope_native_vl_call(
                api_key=api_key,
                model=vision_model,
                image_url_value=image_for_model,
                prompt_text=prompt_text,
                temperature=0.1,
            )
            text = _dashscope_native_extract_text(resp_json)
        except Exception:
            return None

        t = (text or "").strip().lower()
        if not t:
            return None
        t = re.sub(r"[^a-z0-9\s\-]", " ", t)
        t = re.sub(r"\s+", " ", t).strip()
        if not t or t == "unknown":
            return None

        tub_signals_en = (
            "massage bathtub",
            "hot tub",
            "whirlpool",
            "bathtub",
            "spa tub",
            "spa bath",
            "jacuzzi",
        )
        if any(s in t for s in tub_signals_en):
            return "massage bathtub" if (resolved_lang == "en") else "按摩浴缸"
        return None

    lang = (target_language or "").strip().lower() or _infer_lang(requirements)
    if lang not in {"zh", "en", "ru", "ja", "ko", "other"}:
        lang = "zh"

    forced_category = _infer_forced_category(requirements, resolved_lang=lang)

    debug: Dict[str, Any] = {
        "model": copy_model,
        "target_language": lang,
        "forced_product_category": forced_category,
        "has_product_image": bool((product_image_url or "").strip()),
        "has_background_image": bool((background_image_url or "").strip()),
    }

    prompt_text = build_step2_prompt(
        step1_result=step1_result or {},
        requirements=requirements,
        target_language=lang,
        forced_product_category=forced_category,
    )

    kwargs: Dict[str, Any] = {
        "model": copy_model,
        "messages": [{"role": "user", "content": [{"type": "text", "text": prompt_text}]}],
        "api_key": api_key,
        "api_base": os.getenv("DASHSCOPE_BASE_URL") or "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "temperature": 0.7,
        "extra_body": {"enable_thinking": False},
    }

    try:
        resp = completion(**kwargs)
        raw = (resp.choices[0].message.content or "").strip()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Step2 生成失败: {exc}") from exc

    try:
        parsed = extract_json(raw)
        validated = _validate_step2(parsed, step1_result=step1_result or {})
        return {"ok": True, "model": copy_model, "result": validated, "raw": raw, "debug": debug}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "model": copy_model, "error": str(exc), "raw": raw, "debug": debug}

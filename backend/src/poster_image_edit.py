import base64
import json
import mimetypes
import os
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from fastapi import HTTPException

from src.api_queries import BACKEND_ROOT
from src.poster_analyzer import resolve_image_url_to_data_url

try:
    from PIL import Image
except Exception:  # pragma: no cover
    Image = None  # type: ignore


@dataclass
class PosterImageEditInputs:
    reference_image_url: str
    product_image_url: str
    background_image_url: Optional[str]
    step1_result: Dict[str, Any]
    product_name: Optional[str]
    bom_code: Optional[str]
    title: str
    subtitle: str
    sellpoints: List[str]
    output_width: int
    output_height: int
    watermark: bool
    negative_prompt: str


DEFAULT_NEGATIVE_PROMPT = "\n".join(
    [
        "不要生成二维码/条形码/网址/电话。",
        "不要生成额外的品牌logo或水印（除非用户明确要求）。",
        "不要生成多余人物、动物、手、道具。",
        "不要改变产品外观、颜色或结构，不要添加额外配件。",
        "不要生成任何文字/字母/数字/符号。",
        "不要生成文本框/边框/标注框/贴纸/标签/UI 元素。",
    ]
)


def _summarize_image_value(v: Optional[str]) -> Dict[str, Any]:
    s = (v or "").strip()
    if not s:
        return {"kind": "none"}
    if s.startswith("data:"):
        return {"kind": "data_url", "len": len(s), "prefix": s[:32] + "..."}
    return {"kind": "url", "len": len(s), "prefix": s[:64] + ("..." if len(s) > 64 else "")}


POSTER_IMAGE_EDIT_QUESTION_PROMPT = "\n".join(
    [
        "你是一个专业电商海报设计模型。",
        "你的任务是：根据参考图的布局结构，结合输入的背景/产品图与文案，生成一张新的电商海报图片。",
        "你只需要输出最终海报图片，不要输出任何解释说明。",
    ]
)


def _sanitize_folder_component(s: Optional[str]) -> str:
    t = (s or "").strip()
    if not t:
        return ""
    t = re.sub(r"[^a-zA-Z0-9_\-]+", "_", t)
    t = re.sub(r"_+", "_", t).strip("_")
    return t[:48]


def _data_url_from_bytes(data: bytes, mime_type: Optional[str]) -> str:
    mime = (mime_type or "").strip() or "image/png"
    b64 = base64.b64encode(data).decode("utf-8")
    return f"data:{mime};base64,{b64}"


def _data_url_from_file(path: Path) -> str:
    data = path.read_bytes()
    mime, _ = mimetypes.guess_type(str(path))
    return _data_url_from_bytes(data, mime)


def _download_url_to_bytes(url: str, timeout_s: int = 120) -> Tuple[bytes, Optional[str]]:
    req = urllib.request.Request(url=url, headers={"User-Agent": "Mozilla/5.0"}, method="GET")
    with urllib.request.urlopen(req, timeout=timeout_s) as resp:  # noqa: S310
        data = resp.read()
        ctype = resp.headers.get("Content-Type")
        if ctype:
            ctype = ctype.split(";", 1)[0].strip()
        return data, ctype


def _ensure_bbox_01(v: float) -> float:
    if not isinstance(v, (int, float)):
        return 0.0
    x = float(v)
    # Heuristic: if bbox in 0..1000, convert to 0..1
    if x > 1.2:
        x = x / 1000.0
    return max(0.0, min(1.0, x))


def _bbox_to_prompt(bb: List[Any]) -> Optional[Dict[str, float]]:
    if not isinstance(bb, list) or len(bb) != 4:
        return None
    y0, x0, y1, x1 = bb
    if not all(isinstance(v, (int, float)) for v in (y0, x0, y1, x1)):
        return None
    y0f = _ensure_bbox_01(float(y0))
    x0f = _ensure_bbox_01(float(x0))
    y1f = _ensure_bbox_01(float(y1))
    x1f = _ensure_bbox_01(float(x1))
    if y1f <= y0f or x1f <= x0f:
        return None
    return {
        "x": x0f,
        "y": y0f,
        "w": max(0.0, x1f - x0f),
        "h": max(0.0, y1f - y0f),
    }


def _collect_layout_regions(step1_result: Dict[str, Any]) -> Dict[str, Dict[str, float]]:
    els = step1_result.get("elements") if isinstance(step1_result, dict) else None
    if not isinstance(els, list):
        return {}

    out: Dict[str, Dict[str, float]] = {}
    for el in els:
        if not isinstance(el, dict):
            continue
        el_id = str(el.get("id") or "").strip()
        if el_id not in {"main_product", "title", "subtitle"} and not re.match(r"^sellpoint_\d+$", el_id):
            continue
        bb = el.get("bbox")
        bb01 = _bbox_to_prompt(bb) if isinstance(bb, list) else None
        if not bb01:
            continue
        out[el_id] = bb01
    return out


def _bytes_from_data_url(data_url: str) -> Tuple[bytes, Optional[str]]:
    s = (data_url or "").strip()
    if not s.startswith("data:"):
        return b"", None
    header, b64_part = s.split(",", 1) if "," in s else (s, "")
    mime = header[5:].split(";", 1)[0].strip() if header.startswith("data:") else None
    try:
        return base64.b64decode(b64_part, validate=False), mime
    except Exception:
        return b"", mime


def _load_pil_image_from_any(image_ref: str) -> "Image.Image":
    if Image is None:
        raise RuntimeError("Pillow 未安装，无法进行合成。")
    data_url = resolve_image_url_to_data_url(image_ref)
    data, _mime = _bytes_from_data_url(data_url)
    if not data:
        raise RuntimeError("无法解析输入图片数据")
    # Open from bytes
    import io

    im = Image.open(io.BytesIO(data))
    im.load()
    if im.mode not in ("RGB", "RGBA"):
        im = im.convert("RGBA")
    return im


def _choose_output_size(*, bg: Optional["Image.Image"], ref: "Image.Image") -> Tuple[int, int]:
    base = bg if bg is not None else ref
    w, h = int(base.size[0]), int(base.size[1])
    if w <= 0 or h <= 0:
        return 1000, 1500
    return w, h


def _clamp_int(v: float, lo: int, hi: int) -> int:
    x = int(round(float(v)))
    if x < lo:
        return lo
    if x > hi:
        return hi
    return x


def _compose_base_image(*, ref_im: "Image.Image", bg_im: Optional["Image.Image"], product_im: "Image.Image", step1_result: Dict[str, Any]) -> "Image.Image":
    if Image is None:
        raise RuntimeError("Pillow 未安装，无法进行合成。")

    regions = _collect_layout_regions(step1_result or {})
    base = bg_im if bg_im is not None else ref_im
    canvas = base.convert("RGBA")
    W, H = canvas.size

    # Paste product into main_product bbox
    mp = regions.get("main_product")
    if mp:
        x0 = _clamp_int(mp["x"] * W, 0, W)
        y0 = _clamp_int(mp["y"] * H, 0, H)
        x1 = _clamp_int((mp["x"] + mp["w"]) * W, 0, W)
        y1 = _clamp_int((mp["y"] + mp["h"]) * H, 0, H)
        box_w = max(1, x1 - x0)
        box_h = max(1, y1 - y0)

        pim = product_im.convert("RGBA")
        pw, ph = pim.size
        if pw > 0 and ph > 0:
            s = min(box_w / pw, box_h / ph)
            nw = max(1, int(round(pw * s)))
            nh = max(1, int(round(ph * s)))
            resample = getattr(getattr(Image, "Resampling", Image), "LANCZOS", 1)
            pim2 = pim.resize((nw, nh), resample=resample)
            px = x0 + (box_w - nw) // 2
            py = y0 + (box_h - nh) // 2
            canvas.alpha_composite(pim2, dest=(px, py))
    return canvas


def build_qwen_image_edit_prompt(inputs: PosterImageEditInputs) -> str:
    has_bg = bool((inputs.background_image_url or "").strip())

    regions = _collect_layout_regions(inputs.step1_result or {})
    mp = regions.get("main_product")
    mp_line = ""
    if mp:
        mp_line = f"- main_product 区域（归一化 0..1）：x={mp['x']:.3f}, y={mp['y']:.3f}, w={mp['w']:.3f}, h={mp['h']:.3f}"

    # We only pass ONE composed image to the model.
    image_roles = "\n".join(
        [
            "- 图1：合成底图（已按布局放置产品）",
        ]
    )
    base_rule = "请在不改变整体布局结构（各区域相对位置）的前提下，优化画面质感与融合度，使产品与背景自然融合。"

    prompt = "\n".join(
        [
            "你是一个专业电商海报设计模型。请基于参考图的布局生成一张新的海报图片。",
            "\n目标：",
            f"- 输出一张 {inputs.output_width}x{inputs.output_height} 的海报图片。",
            "- 海报整体布局结构与参考图相似即可（不要求像素级一致），保持清晰的主次层级与留白。",
            "- 不要生成与输入无关的元素。",
            "\n素材说明：",
            image_roles,
            "\n放置规则：",
            base_rule,
            "- 下面的坐标数字仅用于布局约束，绝对不要在图片中渲染任何数字/坐标/文字。",
            mp_line if mp_line else "",
            "- main_product 区域中必须保留产品主体清晰可见。",
            "- 不要生成任何文字、数字、符号、Logo、水印。",
            "- 严禁生成任何 UI 边框、贴纸、标注框、按钮、二维码、乱码字符。",
            "\n输出要求：",
            "- 只输出最终海报图片，不要输出解释说明。",
        ]
    )

    return prompt


def _write_prompt_files(*, inputs: PosterImageEditInputs, used_prompt: str) -> Dict[str, str]:
    try:
        folder_name = "_".join(
            [
                _sanitize_folder_component(inputs.product_name),
                _sanitize_folder_component(inputs.bom_code),
            ]
        ).strip("_")
        if not folder_name:
            return {}

        product_dir = (Path(BACKEND_ROOT) / "manual_ocr_results" / folder_name).resolve()
        product_dir.mkdir(parents=True, exist_ok=True)
        prompt_path = product_dir / "prompt_poster_image_edit.txt"
        prompt_path.write_text(used_prompt or "", encoding="utf-8")

        return {"prompt_path": str(prompt_path.relative_to(Path(BACKEND_ROOT)).as_posix())}
    except Exception:
        return {}


def _dashscope_native_mm_call(
    *,
    api_key: str,
    model: str,
    contents: List[Dict[str, Any]],
    watermark: bool,
    negative_prompt: str,
    prompt_extend: bool,
    size: Optional[str],
    timeout_s: int = 180,
) -> Dict[str, Any]:
    m = (model or "").strip()
    if m.startswith("dashscope/"):
        m = m.split("/", 1)[1]

    url = "https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation"

    payload = {
        "model": m,
        "input": {"messages": [{"role": "user", "content": contents}]},
        "parameters": {
            "watermark": bool(watermark),
            "negative_prompt": negative_prompt or "",
            "prompt_extend": bool(prompt_extend),
        },
    }

    if size:
        payload["parameters"]["size"] = size

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
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:  # noqa: S310
            body = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:  # noqa: BLE001
        body = ""
        try:
            body = e.read().decode("utf-8", errors="replace")
        except Exception:
            pass
        raise RuntimeError(f"DashScope HTTPError {e.code}: {body[:800]}") from e
    except Exception as e:  # noqa: BLE001
        raise RuntimeError(f"DashScope request failed: {e}") from e

    try:
        return json.loads(body)
    except Exception as e:  # noqa: BLE001
        raise RuntimeError(f"DashScope response is not JSON: {body[:800]}") from e


def _extract_first_image_from_dashscope(resp_json: Dict[str, Any]) -> Optional[str]:
    if not isinstance(resp_json, dict):
        return None

    output = resp_json.get("output")
    if isinstance(output, dict):
        choices = output.get("choices")
        if isinstance(choices, list) and choices:
            msg = choices[0].get("message") if isinstance(choices[0], dict) else None
            if isinstance(msg, dict):
                content = msg.get("content")
                if isinstance(content, list):
                    for part in content:
                        if isinstance(part, dict):
                            img = part.get("image") or part.get("image_url")
                            if isinstance(img, str) and img.strip():
                                return img.strip()
                if isinstance(content, str) and content.strip():
                    return content.strip()

    # Fallback keys
    for key in ("output_image", "image", "result"):
        v = resp_json.get(key)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return None


def generate_poster_image_edit(*, payload: PosterImageEditInputs) -> Dict[str, Any]:
    api_key = os.getenv("DASHSCOPE_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="DASHSCOPE_API_KEY 未配置")

    model = (os.getenv("POSTER_IMAGE_EDIT_MODEL") or "qwen-image-edit-plus").strip()
    if not model.startswith("dashscope/") and "/" not in model:
        model = f"dashscope/{model}"

    # Load images (for size and composition)
    ref_pil = _load_pil_image_from_any(payload.reference_image_url)
    bg_pil = _load_pil_image_from_any(payload.background_image_url) if (payload.background_image_url or "").strip() else None
    prod_pil = _load_pil_image_from_any(payload.product_image_url)

    # S1: output size follows background if provided, else reference
    W, H = _choose_output_size(bg=bg_pil, ref=ref_pil)
    payload.output_width = W
    payload.output_height = H

    # S2: compose a base image with strict layout (no text rendered)
    composed = _compose_base_image(ref_im=ref_pil, bg_im=bg_pil, product_im=prod_pil, step1_result=payload.step1_result)
    # Ensure output matches chosen size
    if composed.size != (W, H):
        resample = getattr(getattr(Image, "Resampling", Image), "LANCZOS", 1)
        composed = composed.resize((W, H), resample=resample)

    import io

    buf = io.BytesIO()
    composed.save(buf, format="PNG")
    composed_data_url = _data_url_from_bytes(buf.getvalue(), "image/png")

    prompt_text = build_qwen_image_edit_prompt(payload)

    contents: List[Dict[str, Any]] = [
        {"image": composed_data_url},
        {"text": prompt_text},
    ]

    negative_prompt = (payload.negative_prompt or "").strip() or DEFAULT_NEGATIVE_PROMPT

    debug = {
        "model": model,
        "watermark": bool(payload.watermark),
        "has_background": bool(bg_pil is not None),
        "prompt_preview": prompt_text[:600],
    }

    prompt_paths = _write_prompt_files(inputs=payload, used_prompt=prompt_text)
    if prompt_paths:
        debug["prompt_files"] = prompt_paths

    try:
        params_size = None
        if "image-edit-plus" in model:
            # Per docs: parameters.size = "宽*高" for edit-plus models.
            params_size = f"{int(payload.output_width)}*{int(payload.output_height)}"
        debug["prompt_extend"] = True
        if params_size:
            debug["size"] = params_size

        resp_json = _dashscope_native_mm_call(
            api_key=api_key,
            model=model,
            contents=contents,
            watermark=bool(payload.watermark),
            negative_prompt=negative_prompt,
            prompt_extend=True,
            size=params_size,
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"qwen-image-edit 调用失败: {exc}") from exc

    img_ref = _extract_first_image_from_dashscope(resp_json)
    if not img_ref:
        return {
            "ok": False,
            "model": model,
            "error": "模型未返回图片",
            "raw": resp_json,
            "debug": debug,
        }

    # Save result image under backend directory so it can be served via /api/files/...
    try:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        folder = f"poster_gen_{ts}"
        out_dir = (Path(BACKEND_ROOT) / "generated_posters" / folder).resolve()
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / "poster.png"

        if isinstance(img_ref, str) and img_ref.startswith("data:"):
            b64_part = img_ref.split(",", 1)[1] if "," in img_ref else ""
            data = base64.b64decode(b64_part, validate=False)
            out_path.write_bytes(data)
        elif isinstance(img_ref, str) and img_ref.startswith("/api/files/"):
            rel = img_ref[len("/api/files/") :]
            resolved = (Path(BACKEND_ROOT) / rel).resolve()
            if resolved.exists() and resolved.is_file():
                out_path.write_bytes(resolved.read_bytes())
            else:
                data, _ctype = _download_url_to_bytes(img_ref)
                out_path.write_bytes(data)
        elif isinstance(img_ref, str) and img_ref.startswith("http"):
            data, _ctype = _download_url_to_bytes(img_ref)
            out_path.write_bytes(data)
        else:
            # Unknown format: store as text for diagnosis
            (out_dir / "poster_ref.txt").write_text(str(img_ref), encoding="utf-8")
            return {
                "ok": False,
                "model": model,
                "error": "无法处理模型返回的图片引用格式",
                "raw": resp_json,
                "debug": {**debug, "image_ref": str(img_ref)[:200]},
            }

        image_url = f"/api/files/{out_path.relative_to(Path(BACKEND_ROOT)).as_posix()}"
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": False,
            "model": model,
            "error": f"保存生成图片失败: {exc}",
            "raw": resp_json,
            "debug": debug,
        }

    return {
        "ok": True,
        "model": model,
        "result": {
            "image_url": image_url,
            "used_prompt": prompt_text,
        },
        "raw": resp_json,
        "debug": debug,
    }

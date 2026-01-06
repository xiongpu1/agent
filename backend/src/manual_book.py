import json
import os
from typing import Optional, Tuple, List, Dict, Any
import re
from pathlib import Path
from datetime import datetime

from src.rag_specsheet import (
    _build_context_from_ocr_documents,
    _run_completion_with_timeout,
    get_llm_config,
)
from src.specsheet_models import ManualBookData, ManualBookFromOcrRequest

# 固定页顺序（需与前端 manualPages 一致）
TARGET_HEADERS = [
    "Cover",
    "Embrace the Revitalizing Chill",
    "Premium Materials",
    "Contents",
    "Installation & User Manual",
    "How To Set Up",
    "Important Safety Instructions",
    "Important Safety Instructions",
    "Specification",
    "Touchscreen Control Panel",
    "Troubleshooting",
    "Troubleshooting",
    "Troubleshooting",
]

DEFAULT_COVER_BACK_SRC = os.getenv("MANUAL_BOOK_COVER_BACK_SRC", "/instruction_book/back.jpg")

# System prompt for manual book generation
MANUAL_BOOK_SYSTEM_PROMPT = """你是一名产品说明书文案助手。严格遵守以下规则，仅输出 JSON 数组纯文本（不要 Markdown、不要代码块、不要说明文字），顺序必须与下列 header 完全一致，且 **数组长度必须是 13，缺一不可，不足时不得输出**：

[
  "Cover",
  "Embrace the Revitalizing Chill",
  "Premium Materials",
  "Contents",
  "Installation & User Manual",
  "How To Set Up",
  "Important Safety Instructions",
  "Important Safety Instructions",
  "Specification",
  "Touchscreen Control Panel",
  "Troubleshooting",
  "Troubleshooting",
  "Troubleshooting"
]

字段/块语义（需用内容字段，不要返回样式字段 fullWidth/rotate/marginTop）：
- cover: { title 主标题, sizeText 尺寸文案, backSrc 封底图, productSrc 产品图, model 可选型号 }
- heading: { text 标题, level 可选 1/2/3, anchor 可选锚点 }
- paragraph: { text 段落, className 可选样式类 }
- list: { items: [字符串，可含基础 HTML], ordered 可选是否有序, className 可选 }
- imageFloat-<pos>: 浮动图 { src 图片URL, pos 位置 bottom-left|bottom-right|top-left|top-right }
- image: { src 图片URL, alt 可选 }
- contents: { items: [{ title, page }] }（目录）
- callout-warning / callout-error / callout: { text 文案，可含 HTML, className 可选, iconSrc 可选, variant 可选 }
- steps: { items: [步骤文本] }
- grid4: { items: [{ index 可选手动序号, title, imgSrc }] }
- grid2: { items: [{ type: 'image', src } | { type: 'list', ordered?, items }] }
- spec-box: { imageSrc 主图, specs: { topLeft/topRight/leftTop/leftMiddle1/leftMiddle2/leftBottom/rightTop/rightMiddle/rightBottom: { title, items[string[]] } } }
- ts-section: { index 序号, images: [3张], magnifier: { serial 可选序列号, qrSrc 可选二维码, qrVisible?, qrSize?, qrMargin?, bgSrc?, lines?: string[] } }
- troubleTable: { headers: [两列标题], groups: [{ title, items: [{ symptom, description?, solutions: string|string[] }] }] }
- 其余自定义字段可保留为内容（extra=allow），但不要引入样式键。

图片选择规则（非常重要）：
- Cover 页的 cover.backSrc 必须固定使用默认背景图 "{DEFAULT_COVER_BACK_SRC}"（不要选择候选图片、不要沿用 PDF 整页封面截图）。
- 除 Cover.cover.backSrc 以外：说明书中的所有图片字段都必须由你选择并填充（不要沿用示例图片路径）。
- 若用户输入上下文中提供了“候选图片列表”，则图片字段 **优先从候选列表里选择最匹配的路径**；若候选列表为空或确实无合适图片，可使用示例占位图（/instruction_book/...）兜底。
- 禁止捏造不存在的图片路径；禁止输出列表外的随机 URL。

图片槽位含义（你需要根据含义选图）：
- Cover.cover.backSrc：封面背景图（固定为默认背景图 "{DEFAULT_COVER_BACK_SRC}"，不参与选择）。
- Cover.cover.productSrc：封面产品主视觉。优先选择“产品整体正侧视/能看出形态与双区结构的全景图”，避免说明文字截图。
- Embrace the Revitalizing Chill.imageFloat-bottom-left：冷疗章节的产品示意图（偏整体）。
- Embrace the Revitalizing Chill.imageFloat-bottom-right：冷疗主题图（冷雾/冰水/温度/冷疗氛围/使用场景），若无则可选产品局部细节图。
- Premium Materials.grid4.items[*].imgSrc：材质与结构四宫格配图：
  - 1 Acrylic Surface：外壳/水槽表面材质特写（光泽/耐刮/触感）。
  - 2 Aluminum Frame：框架/支撑结构/型材特写（强度、耐腐蚀）。
  - 3 Tri-layered Side Cabinet：侧柜结构/板材层次/机身侧面结构图。
  - 4 Insulation Sleeve：保温棉/保温套/管路保温特写。
- Important Safety Instructions（含 Package List 的那一页）image.src：包装清单/配件清单图（开箱内容、配件排布、示意图）。
- Specification.spec-box.imageSrc：规格页主示意图：要求能看出产品整体，并适合在图周围标注规格点位/部件位置。
- Specification.grid2.items[0].src：编号零件/功能部件示意图（与右侧 ordered list 对应，如 Chiller/Control box/Pump）。
- Touchscreen Control Panel.image.src：触控面板布局/按键图标示意图：要求能看清按钮区、图标、数显区域。
- Troubleshooting.ts-section.images：三联图，用于定位序列号/铭牌/二维码位置或故障相关位置：
  - images[0]：远景定位（整机哪个区域）。
  - images[1]：中景定位（面板/铭牌所在面）。
  - images[2]：近景细节（能读到序列号/二维码/铭牌信息）。
- Troubleshooting.ts-section.magnifier.qrSrc：二维码或铭牌近景（可与 images[2] 相同或更清晰版本）。
- Troubleshooting.ts-section.magnifier.bgSrc：放大镜背景（可留空；若提供则应为铭牌/二维码所在区域截图）。

输出格式示例（仅结构，内容需根据上下文生成或用合理占位）：[
  { "header": "Cover", "blocks": [
      { "type": "cover", "title": "机型/主标题（如 Masrren 双区冰水缸）", "sizeText": "尺寸文案（如 2150×2150×1000mm）", "backSrc": "/instruction_book/back.jpg", "productSrc": "/instruction_book/product.png" }
  ]},
  { "header": "Embrace the Revitalizing Chill", "blocks": [
      { "type": "heading", "text": "Embrace the Revitalizing Chill（冷疗总览标题）" },
      { "type": "paragraph", "text": "冷疗介绍与卖点，总览段（说明产品提供的冷疗价值）" },
      { "type": "list", "items": [
          "Reduced Inflammation: 解释缓解炎症/酸痛的机理",
          "Faster Recovery: 解释加速运动恢复的原因",
          "Increased Circulation: 解释促进循环的原理",
          "Enhanced Mental Well-being: 解释情绪与专注提升",
          "Boosted Immune System: 解释免疫提升"
      ] },
      { "type": "paragraph", "text": "总结段1（产品双区或关键卖点）" },
      { "type": "paragraph", "text": "总结段2（适用场景或材料优势）" },
      { "type": "imageFloat-bottom-left", "src": "/instruction_book/product.png" },
      { "type": "imageFloat-bottom-right", "src": "/instruction_book/cold.png" }
  ]},
  { "header": "Premium Materials", "blocks": [
      { "type": "heading", "text": "Premium Materials（材质与结构标题）" },
      { "type": "paragraph", "text": "材质卖点段（说明 Acrylic / AluCombo / aluminum frame / insulated sleeve 等）" },
      { "type": "grid4", "items": [
          { "index": 1, "title": "Acrylic Surface（外壳材质）", "imgSrc": "/instruction_book/Acrylic_Surface.png" },
          { "index": 2, "title": "Aluminum Frame（框架材质）", "imgSrc": "/instruction_book/Acrylic_Surface.png" },
          { "index": 3, "title": "Tri-layered Side Cabinet（侧柜层数/工艺）", "imgSrc": "/instruction_book/Acrylic_Surface.png" },
          { "index": 4, "title": "Insulation Sleeve（保温管套）", "imgSrc": "/instruction_book/Acrylic_Surface.png" }
      ] }
  ]},
  { "header": "Contents", "blocks": [
      { "type": "heading", "text": "Contents（目录标题）" },
      { "type": "contents", "items": [
          { "title": "Installation & User Manual（安装/用户指南）", "page": 5 },
          { "title": "How To Set Up（安装步骤）", "page": 6 },
          { "title": "Important Safety Instructions（安全须知）", "page": 7 },
          { "title": "Specification（规格参数）", "page": 9 },
          { "title": "Touchscreen Control Panel（触控面板）", "page": 10 },
          { "title": "Troubleshooting（故障排查）", "page": 11 }
      ] }
  ]},
  { "header": "Installation & User Manual", "blocks": [
      { "type": "heading", "text": "Installation & User Manual（安装/使用标题）" },
      { "type": "callout-warning", "text": "Warning! 安装/用电/漏水等风险提示。" },
      { "type": "callout-error", "text": "Install per manual; 不当安装可能失去保修。" },
      { "type": "callout-warning", "text": "Ensure clearance / ambient temp / 搬运注意事项。" },
      { "type": "paragraph", "text": "To ensure optimal performance after refilling（为补水后性能提供步骤引导）", "className": "callout-align" },
      { "type": "list", "items": [
          "Connect power and start control panel（接电上电）",
          "Run 20–30s, bleed filter 20–40s until water flows, then tighten（排气示例）",
          "If no circulation, repeat steps 1–2（无循环时复查）"
      ], "className": "callout-align" }
  ]},
  { "header": "How To Set Up", "blocks": [
      { "type": "heading", "text": "How To Set Up（设置步骤标题）" },
      { "type": "paragraph", "className": "lead", "text": "开箱/放置/加水的引导说明" },
      { "type": "paragraph", "text": "推荐先阅读安全信息，再开始冷疗" },
      { "type": "steps", "items": [
          "放置设备并加水至推荐水位。",
          "打开滤芯放气螺丝排气。",
          "接通 110V/60Hz 电源并设定温度。",
          "等待冷却后开始体验。",
          "定期清洁消毒。"
      ] }
  ]},
  { "header": "Important Safety Instructions", "blocks": [
      { "type": "heading", "text": "Important Safety Instructions（安全须知标题）" },
      { "type": "paragraph", "className": "lead", "text": "READ AND FOLLOW ALL INSTRUCTIONS（总提示）" },
      { "type": "paragraph", "text": "安全提示概述（总览性说明）" },
      { "type": "list", "items": [
          "Health Disclaimer: 如有不确定，先咨询医生。",
          "Temperature Awareness: 从较高温度/短时长开始。",
          "Gradual Adaptation: 逐步增加时间，避免冷休克。",
          "Safety Precautions: 儿童/孕妇/特殊人群需监督或咨询医生。",
          "Maintenance/Power Safety: 保持滤芯洁净、注意漏电保护等。"
      ] }
  ]},
  { "header": "Important Safety Instructions", "blocks": [
      { "type": "heading", "text": "Important Safety Instructions（分组版）" },
      { "type": "heading", "level": 2, "text": "WARNING:（警告分组）" },
      { "type": "list", "items": [
          "People with infectious diseases should not use a spa or hot tub.",
          "Do not use drugs or alcohol before/during use.",
          "Prolonged immersion may be injurious to health."
      ] },
      { "type": "heading", "level": 2, "text": "CAUTION:（注意分组）" },
      { "type": "list", "items": [
          "Maintain water chemistry per instructions."
      ] },
      { "type": "paragraph", "className": "warning-text", "text": "* Please read the instructions carefully and use according to the instructions.\nChildren should use this product under the close supervision of adults." },
      { "type": "heading", "text": "WARNING:（附加警告组）" },
      { "type": "list", "items": [
          "After transporting, let tub rest 24h before turning on chiller.",
          "Use cloth/pliers to remove back cover cap carefully.",
          "Wind baffle is consumable; magnet-backed.",
          "ER03 indicates air in pipes; exhaust at filter."
      ] },
      { "type": "divider" },
      { "type": "heading", "text": "Package List" },
      { "type": "image", "src": "/instruction_book/package_list.png" }
  ]},
  { "header": "Specification", "blocks": [
      { "type": "heading", "text": "Specification" },
      { "type": "spec-box", "imageSrc": "/instruction_book/Specification_1.png", "specs": "按前端 spec-box 区域分区填充" },
      { "type": "paragraph", "text": "说明规格示意" },
      { "type": "grid2", "items": [
          { "type": "image", "src": "/instruction_book/Specification_2.png" },
          { "type": "list", "ordered": true, "items": ["Insulation Sleeves","Chiller","Control box","Circulation Pump","Ozone Sterilizer"] }
      ] }
  ]},
  { "header": "Touchscreen Control Panel", "blocks": [
      { "type": "heading", "text": "Touchscreen Control Panel（触控面板安装与按键说明）" },
      { "type": "paragraph", "text": "本页必须说明：触控面板的安装位置（机身外侧/控制箱附近/预留开孔处）、连接方式（与主控板/控制箱的接口类型与插接方向，是否需要断电操作）、固定方式（螺丝/卡扣/密封圈）、防水与走线要求（避免拉扯/折弯/压线）。同时解释面板上主要图标/按键/指示灯分别对应的功能（开关机、温度设定、制冷/加热模式、循环泵/过滤、灯光、童锁、故障提示等）。不要写泛泛的“请按说明安装”。" },
      { "type": "image", "src": "/instruction_book/Touchscreen_Control_Panel.png" }
  ]},
  { "header": "Troubleshooting", "blocks": [
      { "type": "heading", "text": "Troubleshooting" },
      { "type": "list", "items": [
          "Where to find Serial Number on Masrren?",
          "If after-sales service needed, provide this serial number."
      ] },
      { "type": "ts-section", "index": 1, "images": ["/instruction_book/Troubleshooting1_1.png","/instruction_book/Troubleshooting1_2.png","/instruction_book/Troubleshooting1_3.png"], "magnifier": { "serial": "AC003204030", "qrSrc": "/instruction_book/Troubleshooting1_3.png", "qrVisible": true, "qrSize": 78, "qrMargin": "6px auto 8px", "bgSrc": "", "lines": ["32. Masrren","Marble White","1780*840*950mm","23ZBG09E22898","K100CIAICOBOALOANDAOKA","MOD15946"] } },
      { "type": "ts-section", "index": 2, "images": ["/instruction_book/Troubleshooting2_1.png","/instruction_book/Troubleshooting2_2.png","/instruction_book/Troubleshooting2_3.png"], "magnifier": { "bgSrc": "/instruction_book/Troubleshooting2_3.png", "qrSrc": "" } }
  ]},
  { "header": "Troubleshooting", "blocks": [
      { "type": "heading", "text": "Troubleshooting" },
      { "type": "troubleTable", "headers": ["Symptom","Possible Solutions"], "groups": [
          { "title": "Start-up problem", "items": [ { "symptom": "Pump won't prime", "description": "Air trapped in pump.", "solutions": ["Remove airlock", "Check water level"] } ] },
          { "title": "Power and system problems", "items": [ { "symptom": "System won’t start or breaker trips", "solutions": ["Check power / contact technician"] } ] }
      ] }
  ]},
  { "header": "Troubleshooting", "blocks": [
      { "type": "heading", "text": "Troubleshooting" },
      { "type": "troubleTable", "headers": ["Symptom","Possible Solutions"], "groups": [
          { "title": "Chiller problems", "items": [ { "symptom": "Water does not get cold", "solutions": ["Set to low-temp range", "Clean/replace filter", "Remove airlock", "Check water level", "Open gate valves"] } ] },
          { "title": "Other problems", "items": [ { "symptom": "Water is murky / bad smell / temp mismatch", "solutions": ["Clean or change water", "Check filter/ozone", "Probe calibration"] } ] }
      ] }
  ]}
]

要求：
- 顺序和 header 必须与上面列表完全一致且一一对应，数组长度固定为 13，缺少任何一页都视为错误输出。
- 每页 blocks 类型与字段必须符合示例结构；可替换文本/图片，但字段键保持一致。
- 仅输出 JSON 数组，无任何额外文本或 Markdown。"""


def _default_page_for_header(header: str) -> Dict[str, Any]:
    """Provide a minimal default page per header."""
    if header == "Cover":
        return {
            "header": header,
            "blocks": [
                {
                    "type": "cover",
                    "title": "VINTERKÖLD",
                    "sizeText": "85” x 85” x 39”",
                    "backSrc": "/instruction_book/back.jpg",
                    "productSrc": "/instruction_book/product.png",
                }
            ],
        }
    if header == "Embrace the Revitalizing Chill":
        return {
            "header": header,
            "blocks": [
                {"type": "heading", "text": header},
                {"type": "paragraph", "text": "Experience the invigorating benefits of cold therapy through our innovative Masren product."},
                {"type": "list", "items": [
                    "Reduced Inflammation: Cold therapy helps to constrict blood vessels, reducing swelling and pain.",
                    "Faster Recovery: Promotes quicker muscle repair after workouts.",
                    "Increased Circulation: Boosts blood flow after exposure to cold.",
                    "Enhanced Mental Well-being: Cold shock triggers endorphins for a refreshed mind.",
                    "Boosted Immune System: Supports production of immune cells to stay resilient.",
                ]},
                {"type": "paragraph", "text": "Embrace the chill and unlock a new realm of well-being today."},
                {"type": "imageFloat-bottom-left", "src": "/instruction_book/product.png"},
                {"type": "imageFloat-bottom-right", "src": "/instruction_book/cold.png"},
            ],
        }
    if header == "Premium Materials":
        return {
            "header": header,
            "blocks": [
                {"type": "heading", "text": header},
                {"type": "paragraph", "text": "Embrace the chill and rejuvenate your body and mind with our product..."},
                {"type": "grid4", "items": [
                    {"index": 1, "title": "Acrylic Surface", "imgSrc": "/instruction_book/Acrylic_Surface.png"},
                    {"index": 2, "title": "Aluminum Frame", "imgSrc": "/instruction_book/Acrylic_Surface.png"},
                    {"index": 3, "title": "Tri-layered Side Cabinet", "imgSrc": "/instruction_book/Acrylic_Surface.png"},
                    {"index": 4, "title": "Insulation Sleeve", "imgSrc": "/instruction_book/Acrylic_Surface.png"},
                ]},
            ],
        }
    if header == "Contents":
        return {
            "header": header,
            "blocks": [
                {"type": "heading", "text": header},
                {"type": "contents", "items": [
                    {"title": "Installation & User Manual", "page": 1},
                    {"title": "How to Set Up", "page": 2},
                    {"title": "Important Safety Instructions", "page": 3},
                    {"title": "Specification", "page": 5},
                    {"title": "Touchscreen Control Panel", "page": 6},
                    {"title": "Troubleshooting", "page": 7},
                ]},
            ],
        }
    if header == "Specification":
        return {
            "header": header,
            "blocks": [
                {"type": "heading", "text": header},
                {"type": "paragraph", "text": "Specifications overview."},
            ],
        }
    if header == "Touchscreen Control Panel":
        return {
            "header": header,
            "blocks": [
                {"type": "heading", "text": header},
                {"type": "paragraph", "text": "Control Panel Installation Instructions"},
            ],
        }
    if header == "How To Set Up":
        return {
            "header": header,
            "blocks": [
                {"type": "heading", "text": header},
                {"type": "steps", "items": [
                    "Place your Masrren in a suitable location and fill with water.",
                    "Bleed air from filter and pump housing.",
                    "Connect power and set desired temperature.",
                    "Enjoy cold therapy after cooldown.",
                ]},
            ],
        }
    if header == "Installation & User Manual":
        return {
            "header": header,
            "blocks": [
                {"type": "heading", "text": header},
                {"type": "callout-warning", "text": "Warning! Risk of fire, electric shock and water leakage."},
                {"type": "paragraph", "text": "Follow all instructions closely."},
            ],
        }
    if header == "Important Safety Instructions":
        return {
            "header": header,
            "blocks": [
                {"type": "heading", "text": header},
                {"type": "list", "items": [
                    "Read and follow all instructions.",
                    "Consult doctor if unsure.",
                    "Be cautious entering/exiting the spa.",
                ]},
            ],
        }
    if header == "Troubleshooting":
        return {
            "header": header,
            "blocks": [
                {"type": "heading", "text": header},
                {"type": "troubleTable", "headers": ["Symptom", "Possible Solutions"], "groups": [
                    {"title": "Start-up problem", "items": [
                        {"symptom": "Pump won't prime", "solutions": [
                            "Check water level and remove airlock.",
                            "Inspect pump and power.",
                        ]}
                    ]}
                ]},
            ],
        }
    # default minimal
    return {"header": header, "blocks": [{"type": "heading", "text": header}]}


def _default_manual_book(title_hint: Optional[str] = None) -> List[ManualBookData]:
    """Fallback manual book payload when LLM fails. Returns pages array."""
    return [ManualBookData(**_default_page_for_header(hdr)) for hdr in TARGET_HEADERS]


def _strip_code_fence(value: Optional[str]) -> Optional[str]:
    if not value:
        return value
    v = value.strip()
    if v.startswith("```"):
        v = v.lstrip("`").lstrip()
    if v.endswith("```"):
        v = v.rstrip("`").rstrip()
    return v


def _normalize_manual_book(pages_or_book: Any) -> List[ManualBookData]:
    """
    Ensure manual_book returns pages array with required headers。
    接受数组或旧格式对象，输出固定 13 页数组。
    """
    if not pages_or_book:
        return _default_manual_book(None)

    # 保持与前端 manualPages 完整 13 页一致
    target_headers = TARGET_HEADERS

    # 统一 pages 列表
    pages: List[ManualBookData] = []
    if isinstance(pages_or_book, list):
        pages = [ManualBookData(**p) if isinstance(p, dict) else p for p in pages_or_book]
    elif isinstance(pages_or_book, ManualBookData):
        if getattr(pages_or_book, "pages", None):
            pages = [ManualBookData(**p) if isinstance(p, dict) else p for p in pages_or_book.pages]
        else:
            header = _strip_code_fence(pages_or_book.header) or (pages_or_book.header or target_headers[0])
            pages = [ManualBookData(header=header, blocks=pages_or_book.blocks or [])]
    elif isinstance(pages_or_book, dict):
        if pages_or_book.get("pages"):
            pages = [ManualBookData(**p) for p in pages_or_book["pages"]]
        elif pages_or_book.get("blocks"):
            header = _strip_code_fence(pages_or_book.get("header")) or target_headers[0]
            pages = [ManualBookData(header=header, blocks=pages_or_book["blocks"] or [])]

    # 如果模型完全没有返回目标 header，则按顺序对齐，避免全部落默认
    match_count = sum(1 for p in pages if p.header in target_headers)
    if match_count == 0 and pages:
        remapped_pages = []
        for idx, hdr in enumerate(target_headers):
            if idx < len(pages):
                remapped_pages.append(
                    ManualBookData(header=hdr, blocks=pages[idx].blocks or [])
                )
            else:
                default_fp = _default_page_for_header(hdr)
                remapped_pages.append(ManualBookData(**default_fp))
        pages = remapped_pages

    # Build a map of header -> pages queue (preserve duplicates like Troubleshooting)
    pages_by_header: Dict[str, List[ManualBookData]] = {}
    for p in pages:
        if not p.header:
            continue
        pages_by_header.setdefault(p.header, []).append(p)

    normalized_pages: List[ManualBookData] = []
    fallback_pages = _default_manual_book(None)
    fallback_map = {fp.header: fp for fp in fallback_pages}

    for hdr in target_headers:
        queue = pages_by_header.get(hdr) or []
        if queue:
            page = queue.pop(0)
            normalized_pages.append(ManualBookData(header=hdr, blocks=page.blocks or []))
        elif hdr in fallback_map:
            normalized_pages.append(fallback_map[hdr])
        else:
            normalized_pages.append(ManualBookData(header=hdr, blocks=[]))

    # Append extra pages (non-target headers) to the end to avoid loss
    for hdr, queue in pages_by_header.items():
        if hdr in target_headers:
            continue
        for p in queue:
            normalized_pages.append(ManualBookData(header=p.header, blocks=p.blocks or []))

    return normalized_pages


def build_manual_user_prompt(context_text: str, title_hint: str) -> str:
    headers = ", ".join([f'"{h}"' for h in TARGET_HEADERS])
    return (
        "请仅输出 JSON 数组纯文本，无说明文字/Markdown/代码块。数组长度必须是 13，顺序严格为：\n"
        f"[{headers}]\n\n"
        "务必按上述顺序输出全部 13 条目（长度不足视为错误），字段名保持一致，如缺少信息请使用合理占位。\n"
        "上下文：\n"
        f"{context_text}\n"
        "仅返回 JSON 数组。"
    )


def _build_manual_image_prompt(multimodal_segments: Optional[List[Dict[str, str]]]) -> str:
    multimodal_segments = multimodal_segments or []
    image_candidates: List[str] = []
    for idx, seg in enumerate(multimodal_segments):
        path = seg.get("image_path") or seg.get("image") or f"image_{idx}"
        desc = seg.get("description") or ""
        mime = seg.get("mime_type") or "image/*"
        if len(desc) > 500:
            desc = desc[:500] + "..."
        image_candidates.append(
            f"{idx + 1}. path: {path} ({mime})\n   reverse_prompt: {desc}".strip()
        )

    if not image_candidates:
        return ""
    return "\n\n候选图片（请为说明书的每个图片字段选择最匹配的图片路径）：\n" + "\n".join(image_candidates)


def _apply_manual_book_overrides(manual_book: List[ManualBookData]) -> List[ManualBookData]:
    """Apply hard rules after LLM output normalization."""
    for page in manual_book or []:
        if getattr(page, "header", None) != "Cover":
            continue
        blocks = getattr(page, "blocks", None) or []
        for blk in blocks:
            # blocks are dict-like (pydantic model output uses extra=allow)
            if isinstance(blk, dict):
                if blk.get("type") == "cover":
                    blk["backSrc"] = DEFAULT_COVER_BACK_SRC
            else:
                blk_type = getattr(blk, "type", None)
                if blk_type == "cover":
                    try:
                        setattr(blk, "backSrc", DEFAULT_COVER_BACK_SRC)
                    except Exception:
                        pass
        break
    return manual_book


def generate_manual_book_from_ocr(payload: ManualBookFromOcrRequest) -> Tuple[List[ManualBookData], str]:
    """Generate manual book data from OCR docs.

    Returns:
        manual_book: ManualBookData
        user_prompt: str (for debugging/display)
    Raises:
        ValueError: when documents missing or context empty
    """
    if not payload.documents:
        raise ValueError("请至少提供一个 OCR 文档")

    context_text, pseudo_chunks, _multimodal_segments = _build_context_from_ocr_documents(payload.documents)
    if not context_text.strip():
        raise ValueError("未提供可用于生成的 OCR 文档内容")

    llm_config = get_llm_config(
        llm_provider=getattr(payload, "llm_provider", None),
        llm_model=getattr(payload, "llm_model", None),
    )
    title_hint = payload.product_name or payload.bom_code or "Instruction Book"
    user_prompt = build_manual_user_prompt(context_text, title_hint) + _build_manual_image_prompt(_multimodal_segments)

    def _build_messages(extra_instruction: Optional[str] = None) -> list[dict]:
        messages = [
            {"role": "system", "content": MANUAL_BOOK_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]
        if extra_instruction:
            messages.append({"role": "user", "content": extra_instruction})
        return messages

    def _call_llm(messages: list[dict]) -> str:
        kwargs = {
            "model": llm_config.model,
            "messages": messages,
            "temperature": 0.2,
        }
        if _multimodal_segments:
            image_payloads = [seg.get("image") for seg in _multimodal_segments if seg.get("image")]
            if image_payloads:
                kwargs["images"] = image_payloads
        if llm_config.api_key:
            kwargs["api_key"] = llm_config.api_key
        if llm_config.base_url:
            kwargs["api_base"] = llm_config.base_url
        response = _run_completion_with_timeout(kwargs, None)
        return response.choices[0].message.content.strip()

    manual_book: Optional[List[ManualBookData]] = None
    errors: list[str] = []

    for attempt in range(2):
        extra_note = None
        if attempt == 1 and errors:
            extra_note = (
                "上次输出无法解析或缺少必填字段。请仅返回 JSON 数组，无 markdown/代码块/说明文字，"
                "数组长度为 13，header 依次为："
                f"{', '.join(TARGET_HEADERS)}。错误提示：{errors[-1]}"
            )
        try:
            llm_output = _call_llm(_build_messages(extra_note))
            print(f"[ManualBook] Raw LLM output (attempt {attempt+1}):\n{llm_output}")  # debug log
            manual_book = _parse_and_validate_manual_book(llm_output)
            break
        except Exception as exc:  # noqa: BLE001
            errors.append(str(exc))
            manual_book = None

    if manual_book is None:
        print(f"[ManualBook] LLM fallback after retries: {errors}")
        manual_book = _default_manual_book(title_hint)

    manual_book = _normalize_manual_book(manual_book)
    manual_book = _apply_manual_book_overrides(manual_book)

    try:
        _persist_manual_book(manual_book, payload)
    except Exception as exc:  # noqa: BLE001
        print(f"[ManualBook] Failed to persist manual_book: {exc}")

    return manual_book, user_prompt


def _sanitize_filename_component(value: Optional[str]) -> str:
    v = (value or "").strip()
    if not v:
        return ""
    v = v.replace("/", "_").replace("\\", "_")
    v = re.sub(r"\s+", "_", v)
    v = re.sub(r"[^A-Za-z0-9_.\-\u4e00-\u9fff]", "_", v)
    v = re.sub(r"_+", "_", v).strip("_")
    return v


def _persist_manual_book(manual_book: List[ManualBookData], payload: ManualBookFromOcrRequest) -> Path:
    base_dir = Path(__file__).resolve().parents[1] / "manual_ocr_results"
    base_dir.mkdir(parents=True, exist_ok=True)

    product_part = _sanitize_filename_component(getattr(payload, "product_name", None))
    bom_part = _sanitize_filename_component(getattr(payload, "bom_code", None))
    session_part = _sanitize_filename_component(getattr(payload, "session_id", None))

    parts = [p for p in [product_part, bom_part] if p]
    if not parts:
        parts = [p for p in [session_part] if p] or ["manual_book"]

    folder_name = "_".join(parts)
    product_dir = base_dir / folder_name
    if not product_dir.exists() or not product_dir.is_dir():
        raise FileNotFoundError(f"manual_ocr_results 产品目录不存在: {product_dir}")
    generate_dir = product_dir / "generate"
    generate_dir.mkdir(parents=True, exist_ok=True)
    target_path = generate_dir / "manual_book.json"

    payload_json = [page.dict() for page in (manual_book or [])]
    content = json.dumps(payload_json, ensure_ascii=False, indent=2)

    tmp_path = target_path.with_suffix(f".tmp-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}.json")
    tmp_path.write_text(content, encoding="utf-8")
    tmp_path.replace(target_path)
    print(f"[ManualBook] manual_book saved to: {target_path}")
    return target_path


def _extract_json_or_convert(text: str) -> str:
    """
    Try to extract JSON; if not found, heuristically convert prose to manual_book JSON.
    Keeps function simple to avoid repeated LLM calls.
    """
    # If model returned fenced markdown (e.g., ```markdown ...```), skip to default template
    if "```markdown" in text.lower():
        default_pages = [_default_page_for_header(h) for h in TARGET_HEADERS]
        return json.dumps({"header": TARGET_HEADERS[0], "pages": default_pages}, ensure_ascii=False)

    # direct JSON fenced
    if "```json" in text:
        return text.split("```json")[1].split("```")[0].strip()
    if "```" in text:
        candidate = text.split("```")[1].split("```")[0].strip()
        if candidate.startswith("{") or candidate.startswith("["):
            return candidate

    stripped = text.strip()
    if stripped.startswith("{") and stripped.endswith("}"):
        return stripped
    if stripped.startswith("[") and stripped.endswith("]"):
        return stripped

    # heuristic conversion: use first non-empty line as header,
    # then treat paragraphs separated by blank lines,
    # and numbered list items as list block.
    lines = [ln.strip() for ln in stripped.splitlines()]
    lines = [ln for ln in lines if ln]  # drop empty
    if not lines:
        raise ValueError("LLM returned empty content")

    header = lines[0].strip("*# ").strip()
    paragraphs = []
    list_items = []

    for ln in lines[1:]:
        if re.match(r"^\\d+\\.\\s", ln):
            list_items.append(re.sub(r"^\\d+\\.\\s*", "", ln))
        else:
            paragraphs.append(ln)

    blocks = [{"type": "heading", "text": header}]
    for p in paragraphs:
        blocks.append({"type": "paragraph", "text": p})
    if list_items:
        blocks.append({"type": "list", "items": list_items})

    # keep default images for consistency
    blocks.append({"type": "imageFloat-bottom-left", "src": "/instruction_book/product.png"})
    blocks.append({"type": "imageFloat-bottom-right", "src": "/instruction_book/cold.png"})

    manual = {
        "header": header or "Instruction Book",
        "blocks": blocks,
    }
    return json.dumps(manual, ensure_ascii=False)


def _coerce_manual_book(parsed: Any) -> List[ManualBookData]:
    """
    Convert raw parsed JSON into pages array or raise ValueError.
    Enforces presence of header/blocks and basic shape before normalization.
    """
    if isinstance(parsed, list):
        if parsed and all(isinstance(x, dict) and "header" in x and "blocks" in x for x in parsed):
            return [ManualBookData(**p) for p in parsed]
        raise ValueError("LLM 返回的数组缺少 header/blocks")
    if isinstance(parsed, dict):
        if parsed.get("pages"):
            pages = parsed["pages"]
            if not isinstance(pages, list):
                raise ValueError("pages 字段必须是数组")
            for idx, p in enumerate(pages):
                if not isinstance(p, dict):
                    raise ValueError(f"page[{idx}] 不是对象")
                if "header" not in p or "blocks" not in p:
                    raise ValueError(f"page[{idx}] 缺少 header 或 blocks")
                if not isinstance(p.get("blocks"), list):
                    raise ValueError(f"page[{idx}].blocks 必须是数组")
        elif parsed.get("blocks"):
            # 单页兼容：把 blocks 包装为 pages[0]
            header = parsed.get("header") or TARGET_HEADERS[0]
            return [ManualBookData(header=header, blocks=parsed["blocks"])]
        raise ValueError("缺少 pages 或 blocks")
        # Unreachable, kept for clarity
        return [ManualBookData(**parsed)]
    raise ValueError("无法识别的手册结构")


def _parse_and_validate_manual_book(llm_output: str) -> List[ManualBookData]:
    """
    Parse raw LLM output, extract JSON, coerce to pages array, validate basic shape.
    """
    try:
        cleaned = _extract_json_or_convert(llm_output)
        parsed_json = json.loads(cleaned)
        return _coerce_manual_book(parsed_json)
    except Exception as exc:
        print(f"[ManualBook] Parse/validate failed: {exc}\nRaw output:\n{llm_output}")
        # 不再抛错，直接兜底默认手册
        return _default_manual_book(None)

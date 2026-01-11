"""
Pydantic models for specsheet data structure matching example.json format.
Each field includes a description for future sample content addition.
"""
from typing import List, Union, Dict, Optional, Any
from pydantic import BaseModel, Field


class SpecsheetFeatures(BaseModel):
    """Product features including capacity, jets, and pumps."""
    capacity: str = Field(..., description="Product capacity (number of seats/people)")
    jets: str = Field(..., description="Number of jets in the product")
    pumps: str = Field(..., description="Number of pumps in the product")


class SpecsheetImages(BaseModel):
    """Image paths for product and background."""
    product: str = Field(..., description="Path to product image (e.g., '/back/product.png')")
    background: str = Field(..., description="Path to background image (e.g., '/back/back.png')")


class SpecsheetData(BaseModel):
    """Complete specsheet data structure matching example.json format."""
    productTitle: str = Field(..., description="Product title/name (e.g., 'Vastera')")
    features: SpecsheetFeatures = Field(..., description="Product features (capacity, jets, pumps)")
    measurements: str = Field(..., description="Product measurements (e.g., '70\" × 33\" × 37\"')")
    premiumFeatures: List[str] = Field(..., description="List of premium lighting system features")
    insulationFeatures: List[str] = Field(..., description="List of energy-saving insulation system features")
    extraFeatures: List[str] = Field(..., description="List of extra features")
    Specifications: List[Dict[str, Union[str, List[str]]]] = Field(..., description="Specifications list as array of objects: [{\"Cabinet Color\": [\"#c4c4c4\", \"#666666\"]}, {\"Shell Color\": \"#c4c4c4\"}, {\"Dry Weight\": \"293 lbs\"}, {\"Water Capacity\": \"79 gallons\"}, {\"Pump\": \"1 x Chiller\"}, {\"Controls\": \"Joyonway Touch Screen\"}]")
    smartWater: List[str] = Field(..., description="List of smart water purification system features")
    images: SpecsheetImages = Field(..., description="Product and background image paths")


class SpecsheetResponse(BaseModel):
    """API response wrapper for specsheet data."""
    specsheet: SpecsheetData = Field(..., description="Complete specsheet data structure")


class ChunkInfo(BaseModel):
    """Information about a retrieved content chunk used for RAG context."""
    text: str = Field(..., description="Chunk text content")
    source_path: str = Field(..., description="Source file path for this chunk")
    similarity: float = Field(..., description="Similarity score between query and this chunk")


class SpecsheetWithChunksResponse(BaseModel):
    """Extended API response returning specsheet and the retrieved chunks used as context."""
    specsheet: SpecsheetData = Field(..., description="Complete specsheet data structure")
    chunks: List[ChunkInfo] = Field(..., description="Top-k retrieved chunks with text and source path")
    prompt_text: Optional[str] = Field(
        None, description="实际发送给大模型的用户提示词（含上下文与图像描述）"
    )
    system_prompt: Optional[str] = Field(
        None, description="发送给大模型的系统提示词"
    )


class SpecsheetSaveRequest(BaseModel):
    """Payload for persisting a specsheet onto a product BOM node."""
    specsheet: SpecsheetData = Field(..., description="Specsheet JSON to persist")


class DocumentReference(BaseModel):
    """Lightweight reference describing a selected document or image."""
    name: Optional[str] = Field(None, description="Document display name")
    path: Optional[str] = Field(None, description="Relative storage path within backend root")
    type: Optional[str] = Field(None, description="document / image / image_embedded 等类型")
    summary: Optional[str] = Field(None, description="Optional summary extracted on frontend")


class AccessoryDocumentGroup(BaseModel):
    """Holds all documents associated with a specific accessory."""
    accessory: str = Field(..., description="Accessory name")
    documents: List[DocumentReference] = Field(default_factory=list, description="Documents linked to this accessory")


class SpecsheetFromDocsRequest(BaseModel):
    """Payload sent from frontend when it already has the RAG source documents."""
    product_docs: List[DocumentReference] = Field(default_factory=list, description="Documents selected for the product itself")
    accessory_docs: List[AccessoryDocumentGroup] = Field(default_factory=list, description="Accessory documents grouped by accessory name")


class SpecsheetOcrDocument(BaseModel):
    """Flattened OCR document entry without product/配件语义."""
    name: Optional[str] = Field(None, description="Display name captured during OCR")
    path: Optional[str] = Field(None, description="Backend-relative file path for this OCR artifact")
    type: Optional[str] = Field(None, description="Free-form document type metadata")
    summary: Optional[str] = Field(None, description="Optional summary or extracted text snippet")
    text: Optional[str] = Field(None, description="Inline OCR text content if already available")
    mime_type: Optional[str] = Field(None, description="原始文件的 MIME 类型 (image/png, text/markdown 等)")
    image_base64: Optional[str] = Field(
        None,
        description="可选的 base64-encoded 原图（不包含 data: 前缀），便于多模态模型读取",
    )


class SpecsheetFromOcrRequest(BaseModel):
    """Payload for generating specsheet purely基于 OCR 文档."""
    documents: List[SpecsheetOcrDocument] = Field(
        default_factory=list,
        description="OCR 文档列表，将作为规格页上下文",
    )
    product_name: Optional[str] = Field(
        None, description="可选的产品名称提示，用于后续生成说明"
    )
    session_id: Optional[str] = Field(
        None, description="手动 OCR 会话 ID，用于将规格页结果落盘"
    )
    bom_code: Optional[str] = Field(
        None, description="可选的 BOM 编码，用于区分不同版本规格页文件"
    )
    bom_type: Optional[str] = Field(
        None, description="可选：BOM 类型（outdoor/pool/iceTub），用于按指定类型解析 BOM"
    )

    llm_provider: Optional[str] = Field(
        None,
        description="可选：指定文本大模型提供方（如 'ollama' 或 'dashscope'），不传则使用后端默认配置",
    )
    llm_model: Optional[str] = Field(
        None,
        description="可选：指定文本大模型名称（建议传 LiteLLM model 格式，如 'ollama/qwen3-vl:xxx' 或 'dashscope/qwen3-max'）",
    )


class ManualBookFullGenerateRequest(BaseModel):
    """Generate the full 13-page manual book using product context (config_text_zh + BOM + glossary)."""

    product_name: str = Field(..., description="产品名称（用于定位 Neo4j 产品与标题）")
    bom_code: str = Field(..., description="BOM 编码（用于定位 Neo4j 产品与解码摘要）")

    llm_provider: Optional[str] = Field(
        None,
        description="可选：指定文本大模型提供方（如 'ollama' 或 'dashscope'），不传则使用后端默认配置",
    )
    llm_model: Optional[str] = Field(
        None,
        description="可选：指定文本大模型名称（建议传 LiteLLM model 格式，如 'ollama/qwen3-vl:xxx' 或 'dashscope/qwen3-max'）",
    )


class ManualBookVariantPlanRequest(BaseModel):
    documents: List[SpecsheetOcrDocument] = Field(default_factory=list, description="OCR 文档列表")
    product_name: Optional[str] = Field(None, description="产品名称提示")
    session_id: Optional[str] = Field(None, description="会话 ID，可用于落盘")
    bom_code: Optional[str] = Field(None, description="BOM 编码（可选）")

    llm_provider: Optional[str] = Field(
        None,
        description="可选：指定文本大模型提供方（如 'ollama' 或 'dashscope'），不传则使用后端默认配置",
    )
    llm_model: Optional[str] = Field(
        None,
        description="可选：指定文本大模型名称（建议传 LiteLLM model 格式，如 'ollama/qwen3-vl:xxx' 或 'dashscope/qwen3-max'）",
    )


class ManualSpecsheetSaveRequest(BaseModel):
    """Payload for persisting a specsheet JSON inside manual session folder."""
    specsheet: SpecsheetData = Field(..., description="规格页 JSON 数据")
    bom_code: Optional[str] = Field(
        None, description="可选 BOM 编码，控制保存文件名后缀"
    )


class ManualSpecsheetAceRequest(BaseModel):
    """Payload for triggering ACE adaptation on a single specsheet sample."""
    session_id: Optional[str] = Field(None, description="手动 OCR 会话 ID（可使用路径参数）")
    bom_code: Optional[str] = Field(None, description="可选 BOM 编码，定位具体样本")
    ground_truth: Optional[SpecsheetData] = Field(
        None,
        description="可选：用户最终确认的规格页 JSON；若不传则尝试从 manual_ocr_results/<session>/truth/specsheet.json 读取",
    )


# ---------------------- Manual Book (Instruction) Models ----------------------


class ManualBookBlock(BaseModel):
    """Single block entry for instruction book rendering."""
    type: str = Field(..., description="heading / paragraph / list / imageFloat-* 等")
    text: Optional[str] = Field(None, description="文本内容，适用于 heading/paragraph")
    # items 可包含字符串或对象（如 contents/grid4/ts-section 等）
    items: Optional[List[Union[str, Dict[str, Any]]]] = Field(
        None, description="列表条目，支持字符串或对象（contents/grid4/ts-section 等复合结构）"
    )
    src: Optional[str] = Field(None, description="图片路径，适用于 image*")
    ordered: Optional[bool] = Field(None, description="列表是否有序")
    className: Optional[str] = Field(None, description="可选样式类名")

    class Config:
        # 允许模型返回的额外字段（如 table.headers/rows、callout 自定义字段），防止验证失败
        extra = "allow"


class ManualBookData(BaseModel):
    """Instruction book page payload returned by LLM."""
    header: str = Field(..., description="页标题，对应前端 manualPages.header")
    blocks: List[ManualBookBlock] = Field(default_factory=list, description="内容块列表，对应前端 manualPages.blocks")

    class Config:
        extra = "allow"


class ManualBookResponse(BaseModel):
    """API response for instruction book generation."""
    manual_book: List[ManualBookData] = Field(..., description="生成的说明书页数组（长度 13，对应前端 manualPages）")
    prompt_text: Optional[str] = Field(None, description="用户提示词")
    system_prompt: Optional[str] = Field(None, description="系统提示词")


class ManualBookVariantPlanResponse(BaseModel):
    variants: Dict[str, str] = Field(default_factory=dict, description="章节组 -> 版本选择（A/B/C/GENERATE）")
    generated_pages: Dict[str, List[ManualBookData]] = Field(
        default_factory=dict,
        description="章节组 -> 生成的替代页面（仅当 variants[group]==GENERATE 时提供）",
    )
    prompt_text: Optional[str] = Field(None, description="用户提示词")
    system_prompt: Optional[str] = Field(None, description="系统提示词")


class ManualBookOneShotRequest(BaseModel):
    """One-shot manual generation: choose variants (A/B/C) + generate fixed non-variant pages."""

    product_name: str = Field(..., description="产品名称（用于定位 Neo4j 产品与标题）")
    bom_code: str = Field(..., description="BOM 编码（用于定位 Neo4j 产品与解码摘要）")
    documents: List[SpecsheetOcrDocument] = Field(default_factory=list, description="可选 OCR 文档列表（用于提供图片候选/额外上下文）")
    session_id: Optional[str] = Field(None, description="会话 ID，可用于落盘")

    llm_provider: Optional[str] = Field(
        None,
        description="可选：指定文本大模型提供方（如 'ollama' 或 'dashscope'），不传则使用后端默认配置",
    )
    llm_model: Optional[str] = Field(
        None,
        description="可选：指定文本大模型名称（建议传 LiteLLM model 格式，如 'ollama/qwen3-vl:xxx' 或 'dashscope/qwen3-max'）",
    )


class ManualBookOneShotResponse(BaseModel):
    variants: Dict[str, str] = Field(default_factory=dict, description="章节组 -> 版本选择（A/B/C）")
    fixed_pages: Dict[str, ManualBookData] = Field(
        default_factory=dict,
        description="非变体页生成结果：header -> page（例如 Cover / Installation & User Manual / Specification；Contents 将被前端忽略）",
    )
    prompt_text: Optional[str] = Field(None, description="用户提示词")
    system_prompt: Optional[str] = Field(None, description="系统提示词")


class ManualBookFromOcrRequest(BaseModel):
    """Payload for generating instruction book from OCR docs."""
    documents: List[SpecsheetOcrDocument] = Field(default_factory=list, description="OCR 文档列表")
    product_name: Optional[str] = Field(None, description="产品名称提示")
    session_id: Optional[str] = Field(None, description="会话 ID，可用于落盘")
    bom_code: Optional[str] = Field(None, description="BOM 编码（可选）")

    llm_provider: Optional[str] = Field(
        None,
        description="可选：指定文本大模型提供方（如 'ollama' 或 'dashscope'），不传则使用后端默认配置",
    )
    llm_model: Optional[str] = Field(
        None,
        description="可选：指定文本大模型名称（建议传 LiteLLM model 格式，如 'ollama/qwen3-vl:xxx' 或 'dashscope/qwen3-max'）",
    )


# resolve forward refs
ManualBookData.model_rebuild()


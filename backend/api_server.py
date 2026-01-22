"""
FastAPI server for frontend-backend communication.
Provides endpoints for products, BOMs, and specsheet data.
"""
import os
import sys
import json
import re
import mimetypes
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Literal
from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Query, Body
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from dotenv import load_dotenv

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

load_dotenv(project_root / ".env")

from src.kb_chat.routes import router as kb_chat_router

from src.api_queries import (
    get_all_product_names,
    get_all_accessory_names,
    get_all_material_codes,
    get_material_image_by_material_code,
    get_product_image_by_product_name,
    get_boms_by_material_code,
    get_accessories_zh_by_material_bom,
    get_boms_by_product_id,
    get_accessories_by_product_bom_id,
    get_kb_overview_by_product_id,
    update_product_config_text_zh,
    upsert_product_has_doc,
    get_documents_by_product_bom,
    get_documents_by_accessory,
    get_document_detail,
    update_document_content,
    delete_document,
    move_document_owner,
    get_unmatched_documents,
    attach_document_to_owner,
    get_unmatched_document_detail,
    insert_product_with_documents,
    extract_documents_from_session,
    extract_truth_documents,
    BACKEND_ROOT,
)
from src.rag_specsheet import (
    SPEC_SHEET_SYSTEM_PROMPT,
    get_specsheet_by_product_bom,
    get_specsheet_with_chunks_by_product_bom,
    get_specsheet_from_provided_docs,
    get_specsheet_from_provided_docs,
    save_specsheet_for_product_bom,
    generate_specsheet_from_ocr_request,
    _build_context_from_ocr_documents,
    _run_completion_with_timeout,
    _extract_specsheet_from_context,
)
from src.specsheet_evaluator import evaluate_specsheet
from src.rag_bom import generate_bom_from_ocr_request
from src.specsheet_models import (
    SpecsheetResponse,
    SpecsheetWithChunksResponse,
    SpecsheetFromDocsRequest,
    SpecsheetData,
    ChunkInfo,
    SpecsheetSaveRequest,
    SpecsheetFromOcrRequest,
    ManualSpecsheetSaveRequest,
    ManualSpecsheetAceRequest,
    ManualBookFromOcrRequest,
    ManualBookResponse,
    ManualBookData,
    ManualBookVariantPlanRequest,
    ManualBookVariantPlanResponse,
    ManualBookOneShotRequest,
    ManualBookOneShotResponse,
)
from src.specsheet_storage import (
    save_specsheet_for_session,
    load_specsheet_for_session,
)
from src.ace_integration import get_ace_manager, save_pending_sample, load_pending_sample, store_ace_sample, clear_pending_sample
from src.poster_image_edit import PosterImageEditInputs, generate_poster_image_edit as run_poster_image_edit
from src.bom_models import (
    BomGenerationRequest,
    BomGenerationResponse,
    BomSaveRequest,
    BomSaveResponse,
)
from src.bom_storage import save_bom_code_to_file, load_bom_code_for_session
from src.manual_ocr import (
    create_manual_session_entry,
    handle_manual_ocr,
    init_manual_session_entry,
    append_manual_session_uploads,
    delete_manual_session_upload,
    list_session_records,
    load_session_record,
    run_manual_session,
    run_prompt_reverse_only,
    delete_manual_session,
    clear_manual_history,
)
from src.manual_progress import progress_manager
from src.manual_book import (
    MANUAL_BOOK_SYSTEM_PROMPT,
    generate_manual_book_from_ocr as run_manual_book_from_ocr,
    MANUAL_VARIANT_PLAN_SYSTEM_PROMPT,
    plan_manual_variants_from_context,
    MANUAL_ONE_SHOT_SYSTEM_PROMPT,
    generate_manual_one_shot,
)
from src.prompt_playbook import (
    list_prompt_playbooks,
    persist_ace_dataset,
    persist_named_dataset,
    list_saved_datasets,
    delete_saved_dataset,
    get_playbook_rules,
    delete_playbook_rule,
    get_system_prompt,
    PROMPT_PLAYBOOK_TYPES,
)

from src.poster_analyzer import analyze_reference as poster_analyze_reference
from src.poster_analyzer import generate_copy as poster_generate_copy


PROMPT_SNAPSHOT_FILES = {
    "spec": ("question_spec.txt", "context_spec.txt"),
    "manual": ("question_manual.txt", "context_manual.txt"),
    "poster": ("question_poster.txt", "context_poster.txt"),
    "other": ("question_other.txt", "context_other.txt"),
}


def _sanitize_manual_folder_component(value: str | None) -> str:
    v = (value or "").strip()
    if not v:
        return ""
    v = v.replace("/", "_").replace("\\", "_")
    v = re.sub(r"\s+", "_", v)
    v = re.sub(r"[^A-Za-z0-9_.\-\u4e00-\u9fff]", "_", v)
    v = re.sub(r"_+", "_", v).strip("_")
    return v


def _resolve_manual_product_dir(product_name: str | None, bom_code: str | None) -> Path:
    product_part = _sanitize_manual_folder_component(product_name)
    bom_part = _sanitize_manual_folder_component(bom_code)
    if not product_part or not bom_part:
        raise ValueError("product_name 和 bom_code 不能为空")
    base_dir = Path(__file__).resolve().parent / "manual_ocr_results"
    product_dir = base_dir / f"{product_part}_{bom_part}"
    if not product_dir.exists() or not product_dir.is_dir():
        raise FileNotFoundError(f"manual_ocr_results 产品目录不存在: {product_dir}")
    return product_dir


def _write_prompt_snapshot_files(
    product_dir: Path,
    playbook_type: str,
    system_prompt: str | None,
    user_prompt: str | None,
) -> None:
    if not system_prompt and not user_prompt:
        return

    filenames = PROMPT_SNAPSHOT_FILES.get(playbook_type, PROMPT_SNAPSHOT_FILES["other"])
    question_filename, context_filename = filenames

    try:
        if system_prompt:
            (product_dir / question_filename).write_text(system_prompt, encoding="utf-8")
        if user_prompt:
            (product_dir / context_filename).write_text(user_prompt, encoding="utf-8")
    except Exception as exc:  # noqa: BLE001
        print(f"[PromptSnapshot] Failed to write prompt files for {product_dir}: {exc}")


load_dotenv()

# Create FastAPI app
app = FastAPI(title="Product Specsheet API", version="1.0.0")

app.include_router(kb_chat_router)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://d0ctb77hri0c73ctcgdg-36963.agent.damodel.com",
        "http://localhost:36963",
        "http://127.0.0.1:36963",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Static files: material images extracted from Excel
MATERIAL_IMAGES_DIR = Path(__file__).resolve().parent / "material_images"
if MATERIAL_IMAGES_DIR.exists() and MATERIAL_IMAGES_DIR.is_dir():
    app.mount(
        "/static/material_images",
        StaticFiles(directory=str(MATERIAL_IMAGES_DIR)),
        name="material_images",
    )


@app.get("/api/material_images/{file_path:path}")
async def get_material_image_file(file_path: str):
    try:
        rel = (file_path or "").lstrip("/")
        if not rel:
            raise HTTPException(status_code=404, detail="File not found")

        base = MATERIAL_IMAGES_DIR.resolve()
        target = (base / rel).resolve()
        if target != base and base not in target.parents:
            raise HTTPException(status_code=400, detail="Invalid file path")
        if not target.exists() or not target.is_file():
            raise HTTPException(status_code=404, detail="File not found")

        media_type, _ = mimetypes.guess_type(str(target))
        return FileResponse(path=str(target), media_type=media_type or "application/octet-stream")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch material image file: {str(e)}")


class DocumentUpdateRequest(BaseModel):
    content: str
    new_name: str | None = None


class DocumentMoveRequest(BaseModel):
    target_type: Literal["product", "accessory"]
    product_name: str | None = None
    bom_version: str | None = None
    accessory_name: str | None = None


class DocumentAttachRequest(BaseModel):
    doc_path: str
    target_type: Literal["product", "accessory"]
    product_name: str | None = None
    bom_version: str | None = None
    accessory_name: str | None = None


class ProductConfigUpdateRequest(BaseModel):
    config_text_zh: str = Field(default="")


class InsertProductDocument(BaseModel):
    name: str | None = None
    path: str | None = None
    type: str | None = None
    summary: str | None = None
    mime_type: str | None = None


class InsertProductRequest(BaseModel):
    product_name: str
    display_name: str | None = None
    bom_code: str | None = None
    session_id: str | None = None
    documents: list[InsertProductDocument] | None = None


class PromptPlaybookAceSample(BaseModel):
    folder_name: str
    product_name: str
    playbook_type: Literal["spec", "manual", "poster", "other"]
    question: str | None = None
    context: str | None = None
    ground_truth: str | None = None
    generate_content: str | None = None
    truth_content: str | None = None
    source_files: list[str] | None = None


class PromptPlaybookAceRequest(BaseModel):
    playbook_type: Literal["spec", "manual", "poster", "other"]
    dataset_name: str | None = None
    description: str | None = None
    samples: List[PromptPlaybookAceSample]
    custom_rules: List[str] | None = None


class PromptPlaybookDatasetDeleteRequest(BaseModel):
    file_path: str


class PosterAnalyzeReferenceRequest(BaseModel):
    image_url: str | None = None
    prompt: str | None = None
    model: str | None = None
    font_candidates: List[str] | None = None


class PosterGenerateCopyRequest(BaseModel):
    step1_result: Dict[str, Any]
    requirements: str | None = None
    target_language: str | None = None
    model: str | None = None
    product_name: str | None = None
    bom_code: str | None = None
    bom_type: str | None = None
    product_image_url: str | None = None
    background_image_url: str | None = None


class PosterGenerateImageEditRequest(BaseModel):
    reference_image_url: str
    product_image_url: str
    background_image_url: str | None = None
    step1_result: Dict[str, Any]
    product_name: str | None = None
    bom_code: str | None = None
    title: str | None = None
    subtitle: str | None = None
    sellpoints: List[str] | None = None
    output_width: int | None = None
    output_height: int | None = None
    watermark: bool | None = None
    negative_prompt: str | None = None


class ManualSessionInitRequest(BaseModel):
    product_name: str
    bom_code: str | None = None
    bom_type: str | None = None
    material_code: str | None = None
    bom_id: str | None = None


@app.get("/")
async def root():
    """Root endpoint."""
    return {"message": "Product Specsheet API", "version": "1.0.0"}


@app.get("/api/products")
async def get_products():
    """
    Get all unique product English names.
    
    Returns:
        JSON object with list of product names
    """
    try:
        products = get_all_product_names()
        return {"products": products}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch products: {str(e)}")


@app.get("/api/accessories")
async def get_accessories():
    """Get all unique accessory names."""
    try:
        accessories = get_all_accessory_names()
        return {"accessories": accessories}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch accessories: {str(e)}")


@app.get("/api/materials")
async def get_materials():
    """Get all material codes."""
    try:
        materials = get_all_material_codes()
        return {"materials": materials}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch materials: {str(e)}")


@app.get("/api/materials/{material_code}/boms")
async def get_material_boms(material_code: str):
    """Get BOM ids for a material_code."""
    try:
        boms = get_boms_by_material_code(material_code)
        return {"boms": boms}
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch BOMs for material '{material_code}': {str(e)}",
        )


@app.get("/api/materials/{material_code}/image")
async def get_material_image(material_code: str):
    try:
        data = get_material_image_by_material_code(material_code)
        return data
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch image for material '{material_code}': {str(e)}",
        )


@app.get("/api/products/{product_name}/image")
async def get_product_image(product_name: str):
    try:
        data = get_product_image_by_product_name(product_name)
        return data
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch image for product '{product_name}': {str(e)}",
        )


@app.get("/api/materials/{material_code}/boms/{bom_id}/accessories")
async def get_material_bom_accessories(material_code: str, bom_id: str):
    """Get accessory Chinese names for a material_code + bom_id."""
    try:
        accessories = get_accessories_zh_by_material_bom(material_code, bom_id)
        return {"accessories": accessories}
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch accessories for material '{material_code}' BOM '{bom_id}': {str(e)}",
        )


@app.get("/api/products/{product_name}/boms")
async def get_product_boms(product_name: str):
    """
    Get all BOM versions for a specific product.
    
    Args:
        product_name: Product English name
        
    Returns:
        JSON object with list of BOM versions
    """
    try:
        boms = get_boms_by_product_id(product_name)
        if not boms:
            raise HTTPException(
                status_code=404,
                detail=f"No BOMs found for product '{product_name}'"
            )
        return {"boms": boms}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch BOMs for product '{product_name}': {str(e)}"
        )


@app.get("/api/products/{product_name}/boms/{bom_version}/accessories")
async def get_product_bom_accessories(product_name: str, bom_version: str):
    """Get accessories connected to a product and BOM."""
    try:
        accessories = get_accessories_by_product_bom_id(product_name, bom_version)
        return {"accessories": accessories}
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=(
                f"Failed to fetch accessories for product '{product_name}' BOM '{bom_version}': {str(e)}"
            ),
        )


@app.get("/api/products/{product_name}/boms/{bom_version}/documents")
async def get_product_bom_documents(product_name: str, bom_version: str):
    """Get documents linked to a product BOM."""
    try:
        documents = get_documents_by_product_bom(product_name, bom_version)
        return {"documents": documents}
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=(
                f"Failed to fetch documents for product '{product_name}' BOM '{bom_version}': {str(e)}"
            ),
        )


@app.get("/api/products/{product_id}/kb_overview")
async def get_product_kb_overview(product_id: str):
    """Get KB overview for a product_id using Dataset/Folder/Document + HAS_DOC schema."""
    try:
        data = get_kb_overview_by_product_id(product_id)
        return data
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch KB overview for product '{product_id}': {str(e)}",
        )


@app.put("/api/products/{product_id}/config")
async def update_product_config(product_id: str, payload: ProductConfigUpdateRequest):
    """Update product config_text_zh and persist to Neo4j ProductConfig."""
    try:
        return update_product_config_text_zh(product_id, payload.config_text_zh)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update product config for '{product_id}': {str(e)}")


@app.get("/api/accessories/{accessory_name}/documents")
async def get_accessory_documents(accessory_name: str):
    """Get documents linked to a specific accessory."""
    try:
        documents = get_documents_by_accessory(accessory_name)
        return {"documents": documents}
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch documents for accessory '{accessory_name}': {str(e)}",
        )


@app.get("/api/documents/unmatched")
async def list_unmatched_documents():
    """List documents that are not attached to any product/accessory."""
    try:
        return get_unmatched_documents()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch unmatched documents: {str(e)}")


@app.post("/api/documents/attach")
async def attach_document(payload: DocumentAttachRequest):
    """Attach an unmatched document to a product or accessory."""
    try:
        attached = attach_document_to_owner(
            payload.doc_path,
            target_type=payload.target_type,
            product_name=payload.product_name,
            bom_version=payload.bom_version,
            accessory_name=payload.accessory_name,
        )
        return attached
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to attach document '{payload.doc_path}': {str(e)}")


@app.get("/api/documents/unmatched/{doc_path:path}")
async def fetch_unmatched_document_detail(doc_path: str):
    """Return content for an unmatched document (Document or Unknown)."""
    try:
        return get_unmatched_document_detail(doc_path)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load unmatched document '{doc_path}': {str(e)}")


@app.get("/api/documents/{doc_path:path}")
async def fetch_document_detail(doc_path: str):
    """Return metadata plus file content for a specific document path."""
    try:
        return get_document_detail(doc_path)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load document '{doc_path}': {str(e)}")


@app.put("/api/documents/{doc_path:path}")
async def update_document(doc_path: str, payload: DocumentUpdateRequest):
    """Update document content (and optionally rename) while refreshing embeddings."""
    try:
        updated = update_document_content(doc_path, payload.content, payload.new_name)
        return updated
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except (ValueError, FileExistsError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update document '{doc_path}': {str(e)}")


@app.delete("/api/documents/{doc_path:path}")
async def remove_document(doc_path: str):
    """Delete a document and its derived data."""
    try:
        metadata = delete_document(doc_path)
        return {"deleted": metadata}
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete document '{doc_path}': {str(e)}")


@app.post("/api/documents/{doc_path:path}/move")
async def move_document(doc_path: str, payload: DocumentMoveRequest):
    """Move a document to a new product or accessory owner."""
    try:
        moved = move_document_owner(
            doc_path,
            target_type=payload.target_type,
            product_name=payload.product_name,
            bom_version=payload.bom_version,
            accessory_name=payload.accessory_name,
        )
        return moved
    except (ValueError, FileNotFoundError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to move document '{doc_path}': {str(e)}")


@app.get("/api/files/{file_path:path}")
async def serve_file(file_path: str):
    """Serve stored document/image files from backend directory."""

    resolved = (BACKEND_ROOT / file_path).resolve()
    try:
        resolved.relative_to(BACKEND_ROOT)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid file path")

    if not resolved.exists():
        raise HTTPException(status_code=404, detail=f"File '{file_path}' not found")

    return FileResponse(resolved)


@app.post("/api/poster/analyze_reference")
async def analyze_poster_reference(
    payload: PosterAnalyzeReferenceRequest = Body(...),
):
    payload_image_url = (payload.image_url or "").strip() or None
    if not payload_image_url:
        raise HTTPException(status_code=400, detail="请提供 image_url")

    try:
        return await poster_analyze_reference(
            image_url=payload_image_url,
            prompt_extra=(payload.prompt or None),
            model=(payload.model or None),
            font_candidates=(payload.font_candidates or None),
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"海报参考图分析失败: {exc}") from exc


@app.post("/api/poster/generate_copy")
async def generate_poster_copy(
    payload: PosterGenerateCopyRequest = Body(...),
):
    if not isinstance(payload.step1_result, dict) or not payload.step1_result:
        raise HTTPException(status_code=400, detail="请提供 step1_result")

    try:
        return await poster_generate_copy(
            step1_result=payload.step1_result,
            requirements=(payload.requirements or None),
            target_language=(payload.target_language or None),
            model=(payload.model or None),
            product_name=(payload.product_name or None),
            bom_code=(payload.bom_code or None),
            bom_type=(payload.bom_type or None),
            product_image_url=(payload.product_image_url or None),
            background_image_url=(payload.background_image_url or None),
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"海报文案生成失败: {exc}") from exc


@app.post("/api/poster/generate_image_edit")
async def generate_poster_image_edit_endpoint(
    payload: PosterGenerateImageEditRequest = Body(...),
):
    ref_url = (payload.reference_image_url or "").strip()
    prod_url = (payload.product_image_url or "").strip()
    if not ref_url:
        raise HTTPException(status_code=400, detail="请提供 reference_image_url")
    if not prod_url:
        raise HTTPException(status_code=400, detail="请提供 product_image_url")
    if not isinstance(payload.step1_result, dict) or not payload.step1_result:
        raise HTTPException(status_code=400, detail="请提供 step1_result")

    try:
        W = int(payload.output_width or 0)
    except Exception:
        W = 0
    try:
        H = int(payload.output_height or 0)
    except Exception:
        H = 0

    if W <= 0:
        try:
            W = int(payload.step1_result.get("width") or 0)
        except Exception:
            W = 0
    if H <= 0:
        try:
            H = int(payload.step1_result.get("height") or 0)
        except Exception:
            H = 0
    if W <= 0:
        W = 1000
    if H <= 0:
        H = 1500

    try:
        inputs = PosterImageEditInputs(
            reference_image_url=ref_url,
            product_image_url=prod_url,
            background_image_url=(payload.background_image_url or None),
            step1_result=payload.step1_result,
            product_name=(payload.product_name or None),
            bom_code=(payload.bom_code or None),
            title=str(payload.title or ""),
            subtitle=str(payload.subtitle or ""),
            sellpoints=[str(s or "") for s in (payload.sellpoints or [])],
            output_width=W,
            output_height=H,
            watermark=bool(payload.watermark) if payload.watermark is not None else True,
            negative_prompt=str(payload.negative_prompt or ""),
        )
        return run_poster_image_edit(payload=inputs)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"海报生成失败: {exc}") from exc


@app.post("/api/manual/insert-neo4j")
async def insert_manual_product(payload: InsertProductRequest):
    product_name = (payload.product_name or "").strip()
    if not product_name:
        raise HTTPException(status_code=400, detail="product_name 不能为空")

    provided_documents = [
        doc.dict(exclude_none=True) for doc in (payload.documents or [])
    ]

    session_documents = []
    truth_documents = []
    session_record = None
    if payload.session_id:
        session_record = load_session_record(payload.session_id)
        if session_record:
            session_documents = extract_documents_from_session(session_record)
        truth_documents = extract_truth_documents(payload.session_id)

    combined_documents = provided_documents + session_documents + truth_documents

    if not combined_documents:
        raise HTTPException(
            status_code=400, detail="缺少可插入的文件，请先上传或加载 OCR 结果"
        )

    try:
        result = insert_product_with_documents(
            product_name,
            display_name=payload.display_name,
            bom_code=payload.bom_code,
            session_id=payload.session_id,
            documents=combined_documents,
        )
        return {
            "result": result,
            "session_documents": len(session_documents),
            "provided_documents": len(provided_documents),
            "truth_documents": len(truth_documents),
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"写入 Neo4j 失败：{exc}") from exc


@app.post("/api/manual-sessions")
async def create_manual_session(
    product_name: str = Form(...),
    bom_code: str | None = Form(default=None),
    bom_type: str | None = Form(default=None),
    product_files: List[UploadFile] = File(default_factory=list),
    accessory_files: List[UploadFile] = File(default_factory=list),
):
    try:
        return await create_manual_session_entry(
            product_name,
            bom_code,
            product_files,
            accessory_files,
            bom_type,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Failed to create manual session: {exc}") from exc


@app.post("/api/manual-sessions/init")
async def init_manual_session(payload: ManualSessionInitRequest):
    try:
        return init_manual_session_entry(
            payload.product_name,
            payload.bom_code,
            payload.bom_type,
            material_code=payload.material_code,
            bom_id=payload.bom_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Failed to init manual session: {exc}") from exc


@app.post("/api/manual-sessions/{session_id}/ocr")
async def trigger_manual_session_ocr(session_id: str):
    try:
        return await run_manual_session(session_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Failed to run manual session OCR: {exc}") from exc


@app.post("/api/manual-sessions/{session_id}/uploads")
async def append_manual_session_files(
    session_id: str,
    product_files: List[UploadFile] = File(default_factory=list),
    accessory_files: List[UploadFile] = File(default_factory=list),
):
    """Append uploaded files to an existing manual session without running OCR."""
    try:
        return await append_manual_session_uploads(session_id, product_files, accessory_files)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Failed to append manual session uploads: {exc}") from exc


@app.delete("/api/manual-sessions/{session_id}/uploads")
async def delete_manual_session_file(session_id: str, path: str = Query(...)):
    """Delete one original upload file from a manual session."""
    try:
        return delete_manual_session_upload(session_id, path)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Failed to delete manual session upload: {exc}") from exc


@app.post("/api/manual-sessions/{session_id}/prompt-reverse")
async def trigger_prompt_reverse(session_id: str, payload: dict | None = Body(default=None)):
    user_prompt = None
    if isinstance(payload, dict):
        user_prompt = payload.get("user_prompt") or payload.get("prompt")
    try:
        return await run_prompt_reverse_only(session_id, user_prompt=user_prompt)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Failed to run prompt reverse: {exc}") from exc


@app.get("/api/manual/ocr/history")
async def manual_ocr_history(limit: int = 50):
    safe_limit = max(1, min(limit, 200))
    try:
        history = list_session_records(safe_limit)
        return {"history": history}
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Failed to fetch manual OCR history: {exc}") from exc


@app.get("/api/manual-sessions/{session_id}")
async def get_manual_session(session_id: str):
    record = load_session_record(session_id)
    if not record:
        raise HTTPException(status_code=404, detail="Manual OCR session not found")
    return record


@app.get("/api/manual-sessions/{session_id}/progress")
async def get_manual_session_progress(session_id: str):
    state = progress_manager.get_state(session_id)
    if not state:
        raise HTTPException(status_code=404, detail="Progress not found")
    return state


@app.delete("/api/manual-sessions/{session_id}")
async def delete_manual_session_endpoint(session_id: str):
    try:
        removed = delete_manual_session(session_id)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Failed to delete OCR session: {exc}") from exc

    if not removed:
        raise HTTPException(status_code=404, detail="Manual OCR session not found")

    return {"session_id": session_id, "deleted": True}


@app.delete("/api/manual/ocr/{session_id}")
async def delete_manual_session_legacy(session_id: str):
    """Backward-compatible alias for older frontend clients."""
    return await delete_manual_session_endpoint(session_id)


@app.delete("/api/manual-sessions/history")
async def delete_manual_session_history():
    try:
        removed = clear_manual_history()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Failed to clear manual OCR history: {exc}") from exc

    return {"deleted_sessions": removed}


@app.get("/api/prompt-playbooks")
async def get_prompt_playbooks_endpoint(
    product_names: List[str] | None = Query(default=None),
    playbook_type: str | None = Query(default=None),
):
    try:
        items = list_prompt_playbooks(
            product_names=product_names,
            playbook_type=playbook_type,
        )
        return {"items": items}
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Failed to fetch prompt playbooks: {exc}") from exc


@app.post("/api/prompt-playbooks/ace")
async def run_prompt_playbook_ace(payload: PromptPlaybookAceRequest):
    if not payload.samples:
        raise HTTPException(status_code=400, detail="samples 不能为空")

    if payload.playbook_type not in PROMPT_PLAYBOOK_TYPES:
        raise HTTPException(status_code=400, detail="playbook_type 参数不支持")

    ace_manager = get_ace_manager(payload.playbook_type)

    ace_results: List[dict] = []
    persisted_files: List[str] = []

    dataset_payload: List[Dict[str, Any]] = []

    for sample in payload.samples:
        question_text = (sample.question or get_system_prompt(sample.playbook_type) or "").strip()
        context_text = (sample.context or sample.generate_content or sample.truth_content or "").strip()
        ground_truth_text = (sample.ground_truth or sample.truth_content or sample.generate_content or "").strip()
        if not context_text and not ground_truth_text:
            continue

        dataset_payload.append(
            {
                "product_name": sample.product_name,
                "folder_name": sample.folder_name,
                "playbook_type": sample.playbook_type,
                "question": question_text,
                "context": context_text,
                "ground_truth": ground_truth_text,
                "source_files": sample.source_files or [],
            }
        )

        persisted = persist_ace_dataset(
            folder_name=sample.folder_name,
            playbook_type=sample.playbook_type,
            samples=[dataset_payload[-1]],
        )
        if persisted:
            persisted_files.append(persisted.as_posix())

        try:
            if sample.playbook_type == "spec":
                specsheet_data, _chunks_unused, _prompt_text_unused, _system_prompt_unused = _extract_specsheet_from_context(
                    context_text,
                    chunks=None,
                    title_hint=sample.product_name,
                    multimodal_segments=None,
                    llm_provider="dashscope",
                    llm_model="dashscope/qwen3-max",
                )
                prediction_text = json.dumps(specsheet_data.dict(), ensure_ascii=False, indent=2)

                algo_eval = evaluate_specsheet(prediction_text, ground_truth_text)
                if algo_eval.is_correct:
                    response = ace_manager.store_external_result(
                        question=question_text or f"优化 {sample.product_name} 的 {sample.playbook_type} 提示词",
                        prediction=prediction_text,
                        ground_truth=ground_truth_text,
                        is_correct=True,
                        algo_evaluation=algo_eval.to_dict(),
                    )
                    response.setdefault("reflection", {})["algo_evaluation"] = algo_eval.to_dict()
                    response["correct"] = True
                    response["skipped_llm_reflection"] = True
                else:
                    response = ace_manager.adapt_with_prediction(
                        question=question_text or f"优化 {sample.product_name} 的 {sample.playbook_type} 提示词",
                        context=context_text,
                        prediction=prediction_text,
                        ground_truth=ground_truth_text,
                        verbose=False,
                    )
                    # Ensure metrics.json correctness/accuracy reflects deterministic evaluator
                    try:
                        ace_manager.force_last_metrics_correctness(False)
                        ace_manager.attach_last_algo_evaluation(algo_eval.to_dict())
                    except Exception:
                        pass
                    response.setdefault("reflection", {})["algo_evaluation"] = algo_eval.to_dict()
                    response["reflection"]["is_correct"] = False
                    response["correct"] = False
            else:
                response = ace_manager.adapt_single_sample(
                    question=question_text or f"优化 {sample.product_name} 的 {sample.playbook_type} 提示词",
                    context=context_text,
                    ground_truth=ground_truth_text,
                    verbose=False,
                )
            ace_results.append(response)
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=500, detail=f"ACE 运行失败: {exc}") from exc

    if not ace_results:
        raise HTTPException(status_code=400, detail="未找到可用于 ACE 的样本")

    snapshot_rules = ace_manager.get_playbook_snapshot()
    custom_rules = [rule.strip() for rule in (payload.custom_rules or []) if rule and rule.strip()]

    named_path = persist_named_dataset(
        dataset_name=payload.dataset_name or f"dataset_{payload.playbook_type}",
        playbook_type=payload.playbook_type,
        samples=dataset_payload,
        description=payload.description,
        global_rules=snapshot_rules,
        custom_rules=[{"content": rule} for rule in custom_rules],
    )

    relative_dataset_path = None
    if named_path:
        try:
            relative_dataset_path = named_path.resolve().relative_to(BACKEND_ROOT.resolve()).as_posix()
        except ValueError:
            relative_dataset_path = named_path.as_posix()

    return {
        "processed_samples": len(ace_results),
        "persisted_files": persisted_files,
        "named_dataset": named_path.as_posix() if named_path else None,
        "named_dataset_relative": relative_dataset_path,
        "ace_results": ace_results,
        "global_rules": snapshot_rules,
        "custom_rules": [
            {"content": rule}
            for rule in custom_rules
        ],
    }


@app.get("/api/prompt-playbooks/datasets")
async def list_prompt_playbook_datasets(limit: int = 20):
    try:
        datasets = list_saved_datasets(limit)
        return {"datasets": datasets}
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Failed to fetch ACE datasets: {exc}") from exc


@app.delete("/api/prompt-playbooks/datasets")
async def delete_prompt_playbook_dataset(payload: PromptPlaybookDatasetDeleteRequest):
    if not payload.file_path:
        raise HTTPException(status_code=400, detail="file_path 不能为空")
    try:
        deleted = delete_saved_dataset(payload.file_path)
    except ValueError as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not deleted:
        raise HTTPException(status_code=404, detail="未找到指定的数据集文件")

    return {"deleted": True}


@app.get("/api/prompt-playbooks/rules")
async def get_prompt_playbook_rules(limit: int | None = None, playbook_type: str = "spec"):
    try:
        rules = get_playbook_rules(limit, playbook_type=playbook_type)
        return {"rules": rules}
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Failed to fetch prompt playbook rules: {exc}") from exc


@app.delete("/api/prompt-playbooks/rules/{rule_id}")
async def delete_prompt_playbook_rule(rule_id: str, playbook_type: str = "spec"):
    if not rule_id:
        raise HTTPException(status_code=400, detail="rule_id 不能为空")

    removed = delete_playbook_rule(rule_id, playbook_type=playbook_type)
    if not removed:
        raise HTTPException(status_code=404, detail="未找到对应规则或删除失败")

    return {"deleted": True}


@app.post("/api/specsheet/from_ocr_docs", response_model=SpecsheetWithChunksResponse)
async def generate_specsheet_from_ocr(payload: SpecsheetFromOcrRequest):
    if not payload.documents and not (payload.bom_code and payload.bom_code.strip()):
        raise HTTPException(status_code=400, detail="请至少提供一个 OCR 文档，或提供 bom_code")

    try:
        specsheet_data, chunks, prompt_text, system_prompt, context_text = generate_specsheet_from_ocr_request(payload)
        try:
            _persist_generated_specsheet(specsheet_data, payload)
        except Exception as exc:  # noqa: BLE001
            print(f"[Specsheet] Failed to persist generated specsheet: {exc}")
        try:
            product_dir = _resolve_manual_product_dir(
                payload.product_name or specsheet_data.productTitle,
                payload.bom_code,
            )
            _write_prompt_snapshot_files(
                product_dir,
                "spec",
                system_prompt,
                prompt_text,
            )
        except Exception as exc:  # noqa: BLE001
            print(f"[PromptSnapshot] Skipped writing spec prompts: {exc}")
        if payload.session_id:
            try:
                question = (
                    specsheet_data.productTitle
                    or payload.product_name
                    or f"{payload.session_id} 规格页"
                )
                save_pending_sample(
                    payload.session_id,
                    payload.bom_code,
                    question=question,
                    context=context_text,
                    prediction=specsheet_data.dict(),
                )
            except Exception as exc:  # noqa: BLE001
                print(f"[ACE] Failed to persist pending sample: {exc}")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Failed to generate specsheet from OCR docs: {exc}") from exc

    chunk_models = [ChunkInfo(**chunk) for chunk in chunks]
    return SpecsheetWithChunksResponse(
        specsheet=specsheet_data,
        chunks=chunk_models,
        prompt_text=prompt_text,
        system_prompt=system_prompt,
    )

@app.post(
    "/api/manual/book/from_ocr_docs",
    response_model=ManualBookResponse,
    response_model_exclude_none=True,
)
async def generate_manual_book_from_ocr(payload: ManualBookFromOcrRequest):
    """Generate manual/instruction book from OCR docs using LLM with dedicated prompt."""
    try:
        manual_book, user_prompt = run_manual_book_from_ocr(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"生成说明书失败: {exc}") from exc

    if payload.product_name and payload.bom_code:
        try:
            product_dir = _resolve_manual_product_dir(payload.product_name, payload.bom_code)
            _write_prompt_snapshot_files(
                product_dir,
                "manual",
                MANUAL_BOOK_SYSTEM_PROMPT,
                user_prompt,
            )
        except Exception as exc:  # noqa: BLE001
            print(f"[PromptSnapshot] Skipped writing manual prompts: {exc}")

    return ManualBookResponse(
        manual_book=manual_book,
        prompt_text=user_prompt,
        system_prompt=MANUAL_BOOK_SYSTEM_PROMPT,
    )


@app.post(
    "/api/manual/book/variant_plan",
    response_model=ManualBookVariantPlanResponse,
    response_model_exclude_none=True,
)
async def plan_manual_book_variants(payload: ManualBookVariantPlanRequest):
    """Plan which A/B/C template variant to use for each section group, and generate pages only when uncertain."""
    try:
        variants, generated_pages, user_prompt = plan_manual_variants_from_context(payload)
        try:
            if payload.product_name and payload.bom_code:
                product_dir = _resolve_manual_product_dir(payload.product_name, payload.bom_code)
                question_path = product_dir / "question_manual.txt"
                context_path = product_dir / "context_manual.txt"
                question_text = (
                    "# VARIANT_PLAN_SYSTEM_PROMPT\n"
                    + (MANUAL_VARIANT_PLAN_SYSTEM_PROMPT or "")
                    + "\n\n# MANUAL_BOOK_SYSTEM_PROMPT\n"
                    + (MANUAL_BOOK_SYSTEM_PROMPT or "")
                    + "\n"
                )
                question_path.write_text(question_text, encoding="utf-8")
                context_path.write_text(user_prompt or "", encoding="utf-8")
        except Exception as exc:  # noqa: BLE001
            print(f"[ManualBook] Skipped writing manual prompt snapshots: {exc}")
        return ManualBookVariantPlanResponse(
            variants=variants,
            generated_pages=generated_pages,
            prompt_text=user_prompt,
            system_prompt=MANUAL_VARIANT_PLAN_SYSTEM_PROMPT,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"生成说明书版本规划失败: {exc}") from exc


@app.post(
    "/api/manual/book/one_shot",
    response_model=ManualBookOneShotResponse,
    response_model_exclude_none=True,
)
async def generate_manual_book_one_shot(payload: ManualBookOneShotRequest):
    """One-shot: single LLM call to decide variants (A/B/C) + generate fixed non-variant pages."""
    try:
        variants, fixed_pages, user_prompt = generate_manual_one_shot(payload)

        try:
            cover = fixed_pages.get("Cover") if isinstance(fixed_pages, dict) else None
            if cover is not None:
                blocks = getattr(cover, "blocks", None) or []
                for blk in blocks:
                    if isinstance(blk, dict):
                        if blk.get("type") == "cover":
                            blk.pop("model", None)
                    else:
                        if getattr(blk, "type", None) == "cover":
                            try:
                                if getattr(blk, "model", None) is not None:
                                    delattr(blk, "model")
                            except Exception:
                                pass
        except Exception:
            pass
        try:
            if payload.product_name and payload.bom_code:
                product_dir = _resolve_manual_product_dir(payload.product_name, payload.bom_code)
                question_path = product_dir / "question_manual.txt"
                context_path = product_dir / "context_manual.txt"
                question_text = "# MANUAL_ONE_SHOT_SYSTEM_PROMPT\n" + (MANUAL_ONE_SHOT_SYSTEM_PROMPT or "") + "\n"
                question_path.write_text(question_text, encoding="utf-8")
                context_path.write_text(user_prompt or "", encoding="utf-8")
        except Exception as exc:  # noqa: BLE001
            print(f"[ManualBook] Skipped writing one-shot manual prompt snapshots: {exc}")

        return ManualBookOneShotResponse(
            variants=variants,
            fixed_pages=fixed_pages,
            prompt_text=user_prompt,
            system_prompt=MANUAL_ONE_SHOT_SYSTEM_PROMPT,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"one-shot 生成说明书失败: {exc}") from exc


def _sanitize_manual_folder_component(value: str | None) -> str:
    v = (value or "").strip()
    if not v:
        return ""
    v = v.replace("/", "_").replace("\\", "_")
    v = re.sub(r"\s+", "_", v)
    v = re.sub(r"[^A-Za-z0-9_.\-\u4e00-\u9fff]", "_", v)
    v = re.sub(r"_+", "_", v).strip("_")
    return v


def _persist_generated_specsheet(specsheet_data: SpecsheetData, payload: SpecsheetFromOcrRequest) -> Path:
    product_part = _sanitize_manual_folder_component(payload.product_name or specsheet_data.productTitle)
    bom_part = _sanitize_manual_folder_component(payload.bom_code)
    if not product_part or not bom_part:
        raise ValueError("product_name 和 bom_code 不能为空")

    base_dir = Path(__file__).resolve().parent / "manual_ocr_results"
    product_dir = base_dir / f"{product_part}_{bom_part}"
    if not product_dir.exists() or not product_dir.is_dir():
        raise FileNotFoundError(f"manual_ocr_results 产品目录不存在: {product_dir}")

    truth_dir = product_dir / "truth"
    truth_dir.mkdir(parents=True, exist_ok=True)
    target_path = truth_dir / "specsheet.json"
    target_path.write_text(
        json.dumps(specsheet_data.dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    try:
        rel = target_path.resolve().relative_to(BACKEND_ROOT.resolve()).as_posix()
        product_id = f"{(payload.product_name or '').strip()}_{(payload.bom_code or '').strip()}".strip("_")
        if product_id:
            upsert_product_has_doc(
                product_id=product_id,
                role="specsheet",
                doc_path=rel,
                name=target_path.name,
                mime_type="application/json",
                doc_kind="specsheet",
            )
    except Exception as exc:  # noqa: BLE001
        print(f"[Specsheet] Failed to bind HAS_DOC for specsheet: {exc}")
    print(f"[Specsheet] specsheet saved to: {target_path}")
    return target_path


@app.get(
    "/api/manual/book/saved",
    response_model=ManualBookResponse,
    response_model_exclude_none=True,
)
async def get_saved_manual_book(product_name: str, bom_code: str):
    target_dir = _resolve_manual_product_dir(product_name, bom_code)
    truth_path = target_dir / "truth" / "manual_book.json"
    generate_path = target_dir / "generate" / "manual_book.json"
    target_path = generate_path if generate_path.exists() else truth_path
    if not target_path.exists():
        raise HTTPException(status_code=404, detail="未找到已保存的说明书文件")

    try:
        raw = json.loads(target_path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"读取说明书文件失败: {exc}") from exc

    if not isinstance(raw, list):
        raise HTTPException(status_code=500, detail="说明书文件格式错误：不是数组")

    pages = [ManualBookData(**p) for p in raw if isinstance(p, dict)]
    if not pages:
        raise HTTPException(status_code=500, detail="说明书文件为空或格式错误")

    return ManualBookResponse(manual_book=pages)


@app.get("/api/manual/specsheet/saved", response_model=SpecsheetResponse)
async def get_saved_manual_specsheet(product_name: str, bom_code: str):
    base_product_dir = _resolve_manual_product_dir(product_name, bom_code)
    truth_path = base_product_dir / "truth" / "specsheet.json"
    generate_path = base_product_dir / "generate" / "specsheet.json"
    target_path = truth_path if truth_path.exists() else generate_path
    if not target_path.exists():
        raise HTTPException(status_code=404, detail="未找到已保存的规格页文件")

    try:
        raw = json.loads(target_path.read_text(encoding="utf-8"))
        specsheet = SpecsheetData(**raw)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"读取规格页文件失败: {exc}") from exc

    return SpecsheetResponse(specsheet=specsheet)


class ManualSpecsheetLayoutResponse(BaseModel):
    layout: Dict[str, Any]


class ManualSpecsheetLayoutSaveRequest(BaseModel):
    product_name: str
    bom_code: str
    layout: Dict[str, Any] = Field(default_factory=dict)
    updated_by: Optional[str] = None


@app.get("/api/manual/specsheet/layout", response_model=ManualSpecsheetLayoutResponse)
async def get_manual_specsheet_layout(product_name: str, bom_code: str):
    base_product_dir = _resolve_manual_product_dir(product_name, bom_code)
    truth_path = base_product_dir / "truth" / "specsheet.layout.json"
    if not truth_path.exists():
        raise HTTPException(status_code=404, detail="未找到已保存的规格页布局文件")

    try:
        raw = json.loads(truth_path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"读取规格页布局文件失败: {exc}") from exc

    if not isinstance(raw, dict):
        raise HTTPException(status_code=500, detail="规格页布局文件格式错误：不是对象")

    return ManualSpecsheetLayoutResponse(layout=raw)


@app.post("/api/manual/specsheet/layout", response_model=ManualSpecsheetLayoutResponse)
async def save_manual_specsheet_layout(payload: ManualSpecsheetLayoutSaveRequest):
    try:
        product_dir = _resolve_manual_product_dir(payload.product_name, payload.bom_code)
        truth_dir = product_dir / "truth"
        truth_dir.mkdir(parents=True, exist_ok=True)

        target_path = truth_dir / "specsheet.layout.json"
        layout_obj: Dict[str, Any] = payload.layout if isinstance(payload.layout, dict) else {}
        layout_obj = dict(layout_obj)
        layout_obj["updated_at"] = int(time.time())
        if payload.updated_by is not None:
            layout_obj["updated_by"] = str(payload.updated_by)

        target_path.write_text(
            json.dumps(layout_obj, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"[SpecsheetLayout] truth saved to: {target_path}")
        return ManualSpecsheetLayoutResponse(layout=layout_obj)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"保存规格页布局 truth 失败: {exc}") from exc


class ManualBookTruthSaveRequest(BaseModel):
    product_name: str
    bom_code: str
    manual_book: List[ManualBookData]
    target_folder: Literal["truth", "generate"] = "truth"


class ManualBookVariantsPayload(BaseModel):
    product_name: str
    bom_code: str
    variants: Dict[str, str] = Field(default_factory=dict)


class ManualSpecsheetTruthSaveRequest(BaseModel):
    product_name: str
    bom_code: str
    specsheet: SpecsheetData


def _resolve_manual_product_dir(product_name: str, bom_code: str) -> Path:
    product_part = _sanitize_manual_folder_component(product_name)
    bom_part = _sanitize_manual_folder_component(bom_code)
    if not product_part or not bom_part:
        raise ValueError("product_name 和 bom_code 不能为空")
    base_dir = Path(__file__).resolve().parent / "manual_ocr_results"
    product_dir = base_dir / f"{product_part}_{bom_part}"
    if not product_dir.exists() or not product_dir.is_dir():
        raise FileNotFoundError(f"manual_ocr_results 产品目录不存在: {product_dir}")
    return product_dir


@app.post(
    "/api/manual/book/truth",
    response_model=ManualBookResponse,
    response_model_exclude_none=True,
)
async def save_manual_book_truth(payload: ManualBookTruthSaveRequest):
    try:
        product_dir = _resolve_manual_product_dir(payload.product_name, payload.bom_code)
        folder = (payload.target_folder or "truth").strip() or "truth"
        if folder not in {"truth", "generate"}:
            raise ValueError("target_folder 仅支持 truth 或 generate")
        target_dir = product_dir / folder
        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = target_dir / "manual_book.json"
        target_path.write_text(
            json.dumps([p.dict(exclude_none=True) for p in payload.manual_book], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        if folder == "truth":
            rel = target_path.resolve().relative_to(BACKEND_ROOT.resolve()).as_posix()
            product_id = f"{payload.product_name.strip()}_{payload.bom_code.strip()}".strip("_")
            upsert_product_has_doc(
                product_id=product_id,
                role="manual",
                doc_path=rel,
                name=target_path.name,
                mime_type="application/json",
                doc_kind="manual_book",
            )
            print(f"[ManualBook] truth saved to: {target_path}")
        else:
            print(f"[ManualBook] generate saved to: {target_path}")
        return ManualBookResponse(manual_book=payload.manual_book)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"保存说明书 truth 失败: {exc}") from exc


@app.get("/api/manual/book/variants")
async def get_manual_book_variants(product_name: str, bom_code: str):
    try:
        product_dir = _resolve_manual_product_dir(product_name, bom_code)
        truth_path = product_dir / "truth" / "manual_variants.json"
        if not truth_path.exists():
            raise HTTPException(status_code=404, detail="未找到已保存的说明书版本配置")
        raw = json.loads(truth_path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise HTTPException(status_code=500, detail="说明书版本配置文件格式错误：不是对象")
        variants = raw.get("variants") if isinstance(raw.get("variants"), dict) else raw
        if not isinstance(variants, dict):
            raise HTTPException(status_code=500, detail="说明书版本配置格式错误")
        # Ensure all values are strings
        normalized = {str(k): str(v) for k, v in variants.items()}
        return {"variants": normalized}
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"读取说明书版本配置失败: {exc}") from exc


@app.post("/api/manual/book/variants")
async def save_manual_book_variants(payload: ManualBookVariantsPayload):
    try:
        product_dir = _resolve_manual_product_dir(payload.product_name, payload.bom_code)
        truth_dir = product_dir / "truth"
        truth_dir.mkdir(parents=True, exist_ok=True)
        target_path = truth_dir / "manual_variants.json"
        target_path.write_text(
            json.dumps({"variants": payload.variants}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return {"variants": payload.variants}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"保存说明书版本配置失败: {exc}") from exc


@app.post("/api/manual/specsheet/truth", response_model=SpecsheetResponse)
async def save_manual_specsheet_truth(payload: ManualSpecsheetTruthSaveRequest):
    try:
        product_dir = _resolve_manual_product_dir(payload.product_name, payload.bom_code)
        truth_dir = product_dir / "truth"
        truth_dir.mkdir(parents=True, exist_ok=True)
        target_path = truth_dir / "specsheet.json"
        target_path.write_text(
            json.dumps(payload.specsheet.dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        rel = target_path.resolve().relative_to(BACKEND_ROOT.resolve()).as_posix()
        product_id = f"{payload.product_name.strip()}_{payload.bom_code.strip()}".strip("_")
        upsert_product_has_doc(
            product_id=product_id,
            role="specsheet",
            doc_path=rel,
            name=target_path.name,
            mime_type="application/json",
            doc_kind="specsheet",
        )
        print(f"[Specsheet] truth saved to: {target_path}")
        return SpecsheetResponse(specsheet=payload.specsheet)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"保存规格页 truth 失败: {exc}") from exc


@app.get("/api/manual/specsheet/{session_id}", response_model=SpecsheetResponse)
async def get_manual_specsheet(session_id: str, bom_code: str | None = None):
    specsheet = load_specsheet_for_session(session_id, bom_code)
    if not specsheet:
        raise HTTPException(status_code=404, detail="未找到该会话的规格页文件")
    return SpecsheetResponse(specsheet=specsheet)


@app.post("/api/manual/specsheet/{session_id}", response_model=SpecsheetResponse)
async def save_manual_specsheet(session_id: str, payload: ManualSpecsheetSaveRequest):
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id 不能为空")
    try:
        saved = save_specsheet_for_session(
            session_id,
            payload.specsheet,
            bom_code=payload.bom_code,
        )
        return SpecsheetResponse(specsheet=saved)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"保存规格页失败: {exc}") from exc


@app.post("/api/manual/specsheet/{session_id}/ace")
async def run_manual_specsheet_ace(session_id: str, payload: ManualSpecsheetAceRequest):
    resolved_session = payload.session_id or session_id
    if not resolved_session:
        raise HTTPException(status_code=400, detail="session_id 不能为空")

    def _load_specsheet_json(path: Path) -> SpecsheetData | None:
        try:
            if not path.exists():
                return None
            raw = json.loads(path.read_text(encoding="utf-8"))
            return SpecsheetData(**raw)
        except Exception:
            return None

    base_dir = Path(__file__).resolve().parent / "manual_ocr_results"
    base_session_dir = base_dir / _sanitize_manual_folder_component(resolved_session)
    truth_path = base_session_dir / "truth" / "specsheet.json"
    generate_path = base_session_dir / "generate" / "specsheet.json"

    ground_truth_obj = payload.ground_truth
    if not ground_truth_obj:
        ground_truth_obj = _load_specsheet_json(truth_path)
    if not ground_truth_obj:
        raise HTTPException(status_code=404, detail="未找到可用于 ACE 的规格页 GT（truth/specsheet.json）")

    prediction_specsheet = _load_specsheet_json(generate_path)

    pending_sample = load_pending_sample(resolved_session, payload.bom_code)

    if pending_sample:
        prediction_payload = pending_sample.get("prediction") or {}
        question = pending_sample.get("question") or f"{resolved_session} 规格页"
        context = pending_sample.get("context") or ""
    else:
        if not prediction_specsheet:
            # legacy: session-local specsheet.json (manual_ocr_results/<session>/specsheet*.json)
            prediction_specsheet = load_specsheet_for_session(resolved_session, payload.bom_code)
        if not prediction_specsheet:
            raise HTTPException(status_code=404, detail="未找到可用于 ACE 的 prediction（generate/specsheet.json）")

        prediction_payload = prediction_specsheet.dict()
        question = (
            ground_truth_obj.productTitle
            or prediction_specsheet.productTitle
            or f"{resolved_session} 规格页"
        )
        context = ""

    try:
        prediction_text = json.dumps(prediction_payload, ensure_ascii=False)
        ground_truth_text = json.dumps(ground_truth_obj.dict(), ensure_ascii=False)
        result = ace_manager.adapt_with_prediction(
            question=question,
            context=context,
            prediction=prediction_text,
            ground_truth=ground_truth_text,
            verbose=False,
        )
        store_ace_sample(
            resolved_session,
            payload.bom_code,
            {
                "question": question,
                "context": context,
                "prediction": prediction_payload,
                "ground_truth": ground_truth_obj.dict(),
                "result": result,
            },
        )
        clear_pending_sample(resolved_session, payload.bom_code)
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"ACE 训练失败: {exc}") from exc

    return {
        "session_id": resolved_session,
        "bom_code": payload.bom_code,
        "result": result,
        "playbook_size": ace_manager.get_playbook_size(),
        "playbook_snapshot": ace_manager.get_playbook_snapshot(limit=10),
    }


@app.post("/api/bom/from_ocr_docs", response_model=BomGenerationResponse)
async def generate_bom_from_ocr(payload: BomGenerationRequest):
    if not payload.documents:
        raise HTTPException(status_code=400, detail="请至少提供一个 OCR 文档")

    if payload.bom_type not in {"outdoor", "pool"}:
        raise HTTPException(status_code=400, detail="bomType 仅支持 outdoor / pool")

    try:
        response = generate_bom_from_ocr_request(payload)
        return response
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate BOM from OCR docs: {exc}",
        ) from exc


@app.post("/api/bom/save", response_model=BomSaveResponse)
async def save_bom(payload: BomSaveRequest):
    code = payload.code.strip()
    if not code:
        raise HTTPException(status_code=400, detail="BOM 编码不能为空")

    try:
        save_result = save_bom_code_to_file(
            code=code,
            product_name=payload.product_name,
            bom_type=payload.bom_type,
            session_id=payload.session_id,
            selections=payload.selections,
            segments=[segment.dict() for segment in payload.segments] if payload.segments else None,
        )
        return BomSaveResponse(**save_result)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=500,
            detail=f"Failed to save BOM code: {exc}",
        ) from exc


@app.get("/api/bom/session/{session_id}", response_model=BomSaveResponse)
async def get_bom_by_session(session_id: str):
    if not session_id:
        raise HTTPException(status_code=400, detail="Session ID 不能为空")

    saved = load_bom_code_for_session(session_id)
    if not saved:
        raise HTTPException(status_code=404, detail="未找到对应会话的 BOM")

    return BomSaveResponse(**saved)
@app.get("/api/products/{product_name}/boms/{bom_version}/specsheet", response_model=SpecsheetResponse)
async def get_product_specsheet(product_name: str, bom_version: str):
    """
    Get specsheet content for a product and BOM version using RAG.
    
    Args:
        product_name: Product English name
        bom_version: BOM version
        
    Returns:
        SpecsheetResponse with specsheet data
    """
    try:
        specsheet_data = get_specsheet_by_product_bom(product_name, bom_version)
        return SpecsheetResponse(specsheet=specsheet_data)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch specsheet for product '{product_name}' BOM '{bom_version}': {str(e)}"
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)


from __future__ import annotations

from typing import Dict, List, Optional
from pydantic import BaseModel, Field

from src.specsheet_models import SpecsheetOcrDocument


class BomChildField(BaseModel):
    key: str
    label: str
    digits: int = Field(..., ge=0)
    options: Optional[Dict[str, str]] = None


class BomSection(BaseModel):
    key: str
    label: str
    digits: Optional[int] = Field(None, ge=0)
    options: Optional[Dict[str, str]] = None
    children: Optional[List[BomChildField]] = None


class BomGenerationRequest(BaseModel):
    bom_type: str = Field(..., alias="bomType", description="可选：outdoor / pool")
    documents: List[SpecsheetOcrDocument] = Field(default_factory=list)
    sections: List[BomSection] = Field(default_factory=list)

    class Config:
        validate_by_name = True


class BomLlmSegment(BaseModel):
    key: str = Field(..., description="BOM 段位 key（例如 shellColor）")
    value: str = Field(..., description="22 位编码中的子段编码")
    reason: Optional[str] = Field(None, description="LLM 对该编码的依据说明")


class BomLlmResult(BaseModel):
    segments: List[BomLlmSegment] = Field(..., min_items=1, description="LLM 推测到的所有段位编码")


class BomSelection(BaseModel):
    key: str
    label: str
    value: str
    meaning: Optional[str] = None
    digits: Optional[int] = None
    reason: Optional[str] = None


class BomGenerationResponse(BaseModel):
    type: str
    selections: Dict[str, str] = Field(default_factory=dict)
    segments: List[BomSelection] = Field(default_factory=list)


class BomSaveRequest(BaseModel):
    code: str = Field(..., min_length=1, max_length=64, description="完整的 BOM 编码（通常 22 位）")
    product_name: Optional[str] = Field(None, alias="productName")
    bom_type: Optional[str] = Field(None, alias="bomType")
    session_id: Optional[str] = Field(None, alias="sessionId")
    selections: Dict[str, str] = Field(default_factory=dict)
    segments: List[BomSelection] = Field(default_factory=list)

    class Config:
        validate_by_name = True


class BomSaveResponse(BaseModel):
    code: str
    product_name: Optional[str] = Field(None, alias="productName")
    bom_type: Optional[str] = Field(None, alias="bomType")
    session_id: Optional[str] = Field(None, alias="sessionId")
    saved_at: str = Field(..., alias="savedAt")
    selections: Dict[str, str] = Field(default_factory=dict)
    segments: List[BomSelection] = Field(default_factory=list)
    path: str
    absolute_path: str = Field(..., alias="absolutePath")

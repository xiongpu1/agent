"""
Capsule 生成器
从文件生成 summary + keyphrases
适配 spa_classify.py 的功能
"""
import os
from pathlib import Path
from typing import Dict, Any, Optional

# 导入 spa_classify 的核心函数
try:
    from spa_classify import (
        _vision_capsule,
        _text_capsule,
        _to_data_url_for_image,
        _read_excel_snippet,
        _read_text_snippet,
        _read_pdf_excerpt_and_image,
        _read_docx_snippet,
        _extract_first_docx_image_data_url,
    )
except ImportError:
    # 如果直接导入失败，尝试从 src 导入
    try:
        from src.spa_classify import (
            _vision_capsule,
            _text_capsule,
            _to_data_url_for_image,
            _read_excel_snippet,
            _read_text_snippet,
            _read_pdf_excerpt_and_image,
            _read_docx_snippet,
            _extract_first_docx_image_data_url,
        )
    except ImportError as e:
        raise ImportError(f"无法导入 spa_classify 模块: {e}")


class CapsuleGenerator:
    """Capsule 生成器"""
    
    def __init__(
        self,
        vision_model: Optional[str] = None,
        text_model: Optional[str] = None,
        max_chars: int = 4000,
        max_image_bytes: int = 20_000_000,  # 提高到 20MB，会自动压缩
        pdf_max_pages: int = 3,
        pdf_lang: str = "chi_sim+eng",
        excel_nrows: int = 20
    ):
        """
        初始化生成器
        
        Args:
            vision_model: 视觉模型名称
            text_model: 文本模型名称
            max_chars: 文本摘录最大字符数
            max_image_bytes: 图片最大字节数
            pdf_max_pages: PDF最大页数
            pdf_lang: PDF OCR语言
            excel_nrows: Excel读取行数
        """
        self.vision_model = vision_model
        self.text_model = text_model
        self.max_chars = max_chars
        self.max_image_bytes = max_image_bytes
        self.pdf_max_pages = pdf_max_pages
        self.pdf_lang = pdf_lang
        self.excel_nrows = excel_nrows
    
    def _get_file_kind(self, extension: str) -> str:
        """获取文件类型"""
        ext = extension.lower()
        
        if ext in {'.png', '.jpg', '.jpeg', '.bmp', '.gif', '.tif', '.tiff', '.webp', '.jfif', '.pjpeg', '.pjp'}:
            return 'image'
        elif ext in {'.xlsx', '.xls'}:
            return 'excel'
        elif ext in {'.md', '.markdown', '.txt', '.json'}:
            return 'text'
        elif ext in {'.pdf'}:
            return 'pdf'
        elif ext in {'.docx', '.doc'}:
            return 'docx'
        else:
            return 'unknown'
    
    def _get_modality(self, kind: str) -> str:
        """获取模态类型"""
        if kind == 'image':
            return 'image'
        elif kind == 'excel':
            return 'table'
        else:
            return 'document'
    
    def generate_from_file(
        self,
        file_path: Path,
        file_name: str,
        extension: str,
        size: int,
        mtime: float = 0.0,
        rel_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        从文件生成 capsule
        
        Args:
            file_path: 文件路径
            file_name: 文件名
            extension: 文件扩展名
            size: 文件大小
            mtime: 修改时间
            rel_path: 相对路径
            
        Returns:
            capsule 字典，包含 summary, keyphrases, confidence_read, modality, kind
        """
        kind = self._get_file_kind(extension)
        modality = self._get_modality(kind)
        
        # 构建元信息
        meta = {
            "rel_path": rel_path or file_name,
            "file_name": file_name,
            "ext": extension,
            "size": size,
            "mtime": mtime,
        }
        
        capsule: Dict[str, Any] = {}
        
        try:
            if kind == 'image':
                # 图片文件
                data_url = _to_data_url_for_image(file_path, max_bytes=self.max_image_bytes)
                if data_url is None:
                    capsule = {
                        "summary": "图片过大或读取失败，未生成视觉摘要。",
                        "keyphrases": [],
                        "confidence_read": 0.0
                    }
                else:
                    capsule = _vision_capsule(
                        data_url=data_url,
                        model=self.vision_model,
                        meta=meta
                    )
            
            elif kind == 'excel':
                # Excel 文件
                excerpt = _read_excel_snippet(
                    file_path,
                    max_chars=self.max_chars,
                    nrows=self.excel_nrows
                )
                capsule = _text_capsule(
                    kind=kind,
                    excerpt=excerpt,
                    model=self.text_model,
                    meta=meta
                )
            
            elif kind == 'text':
                # 文本文件
                excerpt = _read_text_snippet(file_path, max_chars=self.max_chars)
                capsule = _text_capsule(
                    kind=kind,
                    excerpt=excerpt,
                    model=self.text_model,
                    meta=meta
                )
            
            elif kind == 'pdf':
                # PDF 文件
                excerpt, first_image = _read_pdf_excerpt_and_image(
                    file_path,
                    max_chars=self.max_chars,
                    max_pages=self.pdf_max_pages,
                    lang=self.pdf_lang,
                    max_image_bytes=self.max_image_bytes,
                )
                
                if (excerpt or "").strip():
                    capsule = _text_capsule(
                        kind=kind,
                        excerpt=excerpt,
                        model=self.text_model,
                        meta=meta
                    )
                elif (first_image or "").strip():
                    capsule = _vision_capsule(
                        data_url=str(first_image),
                        model=self.vision_model,
                        meta=meta
                    )
                else:
                    capsule = {
                        "summary": "PDF内容抽取失败或为空，未生成内容摘要。",
                        "keyphrases": [],
                        "confidence_read": 0.0
                    }
            
            elif kind == 'docx':
                # DOCX 文件
                excerpt = _read_docx_snippet(file_path, max_chars=self.max_chars)
                if (excerpt or "").strip():
                    capsule = _text_capsule(
                        kind=kind,
                        excerpt=excerpt,
                        model=self.text_model,
                        meta=meta
                    )
                else:
                    img = _extract_first_docx_image_data_url(
                        file_path,
                        max_bytes=self.max_image_bytes
                    )
                    if (img or "").strip():
                        capsule = _vision_capsule(
                            data_url=str(img),
                            model=self.vision_model,
                            meta=meta
                        )
                    else:
                        capsule = {
                            "summary": "DOCX内容抽取失败或为空，未生成内容摘要。",
                            "keyphrases": [],
                            "confidence_read": 0.0
                        }
            
            else:
                capsule = {
                    "summary": f"暂不支持的文件类型: {extension}",
                    "keyphrases": [],
                    "confidence_read": 0.0
                }
        
        except Exception as e:
            capsule = {
                "summary": f"生成 capsule 时出错: {str(e)}",
                "keyphrases": [],
                "confidence_read": 0.0
            }
        
        # 添加 modality 和 kind 信息
        capsule['modality'] = modality
        capsule['kind'] = kind
        
        return capsule


if __name__ == "__main__":
    pass


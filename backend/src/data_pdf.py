# Copyright (c) Opendatalab. All rights reserved.
import os
import base64
import re
from pathlib import Path

from loguru import logger

from mineru.cli.common import convert_pdf_bytes_to_bytes_by_pypdfium2, read_fn
from mineru.utils.enum_class import MakeMode
from mineru.backend.vlm.vlm_analyze import doc_analyze as vlm_doc_analyze
from mineru.backend.pipeline.pipeline_analyze import doc_analyze as pipeline_doc_analyze
from mineru.backend.pipeline.pipeline_middle_json_mkcontent import union_make as pipeline_union_make
from mineru.backend.pipeline.model_json_to_middle_json import result_to_middle_json as pipeline_result_to_middle_json
from mineru.backend.vlm.vlm_middle_json_mkcontent import union_make as vlm_union_make
from mineru.utils.guess_suffix_or_lang import guess_suffix_by_path


class Base64ImageWriter:
    """Custom image writer that stores images as base64 data instead of saving to files"""
    
    def __init__(self):
        self.images = {}  # Store images as {filename: base64_data}
    
    def write(self, filename: str, image_data: bytes):
        """Store image data as base64"""
        try:
            base64_data = base64.b64encode(image_data).decode('utf-8')
            self.images[filename] = base64_data
            logger.debug(f"Stored image {filename} as base64")
        except Exception as e:
            logger.warning(f"Failed to encode image {filename}: {e}")
    
    def get_image_base64(self, filename: str) -> str:
        """Get base64 data for an image"""
        return self.images.get(filename, "")
    
    def get_all_images(self) -> dict:
        """Get all stored images"""
        return self.images


def _replace_images_with_base64(md_content: str, image_writer: Base64ImageWriter) -> str:
    """Replace image paths in markdown with base64 data URLs"""
    
    # Pattern to match markdown image syntax: ![alt](path)
    image_pattern = r'!\[([^\]]*)\]\(([^)]+)\)'
    
    def replace_image(match):
        alt_text = match.group(1)
        image_path = match.group(2)
        
        # Extract filename from path
        filename = os.path.basename(image_path)
        
        # Get base64 data for this image
        base64_data = image_writer.get_image_base64(filename)
        
        if base64_data:
            # Determine image format from filename extension
            ext = os.path.splitext(filename)[1].lower()
            if ext in ['.jpg', '.jpeg']:
                mime_type = 'image/jpeg'
            elif ext == '.png':
                mime_type = 'image/png'
            elif ext == '.gif':
                mime_type = 'image/gif'
            elif ext == '.webp':
                mime_type = 'image/webp'
            else:
                mime_type = 'image/jpeg'  # default
            
            # Create data URL
            data_url = f"data:{mime_type};base64,{base64_data}"
            return f"![{alt_text}]({data_url})"
        else:
            # If no base64 data found, keep original or remove
            logger.warning(f"No base64 data found for image: {filename}")
            return f"![{alt_text}]({image_path})"  # Keep original path
    
    # Replace all image references
    return re.sub(image_pattern, replace_image, md_content)


def _parse_single_doc(
    pdf_bytes: bytes,  # PDF bytes to be parsed
    lang: str = "ch",  # Language for the PDF, default is 'ch' (Chinese)
    backend="pipeline",  # The backend for parsing PDF, default is 'pipeline'
    parse_method="auto",  # The method for parsing PDF, default is 'auto'
    formula_enable=True,  # Enable formula parsing
    table_enable=True,  # Enable table parsing
    server_url=None,  # Server URL for vlm-http-client backend
    start_page_id=0,  # Start page ID for parsing, default is 0
    end_page_id=None,  # End page ID for parsing, default is None (parse all pages until the end of the document)
) -> str:
    """Parse a single PDF document and return markdown content with base64 embedded images"""
    
    if backend == "pipeline":
        # Process single PDF file
        new_pdf_bytes = convert_pdf_bytes_to_bytes_by_pypdfium2(pdf_bytes, start_page_id, end_page_id)
        
        infer_results, all_image_lists, all_pdf_docs, lang_list, ocr_enabled_list = pipeline_doc_analyze(
            [new_pdf_bytes], [lang], 
            parse_method=parse_method, 
            formula_enable=formula_enable,
            table_enable=table_enable
        )

        # Get the first (and only) result
        model_list = infer_results[0]
        images_list = all_image_lists[0]
        pdf_doc = all_pdf_docs[0]
        _lang = lang_list[0]
        _ocr_enable = ocr_enabled_list[0]
        
        # Create custom base64 image writer
        image_writer = Base64ImageWriter()
        middle_json = pipeline_result_to_middle_json(model_list, images_list, pdf_doc, image_writer, _lang, _ocr_enable, formula_enable)

        pdf_info = middle_json["pdf_info"]
        
        # Generate markdown content
        md_content_str = pipeline_union_make(pdf_info, MakeMode.MM_MD, "")
        
        # Replace image paths with base64 data in markdown
        md_content_str = _replace_images_with_base64(md_content_str, image_writer)
        
        return md_content_str
    else:
        if backend.startswith("vlm-"):
            backend = backend[4:]

        parse_method = "vlm"
        new_pdf_bytes = convert_pdf_bytes_to_bytes_by_pypdfium2(pdf_bytes, start_page_id, end_page_id)
        
        # Create custom base64 image writer
        image_writer = Base64ImageWriter()
        middle_json, infer_result = vlm_doc_analyze(new_pdf_bytes, image_writer=image_writer, backend=backend, server_url=server_url)

        pdf_info = middle_json["pdf_info"]
        
        # Generate markdown content
        md_content_str = vlm_union_make(pdf_info, MakeMode.MM_MD, "")
        
        # Replace image paths with base64 data in markdown
        md_content_str = _replace_images_with_base64(md_content_str, image_writer)
        
        return md_content_str


def parse_doc(
        doc_path: Path,
        lang="ch",
        backend="pipeline",
        method="auto",
        server_url=None,
        start_page_id=0,
        end_page_id=None
) -> str:
    """
        Parameter description:
        doc_path: Path to the document to be parsed, can be PDF or image file.
        lang: Language option, default is 'ch', optional values include['ch', 'ch_server', 'ch_lite', 'en', 'korean', 'japan', 'chinese_cht', 'ta', 'te', 'ka']。
            Input the languages in the pdf (if known) to improve OCR accuracy.  Optional.
            Adapted only for the case where the backend is set to "pipeline"
        backend: the backend for parsing pdf:
            pipeline: More general.
            vlm-transformers: More general.
            vlm-vllm-engine: Faster(engine).
            vlm-http-client: Faster(client).
            without method specified, pipeline will be used by default.
        method: the method for parsing pdf:
            auto: Automatically determine the method based on the file type.
            txt: Use text extraction method.
            ocr: Use OCR method for image-based PDFs.
            Without method specified, 'auto' will be used by default.
            Adapted only for the case where the backend is set to "pipeline".
        server_url: When the backend is `http-client`, you need to specify the server_url, for example:`http://127.0.0.1:30000`
        start_page_id: Start page ID for parsing, default is 0
        end_page_id: End page ID for parsing, default is None (parse all pages until the end of the document)
        
        Returns:
        str: The markdown content of the parsed document with base64 embedded images
    """
    try:
        pdf_bytes = read_fn(doc_path)
        return _parse_single_doc(
            pdf_bytes=pdf_bytes,
            lang=lang,
            backend=backend,
            parse_method=method,
            server_url=server_url,
            start_page_id=start_page_id,
            end_page_id=end_page_id
        )
    except Exception as e:
        logger.exception(e)
        return None


# if __name__ == '__main__':
#     """如果您由于网络问题无法下载模型，可以设置环境变量MINERU_MODEL_SOURCE为modelscope使用免代理仓库下载模型"""
#     # os.environ['MINERU_MODEL_SOURCE'] = "modelscope"

#     """Use pipeline mode if your environment does not support VLM"""
#     doc_path = Path("data_test/test.pdf")
#     markdown_content = parse_doc(doc_path, backend="pipeline")
    
#     with open("output.md", "w", encoding="utf-8") as f:
#         f.write(markdown_content)

#     """To enable VLM mode, change the backend to 'vlm-xxx'"""
#     # markdown_content = parse_doc(doc_path, backend="vlm-transformers")  # more general.
#     # markdown_content = parse_doc(doc_path, backend="vlm-vllm-engine")  # faster(engine).
#     # markdown_content = parse_doc(doc_path, backend="vlm-http-client", server_url="http://127.0.0.1:30000")  # faster(client).
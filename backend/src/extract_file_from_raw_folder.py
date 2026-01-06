"""
批量文件转换工具 extract_file_from_raw_folder.py

功能概述：
- 递归读取输入文件夹及其子文件夹中的所有文件。
- 将 PDF、Excel、Word(docx) 转换为 Markdown 或 JSON：
  - PDF -> Markdown（调用 src.data_pdf.parse_doc）
  - Excel(xlsx/xls) -> Markdown（调用 src.data_excel.get_data_from_excel）
  - Word(docx) -> JSON（调用 src.data_word.extract_content_from_docx）
- 将转换后的 md 或 json 保存到输出文件夹中，并保持与原文件夹相同的目录结构。
- 对图片文件（jpg/jpeg/png/bmp/gif/tif/tiff/webp/jfif/pjpeg/pjp），统一转换/保存为 PNG 到输出文件夹中，保持目录结构：
  - 已经是 PNG 的直接复制；
  - 其它格式尝试转换为 PNG（调用 src.data_image.convert_image_to_png）。

使用方法：
  python extract_file_from_raw_folder.py --input <输入文件夹> --output <输出文件夹>

注意：
- 本脚本不修改项目中其它已有文件，只新增本文件和 src/data_image.py。
- Word 提取返回 JSON 字符串（包含文本、表格、图片的 base64 信息）。
- 若图片转换需要 Pillow，如未安装将跳过非 PNG 的转换并给出警告。
"""
from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import Optional, Tuple

# 引入项目内已实现的转换函数
from src.data_pdf import parse_doc as parse_pdf_to_markdown
from src.data_excel import get_data_from_excel as excel_to_markdown
from src.data_word import extract_content_from_docx as docx_to_json
from src.data_image import (
    is_supported_image,
    convert_image_to_png,
    suggest_png_path_for,
)


PDF_SUFFIXES = {".pdf"}
EXCEL_SUFFIXES = {".xlsx", ".xls"}
WORD_SUFFIXES = {".docx"}
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".tif", ".tiff", ".webp", ".jfif", ".pjpeg", ".pjp"}


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


essential_text_encodings = ["utf-8", "utf-8-sig", "gb18030"]

def write_text_safely(path: Path, data: str) -> None:
    ensure_parent(path)
    # 优先 utf-8 写入，失败时尝试其他编码
    last_exc: Optional[Exception] = None
    for enc in essential_text_encodings:
        try:
            path.write_text(data, encoding=enc)
            return
        except Exception as e:
            last_exc = e
    # 如果全部失败，回退为二进制写入（utf-8 编码）
    try:
        path.write_bytes(data.encode("utf-8", errors="ignore"))
    except Exception:
        if last_exc:
            raise last_exc
        else:
            raise


def process_pdf(src: Path, in_root: Path, out_root: Path) -> None:
    rel = src.relative_to(in_root).with_suffix(".md")
    dst = out_root / rel
    print(f"[PDF] {src} -> {dst}")
    try:
        md = parse_pdf_to_markdown(src)
        if not md:
            print(f"  !! PDF 转换失败或为空: {src}")
            return
        write_text_safely(dst, md)
    except Exception as e:
        print(f"  !! PDF 转换异常: {src} -> {e}")


def process_excel(src: Path, in_root: Path, out_root: Path) -> None:
    rel = src.relative_to(in_root).with_suffix(".md")
    dst = out_root / rel
    print(f"[Excel] {src} -> {dst}")
    try:
        md = excel_to_markdown(str(src))
        if not md:
            print(f"  !! Excel 转换失败或为空: {src}")
            return
        write_text_safely(dst, md)
    except Exception as e:
        print(f"  !! Excel 转换异常: {src} -> {e}")


def process_word(src: Path, in_root: Path, out_root: Path) -> None:
    rel = src.relative_to(in_root).with_suffix(".json")
    dst = out_root / rel
    print(f"[Word] {src} -> {dst}")
    try:
        js = docx_to_json(str(src))
        if not js:
            print(f"  !! Word 转换失败或为空: {src}")
            return
        # 校验是否为 JSON 字符串
        try:
            json.loads(js)
        except Exception:
            print(f"  !! Word 返回内容非 JSON 格式，仍按文本写入: {src}")
        write_text_safely(dst, js)
    except Exception as e:
        print(f"  !! Word 转换异常: {src} -> {e}")


def process_image(src: Path, in_root: Path, out_root: Path) -> None:
    # 已是 PNG 的，保持同名复制；否则尝试转为 PNG
    if src.suffix.lower() == ".png":
        rel = src.relative_to(in_root)
        dst = out_root / rel
        print(f"[Image] 复制 PNG {src} -> {dst}")
        ensure_parent(dst)
        try:
            shutil.copy2(src, dst)
        except Exception as e:
            print(f"  !! 复制 PNG 失败: {src} -> {e}")
        return

    # 其它图片格式，转换为 PNG
    dst = suggest_png_path_for(src, out_root, in_root)
    print(f"[Image] 转换为 PNG {src} -> {dst}")
    ok = convert_image_to_png(src, dst)
    if not ok:
        print(f"  !! 图片转换失败或 Pillow 未安装: {src}")


def walk_and_process(
    input_root: Path, 
    output_root: Path, 
    skip_types: Optional[set[str]] = None
) -> None:
    """
    递归处理输入目录中的所有文件
    
    Args:
        input_root: 输入根目录
        output_root: 输出根目录
        skip_types: 要跳过的文件类型集合，可选值: {'pdf', 'excel', 'word', 'image'}
    """
    input_root = input_root.resolve()
    output_root = output_root.resolve()
    print(f"输入目录: {input_root}")
    print(f"输出目录: {output_root}")
    
    if skip_types:
        print(f"跳过类型: {', '.join(sorted(skip_types))}")

    if not input_root.exists() or not input_root.is_dir():
        raise FileNotFoundError(f"输入目录不存在或不是文件夹: {input_root}")

    # 默认不跳过任何类型
    if skip_types is None:
        skip_types = set()

    for dirpath, dirnames, filenames in os.walk(input_root):
        dirpath_p = Path(dirpath)
        # 逐个处理文件
        for name in filenames:
            src = dirpath_p / name
            suffix = src.suffix.lower()
            try:
                if suffix in PDF_SUFFIXES:
                    if 'pdf' not in skip_types:
                        process_pdf(src, input_root, output_root)
                    else:
                        print(f"[Skip PDF] {src}")
                elif suffix in EXCEL_SUFFIXES:
                    if 'excel' not in skip_types:
                        process_excel(src, input_root, output_root)
                    else:
                        print(f"[Skip Excel] {src}")
                elif suffix in WORD_SUFFIXES:
                    if 'word' not in skip_types:
                        process_word(src, input_root, output_root)
                    else:
                        print(f"[Skip Word] {src}")
                elif suffix in IMAGE_SUFFIXES and is_supported_image(src):
                    if 'image' not in skip_types:
                        process_image(src, input_root, output_root)
                    else:
                        print(f"[Skip Image] {src}")
                else:
                    # 其它类型忽略
                    pass
            except Exception as e:
                print(f"[Skip] 处理文件出错 {src}: {e}")

if __name__ == "__main__":
    # 直接指定输入和输出路径
    in_root = Path("/Volumes/SSD_4T/企业产品资料")
    out_root = Path("./structured_processed_files")
    os.makedirs(out_root, exist_ok=True)
    
    # 使用示例：可以跳过某些文件类型的处理
    # 例如：跳过图片和Excel文件的处理
    # skip_types = {'image', 'excel'}
    # walk_and_process(in_root, out_root, skip_types=skip_types)
    
    # 默认处理所有类型
    walk_and_process(in_root, out_root)

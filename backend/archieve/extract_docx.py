#!/usr/bin/env python3
"""
使用unstructured库提取test.docx文件中的内容
"""

import os
import base64
import zipfile
from docx import Document
from unstructured.partition.docx import partition_docx
from unstructured.chunking.title import chunk_by_title
from unstructured.staging.base import elements_to_json


def extract_images_from_docx(file_path: str):
    """
    直接从docx文件中提取图片
    
    Args:
        file_path (str): docx文件路径
    
    Returns:
        list: 图片信息列表
    """
    images = []
    
    try:
        # 打开docx文件作为zip文件
        with zipfile.ZipFile(file_path, 'r') as docx_zip:
            # 查找图片文件
            image_files = [f for f in docx_zip.namelist() if f.startswith('word/media/') and f != 'word/media/']
            
            for img_file in image_files:
                try:
                    # 读取图片数据
                    img_data = docx_zip.read(img_file)
                    
                    # 获取文件扩展名
                    _, ext = os.path.splitext(img_file)
                    if not ext:
                        ext = '.jpeg'  # 默认扩展名
                    
                    # 创建图片信息字典
                    image_info = {
                        'filename': os.path.basename(img_file),
                        'path': img_file,
                        'size': len(img_data),
                        'extension': ext,
                        'data': img_data
                    }
                    images.append(image_info)
                    
                except Exception as e:
                    print(f"读取图片 {img_file} 时出错: {e}")
        
        print(f"从docx文件中提取到 {len(images)} 张图片")
        return images
        
    except Exception as e:
        print(f"提取图片时出错: {e}")
        return []


def extract_docx_content(file_path: str, extract_images: bool = True):
    """
    从docx文件中提取内容
    
    Args:
        file_path (str): docx文件路径
        extract_images (bool): 是否提取图片，默认为True
    
    Returns:
        tuple: (提取的元素列表, 图片列表)
    """
    try:
        # 检查文件是否存在
        if not os.path.exists(file_path):
            print(f"错误: 文件 {file_path} 不存在")
            return None, None
        
        print(f"正在提取文件: {file_path}")
        
        # 使用unstructured提取docx内容，包括图片
        if extract_images:
            # 对于docx文件，使用不同的参数
            elements = partition_docx(filename=file_path, extract_images_in_pdf=False)
        else:
            elements = partition_docx(filename=file_path)
        
        print(f"成功提取 {len(elements)} 个元素")
        
        # 分离图片元素 - 简化逻辑，只检查真正的图片元素
        images = []
        text_elements = []
        
        for element in elements:
            is_image = False
            
            # 检查是否是图片元素 - 只检查真正的图片相关属性
            if hasattr(element, 'metadata') and element.metadata:
                # 方式1: 检查image_path属性且不为空
                if hasattr(element.metadata, 'image_path') and element.metadata.image_path and element.metadata.image_path.strip():
                    is_image = True
                    print(f"检测到图片元素 (image_path): {type(element).__name__}")
                
                # 方式2: 检查filetype是否明确为图片类型
                elif hasattr(element.metadata, 'filetype') and element.metadata.filetype:
                    filetype = str(element.metadata.filetype).lower()
                    if any(img_type in filetype for img_type in ['image/', 'jpeg', 'jpg', 'png', 'gif', 'bmp']):
                        is_image = True
                        print(f"检测到图片元素 (filetype): {type(element).__name__}")
                
                # 方式3: 检查element类型是否明确为Image
                elif 'Image' in str(type(element)) and 'Image' != str(type(element).__name__):
                    is_image = True
                    print(f"检测到图片元素 (type): {type(element).__name__}")
            
            if is_image:
                images.append(element)
            else:
                text_elements.append(element)
        
        print(f"其中包含 {len(images)} 个图片元素，{len(text_elements)} 个文本元素")
        
        return text_elements, images
        
    except Exception as e:
        print(f"提取文件时发生错误: {e}")
        return None, None


def display_content(elements):
    """
    显示提取的内容
    
    Args:
        elements: 提取的元素列表
    """
    if not elements:
        print("没有内容可显示")
        return
    
    print("\n" + "="*50)
    print("提取的内容:")
    print("="*50)
    
    for i, element in enumerate(elements, 1):
        print(f"\n元素 {i}:")
        print(f"类型: {type(element).__name__}")
        print(f"内容: {element.text}")
        
        # 如果有元数据，显示元数据
        if hasattr(element, 'metadata') and element.metadata:
            print(f"元数据: {element.metadata}")


def debug_elements(elements):
    """
    调试函数：显示所有元素的详细信息
    
    Args:
        elements: 元素列表
    """
    print("\n" + "="*50)
    print("调试信息 - 所有元素:")
    print("="*50)
    
    for i, element in enumerate(elements[:10], 1):  # 只显示前10个元素
        print(f"\n元素 {i}:")
        print(f"类型: {type(element).__name__}")
        print(f"文本: '{element.text}'")
        
        if hasattr(element, 'metadata') and element.metadata:
            print(f"元数据类型: {type(element.metadata).__name__}")
            print(f"元数据属性: {dir(element.metadata)}")
            
            # 显示所有元数据属性
            for attr in dir(element.metadata):
                if not attr.startswith('_'):
                    try:
                        value = getattr(element.metadata, attr)
                        if not callable(value):
                            print(f"  {attr}: {value}")
                    except:
                        pass
        
        print(f"元素属性: {[attr for attr in dir(element) if not attr.startswith('_')]}")


def display_images(images):
    """
    显示提取的图片信息
    
    Args:
        images: 图片元素列表
    """
    if not images:
        print("没有图片可显示")
        return
    
    print("\n" + "="*50)
    print("提取的图片:")
    print("="*50)
    
    for i, image in enumerate(images, 1):
        print(f"\n图片 {i}:")
        print(f"类型: {type(image).__name__}")
        
        if hasattr(image, 'metadata') and image.metadata:
            print(f"元数据: {image.metadata}")
            
            # 显示图片路径信息
            if hasattr(image.metadata, 'image_path') and image.metadata.image_path:
                print(f"图片路径: {image.metadata.image_path}")
            
            # 显示图片尺寸信息
            if hasattr(image.metadata, 'image_width') and hasattr(image.metadata, 'image_height'):
                print(f"图片尺寸: {image.metadata.image_width}x{image.metadata.image_height}")
        
        # 如果有文本内容（可能是图片的alt text）
        if hasattr(image, 'text') and image.text and image.text.strip():
            print(f"图片描述: {image.text}")


def save_extracted_images(images, output_dir: str = "extracted_images"):
    """
    保存从docx文件中提取的图片
    
    Args:
        images: 图片信息列表
        output_dir (str): 输出目录路径
    """
    if not images:
        print("没有图片可保存")
        return
    
    try:
        # 创建输出目录
        os.makedirs(output_dir, exist_ok=True)
        
        saved_count = 0
        for i, img in enumerate(images, 1):
            try:
                # 生成新的文件名
                new_filename = f"image_{i:03d}{img['extension']}"
                new_path = os.path.join(output_dir, new_filename)
                
                # 保存图片文件
                with open(new_path, 'wb') as f:
                    f.write(img['data'])
                
                print(f"图片已保存: {new_path} ({img['size']} bytes)")
                saved_count += 1
                
            except Exception as e:
                print(f"保存图片 {img['filename']} 时出错: {e}")
        
        print(f"成功保存 {saved_count} 张图片到目录: {output_dir}")
        
    except Exception as e:
        print(f"保存图片时发生错误: {e}")


def save_images(images, output_dir: str = "extracted_images"):
    """
    保存提取的图片到指定目录
    
    Args:
        images: 图片元素列表
        output_dir (str): 输出目录路径
    """
    if not images:
        print("没有图片可保存")
        return
    
    try:
        import shutil
        
        # 创建输出目录
        os.makedirs(output_dir, exist_ok=True)
        
        saved_count = 0
        for i, image in enumerate(images, 1):
            if hasattr(image, 'metadata') and image.metadata and hasattr(image.metadata, 'image_path'):
                image_path = image.metadata.image_path
                if os.path.exists(image_path):
                    # 获取文件扩展名
                    _, ext = os.path.splitext(image_path)
                    if not ext:
                        ext = '.png'  # 默认扩展名
                    
                    # 生成新的文件名
                    new_filename = f"image_{i:03d}{ext}"
                    new_path = os.path.join(output_dir, new_filename)
                    
                    # 复制图片文件
                    shutil.copy2(image_path, new_path)
                    print(f"图片已保存: {new_path}")
                    saved_count += 1
                else:
                    print(f"警告: 图片文件不存在: {image_path}")
            else:
                print(f"警告: 图片 {i} 没有有效的路径信息")
        
        print(f"成功保存 {saved_count} 张图片到目录: {output_dir}")
        
    except Exception as e:
        print(f"保存图片时发生错误: {e}")


def chunk_content(elements):
    """
    将内容按标题分块
    
    Args:
        elements: 提取的元素列表
    
    Returns:
        list: 分块后的元素列表
    """
    if not elements:
        return None
    
    try:
        # 按标题分块
        chunks = chunk_by_title(elements)
        print(f"\n内容已分为 {len(chunks)} 个块")
        return chunks
    except Exception as e:
        print(f"分块时发生错误: {e}")
        return None


def save_to_json(elements, images, output_file: str):
    """
    将元素和图片保存为JSON格式
    
    Args:
        elements: 提取的元素列表
        images: 图片元素列表
        output_file (str): 输出文件路径
    """
    if not elements and not images:
        print("没有内容可保存")
        return
    
    try:
        import json
        
        # 将文本元素转换为字典格式
        elements_dict = []
        for element in elements:
            element_dict = {
                "element_id": getattr(element, 'element_id', ''),
                "text": element.text,
                "type": type(element).__name__,
                "metadata": {
                    "filename": getattr(element.metadata, 'filename', '') if hasattr(element, 'metadata') and element.metadata else '',
                    "filetype": getattr(element.metadata, 'filetype', '') if hasattr(element, 'metadata') and element.metadata else '',
                    "languages": getattr(element.metadata, 'languages', []) if hasattr(element, 'metadata') and element.metadata else [],
                    "last_modified": getattr(element.metadata, 'last_modified', '') if hasattr(element, 'metadata') and element.metadata else ''
                }
            }
            elements_dict.append(element_dict)
        
        # 将图片信息转换为字典格式
        images_dict = []
        for i, img in enumerate(images, 1):
            image_dict = {
                "image_id": f"img_{i:03d}",
                "filename": img['filename'],
                "path": img['path'],
                "size": img['size'],
                "extension": img['extension'],
                "type": "extracted_image"
            }
            images_dict.append(image_dict)
        
        # 创建完整的输出数据结构
        output_data = {
            "document_info": {
                "total_text_elements": len(elements_dict),
                "total_images": len(images_dict),
                "extraction_timestamp": str(os.path.getmtime("test.docx")) if os.path.exists("test.docx") else ""
            },
            "text_elements": elements_dict,
            "images": images_dict
        }
        
        # 保存到文件，确保中文正确显示
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)
        
        print(f"内容已保存到: {output_file}")
        print(f"包含 {len(elements_dict)} 个文本元素和 {len(images_dict)} 张图片")
        
    except Exception as e:
        print(f"保存JSON文件时发生错误: {e}")


def main():
    """主函数"""
    # 文件路径
    docx_file = "test.docx"
    json_output = "extracted_content.json"
    images_output_dir = "extracted_images"
    
    print("开始提取test.docx文件内容...")
    
    # 提取文本内容
    elements, _ = extract_docx_content(docx_file, extract_images=False)
    
    # 单独提取图片
    images = extract_images_from_docx(docx_file)
    
    if elements is not None:
        # 显示文本内容
        display_content(elements)
        
        # 显示图片信息
        if images:
            print(f"\n找到 {len(images)} 张图片:")
            for i, img in enumerate(images, 1):
                print(f"  图片 {i}: {img['filename']} ({img['size']} bytes)")
        else:
            print("\n没有找到图片")
        
        # 分块处理
        chunks = chunk_content(elements)
        if chunks:
            print(f"\n分块后的内容:")
            for i, chunk in enumerate(chunks, 1):
                print(f"\n块 {i}:")
                if hasattr(chunk, 'text'):
                    print(f"  - {chunk.text[:100]}...")
                else:
                    # 如果是CompositeElement，尝试访问其元素
                    if hasattr(chunk, 'elements'):
                        for element in chunk.elements:
                            print(f"  - {element.text[:100]}...")
                    else:
                        print(f"  - {str(chunk)[:100]}...")
        
        # 保存图片到目录
        if images:
            save_extracted_images(images, images_output_dir)
        
        # 保存为JSON
        save_to_json(elements, images, json_output)
        
        print(f"\n提取完成!")
        print(f"文本元素: {len(elements)} 个")
        print(f"图片: {len(images) if images else 0} 张")
    else:
        print("提取失败")


if __name__ == "__main__":
    main()

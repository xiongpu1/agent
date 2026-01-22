import os
import re
import json
import base64
import io
import time
import sys
import hashlib
from datetime import datetime
from typing import Dict, List, Tuple, Optional, Any
from neo4j import GraphDatabase
from PIL import Image
import pandas as pd
from litellm import completion, embedding
from dotenv import load_dotenv
from src.models_litellm import *
from src.dataclass import LLMConfig, Neo4jConfig

# 加载 .env 文件
load_dotenv()

def parse_markdown(markdown_path: str) -> Tuple[str, List[Image.Image], List[str]]:
    """
    读取 markdown 文件，提取文字内容、图片内容和表格内容。
    
    Args:
        markdown_path: markdown 文件路径
        
    Returns:
        Tuple containing:
        - text: 文字内容（去除图片和表格后的纯文本）
        - images: 图片列表（PIL Image 对象，从 base64 解码）
        - tables: 表格列表（markdown 格式字符串）
    """
    # 读取文件
    with open(markdown_path, 'r', encoding='utf-8', errors='ignore') as f:
        md_content = f.read()
    
    # 提取 base64 图片
    img_pattern = re.compile(
        r"!\[(?P<alt>[^\]]*)\]\(data:image\/(?P<mime>[a-zA-Z0-9+.-]+);base64,(?P<data>[^)]+)\)",
        re.IGNORECASE
    )
    images: List[Image.Image] = []
    
    def img_repl(m):
        data_b64 = m.group('data').strip()
        try:
            raw_bytes = base64.b64decode(data_b64, validate=False)
            # 将 bytes 转换为 PIL Image
            img = Image.open(io.BytesIO(raw_bytes))
            # 如果是 RGBA 或其他格式，转换为 RGB（PNG 格式）
            if img.mode in ('RGBA', 'LA', 'P'):
                # 创建白色背景
                rgb_img = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'P':
                    img = img.convert('RGBA')
                rgb_img.paste(img, mask=img.split()[-1] if img.mode in ('RGBA', 'LA') else None)
                img = rgb_img
            elif img.mode != 'RGB':
                img = img.convert('RGB')
            images.append(img)
        except Exception as e:
            print(f"Warning: Failed to decode image: {e}")
        return ''  # 从文本中移除图片引用
    
    md_wo_images = img_pattern.sub(img_repl, md_content)
    
    # 提取表格
    lines = md_wo_images.split('\n')
    tables: List[str] = []
    out_lines: List[str] = []
    i = 0
    
    while i < len(lines):
        line = lines[i]
        # 检测表格：包含 | 且下一行是分隔符
        if '|' in line:
            j = i + 1
            if j < len(lines) and re.match(r"^\s*\|?\s*:?\-[-:\s|]*\|\s*$", lines[j]):
                # 收集表格行直到空行或非表格模式
                tbl_lines = [line, lines[j]]
                k = j + 1
                while k < len(lines) and ('|' in lines[k]) and not re.match(r"^\s*$", lines[k]):
                    tbl_lines.append(lines[k])
                    k += 1
                
                # 先将 markdown 表格转换为 DataFrame，再转换为 markdown
                try:
                    # 移除首尾的 | 和空格，解析为 DataFrame
                    cleaned_lines = []
                    for tbl_line in tbl_lines:
                        # 跳过分隔行（包含 --- 的行）
                        if re.match(r"^\s*\|?\s*:?\-[-:\s|]*\|\s*$", tbl_line):
                            continue
                        # 分割并清理
                        cells = [cell.strip() for cell in tbl_line.split('|')]
                        # 移除首尾空元素（如果存在）
                        if cells and not cells[0]:
                            cells = cells[1:]
                        if cells and not cells[-1]:
                            cells = cells[:-1]
                        if cells:
                            cleaned_lines.append(cells)
                    
                    if len(cleaned_lines) > 0:
                        # 第一行作为表头
                        header = cleaned_lines[0]
                        data_rows = cleaned_lines[1:] if len(cleaned_lines) > 1 else []
                        # 转换为 DataFrame
                        df = pd.DataFrame(data_rows, columns=header)
                        # 将 DataFrame 转换为 markdown 格式
                        tbl_md = df.to_markdown(index=False)
                        if tbl_md:
                            tables.append(tbl_md)
                except Exception as e:
                    print(f"Warning: Failed to parse table: {e}")
                
                i = k
                continue
        out_lines.append(line)
        i += 1
    
    # 合并剩余文本
    text = '\n'.join(out_lines).strip()
    
    return text, images, tables


def parse_json(json_path: str) -> Tuple[str, List[Image.Image], List[str]]:
    """
    读取 JSON 文件，提取文字内容、图片内容和表格内容。
    
    Args:
        json_path: JSON 文件路径
        
    Returns:
        Tuple containing:
        - text: 文字内容
        - images: 图片列表（PIL Image 对象，从 base64 解码）
        - tables: 表格列表（markdown 格式字符串）
    """
    # 读取 JSON 文件
    with open(json_path, 'r', encoding='utf-8', errors='ignore') as f:
        json_obj = json.load(f)
    
    images: List[Image.Image] = []
    tables: List[str] = []
    text_parts: List[str] = []
    
    def _is_data_url(s: str) -> bool:
        return bool(re.match(r"^data:image/[a-zA-Z0-9+.-]+;base64,", s or ""))
    
    def _decode_data_url(data_url: str) -> Optional[bytes]:
        try:
            m = re.match(r"^data:image/([a-zA-Z0-9+.-]+);base64,(.*)$", data_url)
            if not m:
                return None
            data_b64 = m.group(2)
            return base64.b64decode(data_b64, validate=False)
        except Exception:
            return None
    
    
    def walk(node, path: List[str]):
        nonlocal images, tables, text_parts
        
        # 检测数组字典作为表格
        if isinstance(node, list):
            if node and all(isinstance(x, dict) for x in node):
                # 先转换为 DataFrame，再转换为 markdown 表格
                try:
                    df = pd.DataFrame(node)
                    # 将 DataFrame 转换为 markdown 格式
                    tbl_md = df.to_markdown(index=False)
                    if tbl_md:
                        tables.append(tbl_md)
                except Exception as e:
                    print(f"Warning: Failed to convert list to markdown table: {e}")
                return
            else:
                # 遍历列表元素
                for idx, item in enumerate(node):
                    walk(item, path + [str(idx)])
                return
        
        if isinstance(node, dict):
            for k, v in node.items():
                key = str(k)
                # 检测图片（data URL）
                if isinstance(v, str) and _is_data_url(v):
                    raw_bytes = _decode_data_url(v)
                    if raw_bytes:
                        try:
                            img = Image.open(io.BytesIO(raw_bytes))
                            # 转换为 RGB（PNG 格式）
                            if img.mode in ('RGBA', 'LA', 'P'):
                                rgb_img = Image.new('RGB', img.size, (255, 255, 255))
                                if img.mode == 'P':
                                    img = img.convert('RGBA')
                                rgb_img.paste(img, mask=img.split()[-1] if img.mode in ('RGBA', 'LA') else None)
                                img = rgb_img
                            elif img.mode != 'RGB':
                                img = img.convert('RGB')
                            images.append(img)
                        except Exception as e:
                            print(f"Warning: Failed to decode image: {e}")
                    continue
                
                # 标量文本
                if isinstance(v, (str, int, float, bool)) and not isinstance(v, bytes):
                    text = str(v)
                    if text.strip():
                        heading = "/".join(path + [key])
                        text_parts.append(f"{heading}: {text}")
                    continue
                
                # 递归
                walk(v, path + [key])
            return
        
        # 其他标量
        if isinstance(node, (str, int, float, bool)):
            text = str(node)
            if text.strip():
                text_parts.append(text)
    
    walk(json_obj, [])
    text = '\n'.join(text_parts).strip()
    
    return text, images, tables


def summarize_text(text: str, llm_config: LLMConfig) -> str:
    """
    使用 LLM 对文本内容进行一句话总结。
    
    Args:
        text: 要总结的文本内容
        llm_config: LLM配置（必需）
        
    Returns:
        一句话文本总结
    """
    if not text or not text.strip():
        return ""
    
    # 限制文本长度，避免超出模型限制
    text_snippet = text[:20000] if len(text) > 20000 else text
    
    system_prompt = "你是技术文档的总结助手。请用一句话（不超过 30 个中文字）总结以下文本的关键信息，输出单句，不要标点后的解释。"
    
    kwargs = {
        "model": llm_config.model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": text_snippet},
        ],
        "temperature": 0,
    }
    
    if llm_config.api_key:
        kwargs["api_key"] = llm_config.api_key
    if llm_config.base_url:
        kwargs["api_base"] = llm_config.base_url
    
    try:
        resp = completion(**kwargs)
        text_summary = resp["choices"][0]["message"]["content"].strip() if resp else ""
        # 取第一行，限制长度
        return text_summary.splitlines()[0][:60] if text_summary else ""
    except Exception as e:
        print(f"Warning: Failed to summarize text: {e}")
        return ""


def summarize_image(image: Image.Image, vllm_config: LLMConfig) -> str:
    """
    使用视觉大模型总结图片内容。
    
    Args:
        image: PIL Image 对象
        vllm_config: 视觉LLM配置（必需）
        
    Returns:
        图片内容总结
    """
    if not image:
        return "图片：无内容"
    
    try:
        # 将 PIL Image 转换为 bytes
        img_bytes_io = io.BytesIO()
        # 确保图片是 RGB 模式
        if image.mode != 'RGB':
            image = image.convert('RGB')
        image.save(img_bytes_io, format='PNG')
        img_bytes = img_bytes_io.getvalue()
        
        # 转换为 base64 data URL
        img_b64 = base64.b64encode(img_bytes).decode('utf-8')
        data_url = f"data:image/png;base64,{img_b64}"
        
        messages = [
            {"role": "system", "content": "你是一个视觉分析助手，请简洁总结图片内容（中文，<= 100 字）。"},
            {"role": "user", "content": [
                {"type": "text", "text": "请总结这张图片的关键内容。"},
                {"type": "image_url", "image_url": {"url": data_url}},
            ]},
        ]
        
        kwargs = {
            "model": vllm_config.model,
            "messages": messages,
            "temperature": 0,
        }
        
        if vllm_config.api_key:
            kwargs["api_key"] = vllm_config.api_key
        if vllm_config.base_url:
            kwargs["api_base"] = vllm_config.base_url
        
        try:
            resp = completion(**kwargs)
            image_summary = resp["choices"][0]["message"]["content"].strip() if resp else ""
            return image_summary if image_summary else "图片：无法识别"
        except Exception as e:
            print(f"Warning: Failed to summarize image with vision model: {e}")
            return "图片：分析失败"
    except Exception as e:
        print(f"Warning: Failed to process image: {e}")
        return "图片：处理失败"


def summarize_table(table: str, llm_config: LLMConfig) -> str:
    """
    使用 LLM 对表格内容进行总结。
    
    Args:
        table: markdown 格式的表格内容
        llm_config: LLM配置（必需）
        
    Returns:
        表格内容总结
    """
    if not table or not table.strip():
        return ""
    
    system_prompt = (
        "你是一个专业的技术文档分析助手。\n"
        "请用要点形式完整概括下表的关键信息：指标/维度、范围、异常、对比与结论。\n"
        "最多 16 行，每行不超过 120 字。"
    )
    
    user_prompt = f"表格内容如下（markdown）：\n\n{table}"
    
    kwargs = {
        "model": llm_config.model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0,
    }
    
    if llm_config.api_key:
        kwargs["api_key"] = llm_config.api_key
    if llm_config.base_url:
        kwargs["api_base"] = llm_config.base_url
    
    try:
        resp = completion(**kwargs)
        table_summary = resp["choices"][0]["message"]["content"].strip() if resp else ""
        return table_summary if table_summary else ""
    except Exception as e:
        print(f"Warning: Failed to summarize table: {e}")
        return ""


def fetch_node_name(neo4j_config: Neo4jConfig) -> Dict[str, List[Dict[str, str]]]:
    """
    查询 Neo4j 数据库，返回所有产品和配件的名称。
    
    Returns:
        Dict containing:
        - 'products': List of dicts with 'name', 'english_name', 'chinese_name'
        - 'accessories': List of dicts with 'name' (Chinese name)
    """
    driver = GraphDatabase.driver(neo4j_config.uri, auth=(neo4j_config.user, neo4j_config.password))
    
    try:
        with driver.session() as session:
            # 查询所有产品节点，获取 name, english_name, chinese_name
            result_products = session.run(
                "MATCH (p:Product) RETURN p.name AS name, p.english_name AS english_name, p.chinese_name AS chinese_name"
            )
            products = []
            for record in result_products:
                products.append({
                    "name": record["name"] or "",
                    "english_name": record["english_name"] or "",
                    "chinese_name": record["chinese_name"] or ""
                })
            
            # 查询所有配件节点，获取 name (中文名)
            result_accessories = session.run(
                "MATCH (a:Accessory) RETURN a.name AS name"
            )
            accessories = []
            for record in result_accessories:
                accessories.append({
                    "name": record["name"] or ""
                })
            
            return {
                "products": products,
                "accessories": accessories
            }
    finally:
        driver.close()


def save_content_to_dir(
    text: str,
    images: List[Image.Image],
    tables: List[str],
    original_file_path: str,
    output_dir: str
) -> Dict[str, List[str]]:
    """
    将解析出的文字、图片和表格内容保存到指定目录中。
    
    Args:
        text: 文字内容
        images: 图片列表（PIL Image 对象）
        tables: 表格列表（markdown 格式字符串）
        original_file_path: 原始文件路径（用于生成文件名）
        output_dir: 输出目录路径
        
    Returns:
        Dict containing:
        - 'text_paths': List of saved text file paths
        - 'image_paths': List of saved image file paths
        - 'table_paths': List of saved table file paths
    """
    # 创建子目录
    text_dir = os.path.join(output_dir, "text")
    image_dir = os.path.join(output_dir, "image")
    table_dir = os.path.join(output_dir, "table")
    
    os.makedirs(text_dir, exist_ok=True)
    os.makedirs(image_dir, exist_ok=True)
    os.makedirs(table_dir, exist_ok=True)
    
    # 获取原始文件名（不含扩展名）
    base_name = os.path.splitext(os.path.basename(original_file_path))[0]
    # 清理文件名，移除不合法字符
    base_name = re.sub(r'[<>:"/\\|?*]', '_', base_name)
    
    # 生成唯一标识（时间戳）
    timestamp = int(time.time() * 1000)  # 毫秒级时间戳
    
    text_paths = []
    image_paths = []
    table_paths = []
    
    # 保存文本内容
    if text and text.strip():
        text_filename = f"{base_name}_text_{timestamp}.md"
        text_path = os.path.join(text_dir, text_filename)
        
        # 如果文件已存在，添加序号
        counter = 1
        while os.path.exists(text_path):
            text_filename = f"{base_name}_text_{timestamp}_{counter}.md"
            text_path = os.path.join(text_dir, text_filename)
            counter += 1
        
        try:
            with open(text_path, 'w', encoding='utf-8') as f:
                f.write(text)
            text_paths.append(text_path)
        except Exception as e:
            print(f"Warning: Failed to save text to {text_path}: {e}")
    
    # 保存图片内容
    if images:
        for idx, img in enumerate(images):
            image_filename = f"{base_name}_image_{idx}_{timestamp}.png"
            image_path = os.path.join(image_dir, image_filename)
            
            # 如果文件已存在，添加序号
            counter = 1
            while os.path.exists(image_path):
                image_filename = f"{base_name}_image_{idx}_{timestamp}_{counter}.png"
                image_path = os.path.join(image_dir, image_filename)
                counter += 1
            
            try:
                # 确保图片是 RGB 模式
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                img.save(image_path, 'PNG')
                image_paths.append(image_path)
            except Exception as e:
                print(f"Warning: Failed to save image to {image_path}: {e}")
    
    # 保存表格内容
    if tables:
        for idx, table in enumerate(tables):
            table_filename = f"{base_name}_table_{idx}_{timestamp}.md"
            table_path = os.path.join(table_dir, table_filename)
            
            # 如果文件已存在，添加序号
            counter = 1
            while os.path.exists(table_path):
                table_filename = f"{base_name}_table_{idx}_{timestamp}_{counter}.md"
                table_path = os.path.join(table_dir, table_filename)
                counter += 1
            
            try:
                with open(table_path, 'w', encoding='utf-8') as f:
                    f.write(table)
                table_paths.append(table_path)
            except Exception as e:
                print(f"Warning: Failed to save table to {table_path}: {e}")
    
    return {
        "text_paths": text_paths,
        "image_paths": image_paths,
        "table_paths": table_paths
    }


def match_document_to_node(
    file_path: str,
    llm_config: LLMConfig,
    vllm_config: LLMConfig,
    neo4j_config: Optional[Neo4jConfig] = None,
    nodes_data: Optional[Dict[str, List[Dict[str, str]]]] = None
) -> str:
    """
    匹配文档到节点（产品或配件）。
    
    Args:
        file_path: markdown 或 json 文件路径
        llm_config: LLM配置（必需）
        vllm_config: 视觉LLM配置（必需）
        neo4j_config: Neo4j配置（如果 nodes_data 为 None 则必需）
        nodes_data: 节点数据字典（可选，如果不提供则调用 fetch_node_name()）
                   格式：{"products": [...], "accessories": [...]}
        
    Returns:
        节点名称（产品的 name 或配件的 name），如果匹配不上则返回 "unknown"
    """

    if nodes_data is None:
        if neo4j_config is None:
            print(f"Warning: neo4j_config is required when nodes_data is not provided")
            return "unknown"
        nodes_data = fetch_node_name(neo4j_config)

    if not os.path.exists(file_path):
        return "unknown"
    
    # 获取文件名和路径信息
    filename = os.path.basename(file_path)
    
    # 判断文件类型并解析
    file_ext = os.path.splitext(file_path)[1].lower()
    try:
        if file_ext == '.json':
            text, images, tables = parse_json(file_path)
        elif file_ext == '.md':
            text, images, tables = parse_markdown(file_path)
        else:
            print(f"Warning: Unsupported file type: {file_ext}")
            return "unknown"
    except Exception as e:
        print(f"Warning: Failed to parse file {file_path}: {e}")
        return "unknown"
    
    # 对内容进行总结
    summaries = []
    
    # 总结文本内容
    if text and text.strip():
        text_summary = summarize_text(text, llm_config)
        if text_summary:
            summaries.append(f"文本总结: {text_summary}")
    
    # 总结图片内容
    if images:
        for idx, img in enumerate(images):
            img_summary = summarize_image(img, vllm_config)
            if img_summary:
                summaries.append(f"图片{idx+1}总结: {img_summary}")
    
    # 总结表格内容
    if tables:
        for idx, table in enumerate(tables):
            table_summary = summarize_table(table, llm_config)
            if table_summary:
                summaries.append(f"表格{idx+1}总结: {table_summary}")
    
    # 获取所有节点名称
    try:
        products = nodes_data.get("products", [])
        accessories = nodes_data.get("accessories", [])
        
        # 提取产品名称列表（包括 name、english_name、chinese_name）
        product_names = []
        for p in products:
            if p.get("name"):
                product_names.append(p["name"])
            if p.get("english_name"):
                product_names.append(p["english_name"])
            if p.get("chinese_name"):
                product_names.append(p["chinese_name"])
        product_names = list(set(product_names))  # 去重
        
        # 提取配件名称列表
        accessory_names = []
        for a in accessories:
            if a.get("name"):
                accessory_names.append(a["name"])
        accessory_names = list(set(accessory_names))  # 去重
        
    except Exception as e:
        print(f"Warning: Failed to fetch node names: {e}")
        return "unknown"
    
    # 构建 LLM 提示
    products_list = "\n".join([f"  - {p}" for p in product_names[:100]])  # 限制数量避免提示过长
    accessories_list = "\n".join([f"  - {a}" for a in accessory_names[:100]])
    
    # 构建文档信息摘要
    document_info = f"文件名: {filename}\n文件路径: {file_path}\n"
    if summaries:
        document_info += "\n内容总结:\n" + "\n".join(summaries)
    else:
        # 如果没有总结，使用原始文本的前5000字符
        document_info += f"\n文本内容（前5000字符）:\n{text[:5000] if text else '无文本内容'}"
    
    system_prompt = (
        "你是一个严格的文档分类助手。\n"
        "任务：根据给定的文档信息（文件名、路径、内容总结），判断该文档最可能归属于哪一个产品(Product)或配件(Accessory)。\n"
        "要求：\n"
        "1) 你必须从下面提供的候选名称列表中选择一个，不能自己创造新名称。\n"
        "2) 只能选择 Product 或 Accessory 其中一类。\n"
        "3) 如果不够确定或找不到匹配的，请输出 UNKNOWN。\n"
        "4) 仅输出 JSON 格式：{\"label\": \"Product|Accessory|UNKNOWN\", \"name\": \"精确名称\"}。\n"
        "5) 不要输出解释或多余文本。\n\n"
        f"可选的 Product 名称列表：\n{products_list}\n\n"
        f"可选的 Accessory 名称列表：\n{accessories_list}"
    )
    
    user_prompt = f"{document_info}\n\n请从上述候选列表中选择最匹配的节点，仅输出 JSON。"
    
    kwargs = {
        "model": llm_config.model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0,
    }
    
    if llm_config.api_key:
        kwargs["api_key"] = llm_config.api_key
    if llm_config.base_url:
        kwargs["api_base"] = llm_config.base_url
    
    try:
        resp = completion(**kwargs)
        text = resp["choices"][0]["message"]["content"].strip() if resp else ""
        
        # 解析 JSON
        try:
            data = json.loads(text)
        except Exception:
            # 尝试从文本中提取 JSON
            m = re.search(r"\{[\s\S]*\}", text)
            if not m:
                return "unknown"
            data = json.loads(m.group(0))
        
        label = data.get("label")
        name = data.get("name")
        
        if not isinstance(name, str) or not name:
            return "unknown"
        
        # 验证名称是否在候选列表中
        if label == "Product":
            # 检查是否匹配产品的 name、english_name 或 chinese_name
            for p in products:
                if (name == p.get("name") or 
                    name == p.get("english_name") or 
                    name == p.get("chinese_name")):
                    return p.get("name", name)  # 返回产品的 name 作为标识符
            return "unknown"
        elif label == "Accessory":
            # 检查是否匹配配件的 name
            for a in accessories:
                if name == a.get("name"):
                    return a.get("name", name)
            return "unknown"
        else:
            return "unknown"
            
    except Exception as e:
        print(f"Warning: Failed to match document to node: {e}")
        return "unknown"


def match_image_to_node(
    image_path: str,
    llm_config: LLMConfig,
    vllm_config: LLMConfig,
    neo4j_config: Neo4jConfig,
    nodes_data: Optional[Dict[str, List[Dict[str, str]]]] = None
) -> str:
    """
    匹配图片到节点（产品或配件）。
    
    Args:
        image_path: 图片文件路径
        llm_config: LLM配置（必需）
        vllm_config: 视觉LLM配置（必需）
        neo4j_config: Neo4j配置（必需）
        nodes_data: 节点数据字典（可选，如果不提供则调用 fetch_node_name()）
                   格式：{"products": [...], "accessories": [...]}
        
    Returns:
        节点名称（产品的 name 或配件的 name），如果匹配不上则返回 "unknown"
    """

    if not os.path.exists(image_path):
        return "unknown"
    
    # 获取文件名和路径信息
    filename = os.path.basename(image_path)
    
    # 打开图片
    try:
        image = Image.open(image_path)
        # 确保图片是 RGB 模式
        if image.mode != 'RGB':
            image = image.convert('RGB')
    except Exception as e:
        print(f"Warning: Failed to open image {image_path}: {e}")
        return "unknown"
    
    # 使用 summarize_image 总结图片内容
    try:
        image_summary = summarize_image(image, vllm_config)
        if not image_summary or image_summary.startswith("图片："):
            # 如果总结失败或为空，使用文件名作为参考
            image_summary = f"图片文件名: {filename}"
    except Exception as e:
        print(f"Warning: Failed to summarize image: {e}")
        image_summary = f"图片文件名: {filename}"
    
    # 获取所有节点名称
    try:
        if nodes_data is None:
            nodes_data = fetch_node_name(neo4j_config)
        products = nodes_data.get("products", [])
        accessories = nodes_data.get("accessories", [])
        
        # 提取产品名称列表（包括 name、english_name、chinese_name）
        product_names = []
        for p in products:
            if p.get("name"):
                product_names.append(p["name"])
            if p.get("english_name"):
                product_names.append(p["english_name"])
            if p.get("chinese_name"):
                product_names.append(p["chinese_name"])
        product_names = list(set(product_names))  # 去重
        
        # 提取配件名称列表
        accessory_names = []
        for a in accessories:
            if a.get("name"):
                accessory_names.append(a["name"])
        accessory_names = list(set(accessory_names))  # 去重
        
    except Exception as e:
        print(f"Warning: Failed to fetch node names: {e}")
        return "unknown"
    
    # 构建 LLM 提示
    products_list = "\n".join([f"  - {p}" for p in product_names[:100]])  # 限制数量避免提示过长
    accessories_list = "\n".join([f"  - {a}" for a in accessory_names[:100]])
    
    # 构建图片信息摘要
    image_info = f"图片文件名: {filename}\n图片路径: {image_path}\n图片内容总结: {image_summary}"
    
    system_prompt = (
        "你是一个严格的图片分类助手。\n"
        "任务：根据给定的图片信息（文件名、路径、内容总结），判断该图片最可能归属于哪一个产品(Product)或配件(Accessory)。\n"
        "要求：\n"
        "1) 你必须从下面提供的候选名称列表中选择一个，不能自己创造新名称。\n"
        "2) 只能选择 Product 或 Accessory 其中一类。\n"
        "3) 如果不够确定或找不到匹配的，请输出 UNKNOWN。\n"
        "4) 仅输出 JSON 格式：{\"label\": \"Product|Accessory|UNKNOWN\", \"name\": \"精确名称\"}。\n"
        "5) 不要输出解释或多余文本。\n\n"
        f"可选的 Product 名称列表：\n{products_list}\n\n"
        f"可选的 Accessory 名称列表：\n{accessories_list}"
    )
    
    user_prompt = f"{image_info}\n\n请从上述候选列表中选择最匹配的节点，仅输出 JSON。"
    
    kwargs = {
        "model": llm_config.model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0,
    }
    
    if llm_config.api_key:
        kwargs["api_key"] = llm_config.api_key
    if llm_config.base_url:
        kwargs["api_base"] = llm_config.base_url
    
    try:
        resp = completion(**kwargs)
        text = resp["choices"][0]["message"]["content"].strip() if resp else ""
        
        # 解析 JSON
        try:
            data = json.loads(text)
        except Exception:
            # 尝试从文本中提取 JSON
            m = re.search(r"\{[\s\S]*\}", text)
            if not m:
                return "unknown"
            data = json.loads(m.group(0))
        
        label = data.get("label")
        name = data.get("name")
        
        if not isinstance(name, str) or not name:
            return "unknown"
        
        # 验证名称是否在候选列表中
        if label == "Product":
            # 检查是否匹配产品的 name、english_name 或 chinese_name
            for p in products:
                if (name == p.get("name") or 
                    name == p.get("english_name") or 
                    name == p.get("chinese_name")):
                    return p.get("name", name)  # 返回产品的 name 作为标识符
            return "unknown"
        elif label == "Accessory":
            # 检查是否匹配配件的 name
            for a in accessories:
                if name == a.get("name"):
                    return a.get("name", name)
            return "unknown"
        else:
            return "unknown"
            
    except Exception as e:
        print(f"Warning: Failed to match image to node: {e}")
        return "unknown"


# -------- Copied functions from test_neo4j_create_vector.py --------

def is_progress_enabled() -> bool:
    val = os.getenv("PROGRESS", "1").strip().lower()
    return val not in ("0", "false", "no")


def progress_bar(current: int, total: int, prefix: str = "", width: int = 30) -> None:
    """Lightweight progress bar printed on a single line."""
    if total <= 0:
        return
    if not sys.stdout.isatty():
        return
    current = max(0, min(current, total))
    ratio = current / total
    filled = int(width * ratio)
    bar = "█" * filled + "-" * (width - filled)
    end = "\n" if current >= total else "\r"
    print(f"{prefix} [{bar}] {current}/{total} ({ratio*100:.1f}%)", end=end, flush=True)


def md_chunker(md: str, max_chars: int = 3000, overlap: int = 300) -> List[str]:
    """Simple markdown chunker: split on headings/paragraphs, accumulate up to max_chars with overlap."""
    lines = md.split('\n')
    blocks: List[str] = []
    buf: List[str] = []
    size = 0

    def flush():
        nonlocal buf, size
        if buf:
            block = '\n'.join(buf).strip()
            if block:
                blocks.append(block)
        buf = []
        size = 0

    for ln in lines:
        # Start new block on ATX heading or long horizontal rule
        if re.match(r"^\s*#{1,6}\s+", ln) or re.match(r"^\s*(-{3,}|\*{3,}|_{3,})\s*$", ln):
            # force flush before heading if current buffer sizable
            if size > max_chars * 0.6:
                flush()
        buf.append(ln)
        size += len(ln) + 1
        if size >= max_chars:
            flush()
            # add overlap from previous block
            if blocks:
                tail = blocks[-1][-overlap:]
                if tail:
                    buf = [tail]
                    size = len(tail)
    flush()
    # Further split extremely long blocks by sentence if needed
    out: List[str] = []
    for b in blocks:
        if len(b) <= max_chars:
            out.append(b)
        else:
            # naive sentence split
            parts = re.split(r"(?<=[。！？.!?])\s+", b)
            cur = ''
            for p in parts:
                if len(cur) + len(p) + 1 <= max_chars:
                    cur = (cur + ' ' + p).strip()
                else:
                    if cur:
                        out.append(cur)
                    cur = p
            if cur:
                out.append(cur)
    return out


def stable_chunk_id(file_path: str, chunk_index: int, text: str) -> str:
    h = hashlib.sha256()
    h.update(file_path.encode('utf-8'))
    h.update(b'\x00')
    h.update(str(chunk_index).encode('utf-8'))
    h.update(b'\x00')
    # include a small digest of text to reflect content differences
    h.update(hashlib.sha1(text.encode('utf-8')).digest())
    return h.hexdigest()


def embed_texts(texts: List[str], embedding_config: LLMConfig) -> List[List[float]]:
    res: List[List[float]] = []
    total = len(texts)
    
    for idx, t in enumerate(texts, start=1):
        kwargs = {"model": embedding_config.model, "input": t}
        if embedding_config.api_key:
            kwargs["api_key"] = embedding_config.api_key
        if embedding_config.base_url:
            kwargs["api_base"] = embedding_config.base_url
        er = embedding(**kwargs)
        vec = er["data"][0]["embedding"]
        res.append(vec)
        if is_progress_enabled():
            progress_bar(idx, total, prefix=f"Embedding ({embedding_config.model})")
    return res


def get_neo4j_driver(neo4j_config: Neo4jConfig):
    timeout_s = 15
    try:
        timeout_s = int(os.getenv("NEO4J_CONNECTION_TIMEOUT_SECONDS", "15"))
    except Exception:
        timeout_s = 15

    return GraphDatabase.driver(
        neo4j_config.uri,
        auth=(neo4j_config.user, neo4j_config.password),
        connection_timeout=timeout_s,
    )


def ensure_constraints(session) -> None:
    """Ensure constraints on Neo4j nodes."""
    session.run("""
    CREATE CONSTRAINT chunk_id IF NOT EXISTS
    FOR (c:Chunk) REQUIRE c.id IS UNIQUE
    """)
    session.run("""
    CREATE CONSTRAINT document_path IF NOT EXISTS
    FOR (d:Document) REQUIRE d.path IS UNIQUE
    """)
    session.run("""
    CREATE CONSTRAINT text_description_path IF NOT EXISTS
    FOR (td:TextDescription) REQUIRE td.text_path IS UNIQUE
    """)
    session.run("""
    CREATE CONSTRAINT image_description_path IF NOT EXISTS
    FOR (id:ImageDescription) REQUIRE id.image_path IS UNIQUE
    """)
    session.run("""
    CREATE CONSTRAINT table_description_path IF NOT EXISTS
    FOR (td:TableDescription) REQUIRE td.table_path IS UNIQUE
    """)
    session.run("""
    CREATE CONSTRAINT unknown_file_path IF NOT EXISTS
    FOR (u:Unknown) REQUIRE u.file_path IS UNIQUE
    """)


def ensure_vector_index(session, dim: int) -> None:
    """Ensure a Neo4j vector index exists on :Chunk(embedding)."""
    try:
        session.run(
            """
            CREATE VECTOR INDEX chunk_embedding IF NOT EXISTS
            FOR (c:Chunk) ON (c.embedding)
            OPTIONS { indexConfig: { `vector.dimensions`: $dim, `vector.similarity_function`: 'cosine' } }
            """,
            {"dim": dim},
        )
    except Exception as e:
        print(f"Warning: Failed to create vector index: {e}")


# -------- New functions for Neo4j graph structure --------

def find_node_info(nodes_data: Dict[str, List[Dict[str, str]]], node_name: str) -> Tuple[Optional[str], Optional[str]]:
    """
    从节点数据中查找节点类型和名称。
    
    Args:
        nodes_data: fetch_node_name() 返回的节点数据
        node_name: 要查找的节点名称（可能是 name, english_name, chinese_name）
        
    Returns:
        (owner_label, owner_name) 元组，如果未找到则返回 (None, None)
    """
    # 查找产品
    for p in nodes_data.get("products", []):
        if node_name == p.get("name") or node_name == p.get("english_name") or node_name == p.get("chinese_name"):
            return ("Product", p.get("name"))
    
    # 查找配件
    for a in nodes_data.get("accessories", []):
        if node_name == a.get("name"):
            return ("Accessory", a.get("name"))
    
    return (None, None)


def is_file_processed(session, file_path: str) -> bool:
    """
    检查文件是否已经在 Neo4j 中处理过（断点续传功能）。
    
    Args:
        session: Neo4j session
        file_path: 文件路径
        
    Returns:
        True 如果文件已处理过，False 如果未处理
    """
    # 先获取所有已存在的标签，避免查询不存在的标签时产生警告
    try:
        labels_result = session.run("CALL db.labels() YIELD label RETURN collect(label) AS labels")
        labels_record = labels_result.single()
        existing_labels = set(labels_record["labels"]) if labels_record else set()
    except Exception:
        # 如果无法获取标签列表，使用默认标签集合
        existing_labels = set()
    
    # 检查 Document 节点（通常最先创建）
    if "Document" in existing_labels:
        result_doc = session.run(
            "MATCH (d:Document {path: $file_path}) RETURN d LIMIT 1",
            {"file_path": file_path}
        )
        if result_doc.single():
            return True
    
    # 检查 Image 节点（如果标签存在）
    if "Image" in existing_labels:
        result_img = session.run(
            "MATCH (i:Image {path: $file_path}) RETURN i LIMIT 1",
            {"file_path": file_path}
        )
        if result_img.single():
            return True
    
    # 检查 Unknown 节点（如果标签存在）
    if "Unknown" in existing_labels:
        result_unknown = session.run(
            "MATCH (u:Unknown {file_path: $file_path}) RETURN u LIMIT 1",
            {"file_path": file_path}
        )
        if result_unknown.single():
            return True
    
    return False


def create_unknown_node(session, file_path: str, file_type: str) -> None:
    """
    创建 Unknown 节点，只保存文件路径，不添加子节点。
    
    Args:
        session: Neo4j session
        file_path: 文件路径
        file_type: 文件类型（'document' 或 'image'）
    """
    now = datetime.utcnow().isoformat()
    session.run(
        """
        MERGE (u:Unknown {file_path: $file_path})
        ON CREATE SET u.file_type = $file_type, u.created_at = datetime($now)
        ON MATCH SET u.updated_at = datetime($now)
        """,
        {
            "file_path": file_path,
            "file_type": file_type,
            "now": now,
        }
    )


def create_chunk_nodes(
    session,
    description_node_id: str,
    description_label: str,
    texts: List[str],
    vectors: List[List[float]],
    embedding_model: str,
    source_path: str
) -> None:
    """
    批量创建 Chunk 节点，关联到描述节点。
    
    Args:
        session: Neo4j session
        description_node_id: 描述节点的唯一标识符（用于匹配）
        description_label: 描述节点的标签（TextDescription, ImageDescription, TableDescription）
        texts: 文本块列表
        vectors: 向量列表
        embedding_model: 向量模型名称
        source_path: 源文件路径（作为属性）
    """
    for idx, (text, vec) in enumerate(zip(texts, vectors)):
        cid = stable_chunk_id(source_path, idx, text)
        now = datetime.utcnow().isoformat()
        session.run(
            f"""
            MATCH (desc:{description_label} {{id: $desc_id}})
            MERGE (c:Chunk {{id: $id}})
            ON CREATE SET c.text = $text, c.index = $index,
                          c.embedding = $embedding, c.embedding_model = $embedding_model,
                          c.source_path = $source_path,
                          c.created_at = datetime($now)
            ON MATCH SET  c.text = $text, c.index = $index,
                          c.embedding = $embedding, c.embedding_model = $embedding_model,
                          c.source_path = $source_path,
                          c.updated_at = datetime($now)
            WITH c, desc
            MERGE (desc)-[:HAS_CHUNK]->(c)
            """,
            {
                "id": cid,
                "desc_id": description_node_id,
                "text": text,
                "index": idx,
                "embedding": vec,
                "embedding_model": embedding_model,
                "source_path": source_path,
                "now": now,
            }
        )


def create_image_node(
    session,
    owner_label: str,
    owner_name: str,
    image_path: str,
    saved_path: str,
    summary: str,
    embedding_config: LLMConfig
) -> None:
    """
    创建图片节点及其 ImageDescription 节点。
    
    Args:
        session: Neo4j session
        owner_label: 所有者标签（Product 或 Accessory）
        owner_name: 所有者名称
        image_path: 原始图片路径
        saved_path: 保存后的图片路径
        summary: 图片总结
        embedding_config: Embedding配置（必需）
    """
    now = datetime.utcnow().isoformat()
    
    # 创建 Image 节点
    image_id = hashlib.sha256(image_path.encode('utf-8')).hexdigest()
    session.run(
        f"""
        MATCH (o:{owner_label} {{name: $owner_name}})
        MERGE (img:Image {{path: $image_path}})
        ON CREATE SET img.id = $image_id, img.created_at = datetime($now)
        ON MATCH SET img.updated_at = datetime($now)
        MERGE (o)-[:HAS_IMAGE]->(img)
        """,
        {
            "owner_name": owner_name,
            "image_path": image_path,
            "image_id": image_id,
            "now": now,
        }
    )
    
    # 创建 ImageDescription 节点
    desc_id = hashlib.sha256(f"img_desc:{image_path}".encode('utf-8')).hexdigest()
    session.run(
        """
        MATCH (img:Image {path: $image_path})
        MERGE (desc:ImageDescription {id: $desc_id})
        ON CREATE SET desc.summary = $summary, desc.image_path = $saved_path,
                      desc.created_at = datetime($now)
        ON MATCH SET desc.summary = $summary, desc.image_path = $saved_path,
                      desc.updated_at = datetime($now)
        MERGE (img)-[:HAS_DESCRIPTION]->(desc)
        """,
        {
            "image_path": image_path,
            "desc_id": desc_id,
            "summary": summary,
            "saved_path": saved_path,
            "now": now,
        }
    )
    
    # 对图片总结进行分块和向量化
    if summary and summary.strip():
        summary_chunks = md_chunker(summary)
        if summary_chunks:
            summary_vectors = embed_texts(summary_chunks, embedding_config)
            create_chunk_nodes(
                session,
                desc_id,
                "ImageDescription",
                summary_chunks,
                summary_vectors,
                embedding_config.model,
                saved_path
            )


def create_document_node(
    session,
    owner_label: str,
    owner_name: str,
    file_path: str,
    saved_paths: Dict[str, List[str]],
    summaries: Dict[str, Any],
    text_content: str,
    embedding_config: LLMConfig
) -> None:
    """
    创建文档节点及其描述节点（TextDescription, ImageDescription, TableDescription）。
    
    Args:
        session: Neo4j session
        owner_label: 所有者标签（Product 或 Accessory）
        owner_name: 所有者名称
        file_path: 原始文件路径
        saved_paths: 保存的文件路径字典 {"text_paths": [...], "image_paths": [...], "table_paths": [...]}
        summaries: 总结字典 {"text": str, "images": List[str], "tables": List[str]}
        text_content: 完整文本内容
        embedding_config: Embedding配置（必需）
    """
    now = datetime.utcnow().isoformat()
    
    # 创建 Document 节点
    doc_id = hashlib.sha256(file_path.encode('utf-8')).hexdigest()
    session.run(
        f"""
        MATCH (o:{owner_label} {{name: $owner_name}})
        MERGE (doc:Document {{path: $file_path}})
        ON CREATE SET doc.id = $doc_id, doc.name = $doc_name, doc.created_at = datetime($now)
        ON MATCH SET doc.updated_at = datetime($now)
        MERGE (o)-[:HAS_DOCUMENT]->(doc)
        """,
        {
            "owner_name": owner_name,
            "file_path": file_path,
            "doc_id": doc_id,
            "doc_name": os.path.basename(file_path),
            "now": now,
        }
    )
    
    # 创建文本内容描述节点（TextDescription）
    if text_content and text_content.strip() and saved_paths.get("text_paths"):
        text_path = saved_paths["text_paths"][0] if saved_paths["text_paths"] else None
        text_summary = summaries.get("text", "")
        
        if text_path:
            text_desc_id = hashlib.sha256(f"text_desc:{file_path}".encode('utf-8')).hexdigest()
            session.run(
                """
                MATCH (doc:Document {path: $file_path})
                MERGE (desc:TextDescription {id: $desc_id})
                ON CREATE SET desc.summary = $summary, desc.text_path = $text_path,
                              desc.created_at = datetime($now)
                ON MATCH SET desc.summary = $summary, desc.text_path = $text_path,
                              desc.updated_at = datetime($now)
                MERGE (doc)-[:HAS_TEXT_DESCRIPTION]->(desc)
                """,
                {
                    "file_path": file_path,
                    "desc_id": text_desc_id,
                    "summary": text_summary,
                    "text_path": text_path,
                    "now": now,
                }
            )
            
            # 对完整文本内容进行分块和向量化
            text_chunks = md_chunker(text_content)
            if text_chunks:
                text_vectors = embed_texts(text_chunks, embedding_config)
                create_chunk_nodes(
                    session,
                    text_desc_id,
                    "TextDescription",
                    text_chunks,
                    text_vectors,
                    embedding_config.model,
                    text_path
                )
    
    # 创建图片内容描述节点（ImageDescription）
    image_summaries = summaries.get("images", [])
    image_paths = saved_paths.get("image_paths", [])
    for idx, (img_path, img_summary) in enumerate(zip(image_paths, image_summaries)):
        if img_path and img_summary:
            img_desc_id = hashlib.sha256(f"img_desc:{file_path}:{idx}".encode('utf-8')).hexdigest()
            session.run(
                """
                MATCH (doc:Document {path: $file_path})
                MERGE (desc:ImageDescription {id: $desc_id})
                ON CREATE SET desc.summary = $summary, desc.image_path = $image_path,
                              desc.created_at = datetime($now)
                ON MATCH SET desc.summary = $summary, desc.image_path = $image_path,
                              desc.updated_at = datetime($now)
                MERGE (doc)-[:HAS_IMAGE_DESCRIPTION]->(desc)
                """,
                {
                    "file_path": file_path,
                    "desc_id": img_desc_id,
                    "summary": img_summary,
                    "image_path": img_path,
                    "now": now,
                }
            )
            
            # 对图片总结进行分块和向量化
            if img_summary.strip():
                summary_chunks = md_chunker(img_summary)
                if summary_chunks:
                    summary_vectors = embed_texts(summary_chunks, embedding_config)
                    create_chunk_nodes(
                        session,
                        img_desc_id,
                        "ImageDescription",
                        summary_chunks,
                        summary_vectors,
                        embedding_config.model,
                        img_path
                    )
    
    # 创建表格内容描述节点（TableDescription）
    table_summaries = summaries.get("tables", [])
    table_paths = saved_paths.get("table_paths", [])
    for idx, (table_path, table_summary) in enumerate(zip(table_paths, table_summaries)):
        if table_path and table_summary:
            table_desc_id = hashlib.sha256(f"table_desc:{file_path}:{idx}".encode('utf-8')).hexdigest()
            session.run(
                """
                MATCH (doc:Document {path: $file_path})
                MERGE (desc:TableDescription {id: $desc_id})
                ON CREATE SET desc.summary = $summary, desc.table_path = $table_path,
                              desc.created_at = datetime($now)
                ON MATCH SET desc.summary = $summary, desc.table_path = $table_path,
                              desc.updated_at = datetime($now)
                MERGE (doc)-[:HAS_TABLE_DESCRIPTION]->(desc)
                """,
                {
                    "file_path": file_path,
                    "desc_id": table_desc_id,
                    "summary": table_summary,
                    "table_path": table_path,
                    "now": now,
                }
            )
            
            # 对表格总结进行分块和向量化
            if table_summary.strip():
                summary_chunks = md_chunker(table_summary)
                if summary_chunks:
                    summary_vectors = embed_texts(summary_chunks, embedding_config)
                    create_chunk_nodes(
                        session,
                        table_desc_id,
                        "TableDescription",
                        summary_chunks,
                        summary_vectors,
                        embedding_config.model,
                        table_path
                    )


def insert_file_into_neo4j(
    file_path: str,
    output_dir: str,
    llm_config: LLMConfig,
    vllm_config: LLMConfig,
    embedding_config: LLMConfig,
    neo4j_config: Neo4jConfig,
    owner_label: Optional[str] = None,
    owner_name: Optional[str] = None,
    skip_matching: bool = False
) -> Dict[str, Any]:
    """
    处理单个文件，解析内容，匹配或指定节点，保存内容，并在 Neo4j 中创建图结构。
    支持断点续传功能：如果文件已在 Neo4j 中处理过，则跳过处理。
    
    Args:
        file_path: 文件路径（支持 .md, .json, .png）
        output_dir: 输出目录（用于保存解析出的内容）（必需）
        llm_config: LLM配置（必需）
        vllm_config: 视觉LLM配置（必需）
        embedding_config: Embedding配置（必需）
        neo4j_config: Neo4j配置（必需）
        owner_label: 指定的所有者标签（"Product" 或 "Accessory"），如果提供则跳过自动匹配
        owner_name: 指定的所有者名称，如果提供则跳过自动匹配
        skip_matching: 是否跳过自动匹配（如果指定了 owner_label 和 owner_name，则自动跳过）
        
    Returns:
        处理结果字典，包含：
        - "status": "success"、"error" 或 "skipped"（已处理过，跳过）
        - "file_path": 文件路径
        - "file_type": "document" 或 "image"
        - "matched": True/False/None（None 表示跳过）
        - "owner_label": 所有者标签（如果匹配成功）
        - "owner_name": 所有者名称（如果匹配成功）
        - "error": 错误信息（如果有）
    """
    
    # 检查文件是否存在
    if not os.path.exists(file_path):
        return {
            "status": "error",
            "file_path": file_path,
            "file_type": None,
            "matched": False,
            "error": f"File not found: {file_path}"
        }
    
    # 确定文件类型
    ext = os.path.splitext(file_path)[1].lower()
    if ext in ['.md', '.json']:
        file_type = "document"
    elif ext == '.png':
        file_type = "image"
    else:
        return {
            "status": "error",
            "file_path": file_path,
            "file_type": None,
            "matched": False,
            "error": f"Unsupported file type: {ext}"
        }
    
    # 连接 Neo4j
    driver = get_neo4j_driver(neo4j_config)
    
    result = {
        "status": "success",
        "file_path": file_path,
        "file_type": file_type,
        "matched": False,
        "owner_label": None,
        "owner_name": None,
        "error": None
    }
    
    try:
        with driver.session() as session:
            # 确保约束和向量索引
            ensure_constraints(session)
            # 检测向量维度（从第一个向量推断）
            try:
                test_vec = embed_texts(["test"], embedding_config)[0]
                ensure_vector_index(session, len(test_vec))
            except Exception as e:
                print(f"Warning: Failed to create vector index: {e}")
            
            # 检查文件是否已处理（断点续传功能）
            if is_file_processed(session, file_path):
                result["status"] = "skipped"
                result["matched"] = None
                return result
            
            # 如果指定了 owner_label 和 owner_name，跳过匹配
            if owner_label and owner_name:
                skip_matching = True
                matched_owner_label = owner_label
                matched_owner_name = owner_name
                # 即使跳过匹配，也初始化 nodes_data（可能用于验证）
                nodes_data = None
            else:
                skip_matching = False
                matched_owner_label = None
                matched_owner_name = None
                # 获取节点数据（用于匹配）
                nodes_data = fetch_node_name(neo4j_config)
            
            # 处理文档文件
            if file_type == "document":
                try:
                    # 解析文件
                    if ext == '.json':
                        text, images, tables = parse_json(file_path)
                    else:
                        text, images, tables = parse_markdown(file_path)
                    
                    # 保存内容到目录
                    saved_paths = save_content_to_dir(
                        text=text,
                        images=images,
                        tables=tables,
                        original_file_path=file_path,
                        output_dir=output_dir
                    )
                    
                    # 匹配或使用指定的节点
                    if skip_matching:
                        matched_node = matched_owner_name
                    else:
                        matched_node = match_document_to_node(
                            file_path,
                            llm_config=llm_config,
                            vllm_config=vllm_config,
                            neo4j_config=neo4j_config,
                            nodes_data=nodes_data
                        )
                    
                    if matched_node == "unknown" or not matched_node:
                        # 创建 Unknown 节点
                        create_unknown_node(session, file_path, "document")
                        result["matched"] = False
                    else:
                        # 确定所有者标签和名称
                        if skip_matching:
                            final_owner_label = matched_owner_label
                            final_owner_name = matched_owner_name
                        else:
                            final_owner_label, final_owner_name = find_node_info(nodes_data, matched_node)
                        
                        if final_owner_label and final_owner_name:
                            # 生成总结
                            text_summary = summarize_text(text, llm_config) if text else ""
                            image_summaries = []
                            for img in images:
                                img_summary = summarize_image(img, vllm_config)
                                image_summaries.append(img_summary)
                            table_summaries = []
                            for table in tables:
                                table_summary = summarize_table(table, llm_config)
                                table_summaries.append(table_summary)
                            
                            summaries = {
                                "text": text_summary,
                                "images": image_summaries,
                                "tables": table_summaries
                            }
                            
                            # 创建文档节点
                            create_document_node(
                                session,
                                final_owner_label,
                                final_owner_name,
                                file_path,
                                saved_paths,
                                summaries,
                                text,
                                embedding_config
                            )
                            result["matched"] = True
                            result["owner_label"] = final_owner_label
                            result["owner_name"] = final_owner_name
                        else:
                            create_unknown_node(session, file_path, "document")
                            result["matched"] = False
                            
                except Exception as e:
                    error_msg = f"Error processing document {file_path}: {e}"
                    print(error_msg)
                    result["status"] = "error"
                    result["error"] = str(e)
                    create_unknown_node(session, file_path, "document")
                    result["matched"] = False
            
            # 处理图片文件
            elif file_type == "image":
                try:
                    # 匹配或使用指定的节点
                    if skip_matching:
                        matched_node = matched_owner_name
                    else:
                        matched_node = match_image_to_node(
                            file_path,
                            llm_config=llm_config,
                            vllm_config=vllm_config,
                            neo4j_config=neo4j_config,
                            nodes_data=nodes_data
                        )
                    
                    if matched_node == "unknown" or not matched_node:
                        # 创建 Unknown 节点
                        create_unknown_node(session, file_path, "image")
                        result["matched"] = False
                    else:
                        # 确定所有者标签和名称
                        if skip_matching:
                            final_owner_label = matched_owner_label
                            final_owner_name = matched_owner_name
                        else:
                            final_owner_label, final_owner_name = find_node_info(nodes_data, matched_node)
                        
                        if final_owner_label and final_owner_name:
                            # 打开图片并生成总结
                            image = Image.open(file_path)
                            if image.mode != 'RGB':
                                image = image.convert('RGB')
                            
                            summary = summarize_image(image, vllm_config)
                            
                            # 保存图片（复制到输出目录）
                            img_dir = os.path.join(output_dir, "image")
                            os.makedirs(img_dir, exist_ok=True)
                            img_filename = os.path.basename(file_path)
                            saved_img_path = os.path.join(img_dir, img_filename)
                            
                            # 如果文件已存在，添加序号
                            counter = 1
                            while os.path.exists(saved_img_path):
                                base_name = os.path.splitext(img_filename)[0]
                                img_ext = os.path.splitext(img_filename)[1]
                                saved_img_path = os.path.join(img_dir, f"{base_name}_{counter}{img_ext}")
                                counter += 1
                            
                            image.save(saved_img_path, 'PNG')
                            
                            # 创建图片节点
                            create_image_node(
                                session,
                                final_owner_label,
                                final_owner_name,
                                file_path,
                                saved_img_path,
                                summary,
                                embedding_config
                            )
                            result["matched"] = True
                            result["owner_label"] = final_owner_label
                            result["owner_name"] = final_owner_name
                        else:
                            create_unknown_node(session, file_path, "image")
                            result["matched"] = False
                            
                except Exception as e:
                    error_msg = f"Error processing image {file_path}: {e}"
                    print(error_msg)
                    result["status"] = "error"
                    result["error"] = str(e)
                    create_unknown_node(session, file_path, "image")
                    result["matched"] = False
            
    finally:
        driver.close()
    
    return result


def batch_insert_files_into_neo4j(
    folder_path: str,
    output_dir: str,
    llm_config: LLMConfig,
    vllm_config: LLMConfig,
    embedding_config: LLMConfig,
    neo4j_config: Neo4jConfig
) -> str:
    """
    批量处理文件夹中的所有文件，解析文件，匹配节点，保存内容，并在 Neo4j 中创建图结构。
    
    Args:
        folder_path: 文件夹路径
        output_dir: 输出目录（用于保存解析出的内容）
        llm_config: LLM配置（必需）
        vllm_config: 视觉LLM配置（必需）
        embedding_config: Embedding配置（必需）
        neo4j_config: Neo4j配置（必需）
    Returns:
        处理结果统计字符串
    """
    
    # 遍历文件夹，收集所有文件
    markdown_files = []
    json_files = []
    image_files = []
    
    for root, dirs, files in os.walk(folder_path):
        for file in files:
            file_path_full = os.path.join(root, file)
            ext = os.path.splitext(file)[1].lower()
            if ext == '.md':
                markdown_files.append(file_path_full)
            elif ext == '.json':
                json_files.append(file_path_full)
            elif ext == '.png':
                image_files.append(file_path_full)
    
    all_files = markdown_files + json_files + image_files
    total_files = len(all_files)
    
    print(f"Found {len(markdown_files)} markdown files, {len(json_files)} json files, {len(image_files)} PNG images")
    print(f"Total files to process: {total_files}")
    
    # 统计信息
    stats = {
        "documents_processed": 0,
        "images_processed": 0,
        "documents_matched": 0,
        "images_matched": 0,
        "documents_unknown": 0,
        "images_unknown": 0,
        "documents_skipped": 0,
        "images_skipped": 0,
        "errors": 0
    }
    
    # 处理所有文件
    for idx, file_path in enumerate(all_files, start=1):
        # 打印当前处理的文件信息
        file_name = os.path.basename(file_path)
        print(f"\n[{idx}/{total_files}] 正在处理文件: {file_name}")
        
        # 显示进度
        if is_progress_enabled():
            progress_bar(idx, total_files, prefix="Processing files")
        
        # 调用单文件处理函数
        result = insert_file_into_neo4j(
            file_path=file_path,
            output_dir=output_dir,
            llm_config=llm_config,
            vllm_config=vllm_config,
            embedding_config=embedding_config,
            neo4j_config=neo4j_config
        )
        
        # 更新统计信息
        if result["status"] == "error":
            stats["errors"] += 1
            if result["file_type"] == "document":
                stats["documents_unknown"] += 1
            elif result["file_type"] == "image":
                stats["images_unknown"] += 1
        elif result["status"] == "skipped":
            # 文件已处理过，跳过（断点续传）
            if result["file_type"] == "document":
                stats["documents_skipped"] += 1
            elif result["file_type"] == "image":
                stats["images_skipped"] += 1
        else:
            if result["file_type"] == "document":
                stats["documents_processed"] += 1
                if result["matched"]:
                    stats["documents_matched"] += 1
                else:
                    stats["documents_unknown"] += 1
            elif result["file_type"] == "image":
                stats["images_processed"] += 1
                if result["matched"]:
                    stats["images_matched"] += 1
                else:
                    stats["images_unknown"] += 1
    
    # 返回统计信息
    result_str = (
        f"Processing completed:\n"
        f"  Documents processed: {stats['documents_processed']}\n"
        f"  Documents matched: {stats['documents_matched']}\n"
        f"  Documents unknown: {stats['documents_unknown']}\n"
        f"  Documents skipped (already processed): {stats['documents_skipped']}\n"
        f"  Images processed: {stats['images_processed']}\n"
        f"  Images matched: {stats['images_matched']}\n"
        f"  Images unknown: {stats['images_unknown']}\n"
        f"  Images skipped (already processed): {stats['images_skipped']}\n"
        f"  Errors: {stats['errors']}"
    )
    return result_str

if __name__ == "__main__":
    folder_path = "structured_processed_files"
    output_dir = "data_storage"
    
    # 手动配置大模型
    # LLM配置：文本LLM，用于文本总结、表格总结和文档匹配
    llm_config = LLMConfig(
        model=Ollama_QWEN3_VL_MODEL,  # 模型名称，格式：provider/model-name
        api_key=None,  # API密钥（如果需要）
        base_url=Ollama_BASE_URL  # API base URL，对于 ollama 模型需要指定
    )
    
    # VLLM配置：视觉LLM，用于图片总结和图片匹配
    vllm_config = LLMConfig(
        model=Ollama_QWEN3_VL_MODEL,  # 视觉模型名称
        api_key=None,  # API密钥（如果需要）
        base_url=Ollama_BASE_URL  # API base URL
    )
    
    # Embedding配置：用于文本向量化
    embedding_config = LLMConfig(
        model=Ollama_QWEN3_EMBEDDING,  # Embedding模型名称
        api_key=None,  # API密钥（如果需要）
        base_url=Ollama_BASE_URL  # API base URL
    )
    
    neo4j_config = Neo4jConfig(
        uri=os.getenv("NEO4J_URI"),
        user=os.getenv("NEO4J_USER"),
        password=os.getenv("NEO4J_PASSWORD")
    )
    
    result = batch_insert_files_into_neo4j(
        folder_path=folder_path,
        output_dir=output_dir,
        llm_config=llm_config,
        vllm_config=vllm_config,
        embedding_config=embedding_config,
        neo4j_config=neo4j_config
    )
    print(result)
#!/usr/bin/env python3
"""
验证文档内容顺序的脚本
"""

import json

def analyze_document_order():
    """分析文档内容的顺序"""
    
    # 读取JSON文件
    with open('python_docx_content.json', 'r', encoding='utf-8') as f:
        content = json.load(f)
    
    print("文档内容顺序分析:")
    print("="*50)
    
    # 分析前20个元素的顺序
    for i, element in enumerate(content["ordered_content"][:20], 1):
        if element["type"] == "paragraph":
            print(f"[{i:2d}] 段落: {element['text'][:30]}...")
        elif element["type"] == "table":
            print(f"[{i:2d}] 表格: {element['rows']}行 x {element['columns']}列")
    
    print("\n表格位置分析:")
    print("="*50)
    
    # 找到表格的位置
    for i, element in enumerate(content["ordered_content"], 1):
        if element["type"] == "table":
            print(f"表格位于第 {i} 个位置")
            print(f"前面的段落数: {i-1}")
            
            # 显示表格前后的内容
            if i > 1:
                prev_element = content["ordered_content"][i-2]
                print(f"表格前的内容: {prev_element['text'][:50]}...")
            
            if i < len(content["ordered_content"]):
                next_element = content["ordered_content"][i]
                print(f"表格后的内容: {next_element['text'][:50]}...")
            break
    
    print(f"\n总结:")
    print(f"总元素数: {len(content['ordered_content'])}")
    print(f"段落数: {sum(1 for elem in content['ordered_content'] if elem['type'] == 'paragraph')}")
    print(f"表格数: {sum(1 for elem in content['ordered_content'] if elem['type'] == 'table')}")
    print(f"图片数: {len(content['images'])}")

if __name__ == "__main__":
    analyze_document_order()

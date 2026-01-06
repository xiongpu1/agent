import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Union
from neo4j import GraphDatabase
from dotenv import load_dotenv

# 添加项目根目录到 Python 路径，以便导入 src 模块
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.dataclass import Neo4jConfig

load_dotenv()

def import_node_names_from_file(file_path_or_data: Union[str, List, Dict]) -> Dict[str, List[str]]:
    """
    从JSON文件或已读取的JSON数据导入产品和配件数据到Neo4j，并返回查询到的产品和配件列表
    
    Args:
        file_path_or_data: JSON文件路径（字符串）或已读取的JSON数据（字典或列表）
        
    Returns:
        包含 'products' 和 'accessories' 两个键的字典，值为名称列表
    """
    # 判断输入类型：如果是字符串则读取文件，否则直接使用提供的数据
    if isinstance(file_path_or_data, str):
        # 读取JSON文件
        with open(file_path_or_data, 'r', encoding='utf-8') as f:
            data = json.load(f)
    else:
        # 直接使用提供的JSON数据
        data = file_path_or_data

    neo4j_config = Neo4jConfig(
        uri=os.getenv("NEO4J_URI"),
        user=os.getenv("NEO4J_USER"),
        password=os.getenv("NEO4J_PASSWORD")
    )

    driver = GraphDatabase.driver(
        neo4j_config.uri,
        auth=(neo4j_config.user, neo4j_config.password)
    )

    try:
        with driver.session() as session:
            total_products = len(data)
            for i, item in enumerate(data, start=1):
                product_english_name = (item.get('product_english_name') or '').strip() or None
                product_chinese_name = (item.get('product_chinese_name') or '').strip() or None
                bom_version = (item.get('bom_version') or '').strip() or None

                # Create product identifier by concatenating product_english_name and bom_version
                if not product_english_name or not bom_version:
                    continue
                product_identifier = f"{product_english_name}_{bom_version}"

                print(
                    f"[{i}/{total_products}] Creating product: ID='{product_identifier}' EN='{product_english_name or ''}' CN='{product_chinese_name or ''}' BOM='{bom_version or ''}'"
                )

                # Create/merge product node with identifier, names, and bom_version as properties
                session.run(
                    (
                        "MERGE (p:Product {name: $identifier}) "
                        "SET p.english_name = $english_name, "
                        "    p.chinese_name = $chinese_name, "
                        "    p.bom_version = $bom_version"
                    ),
                    {
                        "identifier": product_identifier,
                        "english_name": product_english_name,
                        "chinese_name": product_chinese_name,
                        "bom_version": bom_version,
                    },
                )

                accessories = item.get('accessories', []) or []
                total_accessories = len(accessories)
                for j, accessory in enumerate(accessories, start=1):
                    if accessory is None:
                        continue
                    accessory_name = str(accessory).strip()
                    if not accessory_name:
                        continue

                    # Skip accessories whose names equal the product's names
                    if accessory_name == product_identifier or \
                       (product_english_name and accessory_name == product_english_name) or \
                       (product_chinese_name and accessory_name == product_chinese_name):
                        continue

                    print(f"  - [{j}/{total_accessories}] Accessory: {accessory_name}")

                    session.run(
                        "MERGE (a:Accessory {name: $name})",
                        {"name": accessory_name}
                    )
                    session.run(
                        (
                            "MATCH (p:Product {name: $product_identifier})\n"
                            "MATCH (a:Accessory {name: $accessory_name})\n"
                            "MERGE (p)-[:HAS]->(a)"
                        ),
                        {"product_identifier": product_identifier, "accessory_name": accessory_name}
                    )

        # 导入完成后，查询产品和配件列表
        session = driver.session()
        try:
            # List distinct Products present in DB
            result_products = session.run("MATCH (p:Product) RETURN DISTINCT p.name AS name ORDER BY name")
            products = [record["name"] for record in result_products]

            # List distinct Accessories only
            result_accessories = session.run("MATCH (a:Accessory) RETURN DISTINCT a.name AS name ORDER BY name")
            accessories = [record["name"] for record in result_accessories]

            return {
                "products": products,
                "accessories": accessories
            }
        finally:
            session.close()
    finally:
        driver.close()

if __name__ == "__main__":
    # 默认使用原来的文件路径
    file_path = 'archieve/ref_BOM_accessories.json'
    result = import_node_names_from_file(file_path)
    print(f"\n导入完成！")
    print(f"产品数量: {len(result['products'])}")
    print(f"配件数量: {len(result['accessories'])}")


########
# prompt：修改代码，将 @ref_BOM_accessories.json 内容import到neo4j中：每一条数据对应一个产品，首先将 product_english_name 和 bom_version 拼接起来，变成 "product_english_name"_"bom_version"，作为产品的唯一键，同时产品使用product作为标签，然后把accessories部分内容作为标签为accessory的节点，最后使用(Product) -[:HAS]-> (Accessory)去连接产品和配件。

import os
import sys
from pathlib import Path
from dotenv import load_dotenv
import pandas as pd
from neo4j import GraphDatabase

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.dataclass import Neo4jConfig

load_dotenv()


def query_products_from_neo4j(neo4j_config: Neo4jConfig) -> list:
    """
    从 Neo4j 查询所有产品信息
    
    Returns:
        产品信息列表，每个元素包含：产品中文名、产品英文名、BOM版本
    """
    driver = GraphDatabase.driver(
        neo4j_config.uri,
        auth=(neo4j_config.user, neo4j_config.password)
    )
    
    products = []
    try:
        with driver.session() as session:
            # 查询所有产品节点，获取中文名、英文名和BOM版本
            result = session.run(
                """
                MATCH (p:Product)
                RETURN p.chinese_name AS chinese_name,
                       p.english_name AS english_name,
                       p.bom_version AS bom_version
                ORDER BY p.english_name, p.bom_version
                """
            )
            
            for record in result:
                products.append({
                    "产品中文名": record["chinese_name"] or "",
                    "产品英文名": record["english_name"] or "",
                    "BOM版本": record["bom_version"] or ""
                })
    finally:
        driver.close()
    
    return products


def save_to_excel(products: list, output_file: str = "products_info.xlsx"):
    """
    将产品信息保存为 Excel 文件
    
    Args:
        products: 产品信息列表
        output_file: 输出 Excel 文件名
    """
    if not products:
        print("警告：没有查询到任何产品信息")
        return
    
    # 创建 DataFrame
    df = pd.DataFrame(products)
    
    # 保存为 Excel
    df.to_excel(output_file, index=False, engine='openpyxl')
    print(f"成功保存 {len(products)} 个产品信息到 {output_file}")
    print(f"文件路径: {os.path.abspath(output_file)}")


def main():
    """主函数"""
    # 配置 Neo4j 连接
    neo4j_config = Neo4jConfig(
        uri=os.getenv("NEO4J_URI"),
        user=os.getenv("NEO4J_USER"),
        password=os.getenv("NEO4J_PASSWORD")
    )
    
    print("正在连接 Neo4j 数据库...")
    print(f"URI: {neo4j_config.uri}")
    print(f"User: {neo4j_config.user}")
    
    # 查询产品信息
    print("\n正在查询产品信息...")
    products = query_products_from_neo4j(neo4j_config)
    
    # 显示统计信息
    print(f"\n查询完成！共找到 {len(products)} 个产品")
    
    # 保存为 Excel
    output_file = "products_info.xlsx"
    print(f"\n正在保存到 Excel 文件: {output_file}")
    save_to_excel(products, output_file)
    
    # 显示前几条数据预览
    if products:
        print("\n前 5 条产品信息预览:")
        df = pd.DataFrame(products)
        print(df.head().to_string(index=False))


if __name__ == "__main__":
    main()


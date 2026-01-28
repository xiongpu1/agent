#!/usr/bin/env python3
"""
恢复产品数据到 Neo4j
包括：产品、配件、BOM、材料图片等
"""
import os
import sys
import argparse
from pathlib import Path
from dotenv import load_dotenv

# 添加 backend 到路径
BACKEND_ROOT = Path(__file__).resolve().parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from src.neo4j_import_node_names import import_products_json

load_dotenv()

def check_neo4j_status():
    """检查 Neo4j 当前状态"""
    from neo4j import GraphDatabase
    
    uri = os.getenv('NEO4J_URI', 'bolt://localhost:7688')
    user = os.getenv('NEO4J_USER', 'neo4j')
    password = os.getenv('NEO4J_PASSWORD', 'Root@12345678@')
    
    driver = GraphDatabase.driver(uri, auth=(user, password))
    
    try:
        with driver.session() as session:
            result = session.run('MATCH (m:Material) RETURN count(m) as count')
            material_count = result.single()["count"]
            
            result = session.run('MATCH (p:Product) RETURN count(p) as count')
            product_count = result.single()["count"]
            
            result = session.run('MATCH (a:Accessory) RETURN count(a) as count')
            accessory_count = result.single()["count"]
            
            result = session.run('MATCH (b:BOM) RETURN count(b) as count')
            bom_count = result.single()["count"]
            
            return {
                'materials': material_count,
                'products': product_count,
                'accessories': accessory_count,
                'boms': bom_count
            }
    finally:
        driver.close()

def main():
    parser = argparse.ArgumentParser(description='恢复产品数据到 Neo4j')
    parser.add_argument('--check', action='store_true', help='只检查当前状态，不导入')
    parser.add_argument('--force', action='store_true', help='强制导入，即使数据已存在')
    parser.add_argument('--products', default='backend/data_test/ref_BOM_products.json', 
                       help='产品数据 JSON 文件路径')
    
    args = parser.parse_args()
    
    print("=" * 80)
    print("产品数据恢复工具")
    print("=" * 80)
    
    # 检查当前状态
    print("\n检查当前 Neo4j 状态...")
    try:
        status = check_neo4j_status()
        print(f"\n当前数据:")
        print(f"  材料: {status['materials']} 个")
        print(f"  产品: {status['products']} 个")
        print(f"  配件: {status['accessories']} 个")
        print(f"  BOM: {status['boms']} 个")
    except Exception as e:
        print(f"\n❌ 无法连接到 Neo4j: {e}")
        return 1
    
    if args.check:
        print("\n✅ 状态检查完成")
        return 0
    
    # 检查是否需要导入
    if status['products'] > 0 and not args.force:
        print(f"\n⚠️ 产品数据已存在 ({status['products']} 个产品)")
        print("如果要重新导入，请使用 --force 参数")
        return 0
    
    # 导入产品数据
    print("\n开始导入产品数据...")
    print(f"数据源: {args.products}")
    
    if not Path(args.products).exists():
        print(f"\n❌ 数据文件不存在: {args.products}")
        return 1
    
    try:
        uri = os.getenv('NEO4J_URI', 'bolt://localhost:7688')
        user = os.getenv('NEO4J_USER', 'neo4j')
        password = os.getenv('NEO4J_PASSWORD', 'Root@12345678@')
        
        if not password:
            print("\n❌ NEO4J_PASSWORD 未设置")
            return 1
        
        stats = import_products_json(
            args.products,
            uri=uri,
            user=user,
            password=password,
            wipe=False,  # 不清空数据库
            wipe_only=False
        )
        
        print("\n✅ 导入完成！")
        print(f"\n导入统计:")
        for key, value in stats.items():
            print(f"  {key}: {value}")
        
        # 再次检查状态
        print("\n验证导入结果...")
        status_after = check_neo4j_status()
        print(f"\n导入后数据:")
        print(f"  材料: {status_after['materials']} 个")
        print(f"  产品: {status_after['products']} 个")
        print(f"  配件: {status_after['accessories']} 个")
        print(f"  BOM: {status_after['boms']} 个")
        
        print("\n" + "=" * 80)
        return 0
        
    except Exception as e:
        print(f"\n❌ 导入失败: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""
清空 Neo4j 中的钉盘数据（保留产品/配件节点）
"""
import os
from dotenv import load_dotenv
from neo4j import GraphDatabase

load_dotenv()

def clear_neo4j():
    uri = os.getenv("NEO4J_URI", "bolt://localhost:7688")
    user = os.getenv("NEO4J_USER", "neo4j")
    password = os.getenv("NEO4J_PASSWORD", "Root@12345678@")
    
    print("=" * 80)
    print("清空 Neo4j 钉盘数据（保留产品/配件节点）")
    print("=" * 80)
    
    try:
        driver = GraphDatabase.driver(uri, auth=(user, password))
        
        with driver.session() as session:
            # 统计删除前的数据
            print("\n删除前统计:")
            result = session.run("MATCH (f:File) RETURN count(f) as count")
            file_count = result.single()["count"]
            print(f"  钉盘文件: {file_count} 个")
            
            result = session.run("MATCH (l1:CategoryL1) RETURN count(l1) as count")
            l1_count = result.single()["count"]
            print(f"  L1 类别: {l1_count} 个")
            
            result = session.run("MATCH (l2:CategoryL2) RETURN count(l2) as count")
            l2_count = result.single()["count"]
            print(f"  L2 类别: {l2_count} 个")
            
            # 统计产品/配件数据（不会删除）
            result = session.run("MATCH (m:Material) RETURN count(m) as count")
            material_count = result.single()["count"]
            print(f"\n保留的数据:")
            print(f"  产品材料: {material_count} 个")
            
            result = session.run("MATCH (p:Product) RETURN count(p) as count")
            product_count = result.single()["count"]
            print(f"  产品: {product_count} 个")
            
            result = session.run("MATCH (a:Accessory) RETURN count(a) as count")
            accessory_count = result.single()["count"]
            print(f"  配件: {accessory_count} 个")
            
            result = session.run("MATCH (b:BOM) RETURN count(b) as count")
            bom_count = result.single()["count"]
            print(f"  BOM: {bom_count} 个")
            
            # 只删除钉盘相关节点
            print("\n正在删除钉盘数据...")
            
            # 删除 File 节点及其关系
            session.run("MATCH (f:File) DETACH DELETE f")
            
            # 删除 CategoryL1 节点及其关系
            session.run("MATCH (l1:CategoryL1) DETACH DELETE l1")
            
            # 删除 CategoryL2 节点及其关系
            session.run("MATCH (l2:CategoryL2) DETACH DELETE l2")
            
            # 统计删除后的数据
            print("\n删除后统计:")
            result = session.run("MATCH (f:File) RETURN count(f) as count")
            file_count_after = result.single()["count"]
            print(f"  钉盘文件: {file_count_after} 个")
            
            result = session.run("MATCH (l1:CategoryL1) RETURN count(l1) as count")
            l1_count_after = result.single()["count"]
            print(f"  L1 类别: {l1_count_after} 个")
            
            result = session.run("MATCH (l2:CategoryL2) RETURN count(l2) as count")
            l2_count_after = result.single()["count"]
            print(f"  L2 类别: {l2_count_after} 个")
            
            # 验证产品/配件数据仍然存在
            result = session.run("MATCH (m:Material) RETURN count(m) as count")
            material_count_after = result.single()["count"]
            print(f"\n保留的数据:")
            print(f"  产品材料: {material_count_after} 个")
            
            result = session.run("MATCH (p:Product) RETURN count(p) as count")
            product_count_after = result.single()["count"]
            print(f"  产品: {product_count_after} 个")
            
            result = session.run("MATCH (a:Accessory) RETURN count(a) as count")
            accessory_count_after = result.single()["count"]
            print(f"  配件: {accessory_count_after} 个")
            
            if file_count_after == 0 and l1_count_after == 0 and l2_count_after == 0:
                if material_count_after == material_count and product_count_after == product_count:
                    print("\n✅ 清空成功！产品/配件数据已保留")
                else:
                    print("\n⚠️ 警告：产品/配件数据可能被意外删除")
            else:
                print(f"\n⚠️ 还有钉盘节点未删除")
        
        driver.close()
        
    except Exception as e:
        print(f"\n❌ 清空失败: {e}")
        return False
    
    print("=" * 80)
    return True

if __name__ == "__main__":
    clear_neo4j()

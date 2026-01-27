#!/usr/bin/env python3
"""
清空 Neo4j 中的钉盘数据
"""
import os
from dotenv import load_dotenv
from neo4j import GraphDatabase

load_dotenv()

def clear_neo4j():
    uri = os.getenv("NEO4J_URI", "bolt://localhost:7688")
    user = os.getenv("NEO4J_USER", "neo4j")
    password = os.getenv("NEO4J_PASSWORD", "Root@12345678@")
    
    print("=" * 60)
    print("清空 Neo4j 钉盘数据")
    print("=" * 60)
    
    try:
        driver = GraphDatabase.driver(uri, auth=(user, password))
        
        with driver.session() as session:
            # 统计删除前的数据
            print("\n删除前统计:")
            result = session.run("MATCH (f:File) RETURN count(f) as count")
            file_count = result.single()["count"]
            print(f"  文件: {file_count} 个")
            
            result = session.run("MATCH (l1:CategoryL1) RETURN count(l1) as count")
            l1_count = result.single()["count"]
            print(f"  L1 类别: {l1_count} 个")
            
            result = session.run("MATCH (l2:CategoryL2) RETURN count(l2) as count")
            l2_count = result.single()["count"]
            print(f"  L2 类别: {l2_count} 个")
            
            # 删除所有数据
            print("\n正在删除...")
            session.run("MATCH (n) DETACH DELETE n")
            
            # 统计删除后的数据
            print("\n删除后统计:")
            result = session.run("MATCH (n) RETURN count(n) as count")
            total_count = result.single()["count"]
            print(f"  剩余节点: {total_count} 个")
            
            if total_count == 0:
                print("\n✅ 清空成功！")
            else:
                print(f"\n⚠️ 还有 {total_count} 个节点未删除")
        
        driver.close()
        
    except Exception as e:
        print(f"\n❌ 清空失败: {e}")
        return False
    
    print("=" * 60)
    return True

if __name__ == "__main__":
    clear_neo4j()

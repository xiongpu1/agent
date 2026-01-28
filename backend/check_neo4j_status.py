#!/usr/bin/env python3
"""
检查 Neo4j 当前数据状态
"""
import os
from dotenv import load_dotenv
from neo4j import GraphDatabase

load_dotenv()

uri = os.getenv('NEO4J_URI', 'bolt://localhost:7688')
user = os.getenv('NEO4J_USER', 'neo4j')
password = os.getenv('NEO4J_PASSWORD', 'Root@12345678@')

driver = GraphDatabase.driver(uri, auth=(user, password))

with driver.session() as session:
    print('当前 Neo4j 数据统计:')
    print('=' * 80)
    
    # 钉盘数据
    print('\n钉盘数据:')
    result = session.run('MATCH (f:File) RETURN count(f) as count')
    print(f'  文件: {result.single()["count"]} 个')
    
    result = session.run('MATCH (l1:CategoryL1) RETURN count(l1) as count')
    print(f'  L1 类别: {result.single()["count"]} 个')
    
    result = session.run('MATCH (l2:CategoryL2) RETURN count(l2) as count')
    print(f'  L2 类别: {result.single()["count"]} 个')
    
    # 产品数据
    print('\n产品数据:')
    result = session.run('MATCH (m:Material) RETURN count(m) as count')
    print(f'  材料: {result.single()["count"]} 个')
    
    result = session.run('MATCH (p:Product) RETURN count(p) as count')
    print(f'  产品: {result.single()["count"]} 个')
    
    result = session.run('MATCH (a:Accessory) RETURN count(a) as count')
    print(f'  配件: {result.single()["count"]} 个')
    
    result = session.run('MATCH (b:BOM) RETURN count(b) as count')
    print(f'  BOM: {result.single()["count"]} 个')
    
    result = session.run('MATCH (pc:ProductConfig) RETURN count(pc) as count')
    print(f'  产品配置: {result.single()["count"]} 个')
    
    result = session.run('MATCH (mi:MaterialImage) RETURN count(mi) as count')
    print(f'  材料图片: {result.single()["count"]} 个')
    
    print('\n' + '=' * 80)

driver.close()

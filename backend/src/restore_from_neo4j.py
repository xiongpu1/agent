#!/usr/bin/env python3
"""
从 Neo4j 恢复处理结果到 JSON 文件
"""
import json
import os
import sys
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

# 添加 backend 到路径
BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from src.dingtalk_neo4j_importer import DingTalkNeo4jImporter

load_dotenv(BACKEND_ROOT / ".env")


def main():
    print("=" * 80)
    print("从 Neo4j 恢复处理结果")
    print("=" * 80)
    
    # 连接 Neo4j
    neo4j_uri = os.getenv("NEO4J_URI", "bolt://localhost:7688")
    neo4j_user = os.getenv("NEO4J_USER", "neo4j")
    neo4j_password = os.getenv("NEO4J_PASSWORD", "Root@12345678@")
    
    print(f"\n连接 Neo4j: {neo4j_uri}")
    importer = DingTalkNeo4jImporter(neo4j_uri, neo4j_user, neo4j_password)
    
    try:
        # 从 Neo4j 导出所有文件
        print("\n从 Neo4j 导出文件...")
        with importer.driver.session() as session:
            result = session.run("""
                MATCH (f:DingTalkFile)
                MATCH (l2:DingTalkL2Category)-[:CONTAINS_FILE]->(f)
                MATCH (l1:DingTalkL1Category)-[:HAS_SUBCATEGORY]->(l2)
                RETURN 
                    f.file_id AS file_id,
                    f.file_name AS file_name,
                    f.file_path AS file_path,
                    f.extension AS extension,
                    f.size AS size,
                    f.summary AS summary,
                    f.keyphrases AS keyphrases,
                    f.modality AS modality,
                    f.confidence_read AS confidence_read,
                    l1.name AS category_l1,
                    l2.name AS category_l2,
                    f.category_confidence AS category_confidence,
                    f.category_evidence AS category_evidence
            """)
            
            neo4j_results = []
            for record in result:
                neo4j_results.append({
                    "file_id": record['file_id'],
                    "file_name": record['file_name'],
                    "file_path": record['file_path'],
                    "extension": record['extension'],
                    "size": record['size'],
                    "status": "success",
                    "capsule": {
                        "summary": record['summary'] or "",
                        "keyphrases": record['keyphrases'] or [],
                        "confidence_read": record['confidence_read'] or 0.0,
                        "modality": record['modality'] or "unknown",
                        "kind": "image" if record['modality'] == "image" else "document"
                    },
                    "category_l1": record['category_l1'],
                    "category_l2": record['category_l2'],
                    "category_confidence": record['category_confidence'] or 0.0,
                    "category_evidence": record['category_evidence'] or "",
                    "error": None,
                    "processing_time": 0.0
                })
        
        print(f"✓ 从 Neo4j 导出 {len(neo4j_results)} 条记录")
        
        # 加载当前 JSON 文件
        results_file = BACKEND_ROOT / "data_storage" / "dingtalk_processing_results.json"
        current_results = []
        
        if results_file.exists():
            with open(results_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                current_results = data.get('results', [])
            print(f"✓ 当前 JSON 文件有 {len(current_results)} 条记录")
        
        # 合并：用 file_id 作为键
        file_id_to_result = {}
        
        # 先加载 Neo4j 的数据（优先级低）
        for r in neo4j_results:
            file_id_to_result[r['file_id']] = r
        
        # 再加载当前 JSON 的数据（优先级高，会覆盖）
        for r in current_results:
            file_id_to_result[r['file_id']] = r
        
        # 转换为列表
        merged_results = list(file_id_to_result.values())
        
        print(f"✓ 合并后共 {len(merged_results)} 条记录")
        
        # 保存合并后的结果
        results_data = {
            "total": len(merged_results),
            "success": sum(1 for r in merged_results if r.get('status') == 'success'),
            "failed": sum(1 for r in merged_results if r.get('status') == 'failed'),
            "skipped": sum(1 for r in merged_results if r.get('status') == 'skipped'),
            "last_update": datetime.utcnow().isoformat(),
            "results": merged_results
        }
        
        with open(results_file, 'w', encoding='utf-8') as f:
            json.dump(results_data, f, ensure_ascii=False, indent=2)
        
        print(f"\n✅ 恢复完成！")
        print(f"  总计: {results_data['total']}")
        print(f"  成功: {results_data['success']}")
        print(f"  失败: {results_data['failed']}")
        print(f"  跳过: {results_data['skipped']}")
        print(f"\n结果已保存到: {results_file}")
        
    finally:
        importer.close()


if __name__ == "__main__":
    main()

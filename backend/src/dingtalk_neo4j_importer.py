"""
钉盘文件 Neo4j 导入器
将处理后的文件导入到 Neo4j 图数据库
"""
import json
import hashlib
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime
from neo4j import GraphDatabase


class DingTalkNeo4jImporter:
    """钉盘文件 Neo4j 导入器"""
    
    def __init__(self, neo4j_uri: str, neo4j_user: str, neo4j_password: str):
        """
        初始化导入器
        
        Args:
            neo4j_uri: Neo4j 连接 URI
            neo4j_user: Neo4j 用户名
            neo4j_password: Neo4j 密码
        """
        self.driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))
        self._ensure_constraints()
    
    def _ensure_constraints(self):
        """确保 Neo4j 约束存在"""
        with self.driver.session() as session:
            # L1 类别约束
            session.run("""
                CREATE CONSTRAINT dingtalk_l1_category_name IF NOT EXISTS
                FOR (c:DingTalkL1Category) REQUIRE c.name IS UNIQUE
            """)
            
            # L2 类别约束
            session.run("""
                CREATE CONSTRAINT dingtalk_l2_category_id IF NOT EXISTS
                FOR (c:DingTalkL2Category) REQUIRE c.id IS UNIQUE
            """)
            
            # 文件约束
            session.run("""
                CREATE CONSTRAINT dingtalk_file_id IF NOT EXISTS
                FOR (f:DingTalkFile) REQUIRE f.file_id IS UNIQUE
            """)
    
    def close(self):
        """关闭数据库连接"""
        self.driver.close()
    
    def import_file(self, file_result: Dict[str, Any]) -> bool:
        """
        导入单个文件到 Neo4j
        
        Args:
            file_result: 文件处理结果字典（来自 DingTalkBatchProcessor）
            
        Returns:
            是否导入成功
        """
        if file_result.get('status') != 'success':
            return False
        
        category_l1 = file_result.get('category_l1')
        category_l2 = file_result.get('category_l2')
        
        if not category_l1 or not category_l2:
            return False
        
        try:
            with self.driver.session() as session:
                # 创建或更新 L1 类别节点
                session.run("""
                    MERGE (l1:DingTalkL1Category {name: $name})
                    ON CREATE SET l1.created_at = datetime($now)
                    ON MATCH SET l1.updated_at = datetime($now)
                """, {
                    "name": category_l1,
                    "now": datetime.utcnow().isoformat()
                })
                
                # 创建或更新 L2 类别节点
                l2_id = hashlib.sha256(f"{category_l1}/{category_l2}".encode('utf-8')).hexdigest()
                session.run("""
                    MATCH (l1:DingTalkL1Category {name: $l1_name})
                    MERGE (l2:DingTalkL2Category {id: $l2_id})
                    ON CREATE SET l2.name = $l2_name, l2.created_at = datetime($now)
                    ON MATCH SET l2.name = $l2_name, l2.updated_at = datetime($now)
                    MERGE (l1)-[:HAS_SUBCATEGORY]->(l2)
                """, {
                    "l1_name": category_l1,
                    "l2_id": l2_id,
                    "l2_name": category_l2,
                    "now": datetime.utcnow().isoformat()
                })
                
                # 创建或更新文件节点
                capsule = file_result.get('capsule', {})
                session.run("""
                    MATCH (l2:DingTalkL2Category {id: $l2_id})
                    MERGE (f:DingTalkFile {file_id: $file_id})
                    ON CREATE SET 
                        f.file_name = $file_name,
                        f.file_path = $file_path,
                        f.extension = $extension,
                        f.size = $size,
                        f.summary = $summary,
                        f.keyphrases = $keyphrases,
                        f.modality = $modality,
                        f.confidence_read = $confidence_read,
                        f.category_confidence = $category_confidence,
                        f.category_evidence = $category_evidence,
                        f.open_url = $open_url,
                        f.space_id = $space_id,
                        f.created_at = datetime($now)
                    ON MATCH SET 
                        f.file_name = $file_name,
                        f.file_path = $file_path,
                        f.extension = $extension,
                        f.size = $size,
                        f.summary = $summary,
                        f.keyphrases = $keyphrases,
                        f.modality = $modality,
                        f.confidence_read = $confidence_read,
                        f.category_confidence = $category_confidence,
                        f.category_evidence = $category_evidence,
                        f.open_url = $open_url,
                        f.space_id = $space_id,
                        f.updated_at = datetime($now)
                    MERGE (l2)-[:CONTAINS_FILE]->(f)
                """, {
                    "l2_id": l2_id,
                    "file_id": file_result['file_id'],
                    "file_name": file_result['file_name'],
                    "file_path": file_result['file_path'],
                    "extension": file_result['extension'],
                    "size": file_result['size'],
                    "summary": capsule.get('summary', ''),
                    "keyphrases": capsule.get('keyphrases', []),
                    "modality": capsule.get('modality', ''),
                    "confidence_read": capsule.get('confidence_read', 0.0),
                    "category_confidence": file_result.get('category_confidence', 0.0),
                    "category_evidence": file_result.get('category_evidence', ''),
                    "open_url": file_result.get('open_url', ''),
                    "space_id": "24834926306",
                    "now": datetime.utcnow().isoformat()
                })
                
                return True
        except Exception as e:
            print(f"  ❌ Neo4j 导入失败: {e}")
            return False
    
    def get_processed_file_ids(self) -> set:
        """
        获取已处理的文件 ID 集合（用于断点续传）
        
        Returns:
            已处理的文件 ID 集合
        """
        with self.driver.session() as session:
            result = session.run("""
                MATCH (f:DingTalkFile)
                RETURN f.file_id AS file_id
            """)
            return {record['file_id'] for record in result}
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        获取导入统计信息
        
        Returns:
            统计信息字典
        """
        with self.driver.session() as session:
            # 统计 L1 类别数量
            l1_result = session.run("""
                MATCH (l1:DingTalkL1Category)
                RETURN count(l1) AS count
            """)
            l1_count = l1_result.single()['count']
            
            # 统计 L2 类别数量
            l2_result = session.run("""
                MATCH (l2:DingTalkL2Category)
                RETURN count(l2) AS count
            """)
            l2_count = l2_result.single()['count']
            
            # 统计文件数量
            file_result = session.run("""
                MATCH (f:DingTalkFile)
                RETURN count(f) AS count
            """)
            file_count = file_result.single()['count']
            
            # 统计各 L1 类别下的文件数量
            l1_files_result = session.run("""
                MATCH (l1:DingTalkL1Category)-[:HAS_SUBCATEGORY]->(l2:DingTalkL2Category)-[:CONTAINS_FILE]->(f:DingTalkFile)
                RETURN l1.name AS category, count(f) AS file_count
                ORDER BY file_count DESC
            """)
            l1_files = [{"category": record['category'], "file_count": record['file_count']} 
                       for record in l1_files_result]
            
            return {
                "l1_categories": l1_count,
                "l2_categories": l2_count,
                "files": file_count,
                "files_by_l1": l1_files
            }


if __name__ == "__main__":
    pass

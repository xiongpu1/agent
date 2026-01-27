"""
文件分类器
基于 capsule 使用 LLM 进行智能分类
"""
import json
from typing import Dict, Any, Optional, List

# 导入 spa_classify 的分类函数
try:
    from spa_classify import _llm_classify_from_capsule
except ImportError:
    try:
        from src.spa_classify import _llm_classify_from_capsule
    except ImportError as e:
        raise ImportError(f"无法导入 spa_classify 模块: {e}")


class FileClassifier:
    """文件分类器"""
    
    def __init__(self, model: Optional[str] = None):
        """
        初始化分类器
        
        Args:
            model: LLM 模型名称
        """
        self.model = model
    
    def classify(
        self,
        capsule: Dict[str, Any],
        file_name: str,
        file_path: str,
        extension: str,
        size: int
    ) -> Dict[str, Any]:
        """
        对文件进行分类
        
        Args:
            capsule: capsule 字典（包含 summary, keyphrases, modality 等）
            file_name: 文件名
            file_path: 文件路径
            extension: 文件扩展名
            size: 文件大小
            
        Returns:
            分类结果字典，包含 category_l1, category_l2, confidence, evidence
        """
        # 提取 capsule 信息
        modality = capsule.get('modality', 'document')
        summary = capsule.get('summary', '')
        keyphrases = capsule.get('keyphrases', [])
        
        # 构建元信息
        meta = {
            "file_name": file_name,
            "rel_path": file_path,
            "ext": extension,
            "size": size,
        }
        
        # 调用 LLM 分类
        try:
            result = _llm_classify_from_capsule(
                modality=modality,
                summary=summary,
                keyphrases=keyphrases,
                model=self.model,
                meta=meta
            )
            return result
        except Exception as e:
            # 分类失败时返回默认值
            return {
                "category_l1": "未分类",
                "category_l2": "未分类",
                "category": "未分类/未分类",
                "confidence": 0.0,
                "evidence": f"分类失败: {str(e)}"
            }
    
    def classify_batch(
        self,
        items: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        批量分类
        
        Args:
            items: 包含 capsule 和文件信息的字典列表
            
        Returns:
            分类结果列表
        """
        results = []
        for item in items:
            result = self.classify(
                capsule=item.get('capsule', {}),
                file_name=item.get('file_name', ''),
                file_path=item.get('file_path', ''),
                extension=item.get('extension', ''),
                size=item.get('size', 0)
            )
            results.append(result)
        return results


if __name__ == "__main__":
    pass


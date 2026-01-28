"""
钉盘文件批量处理器
下载文件 → 生成capsule → 分类 → 导入Neo4j
"""
import json
import time
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict

try:
    from dingtalk_downloader import DingTalkDownloader
    from capsule_generator import CapsuleGenerator
    from file_classifier import FileClassifier
except ImportError:
    from src.dingtalk_downloader import DingTalkDownloader
    from src.capsule_generator import CapsuleGenerator
    from src.file_classifier import FileClassifier


@dataclass
class FileProcessResult:
    """文件处理结果"""
    file_id: str
    file_name: str
    file_path: str
    extension: str
    size: int
    status: str  # success, failed, skipped
    capsule: Optional[Dict[str, Any]] = None
    category_l1: Optional[str] = None
    category_l2: Optional[str] = None
    category_confidence: Optional[float] = None  # 分类置信度
    category_evidence: Optional[str] = None  # 分类证据
    error: Optional[str] = None
    processing_time: float = 0.0


class DingTalkBatchProcessor:
    """钉盘文件批量处理器"""
    
    def __init__(self, space_id: str = "24834926306"):
        """
        初始化处理器
        
        Args:
            space_id: 钉盘空间ID
        """
        self.space_id = space_id
        self.downloader = DingTalkDownloader(space_id)
        self.capsule_generator = CapsuleGenerator()
        self.classifier = FileClassifier()
        
        # 加载文件列表
        self.files_data = self._load_files_data()
        
        # 支持的文件类型
        self.supported_extensions = {'pdf', 'jpg', 'jpeg', 'png', 'xlsx', 'xls', 'docx', 'doc'}
        
        # 跳过的文件类型
        self.skip_extensions = {'adoc'}  # 钉钉文档，size=0
    
    def _load_files_data(self) -> Dict[str, Any]:
        """加载文件统计数据"""
        stats_file = Path(__file__).parent.parent / "data_storage" / "dingtalk_file_stats.json"
        
        if not stats_file.exists():
            raise FileNotFoundError(f"文件统计数据不存在: {stats_file}")
        
        with open(stats_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def get_all_files(self) -> List[Dict[str, Any]]:
        """获取所有文件列表"""
        return self.files_data.get('all_files', [])
    
    def filter_files(
        self,
        extensions: Optional[List[str]] = None,
        max_size: Optional[int] = None,
        min_size: Optional[int] = None,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        过滤文件列表
        
        Args:
            extensions: 文件扩展名列表（如 ['pdf', 'jpg']）
            max_size: 最大文件大小（字节）
            min_size: 最小文件大小（字节）
            limit: 限制返回数量
            
        Returns:
            过滤后的文件列表
        """
        files = self.get_all_files()
        
        # 过滤扩展名
        if extensions:
            files = [f for f in files if f.get('extension', '').lower() in [e.lower() for e in extensions]]
        
        # 过滤大小
        if max_size is not None:
            files = [f for f in files if f.get('size', 0) <= max_size]
        
        if min_size is not None:
            files = [f for f in files if f.get('size', 0) >= min_size]
        
        # 限制数量
        if limit is not None:
            files = files[:limit]
        
        return files
    
    def process_file(self, file_info: Dict[str, Any]) -> FileProcessResult:
        """
        处理单个文件
        
        Args:
            file_info: 文件信息字典
            
        Returns:
            处理结果
        """
        start_time = time.time()
        
        file_id = file_info['id']
        file_name = file_info['name']
        file_path = file_info['path']
        extension = file_info['extension']
        size = file_info['size']
        
        result = FileProcessResult(
            file_id=file_id,
            file_name=file_name,
            file_path=file_path,
            extension=extension,
            size=size,
            status='failed'
        )
        
        try:
            # 跳过不支持的文件类型
            if extension.lower() in self.skip_extensions:
                result.status = 'skipped'
                result.error = f"跳过文件类型: {extension}"
                return result
            
            if extension.lower() not in self.supported_extensions:
                result.status = 'skipped'
                result.error = f"不支持的文件类型: {extension}"
                return result
            
            # 下载文件到临时位置
            print(f"  下载文件: {file_name}")
            temp_path = self.downloader.download_file_to_temp(file_id, suffix=f".{extension}")
            
            if not temp_path:
                result.error = "下载失败"
                return result
            
            try:
                # 生成 capsule
                print(f"  生成 capsule...")
                capsule = self.capsule_generator.generate_from_file(
                    file_path=temp_path,
                    file_name=file_name,
                    extension=f".{extension}",  # 添加点号前缀
                    size=size,
                    mtime=0.0,
                    rel_path=file_path
                )
                
                result.capsule = capsule
                
                # 使用 LLM 分类
                print(f"  智能分类...")
                classification = self.classifier.classify(
                    capsule=capsule,
                    file_name=file_name,
                    file_path=file_path,
                    extension=extension,
                    size=size
                )
                
                result.category_l1 = classification.get('category_l1')
                result.category_l2 = classification.get('category_l2')
                result.category_confidence = classification.get('confidence')
                result.category_evidence = classification.get('evidence')
                
                result.status = 'success'
                
            finally:
                # 清理临时文件
                if temp_path.exists():
                    temp_path.unlink()
        
        except Exception as e:
            result.error = str(e)
        
        finally:
            result.processing_time = time.time() - start_time
        
        return result
    
    def process_batch(
        self,
        files: Optional[List[Dict[str, Any]]] = None,
        extensions: Optional[List[str]] = None,
        limit: Optional[int] = None,
        save_results: bool = True
    ) -> List[FileProcessResult]:
        """
        批量处理文件
        
        Args:
            files: 文件列表（如果为None，则处理所有文件）
            extensions: 文件扩展名过滤
            limit: 限制处理数量
            save_results: 是否保存结果
            
        Returns:
            处理结果列表
        """
        if files is None:
            files = self.filter_files(extensions=extensions, limit=limit)
        
        print(f"=" * 80)
        print(f"开始批量处理 {len(files)} 个文件")
        print(f"=" * 80)
        
        results = []
        
        for i, file_info in enumerate(files, 1):
            print(f"\n[{i}/{len(files)}] 处理文件: {file_info['name']}")
            
            result = self.process_file(file_info)
            results.append(result)
            
            print(f"  状态: {result.status}")
            if result.error:
                print(f"  错误: {result.error}")
            print(f"  耗时: {result.processing_time:.2f}s")
        
        # 统计结果
        success_count = sum(1 for r in results if r.status == 'success')
        failed_count = sum(1 for r in results if r.status == 'failed')
        skipped_count = sum(1 for r in results if r.status == 'skipped')
        
        print(f"\n" + "=" * 80)
        print(f"处理完成")
        print(f"  成功: {success_count}")
        print(f"  失败: {failed_count}")
        print(f"  跳过: {skipped_count}")
        print(f"=" * 80)
        
        # 保存结果
        if save_results:
            self._save_results(results)
        
        return results
    
    def _save_results(self, results: List[FileProcessResult]):
        """保存处理结果"""
        output_dir = Path(__file__).parent.parent / "data_storage"
        output_file = output_dir / "dingtalk_processing_results.json"
        
        results_data = {
            "total": len(results),
            "success": sum(1 for r in results if r.status == 'success'),
            "failed": sum(1 for r in results if r.status == 'failed'),
            "skipped": sum(1 for r in results if r.status == 'skipped'),
            "results": [asdict(r) for r in results]
        }
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(results_data, f, ensure_ascii=False, indent=2)
        
        print(f"\n结果已保存到: {output_file}")


if __name__ == "__main__":
    # 示例用法
    processor = DingTalkBatchProcessor()
    
    # 处理前3个PDF文件
    results = processor.process_batch(
        extensions=['pdf'],
        limit=3,
        save_results=True
    )


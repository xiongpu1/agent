#!/usr/bin/env python3
"""
钉盘文件处理完整流程
方案 B + 断点续传：
1. 扫描所有文件（快速，1-2分钟）
2. 分批处理（每次50-100个文件）
3. 支持断点续传（中断后可继续）
4. 实时导入 Neo4j（处理一个导入一个）
5. 提供进度监控和日志
"""
import os
import sys
import json
import time
import argparse
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
from dotenv import load_dotenv

try:
    from tqdm import tqdm
    HAS_TQDM = True
except ImportError:
    HAS_TQDM = False
    print("提示: 安装 tqdm 可以显示进度条: pip install tqdm")

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

from src.dingtalk_file_explorer import (
    get_access_token,
    get_user_info,
    list_dentries,
    explore_folder
)
from src.dingtalk_batch_processor import DingTalkBatchProcessor
from src.dingtalk_neo4j_importer import DingTalkNeo4jImporter
from collections import defaultdict

# 加载环境变量
load_dotenv(Path(__file__).parent / ".env")


class DingTalkPipeline:
    """钉盘文件处理流程"""
    
    def __init__(
        self,
        space_id: str = "24834926306",
        batch_size: int = 50,
        max_files: Optional[int] = None,
        resume: bool = True,
        import_to_neo4j: bool = True
    ):
        """
        初始化流程
        
        Args:
            space_id: 钉盘空间 ID
            batch_size: 每批处理的文件数量
            max_files: 最大处理文件数（None 表示处理所有）
            resume: 是否启用断点续传
            import_to_neo4j: 是否导入到 Neo4j
        """
        self.space_id = space_id
        self.batch_size = batch_size
        self.max_files = max_files
        self.resume = resume
        self.import_to_neo4j = import_to_neo4j
        
        # 数据存储路径
        self.data_dir = Path(__file__).parent / "data_storage"
        self.data_dir.mkdir(exist_ok=True)
        
        self.file_stats_path = self.data_dir / "dingtalk_file_stats.json"
        self.processing_results_path = self.data_dir / "dingtalk_processing_results.json"
        self.skipped_files_path = self.data_dir / "dingtalk_skipped_files.json"
        self.progress_path = self.data_dir / "dingtalk_progress.json"
        
        # 初始化处理器
        self.processor = DingTalkBatchProcessor(space_id)
        
        # 初始化 Neo4j 导入器
        self.neo4j_importer = None
        if self.import_to_neo4j:
            neo4j_uri = os.getenv("NEO4J_URI", "bolt://localhost:7688")
            neo4j_user = os.getenv("NEO4J_USER", "neo4j")
            neo4j_password = os.getenv("NEO4J_PASSWORD", "Root@12345678@")
            self.neo4j_importer = DingTalkNeo4jImporter(neo4j_uri, neo4j_user, neo4j_password)
    
    def step1_scan_files(self) -> Dict[str, Any]:
        """
        步骤 1: 扫描所有文件
        
        Returns:
            文件统计信息
        """
        print("=" * 80)
        print("步骤 1: 扫描钉盘所有文件")
        print("=" * 80)
        
        # 获取 access_token
        print("\n获取 access_token...")
        access_token = get_access_token()
        if not access_token:
            raise Exception("获取 access_token 失败")
        print("✅ 成功")
        
        # 获取 unionId
        print("\n获取 unionId...")
        union_id = os.getenv("DINGTALK_TEST_UNION_ID")
        if not union_id:
            union_id = get_user_info(access_token)
            if not union_id:
                raise Exception("获取 unionId 失败，请在 .env 中设置 DINGTALK_TEST_UNION_ID")
        print("✅ 成功")
        
        # 扫描文件
        print(f"\n扫描空间 {self.space_id} 的所有文件...")
        print("-" * 80)
        
        stats = {
            'folders': 0,
            'files': 0,
            'extensions': defaultdict(int),
            'categories': defaultdict(int),
            'total_size': 0,
            'examples': {}
        }
        all_files = []
        
        # 从根目录开始递归扫描
        explore_folder(
            access_token, self.space_id, union_id,
            "0", "Root", "/",
            max_depth=10,  # 最多 10 层
            current_depth=0,
            stats=stats,
            all_files=all_files
        )
        
        # 保存文件列表
        stats_json = {
            'folders': stats['folders'],
            'files': stats['files'],
            'total_size': stats['total_size'],
            'extensions': dict(stats['extensions']),
            'categories': dict(stats['categories']),
            'examples': stats['examples'],
            'all_files': all_files,
            'scan_time': datetime.utcnow().isoformat()
        }
        
        with open(self.file_stats_path, 'w', encoding='utf-8') as f:
            json.dump(stats_json, f, ensure_ascii=False, indent=2)
        
        print(f"\n✅ 扫描完成")
        print(f"  文件夹: {stats['folders']} 个")
        print(f"  文件: {stats['files']} 个")
        print(f"  总大小: {stats['total_size'] / (1024 * 1024):.2f} MB")
        print(f"  结果已保存到: {self.file_stats_path}")
        
        return stats_json
    
    def step2_process_files(self) -> Dict[str, Any]:
        """
        步骤 2: 分批处理文件
        
        Returns:
            处理统计信息
        """
        print("\n" + "=" * 80)
        print("步骤 2: 分批处理文件")
        print("=" * 80)
        
        # 加载文件列表
        if not self.file_stats_path.exists():
            raise Exception(f"文件列表不存在: {self.file_stats_path}，请先运行步骤 1")
        
        with open(self.file_stats_path, 'r', encoding='utf-8') as f:
            stats_data = json.load(f)
        
        all_files = stats_data.get('all_files', [])
        
        # 过滤支持的文件类型
        supported_files = [
            f for f in all_files 
            if f.get('extension', '').lower() in self.processor.supported_extensions
        ]
        
        # 排除跳过的文件类型
        supported_files = [
            f for f in supported_files
            if f.get('extension', '').lower() not in self.processor.skip_extensions
        ]
        
        print(f"\n总文件数: {len(all_files)}")
        print(f"支持的文件数: {len(supported_files)}")
        
        # 加载已处理的文件 ID（断点续传）
        processed_ids = set()
        if self.resume:
            # 从 Neo4j 加载已处理的文件
            if self.neo4j_importer:
                processed_ids = self.neo4j_importer.get_processed_file_ids()
                print(f"已处理的文件数（Neo4j）: {len(processed_ids)}")
            
            # 从本地结果文件加载
            if self.processing_results_path.exists():
                with open(self.processing_results_path, 'r', encoding='utf-8') as f:
                    results_data = json.load(f)
                    for result in results_data.get('results', []):
                        if result.get('status') == 'success':
                            processed_ids.add(result['file_id'])
                print(f"已处理的文件数（本地）: {len(processed_ids)}")
        
        # 过滤未处理的文件
        pending_files = [f for f in supported_files if f['id'] not in processed_ids]
        
        # 限制处理数量
        if self.max_files:
            pending_files = pending_files[:self.max_files]
        
        print(f"待处理的文件数: {len(pending_files)}")
        
        if len(pending_files) == 0:
            print("\n✅ 所有文件已处理完成")
            return {"status": "completed", "processed": 0}
        
        # 分批处理
        total_batches = (len(pending_files) + self.batch_size - 1) // self.batch_size
        print(f"批次数: {total_batches} (每批 {self.batch_size} 个文件)")
        
        all_results = []
        skipped_files = []
        
        # 创建总进度条
        if HAS_TQDM:
            total_pbar = tqdm(total=len(pending_files), desc="总进度", unit="文件", position=0)
        
        for batch_idx in range(total_batches):
            start_idx = batch_idx * self.batch_size
            end_idx = min(start_idx + self.batch_size, len(pending_files))
            batch_files = pending_files[start_idx:end_idx]
            
            print(f"\n{'=' * 80}")
            print(f"批次 {batch_idx + 1}/{total_batches}: 处理文件 {start_idx + 1}-{end_idx}/{len(pending_files)}")
            print(f"{'=' * 80}")
            
            batch_start_time = time.time()
            
            # 创建批次进度条
            if HAS_TQDM:
                batch_pbar = tqdm(batch_files, desc=f"批次 {batch_idx + 1}/{total_batches}", unit="文件", position=1, leave=False)
                file_iterator = batch_pbar
            else:
                file_iterator = batch_files
            
            for i, file_info in enumerate(file_iterator, 1):
                file_idx = start_idx + i
                
                if not HAS_TQDM:
                    print(f"\n[{file_idx}/{len(pending_files)}] 处理: {file_info['name']}")
                else:
                    if HAS_TQDM:
                        batch_pbar.set_description(f"批次 {batch_idx + 1}/{total_batches} - {file_info['name'][:30]}")
                
                # 处理文件
                result = self.processor.process_file(file_info)
                all_results.append(result)
                
                # 打印详细状态（非进度条模式）
                if not HAS_TQDM:
                    print(f"  状态: {result.status}")
                    if result.error:
                        print(f"  错误: {result.error}")
                    if result.status == 'success':
                        print(f"  分类: {result.category_l1} > {result.category_l2}")
                        print(f"  置信度: {result.category_confidence:.2f}")
                    print(f"  耗时: {result.processing_time:.2f}s")
                
                # 记录跳过的文件
                if result.status == 'skipped':
                    skipped_files.append({
                        "file_id": result.file_id,
                        "file_name": result.file_name,
                        "file_path": result.file_path,
                        "extension": result.extension,
                        "reason": result.error,
                        "skipped_at": datetime.utcnow().isoformat()
                    })
                
                # 导入到 Neo4j
                if self.import_to_neo4j and result.status == 'success' and self.neo4j_importer:
                    if not HAS_TQDM:
                        print(f"  导入 Neo4j...")
                    from dataclasses import asdict
                    success = self.neo4j_importer.import_file(asdict(result))
                    if not HAS_TQDM:
                        if success:
                            print(f"  ✅ Neo4j 导入成功")
                        else:
                            print(f"  ❌ Neo4j 导入失败")
                
                # 更新总进度条
                if HAS_TQDM:
                    total_pbar.update(1)
                    # 更新进度条后缀信息
                    success_count = sum(1 for r in all_results if r.status == 'success')
                    failed_count = sum(1 for r in all_results if r.status == 'failed')
                    skipped_count = sum(1 for r in all_results if r.status == 'skipped')
                    total_pbar.set_postfix({
                        '成功': success_count,
                        '失败': failed_count,
                        '跳过': skipped_count
                    })
            
            if HAS_TQDM:
                batch_pbar.close()
            
            batch_time = time.time() - batch_start_time
            print(f"\n批次 {batch_idx + 1} 完成，耗时: {batch_time:.2f}s")
            
            # 保存中间结果（断点续传）
            self._save_results(all_results, skipped_files)
            
            # 保存进度
            self._save_progress({
                "total_files": len(pending_files),
                "processed_files": end_idx,
                "current_batch": batch_idx + 1,
                "total_batches": total_batches,
                "last_update": datetime.utcnow().isoformat()
            })
        
        if HAS_TQDM:
            total_pbar.close()
        
        # 统计结果
        success_count = sum(1 for r in all_results if r.status == 'success')
        failed_count = sum(1 for r in all_results if r.status == 'failed')
        skipped_count = sum(1 for r in all_results if r.status == 'skipped')
        
        print(f"\n{'=' * 80}")
        print(f"处理完成")
        print(f"  成功: {success_count}")
        print(f"  失败: {failed_count}")
        print(f"  跳过: {skipped_count}")
        print(f"{'=' * 80}")
        
        return {
            "status": "completed",
            "processed": len(all_results),
            "success": success_count,
            "failed": failed_count,
            "skipped": skipped_count
        }
    
    def _save_results(self, results: List, skipped_files: List):
        """保存处理结果"""
        from dataclasses import asdict
        
        # 保存处理结果
        results_data = {
            "total": len(results),
            "success": sum(1 for r in results if r.status == 'success'),
            "failed": sum(1 for r in results if r.status == 'failed'),
            "skipped": sum(1 for r in results if r.status == 'skipped'),
            "last_update": datetime.utcnow().isoformat(),
            "results": [asdict(r) for r in results]
        }
        
        with open(self.processing_results_path, 'w', encoding='utf-8') as f:
            json.dump(results_data, f, ensure_ascii=False, indent=2)
        
        # 保存跳过的文件
        if skipped_files:
            skipped_data = {
                "total": len(skipped_files),
                "last_update": datetime.utcnow().isoformat(),
                "files": skipped_files
            }
            
            with open(self.skipped_files_path, 'w', encoding='utf-8') as f:
                json.dump(skipped_data, f, ensure_ascii=False, indent=2)
    
    def _save_progress(self, progress: Dict[str, Any]):
        """保存进度信息"""
        with open(self.progress_path, 'w', encoding='utf-8') as f:
            json.dump(progress, f, ensure_ascii=False, indent=2)
    
    def step3_show_statistics(self):
        """步骤 3: 显示统计信息"""
        print("\n" + "=" * 80)
        print("步骤 3: 统计信息")
        print("=" * 80)
        
        # 本地统计
        if self.processing_results_path.exists():
            with open(self.processing_results_path, 'r', encoding='utf-8') as f:
                results_data = json.load(f)
            
            print(f"\n本地处理结果:")
            print(f"  总计: {results_data['total']}")
            print(f"  成功: {results_data['success']}")
            print(f"  失败: {results_data['failed']}")
            print(f"  跳过: {results_data['skipped']}")
        
        # 跳过的文件统计
        if self.skipped_files_path.exists():
            with open(self.skipped_files_path, 'r', encoding='utf-8') as f:
                skipped_data = json.load(f)
            
            print(f"\n跳过的文件:")
            print(f"  总计: {skipped_data['total']}")
            
            # 按原因分组
            reasons = defaultdict(int)
            for file in skipped_data['files']:
                reason = file.get('reason', '未知原因')
                reasons[reason] += 1
            
            print(f"\n  按原因分组:")
            for reason, count in sorted(reasons.items(), key=lambda x: -x[1]):
                print(f"    {reason}: {count}")
        
        # Neo4j 统计
        if self.neo4j_importer:
            print(f"\nNeo4j 统计:")
            stats = self.neo4j_importer.get_statistics()
            print(f"  L1 类别: {stats['l1_categories']}")
            print(f"  L2 类别: {stats['l2_categories']}")
            print(f"  文件: {stats['files']}")
            
            if stats['files_by_l1']:
                print(f"\n  各 L1 类别文件数:")
                for item in stats['files_by_l1']:
                    print(f"    {item['category']}: {item['file_count']}")
    
    def run(self, steps: Optional[List[int]] = None):
        """
        运行完整流程
        
        Args:
            steps: 要运行的步骤列表（None 表示运行所有步骤）
        """
        if steps is None:
            steps = [1, 2, 3]
        
        try:
            if 1 in steps:
                self.step1_scan_files()
            
            if 2 in steps:
                self.step2_process_files()
            
            if 3 in steps:
                self.step3_show_statistics()
        
        finally:
            if self.neo4j_importer:
                self.neo4j_importer.close()


def main():
    parser = argparse.ArgumentParser(description="钉盘文件处理完整流程")
    parser.add_argument("--space-id", default="24834926306", help="钉盘空间 ID")
    parser.add_argument("--batch-size", type=int, default=50, help="每批处理的文件数量")
    parser.add_argument("--max-files", type=int, help="最大处理文件数")
    parser.add_argument("--no-resume", action="store_true", help="禁用断点续传")
    parser.add_argument("--no-neo4j", action="store_true", help="不导入到 Neo4j")
    parser.add_argument("--steps", type=str, default="1,2,3", help="要运行的步骤（逗号分隔，如 1,2,3）")
    
    args = parser.parse_args()
    
    # 解析步骤
    steps = [int(s.strip()) for s in args.steps.split(',') if s.strip()]
    
    # 创建流程
    pipeline = DingTalkPipeline(
        space_id=args.space_id,
        batch_size=args.batch_size,
        max_files=args.max_files,
        resume=not args.no_resume,
        import_to_neo4j=not args.no_neo4j
    )
    
    # 运行流程
    pipeline.run(steps=steps)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
测试钉盘处理流程
快速测试：处理前 3 个文件，不导入 Neo4j
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from run_dingtalk_pipeline import DingTalkPipeline


def main():
    print("=" * 80)
    print("钉盘处理流程测试")
    print("=" * 80)
    print("\n配置:")
    print("  - 最大文件数: 3")
    print("  - 批次大小: 3")
    print("  - 断点续传: 禁用")
    print("  - Neo4j 导入: 禁用")
    print()
    
    # 创建测试流程
    pipeline = DingTalkPipeline(
        space_id="24834926306",
        batch_size=3,
        max_files=3,
        resume=False,  # 禁用断点续传，每次都重新处理
        import_to_neo4j=False  # 禁用 Neo4j 导入
    )
    
    try:
        # 运行步骤 1 和 2
        print("开始测试...\n")
        pipeline.run(steps=[1, 2])
        
        print("\n" + "=" * 80)
        print("✅ 测试完成")
        print("=" * 80)
        print("\n查看结果:")
        print("  - 文件列表: backend/data_storage/dingtalk_file_stats.json")
        print("  - 处理结果: backend/data_storage/dingtalk_processing_results.json")
        print("  - 跳过文件: backend/data_storage/dingtalk_skipped_files.json")
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

import os
from collections import Counter
from pathlib import Path

def get_file_types_in_directory(directory_path):
    """
    递归读取指定文件夹中所有文件，统计文件类型
    
    Args:
        directory_path (str): 要扫描的文件夹路径
        
    Returns:
        dict: 文件类型统计结果
    """
    file_types = []
    file_count = 0
    
    # 使用pathlib递归遍历所有文件
    directory = Path(directory_path)
    
    if not directory.exists():
        print(f"错误：路径 '{directory_path}' 不存在")
        return {}
    
    if not directory.is_dir():
        print(f"错误：'{directory_path}' 不是一个文件夹")
        return {}
    
    print(f"正在扫描文件夹: {directory.absolute()}")
    print("-" * 50)
    
    # 递归遍历所有文件
    for file_path in directory.rglob('*'):
        if file_path.is_file():
            file_count += 1
            # 获取文件扩展名
            file_extension = file_path.suffix.lower()
            if file_extension:
                file_types.append(file_extension)
            else:
                file_types.append('(无扩展名)')
            
            # 显示文件路径（可选，注释掉以减少输出）
            # print(f"发现文件: {file_path.relative_to(directory)}")
    
    # 统计文件类型
    type_counter = Counter(file_types)
    
    print("-" * 50)
    print(f"扫描完成！共发现 {file_count} 个文件")
    print("\n文件类型统计:")
    print("=" * 30)
    
    # 按文件数量降序排列，只显示前20种最常见的文件类型
    print("前20种最常见的文件类型:")
    for i, (file_type, count) in enumerate(type_counter.most_common(20), 1):
        percentage = (count / file_count) * 100
        print(f"{i:>2}. {file_type:<15} : {count:>4} 个文件 ({percentage:>5.1f}%)")
    
    return dict(type_counter)

def main():
    """主函数"""
    import sys
    
    print("文件类型统计工具")
    print("=" * 50)
    
    # 检查命令行参数
    if len(sys.argv) > 1:
        target_directory = sys.argv[1]
    else:
        # 默认扫描当前目录
        target_directory = os.getcwd()
    
    print(f"扫描目录: {target_directory}")
    print()
    
    # 执行文件类型统计
    result = get_file_types_in_directory(target_directory)
    
    if result:
        print(f"\n总结: 该文件夹包含 {len(result)} 种不同的文件类型")
        
        # 显示最常见的文件类型
        most_common_type = max(result, key=result.get)
        print(f"最常见的文件类型: {most_common_type} ({result[most_common_type]} 个文件)")
        
        print(f"\n使用方法:")
        print(f"  python {sys.argv[0]}                    # 扫描当前目录")
        print(f"  python {sys.argv[0]} <目录路径>          # 扫描指定目录")
        print(f"  例如: python {sys.argv[0]} src/         # 扫描src文件夹")

if __name__ == "__main__":
    main()
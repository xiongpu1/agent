"""
删除指定文件夹及其子文件夹中除 .md 和 .json 之外的所有文件

使用示例:
    python delete_image_files.py <文件夹路径>
    python delete_image_files.py /path/to/folder
    
功能说明:
    - 递归遍历指定文件夹及其所有子文件夹
    - 查找并删除除 .md 和 .json 之外的所有文件（不区分大小写）
    - 保留 markdown (.md) 和 json (.json) 文件
    - 显示删除统计信息
    - 支持交互式确认（可选）
    - 生成删除日志

安全提示:
    - 删除操作不可逆，请谨慎使用
    - 建议先备份重要文件
"""

import os
import sys
from pathlib import Path
from datetime import datetime
from typing import List, Tuple


def find_files_to_delete(directory: Path) -> List[Path]:
    """
    递归查找指定目录中需要删除的文件（排除 .md 和 .json 文件）
    
    Args:
        directory: 要搜索的目录路径
        
    Returns:
        List[Path]: 找到的需要删除的文件路径列表（排除 .md 和 .json）
    """
    files_to_delete = []
    # 要保留的文件扩展名（不区分大小写）
    keep_extensions = {'.md', '.json'}
    
    if not directory.exists():
        print(f"错误: 路径 '{directory}' 不存在")
        return files_to_delete
    
    if not directory.is_dir():
        print(f"错误: '{directory}' 不是一个文件夹")
        return files_to_delete
    
    # 递归遍历所有文件，排除 .md 和 .json 文件
    for file_path in directory.rglob('*'):
        if file_path.is_file():
            suffix_lower = file_path.suffix.lower()
            # 如果文件扩展名不是 .md 或 .json，则加入删除列表
            if suffix_lower not in keep_extensions:
                files_to_delete.append(file_path)
    
    return files_to_delete


def delete_files(directory: str, confirm: bool = True, dry_run: bool = False) -> Tuple[int, int, List[str]]:
    """
    删除指定目录中除 .md 和 .json 之外的所有文件
    
    Args:
        directory: 要处理的目录路径
        confirm: 是否在删除前确认（默认 True）
        dry_run: 是否为试运行模式（只显示不删除，默认 False）
        
    Returns:
        Tuple[int, int, List[str]]: (成功删除数量, 失败数量, 失败文件列表)
    """
    directory_path = Path(directory).resolve()
    
    # 查找需要删除的文件（排除 .md 和 .json）
    print(f"正在扫描文件夹: {directory_path}")
    print("-" * 60)
    files_to_delete = find_files_to_delete(directory_path)
    
    if not files_to_delete:
        print("未找到需要删除的文件（所有文件都是 .md 或 .json）")
        return 0, 0, []
    
    print(f"找到 {len(files_to_delete)} 个需要删除的文件（将保留 .md 和 .json 文件）")
    print("-" * 60)
    
    # 显示前10个文件作为预览
    if len(files_to_delete) <= 10:
        print("\n所有文件列表:")
        for i, file_path in enumerate(files_to_delete, 1):
            rel_path = file_path.relative_to(directory_path)
            print(f"  {i}. {rel_path}")
    else:
        print("\n前10个文件预览:")
        for i, file_path in enumerate(files_to_delete[:10], 1):
            rel_path = file_path.relative_to(directory_path)
            print(f"  {i}. {rel_path}")
        print(f"  ... 还有 {len(files_to_delete) - 10} 个文件")
    
    # 确认删除
    if confirm and not dry_run:
        print("\n" + "=" * 60)
        response = input(f"确定要删除这 {len(files_to_delete)} 个文件吗？（将保留 .md 和 .json 文件）(yes/no): ").strip().lower()
        if response not in ['yes', 'y']:
            print("操作已取消")
            return 0, 0, []
    
    # 执行删除
    deleted_count = 0
    failed_count = 0
    failed_files = []
    
    print("\n开始删除文件...")
    print("-" * 60)
    
    for file_path in files_to_delete:
        rel_path = file_path.relative_to(directory_path)
        
        if dry_run:
            print(f"[试运行] 将删除: {rel_path}")
            deleted_count += 1
        else:
            try:
                file_path.unlink()
                print(f"  ✓ 已删除: {rel_path}")
                deleted_count += 1
            except Exception as e:
                print(f"  ✗ 删除失败: {rel_path} - {e}")
                failed_count += 1
                failed_files.append(str(file_path))
    
    return deleted_count, failed_count, failed_files


def generate_log(directory: str, deleted_count: int, failed_count: int, 
                 failed_files: List[str], files_to_delete: List[Path]) -> Path:
    """
    生成删除操作日志文件
    
    Args:
        directory: 处理的目录路径
        deleted_count: 成功删除的文件数量
        failed_count: 失败的文件数量
        failed_files: 失败的文件列表
        files_to_delete: 所有找到的需要删除的文件列表
        
    Returns:
        Path: 日志文件路径
    """
    log_dir = Path(directory).parent
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = log_dir / f"delete_files_log_{timestamp}.txt"
    
    log_content = []
    log_content.append("=" * 60)
    log_content.append("文件删除日志（保留 .md 和 .json 文件）")
    log_content.append("=" * 60)
    log_content.append(f"执行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log_content.append(f"目标目录: {directory}")
    log_content.append(f"找到文件数: {len(files_to_delete)}")
    log_content.append(f"成功删除: {deleted_count}")
    log_content.append(f"删除失败: {failed_count}")
    log_content.append("注意: 已保留所有 .md 和 .json 文件")
    log_content.append("")
    
    if failed_files:
        log_content.append("删除失败的文件:")
        log_content.append("-" * 60)
        for file_path in failed_files:
            log_content.append(f"  {file_path}")
        log_content.append("")
    
    log_content.append("所有处理的文件:")
    log_content.append("-" * 60)
    for file_path in files_to_delete:
        status = "✓" if str(file_path) not in failed_files else "✗"
        log_content.append(f"  {status} {file_path}")
    
    try:
        with open(log_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join(log_content))
        return log_file
    except Exception as e:
        print(f"保存日志文件时出错: {e}")
        return None


def main():
    """主函数"""
    print("文件删除工具（保留 .md 和 .json 文件）")
    print("=" * 60)
    
    # 解析命令行参数
    dry_run = '--dry-run' in sys.argv or '-n' in sys.argv
    no_confirm = '--yes' in sys.argv or '-y' in sys.argv
    
    # 获取目标目录
    target_directory = None
    for arg in sys.argv[1:]:
        if arg not in ['--dry-run', '-n', '--yes', '-y']:
            target_directory = arg
            break
    
    # 如果没有提供目录，提示用户输入
    if not target_directory:
        target_directory = input("请输入要处理的文件夹路径: ").strip()
    
    if not target_directory:
        print("错误: 未指定文件夹路径")
        print("\n使用方法:")
        print(f"  python {sys.argv[0]} <文件夹路径>")
        print(f"  python {sys.argv[0]} <文件夹路径> --dry-run    # 试运行模式（不实际删除）")
        print(f"  python {sys.argv[0]} <文件夹路径> --yes        # 跳过确认直接删除")
        sys.exit(1)
    
    # 检查目录是否存在
    if not os.path.isdir(target_directory):
        print(f"错误: 文件夹 '{target_directory}' 不存在或不是一个有效的目录")
        sys.exit(1)
    
    if dry_run:
        print("\n[试运行模式] 将显示要删除的文件，但不会实际删除")
    
    # 执行删除操作
    deleted_count, failed_count, failed_files = delete_files(
        target_directory, 
        confirm=not no_confirm,
        dry_run=dry_run
    )
    
    # 显示统计信息
    print("\n" + "=" * 60)
    print("删除操作完成!")
    print("-" * 60)
    print(f"成功删除: {deleted_count} 个文件")
    if failed_count > 0:
        print(f"删除失败: {failed_count} 个文件")
    print("注意: 已保留所有 .md 和 .json 文件")
    print("=" * 60)
    
    # 生成日志文件（仅在非试运行模式下）
    if not dry_run and deleted_count + failed_count > 0:
        directory_path = Path(target_directory).resolve()
        files_to_delete = find_files_to_delete(directory_path)
        log_file = generate_log(target_directory, deleted_count, failed_count, 
                               failed_files, files_to_delete)
        if log_file:
            print(f"\n日志已保存到: {log_file}")


if __name__ == "__main__":
    main()


"""
钉盘文件类型探测工具
探测指定文件夹的文件类型分布
"""
import os
import json
import time
import urllib.request
import urllib.parse
from pathlib import Path
from typing import Dict, List, Optional
from collections import defaultdict
from dotenv import load_dotenv

# 加载环境变量
load_dotenv(Path(__file__).parent.parent / ".env")

# 配置
SPACE_ID = "24834926306"  # Bellagio 产品资料

# 扫描模式：full = 全空间扫描，folders = 指定文件夹扫描
SCAN_MODE = os.getenv("DINGTALK_SCAN_MODE", "full")  # 默认全空间扫描

# 要探测的文件夹 (name -> id) - 仅在 folders 模式下使用
TARGET_FOLDERS = {
    "Manuals": "153014262199",
    "🔥Spa": "153015618839",
}


def get_access_token() -> Optional[str]:
    """获取钉钉 access_token"""
    app_key = os.getenv("DINGTALK_CLIENT_ID") or os.getenv("DINGTALK_APP_KEY")
    app_secret = os.getenv("DINGTALK_CLIENT_SECRET") or os.getenv("DINGTALK_APP_SECRET")
    
    if not app_key or not app_secret:
        return None
    
    url = f"https://oapi.dingtalk.com/gettoken?appkey={app_key}&appsecret={app_secret}"
    
    try:
        with urllib.request.urlopen(url, timeout=10) as response:
            data = json.loads(response.read().decode('utf-8'))
            
        if data.get('errcode') == 0:
            return data.get('access_token')
        return None
    except Exception:
        return None


def get_user_info(access_token: str) -> Optional[str]:
    """获取用户 unionId"""
    url = f"https://oapi.dingtalk.com/topapi/user/listadmin?access_token={access_token}"
    
    try:
        req = urllib.request.Request(url, method='POST')
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode('utf-8'))
        
        if data.get('errcode') == 0:
            result = data.get('result', {})
            if isinstance(result, dict):
                admins = result.get('adminList', [])
            else:
                admins = result if isinstance(result, list) else []
            
            if admins:
                admin_userid = admins[0] if isinstance(admins[0], str) else admins[0].get('userid')
                return get_user_detail(access_token, admin_userid)
        return None
    except Exception:
        return None


def get_user_detail(access_token: str, userid: str) -> Optional[str]:
    """获取用户详细信息"""
    url = f"https://oapi.dingtalk.com/topapi/v2/user/get?access_token={access_token}"
    
    data = json.dumps({"userid": userid}).encode('utf-8')
    headers = {'Content-Type': 'application/json'}
    
    try:
        req = urllib.request.Request(url, data=data, headers=headers, method='POST')
        with urllib.request.urlopen(req, timeout=10) as response:
            result = json.loads(response.read().decode('utf-8'))
        
        if result.get('errcode') == 0:
            user_info = result.get('result', {})
            return user_info.get('unionid')
        return None
    except Exception:
        return None


def list_dentries(access_token, space_id, union_id, parent_id="0", max_results=30):
    """
    获取钉钉存储空间的文件列表
    
    Args:
        access_token: 访问令牌
        space_id: 空间ID
        union_id: 用户 unionId
        parent_id: 父文件夹ID，0表示根目录
        max_results: 最大返回数量
    
    Returns:
        dict: API 响应结果
    """
    # 构建 URL
    base_url = f"https://api.dingtalk.com/v1.0/storage/spaces/{space_id}/dentries"
    
    # 查询参数
    params = {
        'unionId': union_id,
        'parentId': parent_id,
        'maxResults': max_results,
        'orderBy': 'MODIFIED_TIME',
        'order': 'DESC',
        'withThumbnail': 'false'
    }
    
    url = f"{base_url}?{urllib.parse.urlencode(params)}"
    
    # 请求头
    headers = {
        'x-acs-dingtalk-access-token': access_token,
        'Content-Type': 'application/json'
    }
    
    try:
        req = urllib.request.Request(url, headers=headers, method='GET')
        with urllib.request.urlopen(req, timeout=10) as response:
            result = json.loads(response.read().decode('utf-8'))
        return result
    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8', errors='replace')
        return {"error": f"HTTP {e.code}", "detail": error_body}
    except Exception as e:
        return {"error": str(e)}


def explore_folder(
    access_token: str,
    space_id: str,
    union_id: str,
    parent_id: str,
    parent_name: str,
    parent_path: str,
    max_depth: int,
    current_depth: int,
    stats: Dict,
    all_files: List[Dict]
) -> None:
    """递归探测文件夹"""
    if current_depth > max_depth:
        return
    
    indent = "  " * current_depth
    print(f"{indent}📂 探测: {parent_name} (depth={current_depth}, parent_id={parent_id})")
    
    # 添加重试逻辑
    max_retries = 3
    for attempt in range(max_retries):
        result = list_dentries(access_token, space_id, union_id, parent_id)
        
        if "error" in result:
            error_detail = result.get('detail', '')
            print(f"{indent}  ⚠️ 错误 (尝试 {attempt + 1}/{max_retries}): {result.get('error')}")
            if attempt < max_retries - 1:
                time.sleep(1)  # 等待1秒后重试
                continue
            else:
                print(f"{indent}  ❌ 最终失败: {error_detail[:200]}")
                return
        
        if "dentries" not in result:
            print(f"{indent}  ⚠️ 无 dentries 字段")
            return
        
        # 成功获取数据，跳出重试循环
        break
    
    dentries = result.get('dentries', [])
    print(f"{indent}  找到 {len(dentries)} 个项目")
    
    for entry in dentries:
        entry_type = entry.get('type', 'UNKNOWN')
        entry_name = entry.get('name', 'Unnamed')
        entry_id = entry.get('id', 'N/A')
        entry_path = f"{parent_path}/{entry_name}"
        
        if entry_type == 'FOLDER':
            stats['folders'] += 1
            print(f"{indent}  📁 {entry_name} (id={entry_id})")
            
            # 递归探测子文件夹
            if current_depth < max_depth:
                time.sleep(0.2)  # 避免请求过快
                explore_folder(
                    access_token, space_id, union_id,
                    entry_id, entry_name, entry_path,
                    max_depth, current_depth + 1, stats, all_files
                )
        
        elif entry_type == 'FILE':
            stats['files'] += 1
            extension = entry.get('extension', 'no_ext')
            category = entry.get('category', 'UNKNOWN')
            size = entry.get('size', 0)
            
            # 统计
            stats['extensions'][extension] += 1
            stats['categories'][category] += 1
            stats['total_size'] += size
            
            # 记录文件信息
            file_info = {
                'id': entry_id,
                'name': entry_name,
                'path': entry_path,
                'extension': extension,
                'category': category,
                'size': size,
                'modifiedTime': entry.get('modifiedTime', ''),
                'parent_folder': parent_name,
                'space_id': space_id
            }
            all_files.append(file_info)
            
            # 记录示例
            if extension not in stats['examples']:
                stats['examples'][extension] = []
            if len(stats['examples'][extension]) < 3:
                stats['examples'][extension].append(file_info)
            
            size_mb = size / (1024 * 1024)
            size_str = f"{size_mb:.2f}MB" if size_mb >= 1 else f"{size / 1024:.2f}KB"
            print(f"{indent}  📄 {entry_name} (.{extension}, {category}, {size_str})")


def main():
    print("=" * 80)
    print("🔍 钉盘文件类型探测工具 V2")
    print("=" * 80)
    
    # 1. 获取 access_token
    print("\n步骤 1: 获取 access_token")
    access_token = get_access_token()
    if not access_token:
        print("❌ 失败")
        return
    print("✅ 成功")
    
    # 2. 获取 unionId
    print("\n步骤 2: 获取 unionId")
    union_id = get_user_info(access_token)
    if not union_id:
        print("❌ 失败")
        return
    print("✅ 成功")
    
    # 3. 探测文件类型
    print(f"\n步骤 3: 探测文件类型 (模式: {SCAN_MODE})")
    print("=" * 80)
    
    stats = {
        'folders': 0,
        'files': 0,
        'extensions': defaultdict(int),
        'categories': defaultdict(int),
        'total_size': 0,
        'examples': {}
    }
    all_files = []
    
    if SCAN_MODE == "full":
        # 全空间扫描：从根目录开始
        print(f"\n🎯 全空间扫描: 从根目录开始")
        print("-" * 80)
        explore_folder(
            access_token, SPACE_ID, union_id,
            "0", "Root", "/",
            max_depth=10,  # 最多探测 10 层
            current_depth=0,
            stats=stats,
            all_files=all_files
        )
    else:
        # 指定文件夹扫描
        for folder_name, folder_id in TARGET_FOLDERS.items():
            print(f"\n🎯 探测文件夹: {folder_name}")
            print("-" * 80)
            explore_folder(
                access_token, SPACE_ID, union_id,
                folder_id, folder_name, f"/{folder_name}",
                max_depth=2,  # 最多探测 2 层
                current_depth=0,
                stats=stats,
                all_files=all_files
            )
    
    # 4. 显示统计结果
    print("\n" + "=" * 80)
    print("📊 统计结果")
    print("=" * 80)
    
    print(f"\n总计:")
    print(f"  文件夹: {stats['folders']} 个")
    print(f"  文件: {stats['files']} 个")
    print(f"  总大小: {stats['total_size'] / (1024 * 1024):.2f} MB")
    
    print(f"\n文件扩展名分布:")
    for ext, count in sorted(stats['extensions'].items(), key=lambda x: -x[1]):
        print(f"  .{ext}: {count} 个")
    
    print(f"\n文件类别分布:")
    for cat, count in sorted(stats['categories'].items(), key=lambda x: -x[1]):
        print(f"  {cat}: {count} 个")
    
    print(f"\n示例文件 (每种扩展名最多3个):")
    for ext, examples in sorted(stats['examples'].items()):
        print(f"\n  扩展名: .{ext}")
        for ex in examples[:3]:
            print(f"    - {ex['name']}")
            print(f"      路径: {ex['path']}")
            print(f"      大小: {ex['size'] / 1024:.2f} KB")
            print(f"      类别: {ex['category']}")
    
    # 5. 保存结果到统一的 data_storage 目录
    output_file = Path(__file__).parent.parent / "data_storage" / "dingtalk_file_stats.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        stats_json = {
            'folders': stats['folders'],
            'files': stats['files'],
            'total_size': stats['total_size'],
            'extensions': dict(stats['extensions']),
            'categories': dict(stats['categories']),
            'examples': stats['examples'],
            'all_files': all_files
        }
        json.dump(stats_json, f, ensure_ascii=False, indent=2)
    
    print(f"\n💾 统计结果已保存到: {output_file}")
    print("=" * 80)


if __name__ == "__main__":
    main()

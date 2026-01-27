"""
钉钉存储 API 测试 - 使用正确的 storage API
API: GET /v1.0/storage/spaces/{spaceId}/dentries
"""
import os
import json
import urllib.request
import urllib.parse
from pathlib import Path
from dotenv import load_dotenv

# 加载环境变量
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

# 配置 spaceId
SPACE_ID = "24834926306"  # Bellagio 产品资料


def get_access_token():
    """获取钉钉 access_token"""
    app_key = os.getenv("DINGTALK_CLIENT_ID") or os.getenv("DINGTALK_APP_KEY")
    app_secret = os.getenv("DINGTALK_CLIENT_SECRET") or os.getenv("DINGTALK_APP_SECRET")
    
    if not app_key or not app_secret:
        print("❌ 错误: 未配置钉钉应用凭证")
        return None
    
    url = f"https://oapi.dingtalk.com/gettoken?appkey={app_key}&appsecret={app_secret}"
    
    try:
        with urllib.request.urlopen(url, timeout=10) as response:
            data = json.loads(response.read().decode('utf-8'))
            
        if data.get('errcode') == 0:
            token = data.get('access_token')
            print(f"✅ 成功获取 access_token: {token[:20]}...")
            return token
        else:
            print(f"❌ 获取 access_token 失败: {data}")
            return None
    except Exception as e:
        print(f"❌ 请求失败: {e}")
        return None


def get_user_info(access_token):
    """
    获取当前用户信息（需要先通过免登获取 auth_code）
    这里我们使用一个简化的方法：直接使用管理员的 userid
    """
    # 方法1: 如果你知道管理员的 userid，可以直接获取
    # 这里我们尝试获取企业管理员列表
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
                # 获取第一个管理员的详细信息
                admin_userid = admins[0] if isinstance(admins[0], str) else admins[0].get('userid')
                return get_user_detail(access_token, admin_userid)
        
        return None
    except Exception as e:
        print(f"⚠️ 获取管理员信息失败: {e}")
        return None


def get_user_detail(access_token, userid):
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
    except Exception as e:
        print(f"⚠️ 获取用户详情失败: {e}")
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


def display_dentries(dentries):
    """显示文件列表"""
    if not dentries:
        print("📭 没有找到文件")
        return
    
    print(f"\n📁 找到 {len(dentries)} 个文件/文件夹:")
    print("=" * 80)
    
    for idx, entry in enumerate(dentries, 1):
        entry_type = entry.get('type', 'UNKNOWN')
        entry_name = entry.get('name', 'Unnamed')
        entry_id = entry.get('id', 'N/A')
        entry_size = entry.get('size', 0)
        modified_time = entry.get('modifiedTime', 'N/A')
        
        # 类型图标
        type_icon = {
            'FILE': '📄',
            'FOLDER': '📁',
        }.get(entry_type, '📎')
        
        # 文件大小格式化
        if entry_type == 'FILE' and entry_size:
            size_mb = entry_size / (1024 * 1024)
            size_str = f"{size_mb:.2f} MB" if size_mb >= 1 else f"{entry_size / 1024:.2f} KB"
        else:
            size_str = "-"
        
        print(f"{idx}. {type_icon} {entry_name}")
        print(f"   ID: {entry_id} | 类型: {entry_type} | 大小: {size_str}")
        print(f"   修改时间: {modified_time}")
        
        # 显示文件夹子项数量
        if entry_type == 'FOLDER':
            app_props = entry.get('appProperties', {}).get('pZcQS2Q25Bfq1qzCceiS3E9qpSLtQCkwe', [])
            for prop in app_props:
                if prop.get('name') == 'folderChildrenCount':
                    folder_count = prop.get('value', '0')
                    print(f"   📁 子文件夹: {folder_count} 个")
                elif prop.get('name') == 'fileChildrenCount':
                    file_count = prop.get('value', '0')
                    print(f"   📄 文件: {file_count} 个")
        
        print()


def main():
    print("=" * 80)
    print("🧪 钉钉存储 API 测试")
    print("=" * 80)
    
    # 1. 获取 access_token
    print("\n步骤 1: 获取 access_token")
    access_token = get_access_token()
    if not access_token:
        return
    
    # 2. 获取用户 unionId
    print("\n步骤 2: 获取用户 unionId")
    union_id = get_user_info(access_token)
    if not union_id:
        print("❌ 无法获取 unionId")
        print("\n💡 提示: 你可以手动设置 unionId")
        print("   1. 在钉钉开放平台获取你的 unionId")
        print("   2. 或者在代码中直接设置 union_id 变量")
        return
    
    print(f"✅ 成功获取 unionId: {union_id[:20]}...")
    
    # 3. 获取文件列表
    print(f"\n步骤 3: 获取文件列表 (spaceId={SPACE_ID})")
    result = list_dentries(access_token, SPACE_ID, union_id)
    
    # 4. 显示结果
    print("\n" + "=" * 80)
    print("📊 测试结果:")
    print("=" * 80)
    
    if "error" in result:
        print(f"\n❌ 请求失败:")
        print(f"   错误: {result.get('error')}")
        print(f"   详情: {result.get('detail', 'N/A')}")
    elif "dentries" in result:
        print("\n✅ 成功获取文件列表！")
        dentries = result.get('dentries', [])
        display_dentries(dentries)
        
        print("=" * 80)
        print("✅ 测试成功！钉钉存储 API 可以正常使用。")
        print("=" * 80)
        
        # 保存结果到文件
        output_file = Path(__file__).parent / "dingtalk_files_list.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"\n💾 完整结果已保存到: {output_file}")
        
    else:
        print(f"\n⚠️ 未知响应格式:")
        print(json.dumps(result, indent=2, ensure_ascii=False))
    
    print("\n" + "=" * 80)
    print("📋 下一步:")
    print("=" * 80)
    print("\n现在你可以:")
    print("1. 实现文件下载功能")
    print("2. 实现文件夹遍历功能")
    print("3. 集成到现有的 OCR 处理流程")
    print("4. 添加前端文件选择器")
    print("=" * 80)


if __name__ == "__main__":
    main()

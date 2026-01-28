"""
钉盘文件下载模块
提供完整的文件下载功能
"""
import os
import json
import urllib.request
import urllib.parse
import tempfile
from pathlib import Path
from typing import Optional, Dict, Any, BinaryIO
from dotenv import load_dotenv

# 加载环境变量
load_dotenv(Path(__file__).parent.parent / ".env")


class DingTalkDownloader:
    """钉盘文件下载器"""
    
    def __init__(self, space_id: str = "24834926306"):
        """
        初始化下载器
        
        Args:
            space_id: 钉盘空间ID
        """
        self.space_id = space_id
        self.access_token = None
        self.union_id = None
        
        # 从环境变量加载配置
        self.app_key = os.getenv("DINGTALK_CLIENT_ID")
        self.app_secret = os.getenv("DINGTALK_CLIENT_SECRET")
        self.test_union_id = os.getenv("DINGTALK_TEST_UNION_ID")
        
        if not self.app_key or not self.app_secret:
            raise ValueError("未配置钉钉应用凭证 (DINGTALK_CLIENT_ID, DINGTALK_CLIENT_SECRET)")
    
    def refresh_access_token(self) -> Optional[str]:
        """
        强制刷新 access_token（不使用缓存）
        
        Returns:
            新的 access_token 或 None
        """
        url = f"https://oapi.dingtalk.com/gettoken?appkey={self.app_key}&appsecret={self.app_secret}"
        
        try:
            with urllib.request.urlopen(url, timeout=10) as response:
                data = json.loads(response.read().decode('utf-8'))
                
            if data.get('errcode') == 0:
                self.access_token = data.get('access_token')
                print(f"✓ 已刷新 access_token")
                return self.access_token
            else:
                print(f"获取 access_token 失败: {data}")
                return None
        except Exception as e:
            print(f"获取 access_token 异常: {e}")
            return None
    
    def get_access_token(self, force_refresh: bool = False) -> Optional[str]:
        """
        获取钉钉 access_token
        
        Args:
            force_refresh: 是否强制刷新 token
        
        Returns:
            access_token 或 None
        """
        if force_refresh or not self.access_token:
            return self.refresh_access_token()
        
        return self.access_token
    
    def get_union_id(self) -> Optional[str]:
        """
        获取 unionId
        
        Returns:
            unionId 或 None
        """
        if self.union_id:
            return self.union_id
        
        # 使用测试unionId
        if self.test_union_id:
            self.union_id = self.test_union_id
            return self.union_id
        
        print("警告: 未设置 DINGTALK_TEST_UNION_ID，无法下载文件")
        return None
    
    def get_download_info(self, file_id: str, retry_on_auth_error: bool = True) -> Optional[Dict[str, Any]]:
        """
        获取文件下载信息
        
        Args:
            file_id: 文件ID
            retry_on_auth_error: 认证失败时是否自动重试
            
        Returns:
            下载信息字典 或 None
        """
        access_token = self.get_access_token()
        union_id = self.get_union_id()
        
        if not access_token or not union_id:
            return None
        
        base_url = f"https://api.dingtalk.com/v1.0/storage/spaces/{self.space_id}/dentries/{file_id}/downloadInfos/query"
        params = {'unionId': union_id}
        url = f"{base_url}?{urllib.parse.urlencode(params)}"
        
        headers = {
            'x-acs-dingtalk-access-token': access_token,
            'Content-Type': 'application/json'
        }
        
        body = {
            "option": {
                "version": 1,
                "preferIntranet": False
            }
        }
        
        try:
            data = json.dumps(body).encode('utf-8')
            req = urllib.request.Request(url, data=data, headers=headers, method='POST')
            with urllib.request.urlopen(req, timeout=30) as response:
                result = json.loads(response.read().decode('utf-8'))
                return result
        except urllib.error.HTTPError as e:
            error_body = e.read().decode('utf-8', errors='replace')
            
            # 检查是否是认证错误
            if e.code == 400 and retry_on_auth_error:
                try:
                    error_data = json.loads(error_body)
                    if error_data.get('code') == 'InvalidAuthentication':
                        print(f"⚠️ access_token 已过期，正在刷新...")
                        # 刷新 token 并重试
                        if self.get_access_token(force_refresh=True):
                            return self.get_download_info(file_id, retry_on_auth_error=False)
                except:
                    pass
            
            print(f"获取下载信息失败 (HTTP {e.code}): {error_body}")
            return None
        except Exception as e:
            print(f"获取下载信息异常: {e}")
            return None
    
    def get_open_url(self, file_id: str, open_type: str = 'PREVIEW', retry_on_auth_error: bool = True) -> Optional[str]:
        """
        获取文件预览/编辑链接
        
        Args:
            file_id: 文件ID
            open_type: 打开类型，'PREVIEW' 或 'EDIT'
            retry_on_auth_error: 认证失败时是否自动重试
            
        Returns:
            文件链接 或 None
        """
        access_token = self.get_access_token()
        union_id = self.get_union_id()
        
        if not access_token or not union_id:
            return None
        
        base_url = f"https://api.dingtalk.com/v1.0/storage/spaces/{self.space_id}/dentries/{file_id}/openInfos/query"
        params = {'unionId': union_id}
        url = f"{base_url}?{urllib.parse.urlencode(params)}"
        
        headers = {
            'x-acs-dingtalk-access-token': access_token,
            'Content-Type': 'application/json'
        }
        
        body = {
            "option": {
                "version": 1,
                "type": open_type,
                "waterMark": True,
                "checkLogin": False  # 改为 False，允许无需登录访问
            }
        }
        
        try:
            data = json.dumps(body).encode('utf-8')
            req = urllib.request.Request(url, data=data, headers=headers, method='POST')
            with urllib.request.urlopen(req, timeout=30) as response:
                result = json.loads(response.read().decode('utf-8'))
                return result.get('url')
        except urllib.error.HTTPError as e:
            error_body = e.read().decode('utf-8', errors='replace')
            
            # 检查是否是认证错误
            if e.code == 400 and retry_on_auth_error:
                try:
                    error_data = json.loads(error_body)
                    if error_data.get('code') == 'InvalidAuthentication':
                        print(f"⚠️ access_token 已过期，正在刷新...")
                        # 刷新 token 并重试
                        if self.get_access_token(force_refresh=True):
                            return self.get_open_url(file_id, open_type, retry_on_auth_error=False)
                except:
                    pass
            
            print(f"获取文件链接失败 (HTTP {e.code}): {error_body}")
            return None
        except Exception as e:
            print(f"获取文件链接异常: {e}")
            return None
    
    def get_download_url(self, file_id: str, expire_seconds: int = 3600) -> Optional[str]:
        """
        获取文件临时下载链接（有效期内可直接访问）
        
        Args:
            file_id: 文件ID
            expire_seconds: 链接有效期（秒），默认 1 小时
            
        Returns:
            下载链接 或 None
        """
        download_info = self.get_download_info(file_id)
        if not download_info:
            return None
        
        protocol = download_info.get('protocol')
        
        if protocol != 'HEADER_SIGNATURE':
            print(f"不支持的协议类型: {protocol}")
            return None
        
        header_info = download_info.get('headerSignatureInfo', {})
        resource_urls = header_info.get('resourceUrls', [])
        
        if not resource_urls:
            print("未找到下载URL")
            return None
        
        # 返回第一个下载URL（这是带签名的临时链接）
        return resource_urls[0]
    
    def download_file_to_bytes(self, file_id: str) -> Optional[bytes]:
        """
        下载文件到内存
        
        Args:
            file_id: 文件ID
            
        Returns:
            文件内容（bytes）或 None
        """
        download_info = self.get_download_info(file_id)
        if not download_info:
            return None
        
        protocol = download_info.get('protocol')
        
        if protocol != 'HEADER_SIGNATURE':
            print(f"不支持的协议类型: {protocol}")
            return None
        
        header_info = download_info.get('headerSignatureInfo', {})
        headers = header_info.get('headers', {})
        resource_urls = header_info.get('resourceUrls', [])
        
        if not resource_urls:
            print("未找到下载URL")
            return None
        
        download_url = resource_urls[0]
        
        try:
            req = urllib.request.Request(download_url, method='GET')
            for key, value in headers.items():
                req.add_header(key, value)
            
            with urllib.request.urlopen(req, timeout=60) as response:
                return response.read()
        except urllib.error.HTTPError as e:
            error_body = e.read().decode('utf-8', errors='replace')
            print(f"下载文件失败 (HTTP {e.code}): {error_body}")
            return None
        except Exception as e:
            print(f"下载文件异常: {e}")
            return None
    
    def download_file_to_path(self, file_id: str, output_path: Path) -> bool:
        """
        下载文件到指定路径
        
        Args:
            file_id: 文件ID
            output_path: 输出文件路径
            
        Returns:
            是否成功
        """
        content = self.download_file_to_bytes(file_id)
        if not content:
            return False
        
        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, 'wb') as f:
                f.write(content)
            return True
        except Exception as e:
            print(f"保存文件失败: {e}")
            return False
    
    def download_file_to_temp(self, file_id: str, suffix: str = "") -> Optional[Path]:
        """
        下载文件到临时文件
        
        Args:
            file_id: 文件ID
            suffix: 文件后缀（如 .pdf）
            
        Returns:
            临时文件路径 或 None
        """
        content = self.download_file_to_bytes(file_id)
        if not content:
            return None
        
        try:
            # 创建临时文件
            fd, temp_path = tempfile.mkstemp(suffix=suffix)
            with os.fdopen(fd, 'wb') as f:
                f.write(content)
            return Path(temp_path)
        except Exception as e:
            print(f"创建临时文件失败: {e}")
            return None
    
    def download_file_stream(self, file_id: str) -> Optional[BinaryIO]:
        """
        下载文件并返回文件流（用于流式处理）
        
        Args:
            file_id: 文件ID
            
        Returns:
            文件流 或 None
        """
        content = self.download_file_to_bytes(file_id)
        if not content:
            return None
        
        try:
            import io
            return io.BytesIO(content)
        except Exception as e:
            print(f"创建文件流失败: {e}")
            return None


if __name__ == "__main__":
    pass


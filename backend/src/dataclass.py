from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional, Any

@dataclass
class LLMConfig:
    """文本LLM配置"""
    model: str  # 模型名称
    api_key: Optional[str] = None  # API密钥（可选）
    base_url: Optional[str] = None  # API base URL（可选）

@dataclass
class Neo4jConfig:
    """Neo4j数据库配置"""
    uri: str  # Neo4j URI
    user: str  # 用户名
    password: str  # 密码

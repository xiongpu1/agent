"""Base agent class for all ACE agents"""
from abc import ABC, abstractmethod
from typing import Dict, Any
from ..utils.llm_client import LLMClient
from ..config import ModelConfig


class BaseAgent(ABC):
    """Abstract base class for ACE agents"""
    
    def __init__(self, config: ModelConfig):
        self.config = config
        self.llm_client = LLMClient(
            api_key=config.api_key,
            model_name=config.name,
            base_url=config.base_url,
        )
    
    @abstractmethod
    def _build_prompt(self, **kwargs) -> str:
        """Build prompt for the agent"""
        pass
    
    @abstractmethod
    def _parse_response(self, response: Dict[str, Any]) -> Dict[str, Any]:
        """Parse and validate LLM response"""
        pass
    
    def execute(self, **kwargs) -> Dict[str, Any]:
        """
        Execute agent logic
        
        Returns:
            Parsed response or error dict
        """
        prompt = self._build_prompt(**kwargs)
        
        response = self.llm_client.generate_with_retry(
            prompt=prompt,
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens
        )
        
        if response is None:
            return self._get_error_response()
        
        return self._parse_response(response)
    
    @abstractmethod
    def _get_error_response(self) -> Dict[str, Any]:
        """Get default error response"""
        pass
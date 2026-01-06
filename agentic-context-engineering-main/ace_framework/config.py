"""Configuration management for ACE Framework"""
import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class ModelConfig:
    """LLM model configuration

    Defaults now align with the qwen3-max model used by the specsheet
    generator so ACE can reuse the same vendor credentials. All values can
    still be overridden via environment variables or explicit constructor
    arguments.
    """

    name: str = os.environ.get("ACE_LLM_MODEL", "dashscope/qwen3-max")
    temperature: float = 0.5  # Increased for better reasoning
    max_tokens: int = 1500  # More tokens for detailed reasoning
    api_key: Optional[str] = None
    base_url: Optional[str] = None

    def __post_init__(self):
        env_model = os.environ.get("ACE_LLM_MODEL")
        if env_model:
            self.name = env_model

        if self.base_url is None:
            self.base_url = os.environ.get("ACE_LLM_BASE_URL")

        if self.name.startswith("dashscope/"):
            if self.base_url is None:
                self.base_url = os.environ.get(
                    "DASHSCOPE_API_BASE_URL",
                    "https://dashscope.aliyuncs.com/compatible-mode/v1",
                )
            if self.api_key is None:
                self.api_key = os.environ.get("DASHSCOPE_API_KEY")
        else:
            if self.base_url is None:
                self.base_url = os.environ.get(
                    "OLLAMA_BASE_URL",
                    "http://localhost:11434",
                )
            if self.api_key is None:
                # Preserve legacy Groq fallback for backwards compatibility.
                self.api_key = os.environ.get("OLLAMA_API_KEY") or os.environ.get(
                    "GROQ_API_KEY"
                )

        if self.base_url:
            self.base_url = self.base_url.rstrip("/")


@dataclass
class ExperimentConfig:
    """Experiment configuration"""
    dataset_path: str = "./hotpotqa_subset"
    num_samples: int = 25
    checkpoint_interval: int = 10
    output_dir: str = "./results"
    playbook_filename: str = "ace_playbook.json"
    metrics_filename: str = "metrics.json"
    plot_filename: str = "accuracy_plot.png"
    
    def __post_init__(self):
        os.makedirs(self.output_dir, exist_ok=True)


@dataclass
class PromptConfig:
    """Prompt templates configuration"""
    generator_sections: list = None
    reflector_sections: list = None
    curator_sections: list = None
    
    def __post_init__(self):
        if self.generator_sections is None:
            self.generator_sections = [
                "multi_hop_reasoning",
                "entity_extraction",
                "fact_verification",
                "common_mistakes"
            ]
        if self.reflector_sections is None:
            self.reflector_sections = self.generator_sections
        if self.curator_sections is None:
            self.curator_sections = self.generator_sections


class Config:
    """Main configuration class"""
    def __init__(
        self,
        model_config: Optional[ModelConfig] = None,
        experiment_config: Optional[ExperimentConfig] = None,
        prompt_config: Optional[PromptConfig] = None
    ):
        self.model = model_config or ModelConfig()
        self.experiment = experiment_config or ExperimentConfig()
        self.prompt = prompt_config or PromptConfig()
    
    @classmethod
    def default(cls) -> "Config":
        """Create default configuration"""
        return cls()
    
    @classmethod
    def from_dict(cls, config_dict: dict) -> "Config":
        """Create configuration from dictionary"""
        return cls(
            model_config=ModelConfig(**config_dict.get("model", {})),
            experiment_config=ExperimentConfig(**config_dict.get("experiment", {})),
            prompt_config=PromptConfig(**config_dict.get("prompt", {}))
        )
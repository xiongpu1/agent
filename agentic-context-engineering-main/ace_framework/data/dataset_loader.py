"""Dataset loading and preprocessing"""
from typing import Dict, Any, Iterator
from datasets import load_from_disk, Dataset
import logging

logger = logging.getLogger(__name__)


class DatasetLoader:
    """Handles loading and preprocessing of datasets"""
    
    def __init__(self, dataset_path: str):
        self.dataset_path = dataset_path
        self.dataset: Dataset = None
    
    def load(self) -> Dataset:
        """Load dataset from disk"""
        try:
            self.dataset = load_from_disk(self.dataset_path)
            logger.info(f"Loaded dataset with {len(self.dataset)} samples")
            return self.dataset
        except Exception as e:
            logger.error(f"Failed to load dataset: {e}")
            raise
    
    def get_sample(self, index: int) -> Dict[str, Any]:
        """
        Get a single preprocessed sample
        
        Args:
            index: Sample index
            
        Returns:
            Dictionary with question, context, and answer
        """
        if self.dataset is None:
            raise ValueError("Dataset not loaded. Call load() first.")
        
        sample = self.dataset[index]
        return self.preprocess_sample(sample)
    
    def iterate_samples(self, num_samples: int = None) -> Iterator[Dict[str, Any]]:
        """
        Iterate over samples
        
        Args:
            num_samples: Number of samples to iterate (None for all)
            
        Yields:
            Preprocessed sample dictionaries
        """
        if self.dataset is None:
            raise ValueError("Dataset not loaded. Call load() first.")
        
        total_samples = len(self.dataset)
        if num_samples is None:
            num_samples = total_samples
        else:
            num_samples = min(num_samples, total_samples)
        
        for i in range(num_samples):
            yield self.get_sample(i)
    
    @staticmethod
    def preprocess_sample(sample: Dict[str, Any]) -> Dict[str, Any]:
        """
        Preprocess a raw sample
        
        Args:
            sample: Raw sample from dataset
            
        Returns:
            Dictionary with question, context, and answer
        """
        # Extract context from nested structure
        context_sentences = sample.get("context", {}).get("sentences", [])
        context = " ".join([" ".join(ctx) for ctx in context_sentences])
        
        return {
            "question": sample.get("question", ""),
            "context": context,
            "answer": sample.get("answer", "")
        }
    
    def __len__(self) -> int:
        """Get dataset size"""
        if self.dataset is None:
            return 0
        return len(self.dataset)
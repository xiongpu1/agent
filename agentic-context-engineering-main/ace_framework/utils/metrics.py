"""Metrics tracking and management"""
import json
from typing import Dict, Any, List
from pathlib import Path


class MetricsTracker:
    """Tracks performance metrics during ACE execution"""
    
    def __init__(self):
        self.processed = 0
        self.correct = 0
        self.playbook_updates = 0
        self.history: List[Dict[str, Any]] = []
    
    def record_result(
        self,
        question: str,
        predicted: str,
        ground_truth: str,
        is_correct: bool,
        playbook_size: int,
        algo_evaluation: Dict[str, Any] | None = None,
    ) -> None:
        """Record a single result"""
        self.processed += 1
        if is_correct:
            self.correct += 1
        
        record: Dict[str, Any] = {
            "step": self.processed,
            "question": question,
            "predicted": predicted,
            "ground_truth": ground_truth,
            "correct": is_correct,
            "accuracy": self.get_accuracy(),
            "playbook_size": playbook_size
        }
        if algo_evaluation is not None:
            record["algo_evaluation"] = algo_evaluation
        self.history.append(record)
    
    def record_playbook_update(self) -> None:
        """Record a playbook update"""
        self.playbook_updates += 1
    
    def get_accuracy(self) -> float:
        """Calculate current accuracy"""
        if self.processed == 0:
            return 0.0
        return (self.correct / self.processed) * 100
    
    def get_accuracy_history(self) -> List[float]:
        """Get accuracy at each step"""
        return [record["accuracy"] for record in self.history]
    
    def get_playbook_size_history(self) -> List[int]:
        """Get playbook size at each step"""
        return [record["playbook_size"] for record in self.history]

    def get_algo_score_history(self) -> List[float]:
        scores: List[float] = []
        for record in self.history:
            algo = record.get("algo_evaluation")
            if isinstance(algo, dict) and isinstance(algo.get("score"), (int, float)):
                scores.append(float(algo["score"]))
            else:
                scores.append(float("nan"))
        return scores
    
    def get_summary(self) -> Dict[str, Any]:
        """Get summary statistics"""
        return {
            "total_processed": self.processed,
            "total_correct": self.correct,
            "final_accuracy": self.get_accuracy(),
            "playbook_updates": self.playbook_updates,
            "accuracy_history": self.get_accuracy_history(),
            "playbook_size_history": self.get_playbook_size_history(),
            "algo_score_history": self.get_algo_score_history(),
        }
    
    def save(self, filepath: str) -> None:
        """Save metrics to JSON file"""
        Path(filepath).parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, 'w') as f:
            json.dump({
                "summary": self.get_summary(),
                "detailed_history": self.history
            }, f, indent=2)
    
    def load(self, filepath: str) -> None:
        """Load metrics from JSON file"""
        with open(filepath, 'r') as f:
            data = json.load(f)
        
        summary = data["summary"]
        self.processed = summary["total_processed"]
        self.correct = summary["total_correct"]
        self.playbook_updates = summary["playbook_updates"]
        self.history = data["detailed_history"]
    
    def __str__(self) -> str:
        """String representation"""
        return (
            f"Metrics(processed={self.processed}, "
            f"correct={self.correct}, "
            f"accuracy={self.get_accuracy():.1f}%, "
            f"updates={self.playbook_updates})"
        )
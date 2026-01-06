"""Reflector agent - reflects on trajectories to extract insights"""
from typing import Dict, Any, List
from .base_agent import BaseAgent
from ..models.playbook import Playbook


class Reflector(BaseAgent):
    """Reflects on trajectories to extract insights"""
    
    def _build_prompt(
        self,
        question: str,
        reasoning: str,
        predicted: str,
        ground_truth: str,
        used_bullets: List[str],
        playbook: Playbook,
        is_correct: bool
    ) -> str:
        """Build reflection prompt"""
        bullet_info = ""
        for bullet_id in used_bullets:
            bullet = playbook.get_bullet_by_id(bullet_id)
            if bullet:
                bullet_info += f"\n- [{bullet_id}]: {bullet.content}"
        
        return f"""You are an expert analyzer. Analyze this question-answering attempt.

Question: {question}
Model's Reasoning: {reasoning}
Predicted Answer: {predicted}
Ground Truth: {ground_truth}
Result: {"✓ CORRECT" if is_correct else "✗ INCORRECT"}

Bullets Used: {bullet_info if bullet_info else "None"}

Instructions:
Analyze the attempt and extract insights:
1. What strategies worked well or failed?
2. What new insights should be added to the playbook?
3. Tag each used bullet as helpful, harmful, or neutral

Respond in JSON format:
{{
    "error_identification": "What went wrong or right",
    "root_cause": "Why this happened",
    "key_insight": "Actionable strategy to remember",
    "bullet_tags": [{{"id": "ctx-00001", "tag": "helpful"}}]
}}
"""
    
    def _parse_response(self, response: Dict[str, Any]) -> Dict[str, Any]:
        """Parse reflection response"""
        return {
            "error_identification": response.get("error_identification", ""),
            "root_cause": response.get("root_cause", ""),
            "key_insight": response.get("key_insight", ""),
            "bullet_tags": response.get("bullet_tags", [])
        }
    
    def _get_error_response(self) -> Dict[str, Any]:
        """Get error response for reflection"""
        return {
            "error_identification": "Analysis error",
            "root_cause": "Unknown",
            "key_insight": "Unable to extract insight",
            "bullet_tags": []
        }
    
    @staticmethod
    def check_answer(predicted: str, ground_truth: str) -> bool:
        """Check if predicted answer matches ground truth"""
        import re
        
        # Clean and normalize
        pred_clean = predicted.lower().strip()
        gt_clean = ground_truth.lower().strip()
        
        # Remove punctuation and extra spaces
        pred_clean = re.sub(r'[^\w\s]', '', pred_clean)
        gt_clean = re.sub(r'[^\w\s]', '', gt_clean)
        pred_clean = ' '.join(pred_clean.split())
        gt_clean = ' '.join(gt_clean.split())
        
        # Exact match
        if pred_clean == gt_clean:
            return True
        
        # Substring match
        if pred_clean in gt_clean or gt_clean in pred_clean:
            return True
        
        # Token overlap (at least 70% of ground truth tokens in prediction)
        pred_tokens = set(pred_clean.split())
        gt_tokens = set(gt_clean.split())
        
        if len(gt_tokens) > 0:
            overlap = len(pred_tokens.intersection(gt_tokens))
            if overlap / len(gt_tokens) >= 0.7:
                return True
        
        return False
    
    def reflect(
        self,
        question: str,
        reasoning: str,
        predicted: str,
        ground_truth: str,
        used_bullets: List[str],
        playbook: Playbook
    ) -> Dict[str, Any]:
        """
        Analyze what went right or wrong
        
        Args:
            question: Original question
            reasoning: Model's reasoning
            predicted: Predicted answer
            ground_truth: Correct answer
            used_bullets: List of bullet IDs used
            playbook: Current playbook
            
        Returns:
            Dictionary with reflection analysis and correctness
        """
        is_correct = self.check_answer(predicted, ground_truth)
        
        result = self.execute(
            question=question,
            reasoning=reasoning,
            predicted=predicted,
            ground_truth=ground_truth,
            used_bullets=used_bullets,
            playbook=playbook,
            is_correct=is_correct
        )
        
        result["is_correct"] = is_correct
        return result
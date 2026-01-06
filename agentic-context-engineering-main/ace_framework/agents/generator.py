"""Generator agent - generates answers using playbook"""
from typing import Dict, Any
from .base_agent import BaseAgent
from ..models.playbook import Playbook


class Generator(BaseAgent):
    """Generates answers using current playbook"""
    
    def _build_prompt(self, question: str, context: str, playbook: Playbook) -> str:
        """Build generation prompt"""
        playbook_text = playbook.get_formatted_playbook()
        strategies_block = playbook_text if playbook_text.strip() else "[Playbook is currently empty]"

        return f"""You are ACE's structured generation agent. Your job is to follow the original task instructions
exactly, leveraging any helpful strategies from the playbook.

Playbook strategies:
{strategies_block}

Task (user question):
{question}

Supporting context:
{context}

Generation requirements:
1. Read the playbook and identify any helpful strategies; cite their IDs in reasoning if used.
2. Obey the task instructions verbatim (format, schema, ordering, language, etc.).
3. Produce full reasoning describing how the answer is derived from the context and strategies.
4. Set final_answer to the complete response requested by the task. Do NOT shorten, summarize,
   or omit required structure—even if it is long JSON or tabular data.
5. Output nothing besides the JSON object described below.

Respond strictly in JSON format:
{{
    "reasoning": "Step-by-step reasoning referencing context and strategy IDs you applied",
    "used_bullet_ids": ["ctx-00001", "ctx-00002"],
    "final_answer": "The full answer exactly as required by the user question (can span multiple lines)"
}}
"""
    
    def _parse_response(self, response: Dict[str, Any]) -> Dict[str, Any]:
        """Parse generation response"""
        return {
            "reasoning": response.get("reasoning", ""),
            "used_bullet_ids": response.get("used_bullet_ids", []),
            "final_answer": response.get("final_answer", "")
        }
    
    def _get_error_response(self) -> Dict[str, Any]:
        """Get error response for generation"""
        return {
            "reasoning": "Error in generation",
            "used_bullet_ids": [],
            "final_answer": "Unable to generate answer"
        }
    
    def generate(self, question: str, context: str, playbook: Playbook) -> Dict[str, Any]:
        """
        Generate answer with reasoning
        
        Args:
            question: Question to answer
            context: Supporting context
            playbook: Current playbook
            
        Returns:
            Dictionary with reasoning, used_bullet_ids, and final_answer
        """
        return self.execute(question=question, context=context, playbook=playbook)
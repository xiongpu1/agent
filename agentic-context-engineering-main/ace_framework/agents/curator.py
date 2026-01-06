"""Curator agent - curates playbook updates based on reflections"""
from typing import Dict, Any, List
from .base_agent import BaseAgent
from ..models.playbook import Playbook


class Curator(BaseAgent):
    """Curates playbook updates based on reflections"""
    
    def __init__(self, config, available_sections: List[str]):
        super().__init__(config)
        self.available_sections = available_sections
    
    def _build_prompt(self, reflection: Dict[str, Any], playbook: Playbook) -> str:
        """Build curation prompt"""
        sections_str = ", ".join(self.available_sections)
        
        return f"""You are a knowledge curator. Based on this reflection, decide what to add to the playbook.

Current Playbook:
{playbook.get_formatted_playbook()}

Reflection:
- Error: {reflection.get('error_identification', '')}
- Root Cause: {reflection.get('root_cause', '')}
- Key Insight: {reflection.get('key_insight', '')}

Instructions:
Only add NEW, actionable strategies that are missing from the current playbook.
Avoid redundancy. Be specific and concise.

Respond in JSON format:
{{
    "operations": [
        {{
            "type": "ADD",
            "section": "multi_hop_reasoning",
            "content": "New strategy here..."
        }}
    ]
}}

Available sections: {sections_str}
"""
    
    def _parse_response(self, response: Dict[str, Any]) -> Dict[str, Any]:
        """Parse curation response"""
        operations = response.get("operations", [])
        
        # Validate operations
        valid_operations = []
        for op in operations:
            if (op.get("type") == "ADD" and 
                op.get("section") in self.available_sections and
                op.get("content")):
                valid_operations.append(op)
        
        return {"operations": valid_operations}
    
    def _get_error_response(self) -> Dict[str, Any]:
        """Get error response for curation"""
        return {"operations": []}
    
    def curate(self, reflection: Dict[str, Any], playbook: Playbook) -> List[Dict[str, str]]:
        """
        Generate playbook updates
        
        Args:
            reflection: Reflection results
            playbook: Current playbook
            
        Returns:
            List of operations to perform
        """
        result = self.execute(reflection=reflection, playbook=playbook)
        return result.get("operations", [])
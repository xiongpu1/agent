"""Bullet model - represents a single knowledge item"""
from dataclasses import dataclass
from typing import Dict, Any


@dataclass
class Bullet:
    """Represents a single knowledge item in the playbook"""
    id: str
    section: str
    content: str
    helpful: int = 0
    harmful: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert bullet to dictionary"""
        return {
            "id": self.id,
            "section": self.section,
            "content": self.content,
            "helpful": self.helpful,
            "harmful": self.harmful
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Bullet":
        """Create bullet from dictionary"""
        return cls(
            id=data["id"],
            section=data["section"],
            content=data["content"],
            helpful=data.get("helpful", 0),
            harmful=data.get("harmful", 0)
        )
    
    def update_feedback(self, is_helpful: bool) -> None:
        """Update feedback counts"""
        if is_helpful:
            self.helpful += 1
        else:
            self.harmful += 1
    
    def get_score(self) -> float:
        """Calculate bullet effectiveness score"""
        total = self.helpful + self.harmful
        if total == 0:
            return 0.0
        return (self.helpful - self.harmful) / total
    
    def __str__(self) -> str:
        """String representation"""
        return f"[{self.id}] (✓{self.helpful} ✗{self.harmful}): {self.content}"
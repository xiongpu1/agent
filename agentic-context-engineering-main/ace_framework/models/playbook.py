"""Playbook model - manages collection of bullets"""
import json
from typing import List, Dict, Any, Optional
from pathlib import Path
from .bullet import Bullet


class Playbook:
    """Dynamic playbook that accumulates strategies"""
    
    def __init__(self):
        self.bullets: List[Bullet] = []
        self.next_id: int = 1
    
    def add_bullet(self, section: str, content: str) -> Bullet:
        """Add a new bullet to the playbook"""
        bullet = Bullet(
            id=f"ctx-{str(self.next_id).zfill(5)}",
            section=section,
            content=content
        )
        self.bullets.append(bullet)
        self.next_id += 1
        return bullet
    
    def get_bullet_by_id(self, bullet_id: str) -> Optional[Bullet]:
        """Retrieve bullet by ID"""
        for bullet in self.bullets:
            if bullet.id == bullet_id:
                return bullet
        return None
    
    def update_feedback(self, bullet_id: str, is_helpful: bool) -> bool:
        """Update helpful/harmful counts for a bullet"""
        bullet = self.get_bullet_by_id(bullet_id)
        if bullet:
            bullet.update_feedback(is_helpful)
            return True
        return False

    def remove_bullet(self, bullet_id: str) -> bool:
        """Remove a bullet from the playbook."""
        before = len(self.bullets)
        self.bullets = [b for b in self.bullets if b.id != bullet_id]
        return len(self.bullets) < before
    
    def get_bullets_by_section(self, section: str) -> List[Bullet]:
        """Get all bullets in a section"""
        return [b for b in self.bullets if b.section == section]
    
    def get_formatted_playbook(self) -> str:
        """Get formatted playbook text for prompts"""
        if not self.bullets:
            return "No strategies yet. This is your first attempt."
        
        sections = {}
        for bullet in self.bullets:
            if bullet.section not in sections:
                sections[bullet.section] = []
            sections[bullet.section].append(bullet)
        
        formatted = []
        for section, bullets in sections.items():
            formatted.append(f"\n## {section.replace('_', ' ').title()}\n")
            for bullet in bullets:
                formatted.append(str(bullet))
        
        return "\n".join(formatted)
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get playbook statistics"""
        if not self.bullets:
            return {
                "total_bullets": 0,
                "sections": {},
                "avg_score": 0.0
            }
        
        sections = {}
        total_score = 0.0
        
        for bullet in self.bullets:
            if bullet.section not in sections:
                sections[bullet.section] = 0
            sections[bullet.section] += 1
            total_score += bullet.get_score()
        
        return {
            "total_bullets": len(self.bullets),
            "sections": sections,
            "avg_score": total_score / len(self.bullets) if self.bullets else 0.0
        }
    
    def save(self, filepath: str) -> None:
        """Save playbook to JSON file"""
        Path(filepath).parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, 'w') as f:
            json.dump([b.to_dict() for b in self.bullets], f, indent=2)
    
    def load(self, filepath: str) -> None:
        """Load playbook from JSON file"""
        with open(filepath, 'r') as f:
            data = json.load(f)
        
        self.bullets = [Bullet.from_dict(b) for b in data]
        
        # Update next_id based on loaded bullets
        if self.bullets:
            max_id = max(int(b.id.split('-')[1]) for b in self.bullets)
            self.next_id = max_id + 1
        else:
            self.next_id = 1
    
    def __len__(self) -> int:
        """Get number of bullets"""
        return len(self.bullets)
    
    def __iter__(self):
        """Iterate over bullets"""
        return iter(self.bullets)
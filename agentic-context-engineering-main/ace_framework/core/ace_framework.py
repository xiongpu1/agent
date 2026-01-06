"""Core ACE Framework orchestrator"""
import logging
from typing import Dict, Any
from pathlib import Path

from ..config import Config
from ..models.playbook import Playbook
from ..agents.generator import Generator
from ..agents.reflector import Reflector
from ..agents.curator import Curator
from ..utils.metrics import MetricsTracker
from ..utils.visualization import PerformancePlotter

logger = logging.getLogger(__name__)


class ACEFramework:
    """Main ACE framework orchestrator"""
    
    def __init__(self, config: Config = None):
        """
        Initialize ACE Framework
        
        Args:
            config: Configuration object (uses default if None)
        """
        self.config = config or Config.default()
        
        # Initialize components
        self.playbook = Playbook()
        self.metrics = MetricsTracker()
        
        # Initialize agents
        self.generator = Generator(self.config.model)
        self.reflector = Reflector(self.config.model)
        self.curator = Curator(
            self.config.model,
            self.config.prompt.curator_sections
        )
        
        # Initialize plotter
        self.plotter = PerformancePlotter()
        
        logger.info("ACE Framework initialized")
    
    def adapt_online(
        self,
        question: str,
        context: str,
        ground_truth: str,
        verbose: bool = True
    ) -> Dict[str, Any]:
        """
        Online adaptation: process one sample and update playbook
        
        Args:
            question: Question to answer
            context: Supporting context
            ground_truth: Correct answer
            verbose: Whether to print progress
            
        Returns:
            Dictionary with generation, reflection, and correctness
        """
        if verbose:
            print(f"\n{'='*60}")
            print(f"🔄 Processing: {question[:80]}...")
        
        # 1. Generate answer
        generation = self.generator.generate(question, context, self.playbook)
        
        # 2. Reflect on result
        reflection = self.reflector.reflect(
            question,
            generation["reasoning"],
            generation["final_answer"],
            ground_truth,
            generation["used_bullet_ids"],
            self.playbook
        )
        
        # 3. Update bullet feedback
        for tag_info in reflection.get("bullet_tags", []):
            is_helpful = tag_info.get("tag") == "helpful"
            bullet_id = tag_info.get("id")
            if bullet_id:
                self.playbook.update_feedback(bullet_id, is_helpful)
        
        # 4. Curate new bullets
        operations = self.curator.curate(reflection, self.playbook)
        for op in operations:
            if op["type"] == "ADD":
                bullet = self.playbook.add_bullet(op["section"], op["content"])
                self.metrics.record_playbook_update()
                if verbose:
                    print(f"  ➕ Added: [{bullet.id}] {op['content'][:60]}...")
        
        # 5. Record metrics
        self.metrics.record_result(
            question=question,
            predicted=generation["final_answer"],
            ground_truth=ground_truth,
            is_correct=reflection["is_correct"],
            playbook_size=len(self.playbook)
        )
        
        if verbose:
            if reflection["is_correct"]:
                print(f"  ✅ Correct! Accuracy: {self.metrics.get_accuracy():.1f}%")
            else:
                print(f"  ❌ Incorrect. Accuracy: {self.metrics.get_accuracy():.1f}%")
        
        return {
            "generation": generation,
            "reflection": reflection,
            "correct": reflection["is_correct"]
        }
    
    def adapt_with_prediction(
        self,
        question: str,
        context: str,
        prediction: str,
        ground_truth: str,
        verbose: bool = True
    ) -> Dict[str, Any]:
        """
        Adapt playbook using an externally generated prediction instead of invoking the generator.
        """
        if verbose:
            print(f"\n{'='*60}")
            print(f"🧠 External Sample: {question[:80]}...")
        
        generation = {
            "reasoning": prediction,
            "final_answer": prediction,
            "used_bullet_ids": []
        }
        
        reflection = self.reflector.reflect(
            question,
            generation["reasoning"],
            generation["final_answer"],
            ground_truth,
            generation["used_bullet_ids"],
            self.playbook
        )
        
        for tag_info in reflection.get("bullet_tags", []):
            is_helpful = tag_info.get("tag") == "helpful"
            bullet_id = tag_info.get("id")
            if bullet_id:
                self.playbook.update_feedback(bullet_id, is_helpful)
        
        operations = self.curator.curate(reflection, self.playbook)
        for op in operations:
            if op["type"] == "ADD":
                bullet = self.playbook.add_bullet(op["section"], op["content"])
                self.metrics.record_playbook_update()
                if verbose:
                    print(f"  ➕ Added: [{bullet.id}] {op['content'][:60]}...")
        
        self.metrics.record_result(
            question=question,
            predicted=generation["final_answer"],
            ground_truth=ground_truth,
            is_correct=reflection["is_correct"],
            playbook_size=len(self.playbook)
        )
        
        if verbose:
            if reflection["is_correct"]:
                print(f"  ✅ Aligns with ground truth. Accuracy: {self.metrics.get_accuracy():.1f}%")
            else:
                print(f"  ❌ Differs from ground truth. Accuracy: {self.metrics.get_accuracy():.1f}%")
        
        return {
            "generation": generation,
            "reflection": reflection,
            "correct": reflection["is_correct"]
        }
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get comprehensive statistics"""
        return {
            "metrics": self.metrics.get_summary(),
            "playbook": self.playbook.get_statistics()
        }
    
    def save_results(self, output_dir: str = None) -> None:
        """
        Save all results (playbook, metrics, plots)
        
        Args:
            output_dir: Output directory (uses config default if None)
        """
        if output_dir is None:
            output_dir = self.config.experiment.output_dir
        
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        # Save playbook
        playbook_path = output_path / self.config.experiment.playbook_filename
        self.playbook.save(str(playbook_path))
        logger.info(f"Playbook saved to {playbook_path}")
        
        # Save metrics
        metrics_path = output_path / self.config.experiment.metrics_filename
        self.metrics.save(str(metrics_path))
        logger.info(f"Metrics saved to {metrics_path}")
        
        # Create and save plots
        plot_path = output_path / self.config.experiment.plot_filename
        self.plotter.plot_accuracy(
            accuracy_history=self.metrics.get_accuracy_history(),
            playbook_size_history=self.metrics.get_playbook_size_history(),
            algo_score_history=self.metrics.get_algo_score_history(),
            save_path=str(plot_path)
        )
        
        # Create comprehensive plot
        comprehensive_plot_path = output_path / "comprehensive_metrics.png"
        self.plotter.plot_comprehensive_metrics(
            accuracy_history=self.metrics.get_accuracy_history(),
            playbook_size_history=self.metrics.get_playbook_size_history(),
            algo_score_history=self.metrics.get_algo_score_history(),
            save_path=str(comprehensive_plot_path)
        )
        
        logger.info(f"All results saved to {output_dir}")
    
    def load_checkpoint(self, checkpoint_dir: str) -> None:
        """
        Load checkpoint from directory
        
        Args:
            checkpoint_dir: Directory containing checkpoint files
        """
        checkpoint_path = Path(checkpoint_dir)
        
        # Load playbook
        playbook_path = checkpoint_path / self.config.experiment.playbook_filename
        if playbook_path.exists():
            self.playbook.load(str(playbook_path))
            logger.info(f"Loaded playbook from {playbook_path}")
        
        # Load metrics
        metrics_path = checkpoint_path / self.config.experiment.metrics_filename
        if metrics_path.exists():
            self.metrics.load(str(metrics_path))
            logger.info(f"Loaded metrics from {metrics_path}")
    
    def print_summary(self) -> None:
        """Print execution summary"""
        print("\n" + "="*60)
        print("🎉 ACE Adaptation Complete!")
        print(f"   Final Accuracy: {self.metrics.get_accuracy():.1f}%")
        print(f"   Questions Processed: {self.metrics.processed}")
        print(f"   Correct Answers: {self.metrics.correct}")
        print(f"   Playbook Size: {len(self.playbook)} strategies")
        print(f"   Total Updates: {self.metrics.playbook_updates}")
        
        # Print sample strategies
        if len(self.playbook) > 0:
            print("\n📚 Sample Strategies from Playbook:")
            for i, bullet in enumerate(self.playbook.bullets[:5]):
                print(f"   [{bullet.id}] {bullet.content}")
                if i >= 4:
                    break
        
        print("="*60)
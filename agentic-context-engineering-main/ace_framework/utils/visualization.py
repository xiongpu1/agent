"""Visualization utilities for ACE metrics"""
import matplotlib.pyplot as plt
import seaborn as sns
from typing import List, Optional
from pathlib import Path


class PerformancePlotter:
    """Creates visualizations of ACE performance"""
    
    def __init__(self, style: str = "seaborn-v0_8-darkgrid"):
        try:
            plt.style.use(style)
        except:
            plt.style.use('default')
        sns.set_palette("husl")
    
    def plot_accuracy(
        self,
        accuracy_history: List[float],
        playbook_size_history: Optional[List[int]] = None,
        algo_score_history: Optional[List[float]] = None,
        save_path: Optional[str] = None,
        show: bool = False
    ) -> None:
        """
        Plot accuracy over time with optional playbook size
        
        Args:
            accuracy_history: List of accuracy values
            playbook_size_history: Optional list of playbook sizes
            save_path: Path to save figure
            show: Whether to display the plot
        """
        if playbook_size_history:
            fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10))
        else:
            fig, ax1 = plt.subplots(1, 1, figsize=(12, 6))
        
        # Plot accuracy
        steps = list(range(1, len(accuracy_history) + 1))
        ax1.plot(steps, accuracy_history, linewidth=2, marker='o', 
                markersize=4, label='Accuracy')
        ax1.axhline(y=sum(accuracy_history)/len(accuracy_history), 
                   color='r', linestyle='--', alpha=0.7, label='Mean Accuracy')
        ax1.set_xlabel('Sample Number', fontsize=12)
        ax1.set_ylabel('Accuracy (%)', fontsize=12)
        ax1.set_title('ACE Framework: Accuracy Over Time', fontsize=14, fontweight='bold')
        ax1.grid(True, alpha=0.3)
        ax1.legend()
        ax1.set_ylim(-5, 105)

        # Plot algorithmic score (0-1) on secondary axis if provided
        if algo_score_history is not None and len(algo_score_history) == len(accuracy_history):
            ax1b = ax1.twinx()
            ax1b.plot(
                steps,
                algo_score_history,
                linewidth=2,
                marker='^',
                markersize=4,
                color='purple',
                label='Algo Score',
            )
            ax1b.set_ylabel('Algo Score (0-1)', fontsize=12)
            ax1b.set_ylim(-0.05, 1.05)

            # Merge legends
            lines1, labels1 = ax1.get_legend_handles_labels()
            lines2, labels2 = ax1b.get_legend_handles_labels()
            ax1.legend(lines1 + lines2, labels1 + labels2, loc='best')
        
        # Plot playbook size if provided
        if playbook_size_history:
            ax2.plot(steps, playbook_size_history, linewidth=2, 
                    marker='s', markersize=4, color='green', label='Playbook Size')
            ax2.set_xlabel('Sample Number', fontsize=12)
            ax2.set_ylabel('Number of Strategies', fontsize=12)
            ax2.set_title('Playbook Growth Over Time', fontsize=14, fontweight='bold')
            ax2.grid(True, alpha=0.3)
            ax2.legend()
        
        plt.tight_layout()
        
        if save_path:
            Path(save_path).parent.mkdir(parents=True, exist_ok=True)
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            print(f"\n📊 Plot saved to {save_path}")
        
        if show:
            plt.show()
        else:
            plt.close()
    
    def plot_comprehensive_metrics(
        self,
        accuracy_history: List[float],
        playbook_size_history: List[int],
        algo_score_history: Optional[List[float]] = None,
        save_path: Optional[str] = None,
        show: bool = False
    ) -> None:
        """
        Create comprehensive multi-panel visualization
        
        Args:
            accuracy_history: List of accuracy values
            playbook_size_history: List of playbook sizes
            save_path: Path to save figure
            show: Whether to display the plot
        """
        fig = plt.figure(figsize=(16, 10))
        gs = fig.add_gridspec(2, 2, hspace=0.3, wspace=0.3)
        
        steps = list(range(1, len(accuracy_history) + 1))
        
        # 1. Accuracy over time
        ax1 = fig.add_subplot(gs[0, :])
        ax1.plot(steps, accuracy_history, linewidth=2.5, marker='o', 
                markersize=5, label='Accuracy', color='#2E86AB')
        ax1.axhline(y=sum(accuracy_history)/len(accuracy_history), 
                   color='#A23B72', linestyle='--', linewidth=2, 
                   alpha=0.7, label='Mean Accuracy')
        ax1.fill_between(steps, accuracy_history, alpha=0.3, color='#2E86AB')
        ax1.set_xlabel('Sample Number', fontsize=12, fontweight='bold')
        ax1.set_ylabel('Accuracy (%)', fontsize=12, fontweight='bold')
        ax1.set_title('ACE Framework: Accuracy Over Time', 
                     fontsize=14, fontweight='bold')
        ax1.grid(True, alpha=0.3)
        ax1.legend(fontsize=10)
        ax1.set_ylim(-5, 105)

        if algo_score_history is not None and len(algo_score_history) == len(accuracy_history):
            ax1b = ax1.twinx()
            ax1b.plot(
                steps,
                algo_score_history,
                linewidth=2.5,
                marker='^',
                markersize=4,
                color='#7B2CBF',
                label='Algo Score',
            )
            ax1b.set_ylabel('Algo Score (0-1)', fontsize=11, fontweight='bold')
            ax1b.set_ylim(-0.05, 1.05)

            lines1, labels1 = ax1.get_legend_handles_labels()
            lines2, labels2 = ax1b.get_legend_handles_labels()
            ax1.legend(lines1 + lines2, labels1 + labels2, fontsize=10)
        
        # 2. Playbook growth
        ax2 = fig.add_subplot(gs[1, 0])
        ax2.plot(steps, playbook_size_history, linewidth=2.5, 
                marker='s', markersize=5, color='#F18F01', label='Playbook Size')
        ax2.fill_between(steps, playbook_size_history, alpha=0.3, color='#F18F01')
        ax2.set_xlabel('Sample Number', fontsize=11, fontweight='bold')
        ax2.set_ylabel('Number of Strategies', fontsize=11, fontweight='bold')
        ax2.set_title('Playbook Growth', fontsize=13, fontweight='bold')
        ax2.grid(True, alpha=0.3)
        ax2.legend(fontsize=9)
        
        # 3. Rolling average accuracy (window=10)
        ax3 = fig.add_subplot(gs[1, 1])
        window = min(10, len(accuracy_history))
        rolling_avg = []
        for i in range(len(accuracy_history)):
            start_idx = max(0, i - window + 1)
            rolling_avg.append(sum(accuracy_history[start_idx:i+1]) / (i - start_idx + 1))
        
        ax3.plot(steps, rolling_avg, linewidth=2.5, color='#6A994E', 
                label=f'Rolling Avg (window={window})')
        ax3.fill_between(steps, rolling_avg, alpha=0.3, color='#6A994E')
        ax3.set_xlabel('Sample Number', fontsize=11, fontweight='bold')
        ax3.set_ylabel('Accuracy (%)', fontsize=11, fontweight='bold')
        ax3.set_title('Rolling Average Accuracy', fontsize=13, fontweight='bold')
        ax3.grid(True, alpha=0.3)
        ax3.legend(fontsize=9)
        ax3.set_ylim(-5, 105)
        
        plt.suptitle('ACE Framework Performance Metrics', 
                    fontsize=16, fontweight='bold', y=0.995)
        
        if save_path:
            Path(save_path).parent.mkdir(parents=True, exist_ok=True)
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            print(f"\n📊 Comprehensive plot saved to {save_path}")
        
        if show:
            plt.show()
        else:
            plt.close()
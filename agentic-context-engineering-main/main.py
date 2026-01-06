"""
Main entry point for ACE Framework
Run: python main.py
"""
import logging
import sys
from pathlib import Path

from ace_framework.config import Config, ModelConfig, ExperimentConfig
from ace_framework.core.ace_framework import ACEFramework
from ace_framework.data.dataset_loader import DatasetLoader
# 使用默认配置（会从环境变量读取 GROQ_API_KEY）
ace = ACEFramework()

def setup_logging(log_file: str = None):
    """Setup logging configuration"""
    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    
    handlers = [logging.StreamHandler(sys.stdout)]
    if log_file:
        Path(log_file).parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(log_file))
    
    logging.basicConfig(
        level=logging.INFO,
        format=log_format,
        handlers=handlers
    )


def main():
    """Run ACE on HotpotQA dataset"""
    print("🚀 ACE Framework - HotpotQA Experiment")
    print("="*60)
    
    # Setup logging
    setup_logging(log_file="./results/ace_experiment.log")
    logger = logging.getLogger(__name__)
    
    # Initialize configuration
    # Use default model (qwen3-vl) so that LLMClient can map it to the local
    # Ollama model via litellm. Only experiment settings are customized here.
    config = Config(
        experiment_config=ExperimentConfig(
            dataset_path="./hotpotqa_subset",
            num_samples=20,  # Adjust based on your needs
            checkpoint_interval=10,
            output_dir="./results"
        )
    )
    
    # Load dataset
    print(f"\n📊 Loading HotpotQA subset from {config.experiment.dataset_path}...")
    dataset_loader = DatasetLoader(config.experiment.dataset_path)
    
    try:
        dataset_loader.load()
    except Exception as e:
        logger.error(f"Failed to load dataset: {e}")
        print(f"\n❌ Error: Could not load dataset from {config.experiment.dataset_path}")
        print("   Please ensure the dataset is available at the specified path.")
        return
    
    # Initialize ACE Framework
    print("\n🔧 Initializing ACE Framework...")
    ace = ACEFramework(config)
    
    # Run online adaptation
    print(f"\n🎯 Starting adaptation on {config.experiment.num_samples} samples...")
    print("="*60)
    
    num_samples = min(config.experiment.num_samples, len(dataset_loader))
    
    for i, sample in enumerate(dataset_loader.iterate_samples(num_samples)):
        try:
            ace.adapt_online(
                question=sample["question"],
                context=sample["context"],
                ground_truth=sample["answer"],
                verbose=True
            )
            
            # Print progress at checkpoints
            if (i + 1) % config.experiment.checkpoint_interval == 0:
                print(f"\n📈 Progress Checkpoint: {i+1}/{num_samples}")
                print(f"   Accuracy: {ace.metrics.get_accuracy():.1f}%")
                print(f"   Playbook Size: {len(ace.playbook)} strategies")
                print(f"   Playbook Updates: {ace.metrics.playbook_updates}")
                
        except KeyboardInterrupt:
            print("\n\n⚠️  Interrupted by user. Saving current progress...")
            break
        except Exception as e:
            logger.error(f"Error processing sample {i}: {e}")
            print(f"\n❌ Error on sample {i}: {e}")
            continue
    
    # Print final summary
    ace.print_summary()
    
    # Save all results
    print(f"\n💾 Saving results to {config.experiment.output_dir}...")
    ace.save_results()
    
    print("\n✅ ACE experiment completed successfully!")
    print(f"   Results saved to: {config.experiment.output_dir}")
    print(f"   - Playbook: {config.experiment.playbook_filename}")
    print(f"   - Metrics: {config.experiment.metrics_filename}")
    print(f"   - Plots: {config.experiment.plot_filename}, comprehensive_metrics.png")
    print("\n" + "="*60)


if __name__ == "__main__":
    main()
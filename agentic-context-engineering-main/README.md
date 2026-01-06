# ACE Framework - Agentic Context Engineering

A modular implementation of the ACE (Agentic Context Engineering) framework for self-improving language models, based on the paper "Agentic Context Engineering: Evolving Contexts for Self-Improving Language Models".

## 🏗️ Architecture

The codebase follows software engineering best practices with a clean, modular architecture:

```
ace_framework/
├── __init__.py              # Package initialization
├── config.py                # Configuration management
├── models/                  # Data models
│   ├── __init__.py
│   ├── bullet.py           # Knowledge item representation
│   └── playbook.py         # Strategy collection management
├── agents/                  # AI agents
│   ├── __init__.py
│   ├── base_agent.py       # Abstract base class
│   ├── generator.py        # Answer generation
│   ├── reflector.py        # Performance reflection
│   └── curator.py          # Knowledge curation
├── core/                    # Core framework
│   ├── __init__.py
│   └── ace_framework.py    # Main orchestrator
├── utils/                   # Utilities
│   ├── __init__.py
│   ├── llm_client.py       # LLM API wrapper
│   ├── metrics.py          # Performance tracking
│   └── visualization.py    # Plotting utilities
└── data/                    # Data handling
    ├── __init__.py
    └── dataset_loader.py   # Dataset loading
```

## ✨ Features

- **Modular Design**: Separation of concerns with clear interfaces
- **Configurable**: Centralized configuration management
- **Extensible**: Easy to add new agents or data sources
- **Observable**: Comprehensive metrics tracking and visualization
- **Robust**: Error handling and retry mechanisms
- **Well-documented**: Docstrings and type hints throughout

## 📦 Installation

1. **Clone or download the code**

2. **Install dependencies**:
```bash
pip install -r requirements.txt
```

3. **Set up environment**:
```bash
export GROQ_API_KEY="your_groq_api_key_here"
```

4. **Prepare dataset**:
Ensure you have the HotpotQA subset at `./hotpotqa_subset/`

## 🚀 Usage

### Basic Usage

```python
from ace_framework import ACEFramework, Config

# Initialize with default config
ace = ACEFramework()

# Process a single sample
result = ace.adapt_online(
    question="What is the capital of France?",
    context="France is a country in Europe. Paris is its capital.",
    ground_truth="Paris"
)

# Save results
ace.save_results()
```

### Running the Full Experiment

```bash
python main.py
```

### Custom Configuration

```python
from ace_framework.config import Config, ModelConfig, ExperimentConfig

config = Config(
    model_config=ModelConfig(
        name="llama-3.3-70b-versatile",
        temperature=0.3,
        max_tokens=1000
    ),
    experiment_config=ExperimentConfig(
        dataset_path="./hotpotqa_subset",
        num_samples=100,
        checkpoint_interval=10,
        output_dir="./my_results"
    )
)

ace = ACEFramework(config)
```

## 📊 Output

The framework generates several outputs in the results directory:

1. **ace_playbook.json**: Learned strategies and knowledge
2. **metrics.json**: Detailed performance metrics
3. **accuracy_plot.png**: Simple accuracy over time plot
4. **comprehensive_metrics.png**: Multi-panel visualization with:
   - Accuracy over time
   - Playbook growth
   - Rolling average accuracy

## 🔧 Key Components

### Agents

- **Generator**: Answers questions using the current playbook
- **Reflector**: Analyzes performance and extracts insights
- **Curator**: Decides what strategies to add to the playbook

### Models

- **Bullet**: Represents a single strategy/knowledge item
- **Playbook**: Manages the collection of strategies

### Utils

- **LLMClient**: Wrapper for Groq API with retry logic
- **MetricsTracker**: Tracks accuracy and playbook growth
- **PerformancePlotter**: Creates visualizations

## 🎯 Design Principles

1. **Single Responsibility**: Each class has one clear purpose
2. **Dependency Injection**: Components receive dependencies explicitly
3. **Interface Segregation**: Base classes define clear contracts
4. **DRY (Don't Repeat Yourself)**: Common functionality in shared utilities
5. **Separation of Concerns**: Business logic separate from I/O
6. **Error Handling**: Graceful degradation with informative messages

## 📈 Performance Tracking

The framework tracks:
- Per-sample accuracy
- Cumulative accuracy
- Playbook size over time
- Number of strategy updates
- Detailed question-answer history


## 📝 Example Output

```
🚀 ACE Framework - HotpotQA Experiment
============================================================

📊 Loading HotpotQA subset from ./hotpotqa_subset...
🔧 Initializing ACE Framework...
🎯 Starting adaptation on 50 samples...
============================================================

============================================================
🔄 Processing: What is the capital of the country where...
  ➕ Added: [ctx-00001] Break down multi-hop questions...
  ✅ Correct! Accuracy: 100.0%

============================================================
🔄 Processing: Which actor starred in both...
  ➕ Added: [ctx-00002] When comparing entities...
  ✅ Correct! Accuracy: 100.0%

📈 Progress Checkpoint: 10/50
   Accuracy: 85.0%
   Playbook Size: 8 strategies
   Playbook Updates: 8

============================================================
🎉 ACE Adaptation Complete!
   Final Accuracy: 82.0%
   Questions Processed: 50
   Correct Answers: 41
   Playbook Size: 15 strategies
   Total Updates: 15

📚 Sample Strategies from Playbook:
   [ctx-00001] Break down multi-hop questions...
   [ctx-00002] When comparing entities...
   [ctx-00003] Verify facts before combining...
   [ctx-00004] Look for temporal relationships...
   [ctx-00005] Cross-reference entity mentions...
============================================================

💾 Saving results to ./results...
📊 Plot saved to ./results/accuracy_plot.png
📊 Comprehensive plot saved to ./results/comprehensive_metrics.png

✅ ACE experiment completed successfully!
```



## 📚 References

- Paper: "Agentic Context Engineering: Evolving Contexts for Self-Improving Language Models"
- Dataset: HotpotQA - https://huggingface.co/datasets/hotpotqa/hotpot_qa

## 🔮 Future Enhancements

- [ ] Implement ACE for tasks where the model can actually learn from mistakes and improve through strategy accumulation. Question answering on factual data doesn't benefit much from ACE because the model either knows the fact or doesn't.
from ace_framework.core.ace_framework import ACEFramework  # 注意这里
from ace_framework.config import Config  # 可选，只是演示

# 使用默认配置（会从环境变量读取 GROQ_API_KEY）
ace = ACEFramework()

result = ace.adapt_online(
    question="What is the capital of France?",
    context="France is a country in Europe. Paris is its capital.",
    ground_truth="Paris",
)

print("Result:", result)

ace.save_results(output_dir="./test_results")
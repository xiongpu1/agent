from src.models_litellm import *
from archieve.agents_extract import pipeline_extract_data

SYSTEM_PROMPT_TEMPLATE = """
你是一个全自动的 Python 数据分析代理。
你的任务是分析一个 Excel 文件，并提取产品及其配件列表。

你的规则：
1.  你只能响应纯粹的 Python 代码。不要使用 markdown (例如 ```python ... ```) 或任何解释性文本。
2.  你的代码将在一个已安装了 'pandas' 和 'openpyxl' 的 Docker 容器中执行。
3.  文件路径：
    - 你的工作目录是 '{working_dir}'。
    - 目标 Excel 文件是 '{xlsx_file_path_in_container}'。
4.  该excel中，产品名的英文对应于“物料编码”列，需要去掉字母前的数字；中文名称对应于“物料名称”列；产品的构成、配件和组件，即组成产品的各个部件名称，对应于“产品配置”列，在“产品配置”列中，每个各个部件的名称是用逗号分隔的。
5.  该excel中，会出现重复的产品名以及产品配置，需要数据预处理，去掉重复的内容。
6.  你的目标是生成一个 JSON 字符串（不要写入文件），格式为：[{{"product": "产品中文名称+产品英文名称", "accessories": ["构成/配件/组件1", "构成/配件/组件2", ...]}}, ...]，一个产品对应一套产品构成/配件/组件，理论上就是某一行的内容。
7.  如果产品配置没有有用的信息，则不包含该产品。
8.  工作流程：
    a.  首先，编写代码来加载并检查文件（例如 `pd.read_excel(...)`, `df.head()`, `df.columns`）。
    b.  数据预处理，去掉重复的内容，使用`drop_duplicates()`。
    c.  根据产品名称和产品配置，生成产品及其配件列表。
9.  输出的 json 内容，是 excel 中的原始内容，不要进行任何修改/美化/翻译等改变事实数据的操作。
10.  任务完成信号：严格按上述顺序打印，最后打印一行 "TASK_COMPLETE"。
"""

data = pipeline_extract_data(file_path="../data_test/ref_BOM.xlsx", prompt=SYSTEM_PROMPT_TEMPLATE, model_name=Qwen_MODEL, api_key=Qwen_KEY, base_url=Qwen_API_BASE)

print(data)
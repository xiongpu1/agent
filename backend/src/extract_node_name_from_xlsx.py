import os
import sys
import json
import subprocess
import tempfile
import litellm
from src.models_litellm import *

# --- 系统提示模板 ---
SYSTEM_PROMPT_TEMPLATE = """
你是一个全自动的 Python 数据分析代理。
你的任务是分析一个 Excel 文件，并提取产品及其配件列表。

你的规则：
1.  你只能响应纯粹的 Python 代码。不要使用 markdown (例如 ```python ... ```) 或任何解释性文本。
2.  你的代码将在本机通过 `uv run` 以隔离的沙盒 Python 环境执行；该环境可用且仅提供 `pandas` 与 `openpyxl`。
3.  你必须使用已提供的变量：
    - `file_path`：目标 Excel 文件的绝对路径（字符串）
    - `output_file_path`：最终 JSON 输出文件的绝对路径（字符串）
4.  该 excel 中：
    - 产品名的英文对应于"物料编码"列，需要去掉字母前的数字以及特殊符号；
    - 中文名称对应于"物料名称"列，只保留中文内容；
    - 产品的构成/配件/组件对应于"产品配置"列，其中各部件名称以中文逗号或英文逗号分隔；
    - 每一个产品都有自己的 BOM 版本，对应于"BOM版本"列。
5.  该 excel 中会出现重复的产品名以及产品配置，需要数据预处理，使用 `drop_duplicates()` 去重。
6.  你的目标是创建一个 JSON 文件，格式为：
    [
      {"product_english_name": "产品英文名称", "product_chinese_name": "产品中文名称", "bom_version": "BOM版本", "accessories": ["构成/配件/组件1", "构成/配件/组件2", ...]},
      ...
    ]
    一个产品对应一套产品构成/配件/组件，理论上就是某一行的内容。
7.  如果"产品配置"没有有用的信息，则不保存该产品。
8.  工作流程：
    a. 首先，编写代码来加载并检查文件（例如 `pd.read_excel(...)`, `df.head()`, `df.columns`）。
    b. 数据预处理，去掉重复的内容。
    c. 根据产品名称、BOM 版本和产品配置，生成产品及其配件列表。
    d. 输出产品及其配件列表（打印必要的中间信息以便调试）。
    e. 根据输出迭代完善代码。
    f. 最后，编写代码将该列表保存为 `output_file_path`。
9.  输出的 JSON 内容应忠实于 excel 原始内容，不要进行任何修改/美化/翻译等改变事实数据的操作。
10.  任务完成信号：当你成功保存 JSON 文件后，你的最后一段代码必须打印 "TASK_COMPLETE"。这是我停止循环的唯一信号。
"""


def extract_node_name_from_xlsx(file_path: str) -> list | dict:
    """
    从 Excel 文件中提取产品及其配件列表，并生成 JSON 文件。
    
    Args:
        file_path: Excel 文件的路径（相对路径或绝对路径）
    
    Returns:
        JSON 格式的内容（列表或字典）
    
    Raises:
        SystemExit: 如果文件路径无效或文件不存在
        FileNotFoundError: 如果生成的 JSON 文件不存在
        json.JSONDecodeError: 如果 JSON 文件格式错误
    """
    # 1) 验证用户提供的 file_path
    if not file_path:
        print("错误：请提供有效的 file_path 参数。")
        sys.exit(1)

    input_file_path = os.path.abspath(file_path)
    if not os.path.exists(input_file_path):
        print(f"错误：文件未找到 '{input_file_path}'。")
        sys.exit(1)

    # 2) 计算输出文件路径（与输入文件同目录）
    xlsx_filename = os.path.basename(input_file_path)
    output_filename = os.path.splitext(xlsx_filename)[0] + "_accessories.json"
    host_output_path = os.path.join(os.path.dirname(input_file_path), output_filename)

    print("--- 任务配置 ---")
    print(f"目标文件: {input_file_path}")
    print(f"主机上输出: {host_output_path}")
    print("------------------")

    # 3) 组装系统提示
    system_prompt = SYSTEM_PROMPT_TEMPLATE

    # 初始化对话历史
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": "请开始分析。首先加载 `file_path` 指向的 excel，并打印 df.head() 和 df.columns。"}
    ]

    # 4) 代理循环（本地通过 uv 的隔离环境执行）
    max_rounds = 20
    rounds = 0

    while True:
        rounds += 1
        if rounds > max_rounds:
            print("错误：已达到最大迭代次数（20次）。")
            break

        print("\n" + "=" * 50)
        print("🤖 [Qwen 思考中...]")
        try:
            response = litellm.completion(
                model=Qwen_MODEL,
                messages=messages,
                api_key=Qwen_API_KEY,
                api_base=Qwen_URL_BASE,
            )
        except Exception as e:
            print(f"调用 LiteLLM/Qwen 时出错: {e}")
            break

        code_to_run = response.choices[0].message.content.strip()
        messages.append({"role": "assistant", "content": code_to_run})

        print(f"🐍 [Qwen 提议的代码]:\n{code_to_run}")
        print("=" * 50)

        # 将 LLM 代码写入临时脚本；在顶部注入路径变量
        tmp_script_path = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as tmp_file:
                header = (
                    f"file_path = r\"{input_file_path}\"\n"
                    f"output_file_path = r\"{host_output_path}\"\n"
                )
                tmp_file.write(header)
                tmp_file.write("\n\n")
                tmp_file.write(code_to_run)
                tmp_script_path = tmp_file.name
        except Exception as e:
            print(f"❌ 错误：无法写入临时脚本: {e}")
            break

        # 使用 uv 运行临时脚本，提供隔离环境并安装所需依赖
        try:
            print(f"🧪 [uv 正在执行: python {tmp_script_path}]")
            proc = subprocess.run(
                [
                    "uv",
                    "run",
                    "--no-project",
                    "--with",
                    "pandas",
                    "--with",
                    "openpyxl",
                    "python",
                    tmp_script_path,
                ],
                capture_output=True,
                text=True,
            )
            output = (proc.stdout or "") + ("\n" + proc.stderr if proc.stderr else "")
            print(f"🖥️ [本地 uv 输出]:\n{output}")
        except FileNotFoundError:
            print("错误：未找到 `uv` 可执行文件。请先安装 uv：https://docs.astral.sh/uv/ 并确保在 PATH 中。")
            # 清理临时文件
            if tmp_script_path and os.path.exists(tmp_script_path):
                os.unlink(tmp_script_path)
            break
        except Exception as e:
            print(f"运行 uv 时发生错误: {e}")
            # 清理临时文件
            if tmp_script_path and os.path.exists(tmp_script_path):
                os.unlink(tmp_script_path)
            break
        finally:
            # 清理临时文件
            if tmp_script_path and os.path.exists(tmp_script_path):
                try:
                    os.unlink(tmp_script_path)
                except Exception:
                    pass

        # 任务完成判断
        if "TASK_COMPLETE" in output:
            print("\n✅ 任务完成信号已收到！")
            if os.path.exists(host_output_path):
                print(f"✅ 成功创建输出文件: '{host_output_path}'")
                # 读取 JSON 文件内容并返回
                try:
                    with open(host_output_path, 'r', encoding='utf-8') as f:
                        json_data = json.load(f)
                    return json_data
                except FileNotFoundError:
                    print(f"⚠️ 错误：找不到生成的 JSON 文件 '{host_output_path}'")
                    raise
                except json.JSONDecodeError as e:
                    print(f"⚠️ 错误：JSON 文件格式错误: {e}")
                    raise
            else:
                print("⚠️ 警告：收到 TASK_COMPLETE 信号，但未找到输出文件。")
                raise FileNotFoundError(f"未找到生成的 JSON 文件: {host_output_path}")

        # 将执行输出反馈给 LLM 继续迭代
        messages.append({"role": "user", "content": f"代码已执行。输出：\n{output}"})
    
    # 如果循环结束但未完成任务，抛出异常
    raise RuntimeError("任务未完成：已达到最大迭代次数或发生错误")

if __name__ == "__main__":
    """主函数，用于命令行直接运行"""
    # 默认文件路径（用于向后兼容）
    default_file_path = "data_test/ref_BOM.xlsx"
    
    # 指定保存 JSON 文件的位置
    output_json_path = "data_test/ref_BOM_accessories.json"  # 可以修改为任意路径
    
    # 调用函数获取 JSON 内容
    json_data = extract_node_name_from_xlsx(default_file_path)
    
    # 保存 JSON 文件到指定位置
    try:
        # 确保输出目录存在
        output_dir = os.path.dirname(output_json_path)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)
        
        # 保存 JSON 文件
        with open(output_json_path, 'w', encoding='utf-8') as f:
            json.dump(json_data, f, ensure_ascii=False, indent=2)
        
        print(f"\n✅ JSON 文件已保存到: {os.path.abspath(output_json_path)}")
    except Exception as e:
        print(f"❌ 保存 JSON 文件时出错: {e}")
        sys.exit(1)
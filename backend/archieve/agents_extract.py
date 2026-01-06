from src.models_litellm import *
from pydantic import BaseModel, Field
import os
import sys
import atexit
import subprocess
import tempfile
import json
import re
import docker
import litellm

# --- 配置 ---
DOCKER_IMAGE = "python:3.11-slim"
WORKING_DIR_IN_CONTAINER = "/app"
TEMP_SCRIPT_NAME = "_temp_agent_script.py" # 临时脚本的固定名称

class ProductBase(BaseModel):
    product_name: str = Field(description="产品名称=“物料名称”(中文)+“物料编码”对应的英文名称（去掉字母前的数字后）。例如：中文名+英文名。")
    accessories: list[str] = Field(description="来自“产品配置”列的各部件原始名称列表；按原始逗号分隔并去重、清洗空白；保持原始语种与大小写，不做翻译或美化。")
class ProductList(BaseModel):
    products: list[ProductBase]

def agentA_use_docker_to_extract_data(file_path: str, prompt: str,model_name: str = Qwen_MODEL, api_key: str = Qwen_KEY, base_url: str = Qwen_API_BASE, docker_image: str = DOCKER_IMAGE):
    input_file_path = os.path.abspath(file_path)
    if not os.path.exists(input_file_path):
        raise FileNotFoundError(f"文件未找到: {input_file_path}")

    mount_dir = os.path.abspath(os.path.dirname(input_file_path))
    xlsx_filename_in_container = os.path.basename(input_file_path)

    # 将 prompt 中的占位符替换为容器路径信息（若有）
    formatted_prompt = (
        prompt.format(
            working_dir=WORKING_DIR_IN_CONTAINER,
            xlsx_file_path_in_container=f"{WORKING_DIR_IN_CONTAINER}/{xlsx_filename_in_container}",
        )
        if "{working_dir}" in prompt or "{xlsx_file_path_in_container}" in prompt
        else prompt
    )

    try:
        client = docker.from_env()
    except docker.errors.DockerException as e:
        raise RuntimeError("无法连接到 Docker 守护进程") from e

    container = client.containers.run(
        docker_image,
        command="sleep infinity",
        detach=True,
        tty=True,
        working_dir=WORKING_DIR_IN_CONTAINER,
        volumes={mount_dir: {"bind": WORKING_DIR_IN_CONTAINER, "mode": "rw"}},
    )

    def cleanup():
        try:
            container.stop()
            container.remove()
        except Exception:
            pass

    atexit.register(cleanup)

    # 安装依赖
    exec_result = container.exec_run("pip install pandas openpyxl")
    if exec_result.exit_code != 0:
        out = exec_result.output.decode("utf-8", errors="ignore")
        cleanup()
        raise RuntimeError(f"容器内安装依赖失败: {out}")

    messages = [
        {"role": "system", "content": formatted_prompt},
        {"role": "user", "content": f"请开始分析 '{xlsx_filename_in_container}'。首先加载它并打印 df.head() 和 df.columns。"},
    ]

    full_markdown_logs: list[str] = []

    for _ in range(20):
        response = litellm.completion(
            model=model_name,
            messages=messages,
            api_key=api_key,
            api_base=base_url,
        )
        code_to_run = (response.choices[0].message.content or "").strip()
        messages.append({"role": "assistant", "content": code_to_run})

        # 写入临时脚本并复制进容器
        script_path_in_container = f"{WORKING_DIR_IN_CONTAINER}/{TEMP_SCRIPT_NAME}"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as tmp_file:
            tmp_file.write(code_to_run)
            tmp_script_path = tmp_file.name
        try:
            cp_res = subprocess.run(
                ["docker", "cp", tmp_script_path, f"{container.id}:{script_path_in_container}"],
                capture_output=True,
                text=True,
            )
        finally:
            try:
                os.unlink(tmp_script_path)
            except Exception:
                pass

        if cp_res.returncode != 0:
            cleanup()
            raise RuntimeError(f"复制脚本到容器失败: {cp_res.stderr}")

        exec_res = container.exec_run(f"python {script_path_in_container}")
        output = exec_res.output.decode("utf-8", errors="ignore")
        # 记录为 markdown 日志
        full_markdown_logs.append("```text\n" + output.strip() + "\n```")

        if "TASK_COMPLETE" in output:
            # 返回包含容器输出的 markdown 文本（含原始 JSON 片段标记，供下游解析）
            return "\n\n".join(full_markdown_logs)

        messages.append({"role": "user", "content": f"代码已执行。输出：\n{output}"})

    cleanup()
    raise RuntimeError("达到最大迭代次数，未完成解析任务")

def agentB_analyze_data_and_generate_json(markdown_text: str, prompt: str,model_name: str = Qwen_MODEL, api_key: str = Qwen_KEY, base_url: str = Qwen_API_BASE):
    # 从上游 markdown 中提取 JSON
    start_marker = "===JSON_START==="
    end_marker = "===JSON_END==="
    parsed_data = None
    if start_marker in markdown_text and end_marker in markdown_text:
        s = markdown_text.index(start_marker) + len(start_marker)
        e = markdown_text.index(end_marker, s)
        json_text = markdown_text[s:e].strip()
        try:
            parsed_data = json.loads(json_text)
        except Exception:
            parsed_data = None
    if parsed_data is None:
        # 回退：寻找最后一个 JSON 数组
        candidates = re.findall(r"\[.*?\]", markdown_text, flags=re.DOTALL)
        for cand in reversed(candidates):
            try:
                parsed_data = json.loads(cand)
                break
            except Exception:
                continue
    if parsed_data is None:
        raise ValueError("未能从上游 markdown 中提取出 JSON 数据")

    analysis_messages = [
        {"role": "system", "content": prompt},
        {
            "role": "user",
            "content": (
                "这是解析阶段输出的原始 JSON：\n===JSON_START===\n"
                + json.dumps(parsed_data, ensure_ascii=False)
                + "\n===JSON_END===\n请生成符合 ProductList 的 JSON，仅输出在标记之间。"
            ),
        },
    ]

    analysis_resp = litellm.completion(
        model=model_name,
        messages=analysis_messages,
        api_key=api_key,
        api_base=base_url,
    )
    analysis_text = analysis_resp.choices[0].message.content or ""

    if start_marker in analysis_text and end_marker in analysis_text:
        a_start = analysis_text.index(start_marker) + len(start_marker)
        a_end = analysis_text.index(end_marker, a_start)
        product_list_json = analysis_text[a_start:a_end].strip()
    else:
        product_list_json = analysis_text.strip()

    data_obj = json.loads(product_list_json)
    # 进行一次 Pydantic 校验（不抛错，只在结构不符时提示）
    try:
        _ = ProductList.model_validate(data_obj)
    except Exception:
        pass
    return data_obj

def agentC_disassemble_command_to_two_agents(file_path: str, prompt: str,model_name: str = Qwen_MODEL, api_key: str = Qwen_KEY, base_url: str = Qwen_API_BASE):
    """
    将输入的 prompt 拆解为两个 prompt：
    - 解析 prompt：要求仅输出在 Docker 中可运行的 Python 代码，读取 Excel 并在标记之间输出 JSON，末尾打印 TASK_COMPLETE。
    - 分析 prompt：根据解析阶段 JSON 生成符合 ProductList 的 JSON，仅输出标记之间的 JSON。

    返回 (parse_prompt, analyze_prompt)。
    """
    messages = [
        {
            "role": "system",
            "content": (
                "你是任务规划专家。根据用户给出的任务说明，将其拆解成两个严格分工的提示。\n"
                "- Prompt A(解析)：仅输出可在 Docker 内运行的纯 Python 代码(禁止 Markdown)，使用 pandas/openpyxl 读取指定 Excel，"
                "并以 JSON 形式打印在 ===JSON_START=== 与 ===JSON_END=== 之间；最后打印 TASK_COMPLETE。可使用占位符 {working_dir} 与 {xlsx_file_path_in_container}。\n"
                "- Prompt B(分析)：根据解析得到的原始 JSON，生成符合 ProductList 的 JSON，仅输出在标记之间。"
            ),
        },
        {
            "role": "user",
            "content": (
                "总任务说明如下：\n" + prompt + "\n\n"
                "请返回：\n<PROMPT_A>...解析提示...</PROMPT_A>\n<PROMPT_B>...分析提示...</PROMPT_B>\n"
            ),
        },
    ]

    try:
        resp = litellm.completion(model=model_name, messages=messages, api_key=api_key, api_base=base_url)
        content = resp.choices[0].message.content or ""
        m_a = re.search(r"<PROMPT_A>([\s\S]*?)</PROMPT_A>", content)
        m_b = re.search(r"<PROMPT_B>([\s\S]*?)</PROMPT_B>", content)
        if m_a and m_b:
            return m_a.group(1).strip(), m_b.group(1).strip()
    except Exception:
        pass

    # 兜底：给出一对默认提示
    parse_prompt = (
        "你是一个 Python 数据解析代理。仅输出可执行的纯 Python 代码(禁止 Markdown)，"
        "使用 pandas/openpyxl 读取 Excel：工作目录 '{working_dir}'，文件 '{xlsx_file_path_in_container}'；"
        "按需求解析并在 ===JSON_START=== 与 ===JSON_END=== 之间打印 JSON；最后打印 TASK_COMPLETE。"
    )
    analyze_prompt = (
        "你是结构化结果生成代理。根据解析阶段的原始 JSON，生成符合 ProductList 的 JSON，"
        "仅输出 JSON，放在 ===JSON_START=== 与 ===JSON_END=== 之间。"
    )
    return parse_prompt, analyze_prompt

def pipeline_extract_data(file_path: str, prompt: str,model_name: str = Qwen_MODEL, api_key: str = Qwen_KEY, base_url: str = Qwen_API_BASE, docker_image: str = DOCKER_IMAGE):
    # 拆解 prompt -> 两个阶段的提示
    parse_prompt, analyze_prompt = agentC_disassemble_command_to_two_agents(
        file_path=file_path,
        prompt=prompt,
        model_name=model_name,
        api_key=api_key,
        base_url=base_url,
    )

    # 阶段一：运行 Docker 内代码，返回 markdown（包含原始 JSON 片段）
    markdown_logs = agentA_use_docker_to_extract_data(
        file_path=file_path,
        prompt=parse_prompt,
        model_name=model_name,
        api_key=api_key,
        base_url=base_url,
        docker_image=docker_image,
    )

    # 阶段二：根据 markdown 与分析 prompt 生成最终结构化输出
    result = agentB_analyze_data_and_generate_json(
        markdown_text=markdown_logs,
        prompt=analyze_prompt,
        model_name=model_name,
        api_key=api_key,
        base_url=base_url,
    )
    return result
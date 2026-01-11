import os
import sys
import json
import subprocess
import tempfile
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from difflib import SequenceMatcher

import pandas as pd
try:
    import litellm  # type: ignore
    from src.models_litellm import *  # type: ignore  # noqa: F403
except Exception:  # noqa: BLE001
    litellm = None

# Ensure `backend/` is on sys.path so imports like `src.*` work when running
# `python backend/src/extract_node_name_from_xlsx.py` from repo root.
_BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from src.rag_bom import decode_bom_code

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


def extract_node_name_from_xlsx(file_path: str, output_file_path: Optional[str] = None) -> list | dict:
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
        # Common pitfall: calling from repo root, but file lives under backend/.
        # If a relative path was provided, try resolving it relative to backend/.
        try:
            if not os.path.isabs(file_path):
                backend_dir = Path(__file__).resolve().parent.parent
                alt = (backend_dir / file_path).resolve()
                if alt.exists():
                    input_file_path = str(alt)
        except Exception:
            pass
    if not os.path.exists(input_file_path):
        print(f"错误：文件未找到 '{input_file_path}'。")
        sys.exit(1)

    # 2) 计算输出文件路径
    if output_file_path and str(output_file_path).strip():
        host_output_path = os.path.abspath(str(output_file_path).strip())
    else:
        xlsx_filename = os.path.basename(input_file_path)
        output_filename = os.path.splitext(xlsx_filename)[0] + "_accessories.json"
        host_output_path = os.path.join(os.path.dirname(input_file_path), output_filename)

    print("--- 任务配置 ---")
    print(f"目标文件: {input_file_path}")
    print(f"主机上输出: {host_output_path}")
    print("------------------")

    code_to_product_type_zh: Dict[str, str] = {
        "31": "泳池",
        "32": "户外缸",
        "33": "按摩浴缸",
        "34": "对接按摩缸",
        "35": "按摩缸",
        "37": "冰水缸",
    }

    translate_xlsx_path = (Path(__file__).resolve().parent.parent / "data_test" / "translate_accessories.xlsx").resolve()

    def _extract_prefix_and_material_code(raw_value: Any) -> Tuple[Optional[str], str]:
        s = str(raw_value or "").strip()
        if not s:
            return None, ""
        m = re.match(r"^\s*(\d+)\s*[\.．]\s*(.+?)\s*$", s)
        if m:
            prefix = m.group(1)
            tail = m.group(2)
        else:
            m2 = re.match(r"^\s*(\d+)\s*(.+?)\s*$", s)
            if m2:
                prefix = m2.group(1)
                tail = m2.group(2)
            else:
                prefix = None
                tail = s

        tail = tail.strip()
        tail = re.sub(r"[^A-Za-z0-9]+", "", tail)
        return prefix, tail

    def _normalize_code_tail(raw_value: Any) -> str:
        _, tail = _extract_prefix_and_material_code(raw_value)
        return tail

    def _normalize_zh_text(raw_value: Any) -> str:
        s = str(raw_value or "").strip()
        if not s:
            return ""
        # keep Chinese + common symbols used in accessory names, remove whitespace
        s = re.sub(r"\s+", "", s)
        s = s.replace("（", "(").replace("）", ")")
        return s

    def _is_na_like(s: str) -> bool:
        v = (s or "").strip()
        if not v:
            return True
        return v.lower() in {"#n/a", "n/a", "na", "nan", "none"}

    def _pick_english_name(name_en: Any, detail_en: Any) -> str:
        a = str(name_en or "").strip()
        b = str(detail_en or "").strip()
        if not _is_na_like(a):
            return a
        if not _is_na_like(b):
            return b
        return ""

    def _best_fuzzy_match(query: str, candidates: List[str], threshold: float) -> Optional[str]:
        if not query or not candidates:
            return None
        best_key = None
        best_score = 0.0
        for cand in candidates:
            score = SequenceMatcher(None, query, cand).ratio()
            if score > best_score:
                best_score = score
                best_key = cand
        if best_key is not None and best_score >= threshold:
            return best_key
        return None

    def _load_translate_table(path: Path) -> Optional[pd.DataFrame]:
        if not path.exists():
            return None
        try:
            return pd.read_excel(str(path), engine="openpyxl")
        except Exception:
            return None

    def _find_col(df: pd.DataFrame, candidates: List[str]) -> Optional[str]:
        for c in candidates:
            if c in df.columns:
                return c
        # fallback: substring contains
        for col in df.columns:
            col_s = str(col)
            for c in candidates:
                if c in col_s:
                    return col
        return None

    def _build_translation_index(df: pd.DataFrame) -> Tuple[Dict[Tuple[str, str], str], Dict[str, str]]:
        # Try to be robust to column naming.
        code_col = _find_col(df, ["编码", "物料编码", "产品编码", "型号", "Code"])
        zh_col = _find_col(df, ["名称", "中文名称", "配件名称", "中文", "Name"])
        en_col = _find_col(df, ["英文名称", "英文名", "EN", "English Name"])
        en_detail_col = _find_col(df, ["英文详细说明", "英文说明", "英文描述", "English Description", "English Detail"])

        if zh_col is None:
            raise RuntimeError(f"翻译表缺少中文名称列。实际列: {list(df.columns)}")

        by_code_and_zh: Dict[Tuple[str, str], str] = {}
        by_zh: Dict[str, str] = {}

        for _, r in df.iterrows():
            code_tail = _normalize_code_tail(r.get(code_col)) if code_col else ""
            zh = _normalize_zh_text(r.get(zh_col))
            if not zh:
                continue
            en = _pick_english_name(r.get(en_col) if en_col else None, r.get(en_detail_col) if en_detail_col else None)
            if not en:
                continue

            if code_tail:
                k = (code_tail, zh)
                if k not in by_code_and_zh:
                    by_code_and_zh[k] = en
            if zh not in by_zh:
                by_zh[zh] = en

        return by_code_and_zh, by_zh

    def _extract_zh_only(raw_value: Any) -> str:
        s = str(raw_value or "").strip()
        if not s:
            return ""
        parts = re.findall(r"[\u4e00-\u9fff]+", s)
        return "".join(parts).strip()

    def _split_accessories(config_text: str) -> List[str]:
        raw = (config_text or "").strip()
        if not raw:
            return []
        if raw.lower() == "nan":
            return []
        pieces = re.split(r"[，,;；\n]+", raw)
        out: List[str] = []
        seen = set()
        for p in pieces:
            s = (p or "").strip()
            if not s:
                continue
            if s.lower() == "nan":
                continue
            if s in seen:
                continue
            seen.add(s)
            out.append(s)
        return out

    def _bom_type_from_product_type_zh(product_type_zh: str) -> Optional[str]:
        s = (product_type_zh or "").strip()
        if s == "泳池":
            return "pool"
        if s == "户外缸":
            return "outdoor"
        if s == "冰水缸":
            return "iceTub"
        return None

    def _accessories_from_bom(bom_id: str, bom_type: str) -> List[str]:
        decoded = decode_bom_code(bom_id, bom_type=bom_type)
        if not decoded:
            return []
        segments = decoded.get("segments") or []
        out: List[str] = []
        seen = set()
        for seg in segments:
            meaning = seg.get("meaning") if isinstance(seg, dict) else None
            if not meaning or not isinstance(meaning, str):
                continue
            s = meaning.strip()
            if not s:
                continue
            # Filter out invalid placeholder meanings.
            if "标注错误" in s:
                continue
            if s in seen:
                continue
            seen.add(s)
            out.append(s)
        return out

    try:
        # Explicitly check openpyxl to provide a clearer error message.
        import openpyxl  # noqa: F401
    except ModuleNotFoundError as e:
        raise RuntimeError(
            "读取 Excel 失败：缺少依赖 openpyxl。\n"
            "请安装后再运行：\n"
            "- conda install -n syp openpyxl\n"
            "或\n"
            "- pip install openpyxl\n"
            "或使用 uv：\n"
            "- uv run --no-project --with pandas --with openpyxl python backend/src/extract_node_name_from_xlsx.py"
        ) from e

    try:
        df = pd.read_excel(input_file_path, engine="openpyxl")
    except Exception as e:
        raise RuntimeError(f"读取 Excel 失败: {e}") from e

    required_cols = ["物料编码", "物料名称", "产品配置", "BOM版本"]
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        raise RuntimeError(f"Excel 缺少列: {missing}. 实际列: {list(df.columns)}")

    items: List[Dict[str, Any]] = []
    dedupe = set()
    for _, row in df.iterrows():
        prefix, material_code = _extract_prefix_and_material_code(row.get("物料编码"))
        if not material_code:
            continue

        bom_id = str(row.get("BOM版本") or "").strip()
        if not bom_id:
            continue

        name_zh = _extract_zh_only(row.get("物料名称"))
        config_raw = row.get("产品配置")
        if pd.isna(config_raw):
            continue
        config_text_zh = str(config_raw).strip()
        if not config_text_zh or config_text_zh.lower() == "nan":
            continue

        product_type_zh = code_to_product_type_zh.get(str(prefix or "").strip(), "未知")
        bom_type = _bom_type_from_product_type_zh(product_type_zh)
        if not bom_type:
            continue

        accessories = _accessories_from_bom(bom_id, bom_type=bom_type)
        if not accessories:
            continue

        record = {
            "material_code": material_code,
            "bom_id": bom_id,
            "name_zh": name_zh,
            "name_en": material_code,
            "product_type_zh": product_type_zh,
            "config_text_zh": config_text_zh,
            "accessories": accessories,
        }

        key = (record["material_code"], record["bom_id"], record["config_text_zh"])
        if key in dedupe:
            continue
        dedupe.add(key)
        items.append(record)

    try:
        # Enrich with English accessory names (optional; only if translation table exists).
        translate_df = _load_translate_table(translate_xlsx_path)
        if translate_df is not None and not translate_df.empty:
            by_code_and_zh, by_zh = _build_translation_index(translate_df)

            total = 0
            hit_exact = 0
            hit_fuzzy_code = 0
            hit_exact_global = 0
            miss = 0

            zh_keys_by_code: Dict[str, List[str]] = {}
            for (code_tail, zh_key) in by_code_and_zh.keys():
                zh_keys_by_code.setdefault(code_tail, []).append(zh_key)

            # NOTE: Global fuzzy matching over all keys is very expensive (N accessories * M keys).
            # We only do global exact matching as a safe/fast fallback.

            # Memoize per (code_tail, zh_norm) to avoid repeated matching.
            cache: Dict[Tuple[str, str], str] = {}

            for item in items:
                code_tail = str(item.get("material_code") or "").strip()
                accs = item.get("accessories") or []
                accs_en: List[str] = []
                for acc in accs:
                    total += 1
                    zh_norm = _normalize_zh_text(acc)
                    if not zh_norm:
                        accs_en.append("")
                        miss += 1
                        continue

                    cached = cache.get((code_tail, zh_norm))
                    if cached is not None:
                        accs_en.append(cached)
                        continue

                    en = ""

                    # 1) exact (code + zh)
                    en = by_code_and_zh.get((code_tail, zh_norm), "")
                    if en:
                        hit_exact += 1
                        accs_en.append(en)
                        cache[(code_tail, zh_norm)] = en
                        continue

                    # 2) fuzzy (code + zh)
                    cands = zh_keys_by_code.get(code_tail) or []
                    best = _best_fuzzy_match(zh_norm, cands, threshold=0.85)
                    if best:
                        en = by_code_and_zh.get((code_tail, best), "")
                        if en:
                            hit_fuzzy_code += 1
                            accs_en.append(en)
                            cache[(code_tail, zh_norm)] = en
                            continue

                    # 3) exact global by zh
                    en = by_zh.get(zh_norm, "")
                    if en:
                        hit_exact_global += 1
                        accs_en.append(en)
                        cache[(code_tail, zh_norm)] = en
                        continue

                    miss += 1
                    accs_en.append("")
                    cache[(code_tail, zh_norm)] = ""

                    if total % 5000 == 0:
                        print(f"翻译进度: 已处理配件 {total}")

                item["accessories_en"] = accs_en

            print("\n--- 翻译匹配统计（translate_accessories.xlsx）---")
            print(f"翻译表路径: {translate_xlsx_path}")
            print(f"总配件条目: {total}")
            print(f"命中: 编码+名称精确 {hit_exact}")
            print(f"命中: 编码+名称模糊 {hit_fuzzy_code}")
            print(f"命中: 名称精确 {hit_exact_global}")
            print(f"未命中: {miss}")
            print("-------------------------------------------")

        with open(host_output_path, "w", encoding="utf-8") as f:
            json.dump(items, f, ensure_ascii=False, indent=2)
    except Exception as e:
        raise RuntimeError(f"写入 JSON 失败: {e}") from e

    print(f"\n✅ JSON 文件已保存到: {os.path.abspath(host_output_path)}")
    print("TASK_COMPLETE")
    return items

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
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="backend/data_test/ref_BOM_products.xlsx")
    parser.add_argument("--output", default="backend/data_test/ref_BOM_products.json")
    args = parser.parse_args()

    extract_node_name_from_xlsx(args.input, output_file_path=args.output)
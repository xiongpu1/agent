import os
import json
import re
from typing import Dict, List, Optional, Set, Tuple
from neo4j import GraphDatabase
from dotenv import load_dotenv
import litellm

load_dotenv()

# Model config
from src.models_litellm import *


# Get the directory where this script is located (project root)
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
STRUCTURED_DIR = os.path.join(SCRIPT_DIR, "structured_processed_files")
FORCE_LLM_ALL = os.getenv("FORCE_LLM_ALL", "false").lower() == "true"

# ---- Helpers ----

def read_text_file(path: str, max_chars: int = 12000) -> str:
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read(max_chars)
            return content
    except Exception:
        return ""


def collect_files(root_dir: str) -> List[str]:
    targets: List[str] = []
    for base, _, files in os.walk(root_dir):
        for name in files:
            lower = name.lower()
            if lower.endswith(".md") or lower.endswith(".json"):
                targets.append(os.path.join(base, name))
    return targets


def normalize_text(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip()


# ---- Neo4j ----

def get_driver() -> GraphDatabase.driver:
    uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    user = os.getenv("NEO4J_USER", "neo4j")
    password = os.getenv("NEO4J_PASSWORD", "Root@12345678@")
    return GraphDatabase.driver(uri, auth=(user, password))


def fetch_product_and_accessory_names(driver) -> Tuple[Dict[str, Set[str]], Set[str]]:
    """
    Returns:
      - products_map: {product_identifier -> {all_known_aliases}}
      - accessories_set: {accessory_name}
    """
    products_map: Dict[str, Set[str]] = {}
    accessories_set: Set[str] = set()

    with driver.session() as session:
        # Products
        res = session.run("MATCH (p:Product) RETURN p.name as id, p.english_name as en, p.chinese_name as cn")
        for r in res:
            pid = normalize_text(r.get("id"))
            en = normalize_text(r.get("en"))
            cn = normalize_text(r.get("cn"))
            if not pid:
                continue
            alias: Set[str] = set()
            alias.add(pid)
            if en:
                alias.add(en)
            if cn:
                alias.add(cn)
            products_map[pid] = alias

        # Accessories
        res2 = session.run("MATCH (a:Accessory) RETURN a.name as name")
        for r in res2:
            name = normalize_text(r.get("name"))
            if name:
                accessories_set.add(name)

    return products_map, accessories_set


# ---- Local heuristic to narrow candidates ----

def find_candidate_names(text: str, name_set: Set[str]) -> Set[str]:
    candidates: Set[str] = set()
    if not text:
        return candidates
    lower_text = text.lower()
    for name in name_set:
        nn = name.strip()
        if not nn:
            continue
        # simple substring match (case-insensitive)
        if nn.lower() in lower_text:
            candidates.add(nn)
    return candidates


# ---- LLM classification ----

def call_qwen_classify(file_path: str, file_excerpt: str, product_candidates: List[str], accessory_candidates: List[str]) -> Dict:
    """
    Ask Qwen to choose one of: Product, Accessory, None; and the single best-matching name.
    Returns dict: {"type": "Product"|"Accessory"|"None", "name": str}
    """
    # Safe guard: avoid overly long prompts
    excerpt = file_excerpt[:8000]

    system_prompt = (
        "你是一个分类助手。给定文件内容片段和候选的产品名称、配件名称，判断该文件主要描述的是产品或配件中的哪一个。如果无法判断，返回 None。\n"
        "规则：\n"
        "- 只能在候选列表中选择一个名字；文件不可能同时属于产品与配件。\n"
        "- 如果明显是产品说明书/规格页/目录，倾向于产品；如果是部件/组件/配件的说明或安装图，倾向于配件。\n"
        "- 输出严格的 JSON：{\"type\": \"Product|Accessory|None\", \"name\": \"名称或空字符串\"}。\n"
    )

    user_prompt = (
        f"文件路径: {file_path}\n"
        f"文件内容片段:\n{excerpt}\n\n"
        f"产品候选: {json.dumps(product_candidates, ensure_ascii=False)}\n"
        f"配件候选: {json.dumps(accessory_candidates, ensure_ascii=False)}\n"
        "请只返回 JSON，不要任何多余文字。"
    )

    try:
        resp = litellm.completion(
            model=Ollama_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        content = resp.choices[0].message.content if resp and resp.choices else ""
        # try parse json
        first_brace = content.find("{")
        last_brace = content.rfind("}")
        if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
            snippet = content[first_brace:last_brace + 1]
            return json.loads(snippet)
    except Exception:
        pass

    return {"type": "None", "name": ""}


# ---- Batch update Neo4j ----

def batch_update_paths(driver, product_to_paths: Dict[str, List[str]], accessory_to_paths: Dict[str, List[str]]):
    with driver.session() as session:
        # Products
        for pid, paths in product_to_paths.items():
            session.run(
                (
                    "WITH $paths AS newPaths "
                    "MATCH (p:Product {name: $id}) "
                    "SET p.file_paths = CASE WHEN p.file_paths IS NULL THEN newPaths "
                    "ELSE p.file_paths + [x IN newPaths WHERE NOT x IN p.file_paths] END"
                ),
                {"id": pid, "paths": paths},
            )
        # Accessories
        for aname, paths in accessory_to_paths.items():
            session.run(
                (
                    "WITH $paths AS newPaths "
                    "MATCH (a:Accessory {name: $name}) "
                    "SET a.file_paths = CASE WHEN a.file_paths IS NULL THEN newPaths "
                    "ELSE a.file_paths + [x IN newPaths WHERE NOT x IN a.file_paths] END"
                ),
                {"name": aname, "paths": paths},
            )


# ---- Main ----

def main():
    driver = get_driver()

    print("[1/4] 读取 Neo4j 中的产品与配件名称...")
    products_map, accessories_set = fetch_product_and_accessory_names(driver)

    # Flatten all product aliases to set and map alias -> product id
    alias_to_product_id: Dict[str, str] = {}
    all_product_aliases: Set[str] = set()
    for pid, aliases in products_map.items():
        for a in aliases:
            alias_to_product_id[a] = pid
            all_product_aliases.add(a)

    print(f"  - 产品数: {len(products_map)}，产品别名数: {len(all_product_aliases)}")
    print(f"  - 配件数: {len(accessories_set)}")

    print("[2/4] 收集目标文件 (.md/.json)...")
    print(f"  - 扫描目录: {STRUCTURED_DIR}")
    if not os.path.exists(STRUCTURED_DIR):
        print(f"  ⚠️  警告：目录不存在！请检查路径。")
        driver.close()
        return
    files = collect_files(STRUCTURED_DIR)
    total = len(files)
    print(f"  - 待分析文件数: {total}")

    product_to_paths_accum: Dict[str, Set[str]] = {}
    accessory_to_paths_accum: Dict[str, Set[str]] = {}

    print("[3/4] 使用启发式 + Qwen 模型进行判定 (显示进度)...")
    for idx, fpath in enumerate(files, start=1):
        rel = fpath
        text = read_text_file(fpath)

        # Include path string for candidate detection
        path_text = os.path.basename(fpath) + " " + os.path.dirname(fpath)

        # Narrow by local heuristic from content and path
        prod_cands = set()
        acc_cands = set()
        prod_cands |= find_candidate_names(text, all_product_aliases)
        prod_cands |= find_candidate_names(path_text, all_product_aliases)
        acc_cands |= find_candidate_names(text, accessories_set)
        acc_cands |= find_candidate_names(path_text, accessories_set)

        prod_cands_list = sorted(list(prod_cands))
        acc_cands_list = sorted(list(acc_cands))

        # Optionally force LLM for all files
        if not prod_cands_list and not acc_cands_list and not FORCE_LLM_ALL:
            print(f"[{idx}/{total}] 跳过 (无候选): {rel}")
            continue

        result = call_qwen_classify(fpath, text or path_text, prod_cands_list, acc_cands_list)
        rtype = result.get("type") or "None"
        rname = normalize_text(result.get("name"))

        # Enforce exclusivity and valid mapping
        if rtype == "Product" and rname in alias_to_product_id:
            pid = alias_to_product_id[rname]
            product_to_paths_accum.setdefault(pid, set()).add(rel)
            print(f"[{idx}/{total}] 归类为 产品 -> {pid} | {rel}")
        elif rtype == "Accessory" and rname in accessories_set:
            accessory_to_paths_accum.setdefault(rname, set()).add(rel)
            print(f"[{idx}/{total}] 归类为 配件 -> {rname} | {rel}")
        else:
            print(f"[{idx}/{total}] 无法明确归类 -> {rel}")

    # Prepare lists
    product_to_paths: Dict[str, List[str]] = {k: sorted(list(v)) for k, v in product_to_paths_accum.items()}
    accessory_to_paths: Dict[str, List[str]] = {k: sorted(list(v)) for k, v in accessory_to_paths_accum.items()}

    print("[4/4] 批量写入 Neo4j 属性 file_paths ...")
    print(f"  - 待写入 产品 节点数: {len(product_to_paths)}")
    print(f"  - 待写入 配件 节点数: {len(accessory_to_paths)}")

    batch_update_paths(driver, product_to_paths, accessory_to_paths)

    driver.close()
    print("✅ 完成。")


if __name__ == "__main__":
    main()

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from dotenv import load_dotenv
from neo4j import GraphDatabase

load_dotenv()


EXPECTED_NEO4J_HOME = "/root/workspace/syp/neo4j2"
EXPECTED_NEO4J_CONF = "/root/workspace/syp/neo4j2/conf"


def _get_env(name: str, default: Optional[str] = None) -> Optional[str]:
    v = os.getenv(name)
    if v is None:
        return default
    v = v.strip()
    return v or default


def _fetch_server_home_conf(session) -> Tuple[Optional[str], Optional[str]]:
    errors: List[str] = []

    # Attempt 1: procedure (may be restricted depending on Neo4j config)
    try:
        res = session.run(
            "CALL dbms.listConfig() YIELD name, value "
            "WHERE name IN ['server.directories.home','server.directories.conf'] "
            "RETURN name, value"
        )
        home = None
        conf = None
        for r in res:
            if r["name"] == "server.directories.home":
                home = r["value"]
            elif r["name"] == "server.directories.conf":
                conf = r["value"]
        if home or conf:
            return home, conf
    except Exception as e:  # noqa: BLE001
        errors.append(f"dbms.listConfig failed: {e}")

    # Attempt 2: Neo4j 5+ Cypher command
    try:
        res = session.run(
            "SHOW SETTINGS YIELD name, value "
            "WHERE name IN ['server.directories.home','server.directories.conf'] "
            "RETURN name, value"
        )
        home = None
        conf = None
        for r in res:
            if r["name"] == "server.directories.home":
                home = r["value"]
            elif r["name"] == "server.directories.conf":
                conf = r["value"]
        if home or conf:
            return home, conf
        errors.append("SHOW SETTINGS returned no rows for server.directories.home/conf")
    except Exception as e:  # noqa: BLE001
        errors.append(f"SHOW SETTINGS failed: {e}")

    # Attempt 3: Some Neo4j 5 builds expose config via SHOW CONFIG
    try:
        res = session.run(
            "SHOW CONFIG YIELD name, value "
            "WHERE name IN ['server.directories.home','server.directories.conf'] "
            "RETURN name, value"
        )
        home = None
        conf = None
        for r in res:
            if r["name"] == "server.directories.home":
                home = r["value"]
            elif r["name"] == "server.directories.conf":
                conf = r["value"]
        if home or conf:
            return home, conf
        errors.append("SHOW CONFIG returned no rows for server.directories.home/conf")
    except Exception as e:  # noqa: BLE001
        errors.append(f"SHOW CONFIG failed: {e}")

    print("⚠️ 无法读取 Neo4j server.directories.home/conf：")
    for err in errors:
        print(f"- {err}")
    return None, None


def _env_points_to_expected_neo4j2() -> bool:
    home = (os.getenv("NEO4J_HOME") or "").strip()
    conf = (os.getenv("NEO4J_CONF") or "").strip()
    return bool(home == EXPECTED_NEO4J_HOME and conf == EXPECTED_NEO4J_CONF)


def _ensure_constraints(session) -> None:
    statements = [
        "CREATE CONSTRAINT material_code_unique IF NOT EXISTS FOR (m:Material) REQUIRE m.material_code IS UNIQUE",
        "CREATE CONSTRAINT bom_id_unique IF NOT EXISTS FOR (b:BOM) REQUIRE b.bom_id IS UNIQUE",
        "CREATE CONSTRAINT product_id_unique IF NOT EXISTS FOR (p:Product) REQUIRE p.product_id IS UNIQUE",
        "CREATE CONSTRAINT product_config_id_unique IF NOT EXISTS FOR (pc:ProductConfig) REQUIRE pc.product_id IS UNIQUE",
        "CREATE CONSTRAINT accessory_zh_unique IF NOT EXISTS FOR (a:Accessory) REQUIRE a.name_zh IS UNIQUE",
    ]
    for stmt in statements:
        session.run(stmt)


def import_products_json(
    input_json_path: str,
    *,
    uri: str,
    user: str,
    password: str,
    wipe: bool,
    wipe_only: bool,
) -> Dict[str, int]:
    driver = GraphDatabase.driver(uri, auth=(user, password))
    try:
        with driver.session() as session:
            server_home, server_conf = _fetch_server_home_conf(session)
            if wipe:
                if server_home is None or server_conf is None:
                    if not _env_points_to_expected_neo4j2():
                        raise RuntimeError(
                            "无法确认 Neo4j 实例的 server.directories.home/conf，且环境变量 NEO4J_HOME/NEO4J_CONF "
                            "也未指向 neo4j2，已拒绝执行全库清空（--wipe）。\n"
                            f"期望 NEO4J_HOME={EXPECTED_NEO4J_HOME} 且 NEO4J_CONF={EXPECTED_NEO4J_CONF}"
                        )
                    print(
                        "⚠️ 无法从 Neo4j 查询 server.directories.home/conf，将使用环境变量 NEO4J_HOME/NEO4J_CONF "
                        "进行安全确认（已匹配 neo4j2）。"
                    )
                else:
                    if server_home != EXPECTED_NEO4J_HOME or server_conf != EXPECTED_NEO4J_CONF:
                        raise RuntimeError(
                            "检测到目标 Neo4j 实例路径不匹配，已拒绝执行全库清空（--wipe）。\n"
                            f"实际 home: {server_home}\n"
                            f"实际 conf: {server_conf}\n"
                            f"期望 home: {EXPECTED_NEO4J_HOME}\n"
                            f"期望 conf: {EXPECTED_NEO4J_CONF}"
                        )

                print("\n⚠️ 即将执行全库清空（MATCH (n) DETACH DELETE n）...")
                session.run("MATCH (n) DETACH DELETE n")

                if wipe_only:
                    return {
                        "materials": 0,
                        "boms": 0,
                        "products": 0,
                        "product_configs": 0,
                        "accessories": 0,
                        "has_accessory_rels": 0,
                    }

            with open(input_json_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            if not isinstance(data, list):
                raise RuntimeError("输入 JSON 必须是 list。")

            _ensure_constraints(session)

            stats = {
                "materials": 0,
                "boms": 0,
                "products": 0,
                "product_configs": 0,
                "accessories": 0,
                "has_accessory_rels": 0,
            }

            total = len(data)
            for idx, item in enumerate(data, 1):
                if not isinstance(item, dict):
                    continue

                material_code = str(item.get("material_code") or "").strip()
                bom_id = str(item.get("bom_id") or "").strip()
                name_zh = str(item.get("name_zh") or "").strip()
                name_en = str(item.get("name_en") or "").strip()
                product_type_zh = str(item.get("product_type_zh") or "").strip()
                config_text_zh = str(item.get("config_text_zh") or "").strip()
                accessories_zh = item.get("accessories") or []
                accessories_en = item.get("accessories_en") or []

                if not material_code or not bom_id:
                    continue
                product_id = f"{material_code}_{bom_id}"
                material_name = name_en or name_zh or material_code
                product_name = name_en or name_zh or material_code

                if idx % 200 == 0 or idx == 1 or idx == total:
                    print(f"[{idx}/{total}] Importing product_id={product_id}")

                # Material
                session.run(
                    "MERGE (m:Material {material_code: $material_code}) "
                    "SET m.name_zh = $name_zh, m.name_en = $name_en, m.name = $name, m.product_type_zh = $product_type_zh "
                    "REMOVE m.id",
                    {
                        "material_code": material_code,
                        "name_zh": name_zh,
                        "name_en": name_en,
                        "name": material_name,
                        "product_type_zh": product_type_zh,
                    },
                )
                stats["materials"] += 1

                # BOM
                session.run(
                    "MERGE (b:BOM {bom_id: $bom_id}) "
                    "SET b.revision = coalesce(b.revision, $revision), b.name = $name "
                    "REMOVE b.id",
                    {"bom_id": bom_id, "revision": "v1.0", "name": bom_id},
                )
                stats["boms"] += 1

                # Product
                session.run(
                    "MERGE (p:Product {product_id: $product_id}) "
                    "SET p.material_code = $material_code, "
                    "    p.bom_id = $bom_id, "
                    "    p.display_name_zh = $display_name_zh, "
                    "    p.display_name_en = $display_name_en, "
                    "    p.name = $name, "
                    "    p.product_type_zh = $product_type_zh "
                    "REMOVE p.id",
                    {
                        "product_id": product_id,
                        "material_code": material_code,
                        "bom_id": bom_id,
                        "display_name_zh": name_zh,
                        "display_name_en": name_en or material_code,
                        "name": product_id,
                        "product_type_zh": product_type_zh,
                    },
                )
                stats["products"] += 1

                # Relationships: Material->Product, Product->BOM
                session.run(
                    "MATCH (m:Material {material_code: $material_code}) "
                    "MATCH (p:Product {product_id: $product_id}) "
                    "MERGE (m)-[:HAS_PRODUCT]->(p)",
                    {"material_code": material_code, "product_id": product_id},
                )
                session.run(
                    "MATCH (p:Product {product_id: $product_id}) "
                    "MATCH (b:BOM {bom_id: $bom_id}) "
                    "MERGE (p)-[:USES_BOM]->(b)",
                    {"product_id": product_id, "bom_id": bom_id},
                )

                # ProductConfig
                if config_text_zh:
                    session.run(
                        "MERGE (pc:ProductConfig {product_id: $product_id}) "
                        "SET pc.config_text_zh = $config_text_zh "
                        "REMOVE pc.id",
                        {"product_id": product_id, "config_text_zh": config_text_zh},
                    )
                    stats["product_configs"] += 1
                    session.run(
                        "MATCH (p:Product {product_id: $product_id}) "
                        "MATCH (pc:ProductConfig {product_id: $product_id}) "
                        "MERGE (p)-[:HAS_CONFIG]->(pc)",
                        {"product_id": product_id},
                    )

                # Accessories (name_zh globally unique)
                if not isinstance(accessories_zh, list):
                    accessories_zh = []
                if not isinstance(accessories_en, list):
                    accessories_en = []

                for order, zh in enumerate(accessories_zh):
                    zh_s = str(zh or "").strip()
                    if not zh_s:
                        continue
                    en_s = ""
                    if order < len(accessories_en):
                        en_s = str(accessories_en[order] or "").strip()
                    a_name = en_s or zh_s

                    session.run(
                        "MERGE (a:Accessory {name_zh: $name_zh}) "
                        "SET a.name_en = CASE "
                        "  WHEN (a.name_en IS NULL OR a.name_en = '') AND $name_en <> '' THEN $name_en "
                        "  ELSE a.name_en "
                        "END, "
                        "    a.name = CASE "
                        "  WHEN (a.name IS NULL OR a.name = '') THEN $name "
                        "  ELSE a.name "
                        "END "
                        "REMOVE a.id",
                        {"name_zh": zh_s, "name_en": en_s, "name": a_name},
                    )
                    stats["accessories"] += 1

                    session.run(
                        "MATCH (p:Product {product_id: $product_id}) "
                        "MATCH (a:Accessory {name_zh: $name_zh}) "
                        "MERGE (p)-[r:HAS_ACCESSORY]->(a) "
                        "SET r.order = $order",
                        {"product_id": product_id, "name_zh": zh_s, "order": int(order)},
                    )
                    stats["has_accessory_rels"] += 1

            return stats
    finally:
        driver.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="backend/data_test/ref_BOM_products.json")
    parser.add_argument("--uri", default=_get_env("NEO4J_URI", "neo4j://localhost:7688"))
    parser.add_argument("--user", default=_get_env("NEO4J_USER", "neo4j"))
    parser.add_argument("--password", default=_get_env("NEO4J_PASSWORD", ""))
    parser.add_argument(
        "--wipe",
        action="store_true",
        help=(
            "全库清空（危险）。仅当连接到指定 neo4j2 实例（server.directories.home/conf 匹配）才会执行。"
        ),
    )
    parser.add_argument(
        "--wipe-only",
        action="store_true",
        help=(
            "只执行全库清空然后退出（用于验证清空是否生效）。需要同时传 --wipe。"
        ),
    )
    args = parser.parse_args()

    if not args.password:
        raise SystemExit("NEO4J_PASSWORD 为空，请通过环境变量或 --password 传入。")

    stats = import_products_json(
        args.input,
        uri=args.uri,
        user=args.user,
        password=args.password,
        wipe=bool(args.wipe),
        wipe_only=bool(args.wipe_only),
    )
    print("\n导入完成！统计：")
    for k, v in stats.items():
        print(f"- {k}: {v}")


########
# prompt：修改代码，将 @ref_BOM_accessories.json 内容import到neo4j中：每一条数据对应一个产品，首先将 product_english_name 和 bom_version 拼接起来，变成 "product_english_name"_"bom_version"，作为产品的唯一键，同时产品使用product作为标签，然后把accessories部分内容作为标签为accessory的节点，最后使用(Product) -[:HAS]-> (Accessory)去连接产品和配件。

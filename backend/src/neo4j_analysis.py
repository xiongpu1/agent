import neo4j
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# 添加项目根目录到 Python 路径，以便导入 src 模块
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.dataclass import Neo4jConfig
load_dotenv()


def list_products_and_accessories() -> None:
    neo4j_config = Neo4jConfig(
        uri=os.getenv("NEO4J_URI"),
        user=os.getenv("NEO4J_USER"),
        password=os.getenv("NEO4J_PASSWORD")
    )
    driver = neo4j.GraphDatabase.driver(
        neo4j_config.uri,
        auth=(neo4j_config.user, neo4j_config.password)
    )

    session = driver.session()
    try:
        # List distinct Products present in DB (no relationship traversal)
        result_products = session.run("MATCH (p:Product) RETURN DISTINCT p.name AS name ORDER BY name")
        products = [record["name"] for record in result_products]
        print(f"Products ({len(products)}):")
        # for name in products:
        #     print(f"- {name}")

        print("")

        # List distinct Accessories only (no join with Product to avoid duplicates)
        result_accessories = session.run("MATCH (a:Accessory) RETURN DISTINCT a.name AS name ORDER BY name")
        accessories = [record["name"] for record in result_accessories]
        print(f"Accessories ({len(accessories)}):")
        # for name in accessories:
        #     print(f"- {name}")
    finally:
        session.close()
        driver.close()


if __name__ == "__main__":
    list_products_and_accessories()

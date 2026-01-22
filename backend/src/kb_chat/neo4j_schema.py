import time
from typing import Any, Dict, List, Optional

from src.api_queries import get_neo4j_config
from src.neo4j_file_add_neo4j import get_neo4j_driver


_SCHEMA_CACHE: Optional[Dict[str, Any]] = None
_SCHEMA_CACHE_AT: float = 0.0
_SCHEMA_TTL_SECONDS = 600


def _run(session, query: str, params: Optional[dict] = None) -> List[dict]:
    res = session.run(query, params or {})
    return [r.data() for r in res]


def probe_schema(force: bool = False) -> Dict[str, Any]:
    global _SCHEMA_CACHE, _SCHEMA_CACHE_AT

    now = time.time()
    if not force and _SCHEMA_CACHE and (now - _SCHEMA_CACHE_AT) < _SCHEMA_TTL_SECONDS:
        return _SCHEMA_CACHE

    cfg = get_neo4j_config()
    driver = get_neo4j_driver(cfg)
    try:
        with driver.session() as session:
            labels_rows = _run(session, "CALL db.labels()")
            rel_rows = _run(session, "CALL db.relationshipTypes()")
            labels = sorted([r.get("label") for r in labels_rows if r.get("label")])
            rel_types = sorted([r.get("relationshipType") for r in rel_rows if r.get("relationshipType")])

            schema_visualization: Dict[str, Any] = {"nodes": [], "relationships": []}
            try:
                viz = _run(session, "CALL db.schema.visualization()")
                if viz:
                    schema_visualization = {
                        "nodes": viz[0].get("nodes") or [],
                        "relationships": viz[0].get("relationships") or [],
                    }
            except Exception:
                schema_visualization = {"nodes": [], "relationships": []}

            node_type_properties: List[dict] = []
            rel_type_properties: List[dict] = []
            # Neo4j 5+ provides these procedures in many distributions.
            try:
                node_type_properties = _run(session, "CALL db.schema.nodeTypeProperties()")
            except Exception:
                node_type_properties = []
            try:
                rel_type_properties = _run(session, "CALL db.schema.relTypeProperties()")
            except Exception:
                rel_type_properties = []

            triples: List[dict] = []
            try:
                triples = _run(
                    session,
                    """
                    MATCH (a)-[r]->(b)
                    WITH labels(a) AS al, type(r) AS rt, labels(b) AS bl
                    WITH coalesce(al[0], '') AS aLabel, rt, coalesce(bl[0], '') AS bLabel
                    RETURN aLabel, rt, bLabel, count(*) AS cnt
                    ORDER BY cnt DESC
                    LIMIT 60
                    """,
                )
            except Exception:
                triples = []

            label_props: Dict[str, List[str]] = {}
            for lb in labels[:20]:
                try:
                    rows = _run(session, f"MATCH (n:`{lb}`) RETURN keys(n) AS k LIMIT 1")
                    if rows and isinstance(rows[0].get("k"), list):
                        label_props[lb] = rows[0]["k"]
                except Exception:
                    continue

            schema = {
                "labels": labels,
                "relationshipTypes": rel_types,
                "labelProperties": label_props,
                "schemaVisualization": schema_visualization,
                "nodeTypeProperties": node_type_properties,
                "relTypeProperties": rel_type_properties,
                "sampleTriples": triples,
            }

            _SCHEMA_CACHE = schema
            _SCHEMA_CACHE_AT = now
            return schema
    finally:
        driver.close()

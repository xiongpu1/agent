import json
import re
from typing import Any, Optional


def extract_json_object(text: str) -> Optional[Any]:
    if not text:
        return None

    raw = text.strip()
    try:
        return json.loads(raw)
    except Exception:
        pass

    m = re.search(r"\{[\s\S]*\}", raw)
    if not m:
        return None

    snippet = m.group(0)
    try:
        return json.loads(snippet)
    except Exception:
        return None

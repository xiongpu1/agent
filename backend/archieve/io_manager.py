import os
from typing import Dict


def safe_dir_name(name: str) -> str:
    # replace problematic characters
    return (name or "").strip().replace(os.sep, "_").replace("..", ".").replace(":", "_")


def ensure_owner_artifact_dirs(folder_path: str, owner_dir_name: str) -> Dict[str, str]:
    base_owner = os.path.join(folder_path, safe_dir_name(owner_dir_name))
    table_dir = os.path.join(base_owner, "table")
    image_dir = os.path.join(base_owner, "image")
    text_dir = os.path.join(base_owner, "text")
    os.makedirs(table_dir, exist_ok=True)
    os.makedirs(image_dir, exist_ok=True)
    os.makedirs(text_dir, exist_ok=True)
    return {"base": base_owner, "table_dir": table_dir, "image_dir": image_dir, "text_dir": text_dir}


def save_table_markdown(table_dir: str, base_name: str, table_index: int, table_markdown: str) -> str:
    fname = f"{base_name}_table{table_index}.md"
    fpath = os.path.join(table_dir, fname)
    with open(fpath, "w", encoding="utf-8") as f:
        f.write(table_markdown)
    return fpath


def save_base64_image(image_dir: str, base_name: str, image_index: int, ext: str, data: bytes) -> str:
    if not ext:
        ext = "png"
    fname = f"{base_name}_img{image_index}.{ext}"
    fpath = os.path.join(image_dir, fname)
    with open(fpath, "wb") as f:
        f.write(data)
    return fpath


def save_text_markdown(text_dir: str, base_name: str, content: str) -> str:
    fname = f"{base_name}_text.md"
    fpath = os.path.join(text_dir, fname)
    with open(fpath, "w", encoding="utf-8") as f:
        f.write(content)
    return fpath

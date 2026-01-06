import io
import os
from pathlib import Path
from typing import Optional, Tuple

try:
    from PIL import Image
except Exception as e:  # pragma: no cover
    Image = None  # type: ignore


# Supported input image suffixes we attempt to convert to PNG
SUPPORTED_IMAGE_SUFFIXES = {
    ".png", ".jpg", ".jpeg", ".bmp", ".gif", ".tif", ".tiff", ".webp", ".jfif", ".pjpeg", ".pjp",
}


def is_supported_image(path: os.PathLike | str) -> bool:
    suffix = Path(path).suffix.lower()
    return suffix in SUPPORTED_IMAGE_SUFFIXES


def ensure_parent_dir(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def convert_image_to_png(src_path: os.PathLike | str, dst_png_path: os.PathLike | str) -> bool:
    """
    Convert an image file to PNG and save to the destination path.

    Args:
        src_path: Source image file path.
        dst_png_path: Destination PNG file path (should end with .png).

    Returns:
        bool: True on success, False on failure.
    """
    src = Path(src_path)
    dst = Path(dst_png_path)

    if Image is None:
        # Pillow not available
        return False

    try:
        with Image.open(src) as im:
            # Convert palettes and RGBA with transparency appropriately
            if im.mode in ("P", "LA"):
                im = im.convert("RGBA")
            elif im.mode == "CMYK":
                im = im.convert("RGB")
            elif im.mode not in ("RGB", "RGBA"):
                im = im.convert("RGB")

            ensure_parent_dir(dst)
            im.save(dst, format="PNG")
            return True
    except Exception:
        return False


def suggest_png_path_for(src_path: os.PathLike | str, dst_root: os.PathLike | str, rel_root: os.PathLike | str) -> Path:
    """
    Suggest an output PNG path for a source image file given the desired output root
    and the input root to compute the relative structure.

    For example:
        src = /data/input/a/b/c.jpg
        rel_root = /data/input
        dst_root = /data/output
        -> /data/output/a/b/c.png
    """
    src = Path(src_path)
    dst_root = Path(dst_root)
    rel_root = Path(rel_root)
    rel = src.relative_to(rel_root)
    rel = rel.with_suffix(".png")
    return dst_root / rel

import argparse
import os
import re
import sys
import zipfile
from posixpath import normpath
from xml.etree import ElementTree as ET
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

from dotenv import load_dotenv
from openpyxl import load_workbook

# Ensure backend root (the parent of 'src') is on sys.path so this script can be
# executed from either repo root or backend/.
BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from src.dataclass import Neo4jConfig
from src.neo4j_file_add_neo4j import get_neo4j_driver


def _norm_header(s: str) -> str:
    s = (s or "").strip().lower()
    s = re.sub(r"\s+", " ", s)
    return s


def _get_env(name: str, default: Optional[str] = None) -> Optional[str]:
    v = os.getenv(name)
    if v is None:
        return default
    v = v.strip()
    return v or default


def get_neo4j_config() -> Neo4jConfig:
    uri = _get_env("NEO4J_URI")
    user = _get_env("NEO4J_USER")
    password = _get_env("NEO4J_PASSWORD")
    if not uri or not user or not password:
        missing = [k for k, v in [("NEO4J_URI", uri), ("NEO4J_USER", user), ("NEO4J_PASSWORD", password)] if not v]
        raise RuntimeError(f"Missing Neo4j env vars: {', '.join(missing)}")
    return Neo4jConfig(uri=uri, user=user, password=password)


def detect_image_ext(data: bytes) -> str:
    if not data:
        return ".bin"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if data.startswith(b"\xff\xd8"):
        return ".jpg"
    if data.startswith(b"GIF87a") or data.startswith(b"GIF89a"):
        return ".gif"
    if data.startswith(b"BM"):
        return ".bmp"
    return ".bin"


def sanitize_filename(s: str) -> str:
    s = (s or "").strip()
    s = re.sub(r"[\\/:*?\"<>|\s]+", "_", s)
    s = s.strip("._")
    return s or "unknown"


def _parse_col_spec(ws, col_spec: str, header_row: Optional[int]) -> int:
    spec = (col_spec or "").strip()
    if not spec:
        raise ValueError("empty material column spec")

    if spec.isdigit():
        idx = int(spec)
        if idx <= 0:
            raise ValueError("column index must be 1-based")
        return idx

    if re.fullmatch(r"[A-Za-z]+", spec):
        letters = spec.upper()
        idx = 0
        for ch in letters:
            idx = idx * 26 + (ord(ch) - ord("A") + 1)
        return idx

    if header_row is None:
        raise ValueError("material-col is a header name but header_row is not set")

    target = _norm_header(spec)
    for c in range(1, ws.max_column + 1):
        v = ws.cell(row=header_row, column=c).value
        if v is None:
            continue
        if _norm_header(str(v)) == target:
            return c

    raise ValueError(f"could not find header '{spec}' on row {header_row}")


def guess_header_row(ws, *, max_rows: int = 40) -> Optional[int]:
    candidates = {
        "model",
        "material_code",
        "material code",
        "物料编码",
        "物料",
        "编码",
    }
    for r in range(1, min(max_rows, ws.max_row) + 1):
        hits = 0
        for c in range(1, min(ws.max_column, 80) + 1):
            v = ws.cell(row=r, column=c).value
            if v is None:
                continue
            if _norm_header(str(v)) in candidates:
                hits += 1
        if hits:
            return r
    return None


def _find_header_cols(ws, header_row: int, header_name: str) -> List[int]:
    target = _norm_header(header_name)
    cols: List[int] = []
    for c in range(1, ws.max_column + 1):
        v = ws.cell(row=header_row, column=c).value
        if v is None:
            continue
        if _norm_header(str(v)) == target:
            cols.append(c)
    return cols


def _choose_nearest_header_col(cols: List[int], *, anchor_col: int) -> Optional[int]:
    if not cols:
        return None
    left = [c for c in cols if c <= anchor_col]
    if left:
        return max(left)
    right = [c for c in cols if c > anchor_col]
    if right:
        return min(right)
    return None


def list_sheets(xlsx_path: Path) -> List[str]:
    wb = load_workbook(xlsx_path, data_only=True)
    try:
        return list(wb.sheetnames)
    finally:
        try:
            wb.close()
        except Exception:
            pass


_NS = {
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "wb": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "rel": "http://schemas.openxmlformats.org/package/2006/relationships",
    "xdr": "http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
}


def _zip_read_xml(zf: zipfile.ZipFile, name: str) -> ET.Element:
    data = zf.read(name)
    return ET.fromstring(data)


def _rels_map(zf: zipfile.ZipFile, rels_path: str) -> Dict[str, str]:
    try:
        root = _zip_read_xml(zf, rels_path)
    except KeyError:
        return {}
    out: Dict[str, str] = {}
    for rel in root.findall("rel:Relationship", _NS):
        rid = rel.attrib.get("Id")
        target = rel.attrib.get("Target")
        if rid and target:
            out[rid] = target
    return out


def _resolve_target(base_dir: str, target: str) -> str:
    # base_dir like 'xl/worksheets' ; target like '../drawings/drawing1.xml'
    p = normpath(f"{base_dir}/{target}")
    # normpath may drop leading '..' resolution; ensure it doesn't start with '../'
    p = p.lstrip("./")
    return p


def _sheet_xml_path_from_name(zf: zipfile.ZipFile, sheet_name: str) -> Optional[str]:
    try:
        wb = _zip_read_xml(zf, "xl/workbook.xml")
    except KeyError:
        return None

    rid = None
    for sh in wb.findall("wb:sheets/wb:sheet", _NS):
        if sh.attrib.get("name") == sheet_name:
            rid = sh.attrib.get(f"{{{_NS['r']}}}id")
            break
    if not rid:
        return None

    rels = _rels_map(zf, "xl/_rels/workbook.xml.rels")
    target = rels.get(rid)
    if not target:
        return None
    return _resolve_target("xl", target)


def _iter_images_from_xlsx_zip(xlsx_path: Path, sheet_name: str) -> Iterable[Tuple[int, int, bytes]]:
    with zipfile.ZipFile(xlsx_path, "r") as zf:
        sheet_xml = _sheet_xml_path_from_name(zf, sheet_name)
        if not sheet_xml:
            return

        try:
            sheet_root = _zip_read_xml(zf, sheet_xml)
        except KeyError:
            return

        # sheet rels: find drawings targets
        sheet_base_dir = str(Path(sheet_xml).parent).replace("\\", "/")
        sheet_rels = _rels_map(zf, f"{sheet_base_dir}/_rels/{Path(sheet_xml).name}.rels")

        drawing_targets: List[str] = []
        for dr in sheet_root.findall("wb:drawing", _NS):
            drid = dr.attrib.get(f"{{{_NS['r']}}}id")
            if not drid:
                continue
            t = sheet_rels.get(drid)
            if not t:
                continue
            drawing_targets.append(_resolve_target(sheet_base_dir, t))

        for drawing_xml in drawing_targets:
            try:
                drawing_root = _zip_read_xml(zf, drawing_xml)
            except KeyError:
                continue

            drawing_base_dir = str(Path(drawing_xml).parent).replace("\\", "/")
            drawing_rels = _rels_map(zf, f"{drawing_base_dir}/_rels/{Path(drawing_xml).name}.rels")

            anchors = drawing_root.findall("xdr:twoCellAnchor", _NS) + drawing_root.findall("xdr:oneCellAnchor", _NS)
            for anc in anchors:
                frm = anc.find("xdr:from", _NS)
                if frm is None:
                    continue
                row_el = frm.find("xdr:row", _NS)
                col_el = frm.find("xdr:col", _NS)
                if row_el is None or col_el is None:
                    continue
                try:
                    row1 = int(row_el.text or "0") + 1
                    col1 = int(col_el.text or "0") + 1
                except Exception:
                    continue

                blip = anc.find(".//a:blip", _NS)
                if blip is None:
                    continue
                rid = blip.attrib.get(f"{{{_NS['r']}}}embed")
                if not rid:
                    continue
                tgt = drawing_rels.get(rid)
                if not tgt:
                    continue
                media_path = _resolve_target(drawing_base_dir, tgt)
                try:
                    data = zf.read(media_path)
                except KeyError:
                    continue
                yield row1, col1, data


def iter_sheet_images(ws, *, xlsx_path: Path, sheet_name: str) -> Iterable[Tuple[int, int, object, Optional[bytes]]]:
    imgs = getattr(ws, "_images", None) or []
    if imgs:
        for img in imgs:
            anchor = getattr(img, "anchor", None)
            from_ = getattr(anchor, "_from", None)
            row0 = getattr(from_, "row", None)
            col0 = getattr(from_, "col", None)
            if row0 is None:
                continue
            try:
                row1 = int(row0) + 1
            except Exception:
                continue
            try:
                col1 = int(col0) + 1 if col0 is not None else 1
            except Exception:
                col1 = 1
            yield row1, col1, img, None
        return

    # Fallback: parse the XLSX zip and locate drawing anchors + media.
    for row1, col1, data in _iter_images_from_xlsx_zip(xlsx_path, sheet_name):
        yield row1, col1, None, data


def extract_images_and_map(
    *,
    ws,
    material_col: Optional[int],
    material_cols: Optional[List[int]],
    header_row: Optional[int],
    out_dir: Path,
    overwrite: bool,
    limit: Optional[int],
    xlsx_path: Path,
    sheet_name: str,
) -> List[Tuple[str, Path]]:
    out_dir.mkdir(parents=True, exist_ok=True)

    results: List[Tuple[str, Path]] = []

    row_counts: Dict[int, int] = {}
    count = 0
    for row1, col1, img, raw in iter_sheet_images(ws, xlsx_path=xlsx_path, sheet_name=sheet_name):
        if header_row is not None and row1 == header_row:
            continue

        col_for_row = material_col
        if material_cols:
            col_for_row = _choose_nearest_header_col(material_cols, anchor_col=col1)
        if not col_for_row:
            continue

        code_val = ws.cell(row=row1, column=int(col_for_row)).value
        code = str(code_val).strip() if code_val is not None else ""
        if not code:
            continue

        data = None
        if raw is not None:
            data = raw
        else:
            try:
                data = img._data()  # openpyxl internal
            except Exception:
                data = None
        if not data:
            continue
        ext = detect_image_ext(data)
        base = sanitize_filename(code)

        row_counts[row1] = row_counts.get(row1, 0) + 1
        idx = row_counts[row1]
        name = f"{base}{'' if idx == 1 else f'_{idx}'}{ext}"
        dst = out_dir / name
        if dst.exists() and not overwrite:
            results.append((code, dst))
        else:
            dst.write_bytes(data)
            results.append((code, dst))

        count += 1
        if limit is not None and count >= limit:
            return results

    return results


def update_material_images(
    *,
    mappings: List[Tuple[str, str]],
    batch_size: int,
) -> Dict[str, int]:
    if not mappings:
        return {"matched": 0, "updated": 0}

    neo4j_config = get_neo4j_config()
    driver = get_neo4j_driver(neo4j_config)

    matched = 0
    updated = 0
    try:
        with driver.session() as session:
            for i in range(0, len(mappings), batch_size):
                batch = mappings[i : i + batch_size]
                res = session.run(
                    """
                    UNWIND $rows AS row
                    MATCH (m:Material {material_code: row.code})
                    WITH m, row
                    SET m.image = row.image
                    RETURN count(m) AS matched
                    """,
                    {"rows": [{"code": c, "image": p} for c, p in batch]},
                )
                r = res.single()
                if r and r.get("matched") is not None:
                    m = int(r["matched"])
                    matched += m
                    updated += m
    finally:
        try:
            driver.close()
        except Exception:
            pass

    return {"matched": matched, "updated": updated}


def main() -> None:
    load_dotenv()

    p = argparse.ArgumentParser()
    p.add_argument("--xlsx", required=True, help="Path to .xlsx")
    p.add_argument("--list-sheets", action="store_true", help="List sheet names and exit")
    p.add_argument("--sheet", default="", help="Sheet name to process")
    p.add_argument("--material-col", default="", help="Material column: header name OR column letter (e.g. 'A') OR 1-based index")
    p.add_argument("--header-row", type=int, default=0, help="Header row (1-based). 0 means auto-detect")
    p.add_argument("--out-dir", default="backend/data_test/material_images", help="Output directory for extracted images")
    p.add_argument("--path-prefix", default="", help="Prefix to store into m.image (e.g. '/static'). If empty, store absolute path")
    p.add_argument("--dry-run", action="store_true", help="Do not write to Neo4j")
    p.add_argument("--overwrite", action="store_true", help="Overwrite existing image files")
    p.add_argument("--limit", type=int, default=0, help="Limit number of extracted images")
    p.add_argument("--batch-size", type=int, default=200, help="Neo4j batch size")

    args = p.parse_args()

    xlsx_path = Path(args.xlsx).expanduser().resolve()
    if not xlsx_path.exists():
        raise FileNotFoundError(str(xlsx_path))

    if args.list_sheets:
        for name in list_sheets(xlsx_path):
            print(name)
        return

    sheet_name = (args.sheet or "").strip()
    if not sheet_name:
        raise ValueError("--sheet is required unless --list-sheets")

    wb = load_workbook(xlsx_path, data_only=True)
    try:
        if sheet_name not in wb.sheetnames:
            raise ValueError(f"sheet not found: {sheet_name}")
        ws = wb[sheet_name]

        header_row = int(args.header_row or 0)
        if header_row <= 0:
            header_row = guess_header_row(ws) or 1

        material_col_spec = (args.material_col or "").strip()
        if not material_col_spec:
            raise ValueError("--material-col is required")

        material_col: Optional[int] = None
        material_cols: Optional[List[int]] = None
        spec = material_col_spec
        is_index_or_letter = bool(spec.isdigit() or re.fullmatch(r"[A-Za-z]+", spec))
        if is_index_or_letter:
            material_col = _parse_col_spec(ws, spec, header_row)
        else:
            if header_row is None:
                raise ValueError("header row is required to locate material-col by header name")
            cols = _find_header_cols(ws, header_row, spec)
            if not cols:
                raise ValueError(f"could not find header '{spec}' on row {header_row}")
            if len(cols) == 1:
                material_col = cols[0]
            else:
                material_cols = cols

        out_base = Path(args.out_dir).expanduser().resolve()
        out_dir = out_base / sanitize_filename(sheet_name)
        limit = int(args.limit) if int(args.limit or 0) > 0 else None

        pairs = extract_images_and_map(
            ws=ws,
            material_col=material_col,
            material_cols=material_cols,
            header_row=header_row,
            out_dir=out_dir,
            overwrite=bool(args.overwrite),
            limit=limit,
            xlsx_path=xlsx_path,
            sheet_name=sheet_name,
        )

        if not pairs:
            print("No images extracted or no matching rows.")
            return

        mappings: List[Tuple[str, str]] = []
        for code, path in pairs:
            if args.path_prefix:
                rel = path.relative_to(out_base)
                stored = str(Path(args.path_prefix) / rel)
            else:
                stored = str(path)
            mappings.append((code, stored))

        print(f"Extracted {len(pairs)} images into: {out_dir}")
        print(f"Prepared {len(mappings)} material_code -> image mappings")

        if args.dry_run:
            for code, stored in mappings[: min(20, len(mappings))]:
                print(f"{code}\t{stored}")
            print("Dry-run: skip Neo4j update")
            return

        stats = update_material_images(mappings=mappings, batch_size=int(args.batch_size))
        print(f"Neo4j updated. matched={stats['matched']} updated={stats['updated']}")
    finally:
        try:
            wb.close()
        except Exception:
            pass


if __name__ == "__main__":
    main()

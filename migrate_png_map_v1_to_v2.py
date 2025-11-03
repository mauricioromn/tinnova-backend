import csv, os, uuid
from datetime import datetime
from hashlib import sha256
from PIL import Image
import imagehash

from io import BytesIO

def file_bytes(path):
    with open(path, "rb") as f:
        return f.read()

def calc_sha256(path):
    return sha256(file_bytes(path)).hexdigest()

def calc_phash(path):
    with Image.open(path) as im:
        return str(imagehash.phash(im))

def migrate(v1_csv="png_map.csv", images_dir="imagenes_proformas", v2_csv="png_map_v2.csv"):
    # read v1
    rows_v2 = []
    now = datetime.utcnow().isoformat()
    if os.path.exists(v1_csv):
        with open(v1_csv, newline="", encoding="utf-8") as f:
            r = csv.DictReader(f)
            for row in r:
                fn = row.get("filename_png") or row.get("filename") or ""
                img_path = os.path.join(images_dir, fn) if fn else None
                s = calc_sha256(img_path) if img_path and os.path.exists(img_path) else ""
                p = calc_phash(img_path) if img_path and os.path.exists(img_path) else ""
                out = {
                    "image_id": str(uuid.uuid4()),
                    "filename_png": fn,
                    "sha256": s,
                    "phash": p,
                    "source_pdf": row.get("source_pdf",""),
                    "page": row.get("pagina") or row.get("page") or "",
                    "sku": row.get("sku",""),
                    "description_text": row.get("descripcion") or row.get("description_text") or "",
                    "unit": row.get("unit") or "unit",
                    "qty_default": row.get("cantidad") or row.get("qty_default") or "1",
                    "currency": row.get("currency") or "USD",
                    "price_unit": row.get("precio_unitario") or row.get("price_unit") or "",
                    "price_total": row.get("precio_total") or row.get("price_total") or "",
                    "tax_code": row.get("tax_code") or "",
                    "valid_from": now,
                    "valid_to": "",
                    "price_source": "migration",
                    "approved_by": "migration",
                    "approved_at": now,
                    "active": "1",
                }
                # checksum
                import hashlib, json
                payload = json.dumps({k: out[k] for k in [
                    "filename_png","sha256","phash","source_pdf","page",
                    "sku","description_text","unit","qty_default",
                    "currency","price_unit","price_total","tax_code",
                    "valid_from","valid_to","price_source","active"
                ]}, sort_keys=True, ensure_ascii=False)
                out["row_checksum"] = hashlib.sha256(payload.encode("utf-8")).hexdigest()
                rows_v2.append(out)

    # write v2
    headers = ["image_id","filename_png","sha256","phash","source_pdf","page",
               "sku","description_text","unit","qty_default",
               "currency","price_unit","price_total","tax_code",
               "valid_from","valid_to","price_source","approved_by","approved_at",
               "active","row_checksum"]
    with open(v2_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=headers)
        w.writeheader()
        for r in rows_v2:
            w.writerow(r)

if __name__ == "__main__":
    migrate()
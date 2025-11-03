import os
import csv
import time
import uuid
from datetime import datetime
from typing import Optional, List, Dict

from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, Body, Query, Header
from fastapi.responses import JSONResponse

try:
    # when packaged as a module
    from .utils_image_id import sha256_bytes, phash_from_bytes, hamming
except Exception:
    # when placed next to main.py
    from utils_image_id import sha256_bytes, phash_from_bytes, hamming

PNG_MAP_V2 = os.environ.get("PNG_MAP_V2_PATH", "png_map_v2.csv")
ADMIN_KEY = os.environ.get("TINNOVA_ADMIN_KEY", "")

router = APIRouter()

# ---------------------------- helpers ---------------------------------
def _load_map() -> List[Dict]:
    if not os.path.exists(PNG_MAP_V2):
        return []
    with open(PNG_MAP_V2, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return list(reader)

def _write_map(rows: List[Dict]) -> None:
    if not rows:
        # write headers only
        headers = ["image_id","filename_png","sha256","phash","source_pdf","page",
                   "sku","description_text","unit","qty_default",
                   "currency","price_unit","price_total","tax_code",
                   "valid_from","valid_to","price_source","approved_by","approved_at",
                   "active","row_checksum"]
    else:
        headers = list(rows[0].keys())
    tmp = PNG_MAP_V2 + ".tmp"
    with open(tmp, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=headers)
        w.writeheader()
        for r in rows:
            w.writerow(r)
    os.replace(tmp, PNG_MAP_V2)

def _require_admin(x_admin_key: Optional[str] = Header(None)) -> None:
    if not ADMIN_KEY or x_admin_key != ADMIN_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing X-Admin-Key")

def _row_checksum(row: Dict) -> str:
    import hashlib, json
    biz_fields = {k: row.get(k) for k in [
        "filename_png","sha256","phash","source_pdf","page",
        "sku","description_text","unit","qty_default",
        "currency","price_unit","price_total","tax_code",
        "valid_from","valid_to","price_source","active"
    ]}
    payload = json.dumps(biz_fields, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()

# ---------------------------- endpoints --------------------------------

@router.get("/png-map/resolve")
async def resolve_by_hash(sha256: Optional[str] = Query(None), phash: Optional[str] = Query(None)):
    """Debug/lookup endpoint. Provide sha256 and/or phash; returns best match and neighbors."""
    rows = _load_map()

    exact = None
    if sha256:
        for r in rows:
            if r.get("active") in ("1","true","True",1,True) and r.get("sha256")==sha256:
                exact = r
                break

    nearest = []
    if phash:
        for r in rows:
            if r.get("active") not in ("1","true","True",1,True):
                continue
            rp = r.get("phash")
            if not rp:
                continue
            d = hamming(phash, rp)
            nearest.append({"dist": d, "row": r})
        nearest.sort(key=lambda x: x["dist"])

    return {"exact": exact, "nearest": nearest[:5]}

@router.post("/png-map/upsert")
async def upsert_row(
    payload: Dict = Body(...),
    _ok: None = Depends(_require_admin)
):
    """Create/update a row in png_map_v2.csv. Requires X-Admin-Key."""
    rows = _load_map()
    image_id = payload.get("image_id") or str(uuid.uuid4())
    now_iso = datetime.utcnow().isoformat()

    # find existing
    idx = None
    for i, r in enumerate(rows):
        if r.get("image_id") == image_id or (payload.get("sha256") and r.get("sha256")==payload.get("sha256")):
            idx = i
            break

    # normalize row
    base = {
        "image_id": image_id,
        "filename_png": payload.get("filename_png") or "",
        "sha256": payload.get("sha256") or "",
        "phash": payload.get("phash") or "",
        "source_pdf": payload.get("source_pdf") or "",
        "page": str(payload.get("page") or ""),
        "sku": payload.get("sku") or "",
        "description_text": payload.get("description_text") or "",
        "unit": payload.get("unit") or "unit",
        "qty_default": str(payload.get("qty_default") or "1"),
        "currency": payload.get("currency") or "USD",
        "price_unit": str(payload.get("price_unit") or ""),
        "price_total": str(payload.get("price_total") or ""),
        "tax_code": payload.get("tax_code") or "",
        "valid_from": payload.get("valid_from") or now_iso,
        "valid_to": payload.get("valid_to") or "",
        "price_source": payload.get("price_source") or "manual",
        "approved_by": payload.get("approved_by") or "",
        "approved_at": payload.get("approved_at") or "",
        "active": str(int(bool(payload.get("active", True)))),
    }
    base["row_checksum"] = _row_checksum(base)

    if idx is None:
        rows.append(base)
    else:
        rows[idx] = base

    _write_map(rows)
    return {"status": "ok", "image_id": image_id, "row_checksum": base["row_checksum"]}

@router.post("/png-map/approve")
async def approve_row(
    image_id: str = Body(..., embed=True),
    approved_by: Optional[str] = Body("admin", embed=True),
    _ok: None = Depends(_require_admin)
):
    rows = _load_map()
    for r in rows:
        if r.get("image_id")==image_id:
            r["active"] = "1"
            r["approved_by"] = approved_by or "admin"
            r["approved_at"] = datetime.utcnow().isoformat()
            r["row_checksum"] = _row_checksum(r)
            _write_map(rows)
            return {"status":"ok","image_id":image_id}
    raise HTTPException(status_code=404, detail="image_id not found")

@router.post("/resolve-upload")
async def resolve_upload(file: UploadFile = File(...)):
    """Utility endpoint that returns the mapped row for a raw image upload using sha256/phash logic."""
    data = await file.read()
    s = sha256_bytes(data)
    p = phash_from_bytes(data)

    rows = _load_map()

    # exact
    for r in rows:
        if r.get("active") in ("1","true","True",1,True) and r.get("sha256")==s:
            return {"match": "sha256", "dist": 0, "row": r, "sha256": s, "phash": p}

    # nearest by phash
    best = None
    best_d = None
    for r in rows:
        rp = r.get("phash")
        if not rp or r.get("active") not in ("1","true","True",1,True):
            continue
        d = hamming(p, rp)
        if best is None or d < best_d:
            best = r
            best_d = d

    return {"match": "phash" if best is not None else None, "dist": best_d, "row": best, "sha256": s, "phash": p}
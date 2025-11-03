from typing import Dict, List, Optional, Tuple
from .utils_image_id import sha256_bytes, phash_from_bytes, hamming

PHASH_MAX_DIST = 5  # tune to 4–6 after testing

def resolve_image(mapping_rows: List[Dict], uploaded_bytes: bytes) -> Tuple[Optional[Dict], Optional[Dict]]:
    """Return (row, meta) where meta has {'match': 'sha256'|'phash', 'dist': int} or (None, None)."""
    s = sha256_bytes(uploaded_bytes)
    p = phash_from_bytes(uploaded_bytes)

    # 1) exact sha256
    for r in mapping_rows:
        if r.get("active") in (1, "1", True, "true") and r.get("sha256") == s:
            return r, {"match": "sha256", "dist": 0}

    # 2) nearest by phash within threshold
    candidates = []
    for r in mapping_rows:
        if r.get("active") not in (1, "1", True, "true"):
            continue
        rp = r.get("phash")
        if not rp:
            continue
        d = hamming(p, rp)
        if d <= PHASH_MAX_DIST:
            candidates.append((d, r))
    candidates.sort(key=lambda x: x[0])
    if candidates:
        d, r = candidates[0]
        return r, {"match": "phash", "dist": d}
    return None, None
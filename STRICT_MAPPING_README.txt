# Strict Image→Price Mapping Pack

This bundle adds deterministic mapping between an image and its (description, price) via sha256 and perceptual hash (phash).

## Files
- `png_map_v2_template.csv` — header-only template for the new mapping table.
- `utils_image_id.py` — helpers for sha256/phash/hamming.
- `matching.py` — image resolution logic (sha256 first, then phash neighbors).
- `router_strict_map.py` — FastAPI router with endpoints:
  - `GET /png-map/resolve`
  - `POST /png-map/upsert` (requires `X-Admin-Key`)
  - `POST /png-map/approve` (requires `X-Admin-Key`)
  - `POST /resolve-upload`

- `migrate_png_map_v1_to_v2.py` — migrates your old `png_map.csv` to `png_map_v2.csv` (best-effort).

- `MatchBadge.tsx` — React badge to show Exact/Near duplicate state in results.

## FastAPI integration
1. Place `utils_image_id.py`, `matching.py`, `router_strict_map.py` next to your `main.py` (or as a package).
2. Set env vars:
   - `PNG_MAP_V2_PATH=png_map_v2.csv`
   - `TINNOVA_ADMIN_KEY=changeme`
3. In `main.py`:
   ```python
   from fastapi import FastAPI
   from router_strict_map import router as strict_router

   app = FastAPI()
   app.include_router(strict_router)
   ```

## Frontend
Import and display the badge in your result card:
```tsx
import MatchBadge from "./MatchBadge";

<div className="flex items-center gap-2">
  <MatchBadge match={result.match as any} dist={result.dist as any} />
  <span className="text-xs text-gray-500">SKU: {result.row?.sku}</span>
</div>
```

## Migration
1. Put your old images under `imagenes_proformas/` (or adjust the script args).
2. Run: `python migrate_png_map_v1_to_v2.py`
3. Point the app to `PNG_MAP_V2_PATH`.

## Notes
- Tune `PHASH_MAX_DIST` in `matching.py` after sampling your corpus.
- Store `image_id` and `row_checksum` inside every generated proforma to guarantee auditability.
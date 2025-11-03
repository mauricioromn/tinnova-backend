import os, csv, hashlib
from PIL import Image
import imagehash

IMAGES_DIR = "imagenes_proformas"
OUT_FILE = "png_map_v2.csv"

# columnas oficial v2 mínimas para que funcione
columns = [
    "image_id","filename_png","sha256","phash",
    "active","price_unit","currency","description_text","qty_default","price_total"
]

def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

rows = []
counter = 1

print(f"Escaneando carpeta: {IMAGES_DIR}")

for fname in os.listdir(IMAGES_DIR):
    if not fname.lower().endswith((".png", ".jpg", ".jpeg")):
        continue
    
    path = os.path.join(IMAGES_DIR, fname)
    with open(path, "rb") as f:
        data = f.read()
    
    sha = sha256_bytes(data)
    ph = str(imagehash.phash(Image.open(path)))

    image_id = f"{counter:04d}"  # 0001, 0002, ...
    counter += 1

    rows.append({
        "image_id": image_id,
        "filename_png": fname,
        "sha256": sha,
        "phash": ph,
        "active": "1",
        "price_unit": "",          # para llenar luego
        "currency": "USD",
        "description_text": "",    # para llenar luego
        "qty_default": "1",
        "price_total": "",
    })

# escribir CSV
with open(OUT_FILE, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=columns)
    writer.writeheader()
    writer.writerows(rows)

print(f"\n✅ Mapa generado correctamente → {OUT_FILE}")
print(f"🖼️ Total imágenes mapeadas: {len(rows)}")
print("ℹ️ Ahora edita price_unit y description_text en el CSV.")

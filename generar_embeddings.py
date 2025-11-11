import os, pandas as pd, numpy as np
from PIL import Image
from main import _embed_image, STATIC_DIR, BASE_VISUAL_CSV, _ensure_base_visual_exists

_ensure_base_visual_exists()

files = [f for f in os.listdir(STATIC_DIR) if f.lower().endswith(".png")]
print(f"Imágenes encontradas: {len(files)}")

rows = []
for i,f in enumerate(files,1):
    path = os.path.join(STATIC_DIR, f)
    
    try:
        with Image.open(path) as im:
            vec = _embed_image(im)
        rows.append([f] + [float(x) for x in vec])
        print(f"{i}/{len(files)} -> {f}")
    except Exception as e:
        print(f"Error con {f}: {e}")

df = pd.DataFrame(rows)
df.to_csv(BASE_VISUAL_CSV, index=False)
print("✅ Embeddings generados y guardados")

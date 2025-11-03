# ingestar_proformas.py
# Uso:
#   1) Coloca tus PDFs en: ./proformas_nuevas/
#   2) (opcional) Coloca tus items en: ./items_nuevos.csv  (plantilla abajo)
#   3) venv & run:  python ingestar_proformas.py
#
# Qué hace:
#   - Renderiza cada PDF->PNG (1 imagen por página) en ./imagenes_proformas/
#   - Reconstruye base_visual.csv para TODAS las imágenes de ./imagenes_proformas/
#   - (opcional) Fusiona items_nuevos.csv -> cotizaciones.csv (append + normaliza)
#   - NO toca png_map.csv; luego llamas /auto-build-png-map del backend (o usa flag)

import os, re, sys, csv, glob
from typing import List, Tuple
import pandas as pd
import numpy as np

# ===== Settings =====
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
PDF_INPUT_DIR = os.path.join(BASE_DIR, "proformas_nuevas")     # coloca aquí los PDFs nuevos
IMG_DIR = os.path.join(BASE_DIR, "imagenes_proformas")         # output imágenes
BASE_VISUAL_CSV = os.path.join(BASE_DIR, "base_visual.csv")    # embeddings
COTIZACIONES_CSV = os.path.join(BASE_DIR, "cotizaciones.csv")  # histórico (append)
ITEMS_NUEVOS_CSV = os.path.join(BASE_DIR, "items_nuevos.csv")  # opcional

# ====== Requerimientos para renderizado ======
# Usamos PyMuPDF (pymupdf) para PDF->PNG (más simple que instalar poppler)
# pip install pymupdf
import fitz  # PyMuPDF

# ====== CLIP para embeddings ======
# pip install torch transformers pillow
from PIL import Image
from transformers import CLIPModel, AutoProcessor
import torch

def render_pdf_to_images(pdf_path: str, out_dir: str) -> List[str]:
    os.makedirs(out_dir, exist_ok=True)
    doc = fitz.open(pdf_path)
    base = os.path.splitext(os.path.basename(pdf_path))[0]
    out_files = []
    for pno in range(len(doc)):
        page = doc[pno]
        pix = page.get_pixmap(dpi=150)  # 150 es suficiente
        out_name = f"{base}_p{pno+1}_xref.png"
        out_path = os.path.join(out_dir, out_name)
        pix.save(out_path)
        out_files.append(out_path)
    doc.close()
    return out_files

def render_all_pdfs(pdf_dir: str, out_dir: str) -> List[str]:
    pdfs = sorted(glob.glob(os.path.join(pdf_dir, "*.pdf")))
    all_imgs = []
    for pdf in pdfs:
        imgs = render_pdf_to_images(pdf, out_dir)
        all_imgs.extend(imgs)
        print(f"[PDF] {os.path.basename(pdf)} -> {len(imgs)} páginas")
    if not pdfs:
        print("[PDF] No se encontraron PDFs en", pdf_dir)
    return all_imgs

def build_base_visual(images_dir: str, out_csv: str) -> None:
    files = []
    for ext in ("*.png","*.jpg","*.jpeg"):
        files.extend(glob.glob(os.path.join(images_dir, ext)))
    files = sorted(files)
    if not files:
        print("[EMB] No hay imágenes en", images_dir)
        return
    print(f"[EMB] Generando embeddings para {len(files)} imágenes...")
    model = CLIPModel.from_pretrained("openai/clip-vit-base-patch32")
    proc = AutoProcessor.from_pretrained("openai/clip-vit-base-patch32")
    model.eval()
    rows = []
    device = torch.device("cpu")
    model.to(device)
    bs = 16
    for i in range(0, len(files), bs):
        batch_paths = files[i:i+bs]
        images = [Image.open(p).convert("RGB") for p in batch_paths]
        inputs = proc(images=images, return_tensors="pt").to(device)
        with torch.no_grad():
            feats = model.get_image_features(**inputs).cpu().numpy().astype(np.float32)
        # normalizamos
        norms = np.linalg.norm(feats, axis=1, keepdims=True) + 1e-9
        feats = feats / norms
        for p, v in zip(batch_paths, feats):
            rows.append([os.path.basename(p)] + list(map(float, v.tolist())))
    # guardamos CSV
    cols = ["filename"] + [f"f{i}" for i in range(512)]
    df = pd.DataFrame(rows, columns=cols)
    df.to_csv(out_csv, index=False, encoding="utf-8")
    print("[EMB] base_visual.csv actualizado:", out_csv)

def normalize_pdf_name(s: str) -> str:
    base = os.path.splitext(os.path.basename(s or ""))[0]
    name = re.sub(r"[^A-Za-z0-9]+", "", base.strip().lower())
    return name

def merge_items(items_csv: str, cotizaciones_csv: str) -> None:
    if not os.path.isfile(items_csv):
        print("[ITEMS] No existe items_nuevos.csv (salto).")
        return
    df_new = pd.read_csv(items_csv)
    # Normalización básica
    for c in ["cantidad","precio_unitario","precio_total","pagina"]:
        if c in df_new.columns:
            df_new[c] = pd.to_numeric(df_new[c], errors="coerce")
    if "archivo" not in df_new.columns:
        raise RuntimeError("items_nuevos.csv debe tener columna 'archivo' (nombre PDF).")
    df_new["_norm_archivo"] = df_new["archivo"].astype(str).apply(normalize_pdf_name)
    if os.path.isfile(cotizaciones_csv):
        df_old = pd.read_csv(cotizaciones_csv)
        df = pd.concat([df_old, df_new], ignore_index=True)
    else:
        df = df_new
    df.to_csv(cotizaciones_csv, index=False, encoding="utf-8")
    print(f"[ITEMS] {len(df_new)} filas añadidas a {cotizaciones_csv}")

if __name__ == "__main__":
    print("=== Ingesta de proformas ===")
    # 1) Render PDFs -> PNGs
    render_all_pdfs(PDF_INPUT_DIR, IMG_DIR)
    # 2) Re-generar base_visual.csv con TODAS las imágenes
    build_base_visual(IMG_DIR, BASE_VISUAL_CSV)
    # 3) (opcional) Fusionar items_nuevos.csv -> cotizaciones.csv
    merge_items(ITEMS_NUEVOS_CSV, COTIZACIONES_CSV)
    print("Listo. Ahora ejecuta el backend y visita /auto-build-png-map para generar png_map.csv.")

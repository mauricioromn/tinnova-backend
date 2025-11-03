# image_analyzer.py
# Utilidades para cargar la base visual y calcular similitudes con CLIP

import os
import io
import math
import numpy as np
import pandas as pd
from PIL import Image

import torch
from transformers import CLIPModel, CLIPProcessor


# ==== Rutas (ajusta si hiciera falta) ====
BASE_VISUAL_CSV = "base_visual.csv"  # tu archivo ya creado
IMAGE_DIR = os.path.join(os.getcwd(), "imagenes_proformas")  # donde están las imágenes

# ==== Carga perezosa de modelo CLIP ====
_clip_model = None
_clip_processor = None
_device = None

def _ensure_clip():
    global _clip_model, _clip_processor, _device
    if _clip_model is None or _clip_processor is None:
        print("🧠 Cargando modelo CLIP de OpenAI (visual) ...")
        _clip_model = CLIPModel.from_pretrained("openai/clip-vit-base-patch32")
        _clip_processor = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")
        _device = "cuda" if torch.cuda.is_available() else "cpu"
        _clip_model = _clip_model.to(_device)
        print(f"✅ CLIP listo en {_device}")

def embed_image_bytes(image_bytes: bytes) -> np.ndarray:
    """Genera embedding 512D de una imagen en bytes usando CLIP."""
    _ensure_clip()
    imagen = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    inputs = _clip_processor(images=imagen, return_tensors="pt").to(_device)
    with torch.no_grad():
        feats = _clip_model.get_image_features(**inputs)
        feats = feats / feats.norm(p=2, dim=-1, keepdim=True)
    return feats[0].detach().cpu().numpy().astype(np.float32)

def embed_image_path(path: str) -> np.ndarray:
    with open(path, "rb") as f:
        return embed_image_bytes(f.read())

# ==== Base Visual: filename + vector(512) ====
_base_visual_df = None
_base_visual_matrix = None

def load_base_visual(csv_path: str = BASE_VISUAL_CSV):
    """Lee base_visual.csv (sin encabezado). Columna 0 = filename, 1..512 = vector."""
    global _base_visual_df, _base_visual_matrix
    if _base_visual_df is not None:
        return _base_visual_df, _base_visual_matrix

    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"No se encontró {csv_path}")

    # Si no tiene cabecera: filename + 512 columnas numéricas
    df = pd.read_csv(csv_path, header=None)
    if df.shape[1] < 2:
        raise ValueError("base_visual.csv no tiene formato válido (debe ser filename + 512 valores).")

    df = df.rename(columns={0: "filename"})
    # Normalizamos los vectores
    vecs = df.iloc[:, 1:].astype(np.float32).values
    norms = np.linalg.norm(vecs, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    vecs = vecs / norms

    _base_visual_df = df
    _base_visual_matrix = vecs
    print(f"📦 Base visual cargada: {len(df)} imágenes.")
    return _base_visual_df, _base_visual_matrix

def cosine_sim(a: np.ndarray, B: np.ndarray) -> np.ndarray:
    """Similitud coseno entre vector a (512,) y matriz B (N,512)."""
    return (a @ B.T)

def topk_similares_por_bytes(img_bytes: bytes, k: int = 6):
    """Devuelve top-k: [{filename, score}] usando bytes de imagen."""
    df, mat = load_base_visual()
    q = embed_image_bytes(img_bytes)
    sims = cosine_sim(q, mat)
    idx = np.argsort(-sims)[:k]
    out = []
    for i in idx:
        out.append({
            "filename": df.iloc[i]["filename"],
            "score": float(sims[i])
        })
    return out

def topk_similares_por_filename(filename: str, k: int = 6):
    """Conveniencia: calcula similares usando una imagen de la base por ruta."""
    full = os.path.join(IMAGE_DIR, filename)
    if not os.path.exists(full):
        raise FileNotFoundError(f"No existe imagen: {full}")
    with open(full, "rb") as f:
        return topk_similares_por_bytes(f.read(), k=k)





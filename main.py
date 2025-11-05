# =============================
# main.py — Cotizador Tinnova S.A.C. (v4.6.2 + fallback xref + CLIP local cache)
# =============================

from __future__ import annotations
import os, io, re, uuid, csv, logging
from datetime import datetime
from typing import List, Optional
from pathlib import Path  # <-- para cache local de modelos

# ========= Logging global ==========
logger = logging.getLogger("tinnova")
if not logger.handlers:
    logging.basicConfig(level=logging.INFO)

# ========= ENV / CLOUD ==========
from dotenv import load_dotenv
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE = os.getenv("SUPABASE_SERVICE_ROLE")

AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_REGION = os.getenv("AWS_REGION", "us-east-2")
S3_BUCKET = os.getenv("S3_BUCKET")

from supabase import create_client, Client
supabase: Optional[Client] = None
if SUPABASE_URL and SUPABASE_SERVICE_ROLE:
    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE)
    except Exception as e:
        logger.warning(f"[SUPABASE] No inicializado: {e}")

import boto3
s3 = None
if AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY and S3_BUCKET:
    try:
        s3 = boto3.client(
            "s3",
            aws_access_key_id=AWS_ACCESS_KEY_ID,
            aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
            region_name=AWS_REGION,
        )
    except Exception as e:
        logger.warning(f"[S3] No inicializado: {e}")

# ========= FastAPI ==========
import numpy as np
import pandas as pd
from PIL import Image

from fastapi import FastAPI, File, Form, UploadFile, HTTPException, Body, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import Response
from pydantic import BaseModel, Field

app = FastAPI(title="Cotizador Tinnova", version="4.6.2")

ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:5173,https://app.tinnova.pe").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in ALLOWED_ORIGINS if o.strip() ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ========= Paths ==========
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "imagenes_proformas")
PROFORMAS_DIR = os.path.join(BASE_DIR, "proformas")
os.makedirs(STATIC_DIR, exist_ok=True)
os.makedirs(PROFORMAS_DIR, exist_ok=True)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
app.mount("/proformas", StaticFiles(directory=PROFORMAS_DIR), name="proformas")

# ========= Empresa ==========
COMPANY_NAME = "Tinnova S.A.C."
COMPANY_RUC = "RUC: 20563369745"
COMPANY_ADDRESS = "Avenida Los Heróes 1040, San Juan de Miraflores"
COMPANY_PHONE = "Tel: +51 921396308"
COMPANY_EMAIL = "contacto@tinnova.pe"
COMPANY_WEB = "www.tinnova.pe"
COMPANY_LOGO_PATH = os.path.join(STATIC_DIR, "logo.png")

# ========= Archivos ==========
BASE_VISUAL_CSV = os.path.join(BASE_DIR, "base_visual.csv")
PNG_MAP_CSV = os.path.join(BASE_DIR, "png_map.csv")
COTIZACIONES_CSV = os.path.join(BASE_DIR, "cotizaciones.csv")

# ========= Config ==========
STRICT_MAP_ONLY = True
SIMILARITY_THRESHOLD = 0.70
RETURN_ONLY_MAPPED = True
AUTO_SANITIZE_DESC = True

import re as _re

_BRAND_BLACKLIST_BASE = {
    "tp", "teleperformance", "aces", "cumbra",
    "siemens", "nike", "bbva", "bcp", "scotiabank",
    "interbank", "tottus", "ripley", "saga falabella",
}
_OCR_FIXES = [
    (_re.compile(r"\bedificaci\s+ones\b", _re.I), "edificaciones"),
    (_re.compile(r"\s{2,}"), " "),
    (_re.compile(r"\s+([,.;:])"), r"\1"),
]
_brand_tail_regex = None

def _rebuild_brand_regex():
    global _brand_tail_regex
    brands = set(_BRAND_BLACKLIST_BASE)
    if os.path.exists(COTIZACIONES_CSV):
        try:
            dfc = pd.read_csv(COTIZACIONES_CSV)
            if "empresa" in dfc.columns:
                for v in dfc["empresa"].dropna().astype(str):
                    v = v.strip().lower()
                    if 2 <= len(v) <= 50:
                        brands.add(v)
        except Exception:
            pass
    if not brands:
        _brand_tail_regex = None
        return
    brands = sorted({b for b in brands if b.strip()}, key=len, reverse=True)
    esc = [_re.escape(b) for b in brands]
    _brand_tail_regex = _re.compile(rf"(?:\s|[-—,.:])*(?:{'|'.join(esc)})\s*$", _re.I)

def _limpiar_desc(texto: Optional[str]) -> str:
    if not isinstance(texto, str):
        return ""
    t = texto.strip()
    for pat, rep in _OCR_FIXES:
        t = pat.sub(rep, t)
    if _brand_tail_regex:
        t = _brand_tail_regex.sub("", t).strip()
    t = _re.sub(r"(?:\s|[-—,.:])*\b[A-ZÁÉÍÓÚÑ][A-Za-zÁÉÍÓÚÑ&\-/]{1,}\s*$", "", t).strip()
    t = t.strip(" .,-–—")
    t = _re.sub(r"\s{2,}", " ", t)
    return t

# ========= MODELOS ==========
class SimilarItem(BaseModel):
    filename: str
    similitud: float
    url: str
    precio_unitario_estimado: Optional[float] = None
    descripcion_sugerida: Optional[str] = None

class BuscarSimilaresResponse(BaseModel):
    resultados: List[SimilarItem]

class SeleccionInfo(BaseModel):
    filename: str
    imagen_url: str

class EntradaInfo(BaseModel):
    cantidad: int
    descripcion: Optional[str] = None

class ResultadoCotizacion(BaseModel):
    precio_unitario_estimado: float
    total_estimado: float

class CotizarResponse(BaseModel):
    seleccion: SeleccionInfo
    entrada: EntradaInfo
    resultado: ResultadoCotizacion

class ProformaItemIn(BaseModel):
    filename: str
    cantidad: int = Field(..., gt=0)
    descripcion: Optional[str] = None
    precio_unitario_override: Optional[float] = None
    is_custom: Optional[bool] = False
    custom_filename: Optional[str] = None

class ProformaDatos(BaseModel):
    cliente: str
    contacto: Optional[str] = None
    ruc: Optional[str] = None
    direccion: Optional[str] = None
    fecha: Optional[str] = Field(None)
    validez_oferta_dias: Optional[int] = 15
    tiempo_produccion: Optional[str] = None
    condiciones_pago: Optional[str] = None
    entrega: Optional[str] = None
    observaciones: Optional[str] = None
    igv_porcentaje: Optional[float] = 18.0
    moneda: Optional[str] = "S/"
    cotizado_por: Optional[str] = None

class ProformaPayload(BaseModel):
    datos: ProformaDatos
    items: List[ProformaItemIn]

class ProformaResumenItem(BaseModel):
    filename: str
    cantidad: int
    descripcion: str
    precio_unitario: float
    total: float

class ProformaResumen(BaseModel):
    numero: str
    cliente: str
    fecha: str
    subtotal: float
    igv: float
    total: float
    items: List[ProformaResumenItem]
    pdf_url: str

class PngMapUpsert(BaseModel):
    filename_png: str
    descripcion: Optional[str] = None
    cantidad: Optional[float] = None
    precio_unitario: Optional[float] = None
    precio_total: Optional[float] = None
    pagina: Optional[int] = None
    archivo_pdf: Optional[str] = None

# ========= CLIP & EMBEDDINGS ==========
_clip_model = None
_clip_processor = None
_filenames: List[str] = []
_embeddings: Optional[np.ndarray] = None

def _ensure_base_visual_exists():
    if not os.path.isfile(BASE_VISUAL_CSV):
        with open(BASE_VISUAL_CSV, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["filename"] + [f"f{i}" for i in range(512)])

def _load_base_visual():
    global _filenames, _embeddings
    _ensure_base_visual_exists()
    df = pd.read_csv(BASE_VISUAL_CSV)
    if df.shape[0] == 0:
        _filenames = []
        _embeddings = np.zeros((0, 512), np.float32)
        return
    _filenames = df.iloc[:, 0].astype(str).tolist()
    vecs = df.iloc[:, 1:].to_numpy(np.float32)
    norms = np.linalg.norm(vecs, axis=1, keepdims=True) + 1e-9
    _embeddings = vecs / norms

# ==== PARCHE: cargar CLIP desde cache local primero; si no existe, descargar y guardar ====
from transformers import CLIPModel, CLIPProcessor

def _load_clip():
    global _clip_model, _clip_processor
    if _clip_model is not None and _clip_processor is not None:
        return

    MODEL_ID = "openai/clip-vit-base-patch32"
    MODEL_DIR = Path(__file__).parent / "models" / "clip"

    # 1) Intentar modo offline (cache local)
    try:
        _clip_processor = CLIPProcessor.from_pretrained(MODEL_DIR, local_files_only=True)
        _clip_model = CLIPModel.from_pretrained(MODEL_DIR, local_files_only=True)
        _clip_model.eval()
        logger.info(f"[CLIP] Cargado desde cache local: {MODEL_DIR}")
        return
    except Exception as e:
        logger.warning(f"[CLIP] Cache local no disponible ({MODEL_DIR}): {e}")

    # 2) Si no hay cache, descargar y guardar (solo primera vez)
    try:
        logger.info(f"[CLIP] Descargando {MODEL_ID} y guardando en {MODEL_DIR} ...")
        MODEL_DIR.mkdir(parents=True, exist_ok=True)
        _clip_processor = CLIPProcessor.from_pretrained(MODEL_ID)
        _clip_model = CLIPModel.from_pretrained(MODEL_ID)
        _clip_processor.save_pretrained(MODEL_DIR)
        _clip_model.save_pretrained(MODEL_DIR)
        _clip_model.eval()
        logger.info(f"[CLIP] Descargado y guardado en {MODEL_DIR}")
    except Exception as e:
        logger.exception(f"[CLIP] No se pudo cargar el modelo: {e}")
        raise HTTPException(status_code=500, detail="No se pudo cargar el modelo CLIP")

def _embed_image(pil_img: Image.Image) -> np.ndarray:
    if _clip_model is None or _clip_processor is None:
        _load_clip()
    import torch
    device = torch.device("cpu")
    _clip_model.to(device)
    inputs = _clip_processor(images=pil_img.convert("RGB"), return_tensors="pt")
    with torch.no_grad():
        feats = _clip_model.get_image_features(**{k: v.to(device) for k, v in inputs.items()})
    v = feats.cpu().numpy().astype(np.float32).reshape(-1)
    return v / (np.linalg.norm(v) + 1e-9)

def _append_image_to_base_visual(filename_png: str):
    global _filenames, _embeddings
    _ensure_base_visual_exists()
    base = os.path.basename(filename_png)
    if base in set(_filenames or []): return
    ruta = os.path.join(STATIC_DIR, base)
    if not os.path.exists(ruta): return
    with Image.open(ruta) as im:
        vec = _embed_image(im)
    row = [base] + [float(x) for x in vec.tolist()]
    need_header = os.path.getsize(BASE_VISUAL_CSV) == 0
    with open(BASE_VISUAL_CSV, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if need_header:
            writer.writerow(["filename"]+[f"f{i}" for i in range(512)])
        writer.writerow(row)
    if _embeddings is None or _embeddings.shape[0] == 0:
        _filenames=[base]
        _embeddings=np.array([vec], np.float32)
    else:
        _filenames.append(base)
        _embeddings=np.vstack([_embeddings, vec.astype(np.float32)])

def _topk(query: np.ndarray, k: int) -> List['SimilarItem']:
    if _embeddings is None or len(_filenames)==0:
        _load_base_visual()
    if _embeddings.shape[0]==0:
        return []
    sims = _embeddings @ query
    idx = np.argsort(-sims)[:max(1,k)]
    out=[]
    for i in idx:
        out.append(SimilarItem(
            filename=_filenames[i],
            similitud=float(round(float(sims[i]),4)),
            url=f"/static/{_filenames[i]}"
        ))
    return out

# ========= PNG MAP helpers (con Fallback) ==========
_png_map_df: Optional[pd.DataFrame] = None

def _leer_png_map():
    global _png_map_df
    if _png_map_df is not None:
        return _png_map_df
    if not os.path.isfile(PNG_MAP_CSV):
        _png_map_df = None
        return None
    df = pd.read_csv(PNG_MAP_CSV)
    req = ["filename_png","archivo_pdf","pagina","descripcion","cantidad","precio_unitario","precio_total"]
    for c in req:
        if c not in df.columns:
            raise ValueError("png_map.csv columnas inválidas")
    df["filename_png"]=df["filename_png"].astype(str)
    for c in ["cantidad","precio_unitario","precio_total"]:
        df[c]=pd.to_numeric(df[c], errors="coerce")
    df["pagina"]=pd.to_numeric(df["pagina"], errors="coerce").astype("Int64")
    _rebuild_brand_regex()
    _png_map_df = df
    return _png_map_df

# ✅ Fallback _xrefNN → _xref
def _map_row(filename_png: str) -> Optional[dict]:
    df = _leer_png_map()
    if df is None: return None
    b = os.path.basename(filename_png)

    # match exacto
    r = df[df["filename_png"] == b]
    if not r.empty:
        return r.iloc[0].to_dict()

    # fallback: _xref10.png → _xref.png
    b2 = re.sub(r"_xref\d+\.png$", "_xref.png", b, flags=re.IGNORECASE)
    if b2 != b:
        r2 = df[df["filename_png"] == b2]
        if not r2.empty:
            return r2.iloc[0].to_dict()

    return None

def _upsert_png_map_row(filename_png, descripcion, cantidad, pu, total, archivo_pdf):
    cols=["filename_png","archivo_pdf","pagina","descripcion","cantidad","precio_unitario","precio_total"]
    if os.path.exists(PNG_MAP_CSV):
        df=pd.read_csv(PNG_MAP_CSV)
        for c in cols:
            if c not in df.columns: df[c]=None
    else:
        df=pd.DataFrame(columns=cols)
    if "pagina" in df.columns:
        df["pagina"]=pd.to_numeric(df["pagina"], errors="coerce").astype("Int64")
    for c in ["cantidad","precio_unitario","precio_total"]:
        df[c]=pd.to_numeric(df[c], errors="coerce")
    fn=os.path.basename(filename_png)
    exists=df["filename_png"].astype(str)==fn
    if exists.any():
        idx=df.index[exists][0]
        df.at[idx,"archivo_pdf"]=archivo_pdf or df.at[idx,"archivo_pdf"]
        df.at[idx,"descripcion"]=descripcion or df.at[idx,"descripcion"]
        df.at[idx,"cantidad"]=cantidad if cantidad is not None else df.at[idx,"cantidad"]
        df.at[idx,"precio_unitario"]=pu if pu is not None else df.at[idx,"precio_unitario"]
        df.at[idx,"precio_total"]=total if total is not None else df.at[idx,"precio_total"]
    else:
        df=pd.concat([df,pd.DataFrame([{
            "filename_png":fn,"archivo_pdf":archivo_pdf,"pagina":None,
            "descripcion":descripcion,"cantidad":cantidad,"precio_unitario":pu,"precio_total":total
        }])], ignore_index=True)
    df.to_csv(PNG_MAP_CSV, index=False, encoding="utf-8")
    global _png_map_df; _png_map_df=None

def _strict_desc(filename_png: str) -> Optional[str]:
    row=_map_row(filename_png)
    if not row: return None
    d=str(row.get("descripcion","") or "").strip()
    if not d: return None
    return _limpiar_desc(d) if AUTO_SANITIZE_DESC else d

def _strict_pu(filename_png: str) -> Optional[float]:
    row=_map_row(filename_png)
    if row is None: return None
    pu=row.get("precio_unitario",None)
    if pu is not None and not (pd.isna(pu)):
        return float(pu)
    pt=row.get("precio_total",None)
    q=row.get("cantidad",None)
    try:
        if pt is not None and q not in (None,0,np.nan) and not pd.isna(pt) and not pd.isna(q):
            return float(pt)/float(q)
    except: pass
    return None

# ========= Proforma counter ==========
def _next_number() -> str:
    p=os.path.join(PROFORMAS_DIR,"contador_proformas.txt")
    if not os.path.exists(p):
        with open(p,"w") as f:f.write("1")
        n=1
    else:
        with open(p) as f:txt=f.read().strip()
        n=int(txt) if txt.isdigit() else 1
        with open(p,"w") as f:f.write(str(n+1))
    return f"PF-{n:06d}"

# ========= Supabase / S3 helpers ==========
def sb_get_or_create_cliente(nombre,contacto,ruc,direccion):
    if not supabase or not nombre:
        return None
    nombre_norm=(nombre or "").strip()
    ruc_norm=(ruc or "").strip()
    try:
        if ruc_norm:
            sel=supabase.table("clientes").select("id").eq("ruc",ruc_norm).limit(1).execute()
            if sel.data: return sel.data[0]["id"]
        sel=supabase.table("clientes").select("id").ilike("nombre",nombre_norm).limit(1).execute()
        if sel.data:
            cid=sel.data[0]["id"]
            supabase.table("clientes").update({
                "contacto":contacto,"direccion":direccion,"ruc":ruc or None
            }).eq("id",cid).execute()
            return cid
        ins=supabase.table("clientes").insert({
            "nombre":nombre_norm,"contacto":contacto,"ruc":ruc_norm or None,"direccion":direccion
        }).select("id").execute()
        return ins.data[0]["id"] if ins.data else None
    except Exception as e:
        logger.warning(f"[SUPABASE] cliente: {e}")
        return None

def sb_insert_proforma(cliente_id,numero,fecha_iso,archivo_pdf_url,total):
    if not supabase:return
    try:
        supabase.table("proformas").insert({
            "cliente_id":cliente_id,"fecha":fecha_iso,"numero":numero,
            "archivo_pdf":archivo_pdf_url,"total":float(total)
        }).execute()
    except Exception as e:
        logger.warning(f"[SUPABASE] proforma: {e}")

def s3_upload_local_file(local_path,key):
    if not s3 or not S3_BUCKET:
        return None
    try:
        s3.upload_file(local_path,S3_BUCKET,key)
        return f"s3://{S3_BUCKET}/{key}"
    except Exception as e:
        logger.warning(f"[S3] upload: {e}")
        return None

# ========= Rutas básicas ==========
@app.get("/")
def root(): return {"service":"tinnova-api","ok":True}

@app.get("/health")
def health(): return {"status":"ok"}

@app.get("/favicon.ico")
def favicon(): return Response(status_code=204)

# ========= subir imagen custom ==========
@app.post("/subir-imagen-custom")
async def subir_imagen_custom(imagen: UploadFile = File(...)):
    try:
        fname=imagen.filename or "upload"
        ext=os.path.splitext(fname)[1].lower()
        if ext not in [".png",".jpg",".jpeg",".webp",".bmp",".gif",".tif",".tiff"]:
            raise HTTPException(status_code=422,detail="Formato no soportado")
        content=await imagen.read()
        try: im=Image.open(io.BytesIO(content)).convert("RGB")
        except: raise HTTPException(status_code=422,detail="No se pudo leer la imagen")
        new_name=f"custom_{uuid.uuid4().hex}.png"
        out_path=os.path.join(STATIC_DIR,new_name)
        im.save(out_path,"PNG",optimize=True)
        try: _append_image_to_base_visual(new_name)
        except Exception as e: logger.warning(f"[embed fail] {e}")
        return {"filename":new_name,"url":f"/static/{new_name}"}
    except HTTPException:raise
    except Exception as e:
        logger.exception(e)
        raise HTTPException(status_code=500,detail="Error subiendo imagen")

# ========= auto build map ==========
@app.get("/auto-build-png-map")
@app.post("/auto-build-png-map")
def auto_build_png_map():
    if not os.path.isfile(COTIZACIONES_CSV):
        raise HTTPException(status_code=400,detail="No existe cotizaciones.csv")
    df=pd.read_csv(COTIZACIONES_CSV)
    for c in ["cantidad","precio_unitario","precio_total","pagina"]:
        if c in df.columns: df[c]=pd.to_numeric(df[c],errors="coerce")
    if "archivo" not in df.columns or "pagina" not in df.columns:
        raise HTTPException(status_code=400,detail="csv requiere archivo & pagina")
    rows=[]
    df["_f"]=pd.to_datetime(df["fecha"],dayfirst=True,errors="coerce")
    for (archivo,pagina),sub in df.groupby(["archivo","pagina"]):
        archivo=str(archivo);pagina=int(pagina) if not pd.isna(pagina) else None
        base=re.sub(r"\.pdf$","",os.path.basename(archivo))
        fn=f"{base}_p{pagina}_xref.png" if pagina else f"{base}_xref.png"
        sub_sorted=sub.sort_values("_f",ascending=False)
        desc=""
        for _,rr in sub_sorted.iterrows():
            d=str(rr.get("descripcion","") or "").strip()
            if d:desc=d;break
        cantidad=sub["cantidad"].median() if "cantidad" in sub.columns else None
        pu=sub["precio_unitario"].median() if "precio_unitario" in sub.columns else None
        pt=sub["precio_total"].median() if "precio_total" in sub.columns else None
        rows.append({
            "filename_png":fn,"archivo_pdf":os.path.basename(archivo),"pagina":pagina,
            "descripcion":desc,"cantidad":cantidad,"precio_unitario":pu,"precio_total":pt
        })
    out=pd.DataFrame(rows,columns=["filename_png","archivo_pdf","pagina","descripcion","cantidad","precio_unitario","precio_total"])
    out.to_csv(PNG_MAP_CSV,index=False,encoding="utf-8")
    global _png_map_df;_png_map_df=None;_rebuild_brand_regex()
    return {"status":"ok","filas":len(out)}

# ========= set map ==========
@app.post("/set-png-map")
def set_png_map(item:PngMapUpsert):
    _upsert_png_map_row(
        filename_png=item.filename_png,descripcion=item.descripcion or "",
        cantidad=int(item.cantidad) if item.cantidad is not None else None,
        pu=float(item.precio_unitario) if item.precio_unitario is not None else None,
        total=float(item.precio_total) if item.precio_total is not None else None,
        archivo_pdf=item.archivo_pdf,
    )
    return {"status":"ok"}

# ========= debug precio ==========
@app.get("/debug-precio")
@app.post("/debug-precio")
async def debug_precio(request:Request,filename:Optional[str]=Query(None)):
    if (not filename) and request.method=="POST":
        try: filename=(await request.json()).get("filename")
        except: pass
    if not filename: raise HTTPException(status_code=422,detail="Falta filename")
    info=_map_row(filename)
    return {"filename":filename,"png_map_row":info}

# ========= buscar similares ==========
@app.post("/buscar-similares-imagen",response_model=BuscarSimilaresResponse)
async def buscar_similares_imagen(
    imagen:UploadFile = File(...),
    top_k:int=Form(6),
    min_sim:float=Query(SIMILARITY_THRESHOLD),
    only_mapped:bool=Query(True)
):
    if top_k<=0 or top_k>50: top_k=6
    content=await imagen.read()
    try: pil_img=Image.open(io.BytesIO(content))
    except: raise HTTPException(status_code=422,detail="No se pudo abrir imagen")
    try:
        if _embeddings is None or len(_filenames)==0:_load_base_visual()
        q=_embed_image(pil_img)
        candidatos=_topk(q,k=top_k*3)
    except Exception as e:
        logger.exception(e);raise HTTPException(status_code=500,detail=str(e))
    items=[]
    for it in candidatos:
        if it.similitud<float(min_sim):continue
        row=_map_row(it.filename)
        if only_mapped and row is None: continue
        desc=_strict_desc(it.filename) or ""
        pu=_strict_pu(it.filename)
        it.descripcion_sugerida=desc
        it.precio_unitario_estimado=None if pu is None else round(float(pu),2)
        items.append(it)
        if len(items)>=top_k:break
    return BuscarSimilaresResponse(resultados=items)

# ========= cotizar ==========
@app.post("/cotizar-desde-seleccion",response_model=CotizarResponse)
async def cotizar_desde_seleccion(
    filename:str=Form(...),
    cantidad:int=Form(...),
    descripcion:Optional[str]=Form(None),
    precio_unitario_override:Optional[float]=Form(None)
):
    if cantidad<=0: raise HTTPException(422,"Cantidad debe ser >0")
    row=_map_row(filename)
    if row is None: raise HTTPException(422,"PNG no está en mapa")
    desc_in=(descripcion or "").strip()
    desc=_limpiar_desc(desc_in) if (AUTO_SANITIZE_DESC and desc_in) else (desc_in or (_strict_desc(filename) or ""))
    if precio_unitario_override is not None:
        try: pu=float(precio_unitario_override)
        except: raise HTTPException(422,"Override inválido")
        if pu<0: raise HTTPException(422,"Override negativo")
    else:
        pu=_strict_pu(filename)
        if pu is None: raise HTTPException(422,"Sin precio en mapa")
        pu=float(pu)
    total=float(round(pu*cantidad,2))
    return CotizarResponse(
        seleccion=SeleccionInfo(filename=filename,imagen_url=f"/static/{filename}"),
        entrada=EntradaInfo(cantidad=cantidad,descripcion=desc),
        resultado=ResultadoCotizacion(precio_unitario_estimado=float(round(pu,4)),total_estimado=total)
    )

# ========= generar proforma ==========
@app.post("/generar-proforma",response_model=ProformaResumen)
async def generar_proforma(payload:ProformaPayload=Body(...)):
    if not payload.items: raise HTTPException(422,"Sin items")
    if not payload.datos.cliente: raise HTTPException(422,"Cliente requerido")
    fecha_str=payload.datos.fecha or datetime.now().strftime("%d/%m/%Y")
    igv_pct=float(payload.datos.igv_porcentaje or 18.0)
    moneda=payload.datos.moneda or "S/"
    resumen_items=[]; subtotal=0.0

    for it in payload.items:
        if it.is_custom:
            if not it.custom_filename: raise HTTPException(422,f"{it.filename}: falta custom_filename")
            if it.precio_unitario_override is None: raise HTTPException(422,f"{it.filename}: falta precio")
            try: pu=float(it.precio_unitario_override)
            except: raise HTTPException(422,f"{it.filename}: override inválido")
            if pu<0: raise HTTPException(422,f"{it.filename}: override negativo")
            desc=_limpiar_desc((it.descripcion or "").strip()) if AUTO_SANITIZE_DESC else (it.descripcion or "")
            try:_append_image_to_base_visual(os.path.basename(it.custom_filename))
            except:pass
            total_l=float(round(pu*it.cantidad,2));subtotal+=total_l
            resumen_items.append(ProformaResumenItem(
                filename=os.path.basename(it.custom_filename),cantidad=it.cantidad,
                descripcion=desc,precio_unitario=float(round(pu,4)),total=total_l))
            continue

        row=_map_row(it.filename)
        if row is None: raise HTTPException(422,f"{it.filename} sin mapa")
        desc_in=(it.descripcion or "").strip()
        desc=_limpiar_desc(desc_in) if (AUTO_SANITIZE_DESC and desc_in) else (desc_in or (_strict_desc(it.filename) or ""))
        if it.precio_unitario_override is not None:
            try: pu=float(it.precio_unitario_override)
            except: raise HTTPException(422,"override inválido")
            if pu<0: raise HTTPException(422,"override negativo")
        else:
            pu_map=_strict_pu(it.filename)
            if pu_map is None: raise HTTPException(422,f"{it.filename}: sin precio")
            pu=float(pu_map)
        total_l=float(round(pu*it.cantidad,2));subtotal+=total_l
        resumen_items.append(ProformaResumenItem(
            filename=it.filename,cantidad=it.cantidad,
            descripcion=desc,precio_unitario=float(round(pu,4)),total=total_l
        ))

    igv=round(subtotal*(igv_pct/100),2);total=round(subtotal+igv,2)
    numero=_next_number()
    pdf_path=os.path.join(PROFORMAS_DIR,f"{numero}.pdf")
    _crear_pdf(pdf_path,numero,fecha_str,payload.datos,resumen_items,subtotal,igv,total,moneda,igv_pct)

    s3_key=f"proformas/{numero}.pdf"
    s3_url=s3_upload_local_file(pdf_path,s3_key) or f"/proformas/{numero}.pdf"

    cot_cols=["archivo","pagina","fecha","empresa","descripcion","cantidad","precio_unitario","precio_total","filename_png"]
    cot_rows=[]
    for it in resumen_items:
        cot_rows.append({
            "archivo":os.path.basename(pdf_path),"pagina":None,"fecha":fecha_str,
            "empresa":payload.datos.cliente,"descripcion":it.descripcion,"cantidad":it.cantidad,
            "precio_unitario":it.precio_unitario,"precio_total":it.total,"filename_png":os.path.basename(it.filename),
        })
    if os.path.exists(COTIZACIONES_CSV):
        df_old=pd.read_csv(COTIZACIONES_CSV)
        for c in cot_cols:
            if c not in df_old.columns: df_old[c]=None
        df=pd.concat([df_old,pd.DataFrame(cot_rows,columns=cot_cols)],ignore_index=True)
        df.to_csv(COTIZACIONES_CSV,index=False)
    else:
        pd.DataFrame(cot_rows,columns=cot_cols).to_csv(COTIZACIONES_CSV,index=False)

    for it in resumen_items:
        _upsert_png_map_row(
            filename_png=os.path.basename(it.filename),
            descripcion=it.descripcion,cantidad=it.cantidad,
            pu=it.precio_unitario,total=it.total,archivo_pdf=os.path.basename(pdf_path)
        )

    try: fecha_iso=datetime.strptime(fecha_str,"%d/%m/%Y").isoformat()
    except: fecha_iso=datetime.now().isoformat()

    cliente_id=sb_get_or_create_cliente(
        payload.datos.cliente,payload.datos.contacto,
        payload.datos.ruc,payload.datos.direccion
    )
    sb_insert_proforma(cliente_id,numero,fecha_iso,s3_url,total)

    return ProformaResumen(
        numero=numero,cliente=payload.datos.cliente,fecha=fecha_str,
        subtotal=float(round(subtotal,2)),igv=igv,total=total,
        items=resumen_items,pdf_url=(s3_url if s3_url.startswith("s3://") else f"/proformas/{numero}.pdf")
    )

# ========= PDF helpers ==========
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

def _flow_img(filename:str,max_lado_mm:float=35.0):
    try:
        ruta=os.path.join(STATIC_DIR,filename)
        if not os.path.exists(ruta):return ""
        from PIL import Image as PILImage
        with PILImage.open(ruta) as im:w,h=im.size
        if w==0 or h==0:return ""
        esc=(max_lado_mm*mm)/max(w,h)
        return RLImage(ruta,width=w*esc,height=h*esc)
    except:return ""

def _crear_pdf(pdf_path,numero,fecha,datos,items,subtotal,igv,total,moneda,igv_pct):
    doc=SimpleDocTemplate(pdf_path,pagesize=A4,rightMargin=24,leftMargin=24,topMargin=24,bottomMargin=24,title=f"Proforma {numero}")
    styles=getSampleStyleSheet()
    p_desc=ParagraphStyle("DescWrap",parent=styles["Normal"],leading=13,fontSize=10,wordWrap="CJK")
    p_right=ParagraphStyle("Right",parent=styles["Normal"],alignment=2)
    p_right_b=ParagraphStyle("RightB",parent=styles["Normal"],alignment=2,fontName="Helvetica-Bold")
    story=[]
    logo=RLImage(COMPANY_LOGO_PATH,width=120,height=60) if os.path.exists(COMPANY_LOGO_PATH) else ""
    empresa=[f"<b>{COMPANY_NAME}</b>",COMPANY_RUC,COMPANY_ADDRESS,COMPANY_PHONE,COMPANY_EMAIL,COMPANY_WEB]
    empresa=[Paragraph(x,styles["Normal"]) for x in empresa if x]
    header=Table([[logo,empresa]],colWidths=[60*mm,None],hAlign="LEFT")
    header.setStyle(TableStyle([("VALIGN",(0,0),(-1,-1),"MIDDLE"),("LEFTPADDING",(0,0),(-1,-1),0),
                                ("RIGHTPADDING",(0,0),(-1,-1),6),("BOTTOMPADDING",(0,0),(-1,-1),6)]))
    story.append(header);story.append(Spacer(1,8))
    story.append(Paragraph(f"<b>PROFORMA</b> – {numero}",styles["Title"]))
    story.append(Spacer(1,6))
    story.append(Paragraph(f"Fecha: {fecha}",styles["Normal"]))
    story.append(Spacer(1,10))
    datos_tbl=[
        ["Cliente:",datos.cliente],["Contacto:",datos.contacto or "-"],["RUC:",datos.ruc or "-"],
        ["Dirección:",datos.direccion or "-"],["Cotizado por:",(datos.cotizado_por or "-")],
        ["Tiempo producción:",datos.tiempo_produccion or "-"],["Condiciones de pago:",datos.condiciones_pago or "-"],
        ["Entrega:",datos.entrega or "-"],["Validez de oferta (días):",str(datos.validez_oferta_dias or 15)],
        ["Observaciones:",(datos.observaciones or "-")],
    ]
    t1=Table(datos_tbl,colWidths=[150,360])
    t1.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(0,-1),colors.lightgrey),("BOX",(0,0),(-1,-1),0.5,colors.grey),
        ("INNERGRID",(0,0),(-1,-1),0.25,colors.grey),("VALIGN",(0,0),(-1,-1),"TOP"),
    ]))
    story.append(t1);story.append(Spacer(1,12))
    head=[["Imagen","Descripción","Cant.","P.U.","Total"]];rows=[]
    for it in items:
        img=_flow_img(it.filename,35)
        rows.append([img,Paragraph(it.descripcion,p_desc),str(it.cantidad),
                     f"{moneda} {it.precio_unitario:.2f}",f"{moneda} {it.total:.2f}"])
    t2=Table(head+rows,colWidths=[38*mm,270,45,60,65],repeatRows=1)
    t2.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,0),colors.lightgrey),("BOX",(0,0),(-1,-1),0.5,colors.grey),
        ("INNERGRID",(0,0),(-1,-1),0.25,colors.grey),("VALIGN",(0,0),(-1,-1),"TOP"),
        ("ALIGN",(-2,1),(-1,-1),"RIGHT"),
    ]))
    story.append(t2);story.append(Spacer(1,12))
    t3=Table([
        ["Subtotal:",Paragraph(f"{moneda} {subtotal:.2f}",p_right)],
        [f"IGV ({igv_pct:.0f}%):",Paragraph(f"{moneda} {igv:.2f}",p_right)],
        ["Total:",Paragraph(f"{moneda} {total:.2f}",p_right_b)],
    ],colWidths=[420,130])
    t3.setStyle(TableStyle([
        ("ALIGN",(1,0),(1,-1),"RIGHT"),("BOX",(0,0),(-1,-1),0.5,colors.grey),
        ("INNERGRID",(0,0),(-1,-1),0.25,colors.grey),
    ]))
    story.append(t3)
    def _footer(canvas,doc):
        canvas.saveState()
        from reportlab.lib.pagesizes import A4 as _A4
        w,h=_A4;canvas.setStrokeColor(colors.grey);canvas.setLineWidth(0.5);canvas.line(24,28,w-24,28)
        canvas.setFont("Helvetica",9)
        if datos.cotizado_por:
            canvas.drawString(24,18,f"Cotizado por: {datos.cotizado_por}")
            canvas.drawRightString(w-24,18,f"{COMPANY_WEB}")
        else:
            canvas.drawString(24,18,f"{COMPANY_WEB}")
        canvas.restoreState()
    doc.build(story,onFirstPage=_footer,onLaterPages=_footer)

# ========= ADMIN ==========
ADMIN_KEY=os.getenv("TINNOVA_ADMIN_KEY","tinnova-admin-123")
def _require_admin_key(request:Request):
    key=request.headers.get("X-Admin-Key") or request.headers.get("x-admin-key")
    if key != ADMIN_KEY:
        raise HTTPException(401,"Admin key inválida")

@app.post("/import-items-csv")
async def import_items_csv(request:Request,file:UploadFile=File(...),auto_build_map:bool=Query(True)):
    _require_admin_key(request)
    if not file.filename.lower().endswith(".csv"): raise HTTPException(422,"Sube un .csv")
    content=await file.read()
    import io as _io
    df_new=pd.read_csv(_io.BytesIO(content))
    need=["archivo","pagina","fecha","empresa","descripcion","cantidad","precio_unitario","precio_total"]
    for c in need:
        if c not in df_new.columns: df_new[c]=None
    for c in ["cantidad","precio_unitario","precio_total","pagina"]:
        df_new[c]=pd.to_numeric(df_new[c],errors="coerce")
    if os.path.exists(COTIZACIONES_CSV):
        df_old=pd.read_csv(COTIZACIONES_CSV)
        df=pd.concat([df_old,df_new],ignore_index=True)
    else:
        df=df_new
    df.to_csv(COTIZACIONES_CSV,index=False)
    rows=None
    if auto_build_map:
        r=auto_build_png_map();rows=r.get("filas")
    return {"status":"ok","insertadas":int(df_new.shape[0]),"png_map_filas":rows}

@app.post("/import-items-json")
async def import_items_json(request:Request,items:List[dict]=Body(...),auto_build_map:bool=Query(True)):
    _require_admin_key(request)
    if not isinstance(items,list) or not items:
        raise HTTPException(422,"Lista vacía")
    df_new=pd.DataFrame(items)
    need=["archivo","pagina","fecha","empresa","descripcion","cantidad","precio_unitario","precio_total"]
    for c in need:
        if c not in df_new.columns: df_new[c]=None
    for c in ["cantidad","precio_unitario","precio_total","pagina"]:
        df_new[c]=pd.to_numeric(df_new[c],errors="coerce")
    if os.path.exists(COTIZACIONES_CSV):
        df_old=pd.read_csv(COTIZACIONES_CSV)
        df=pd.concat([df_old,df_new],ignore_index=True)
    else:
        df=df_new
    df.to_csv(COTIZACIONES_CSV,index=False)
    rows=None
    if auto_build_map:
        r=auto_build_png_map();rows=r.get("filas")
    return {"status":"ok","insertadas":int(df_new.shape[0]),"png_map_filas":rows}

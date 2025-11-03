# limpiar_mapa_v2.py
import pandas as pd, re, shutil, os

PNG_MAP = "png_map.csv"
COTIZ = "cotizaciones.csv"
BACKUP = "png_map.backup.csv"

if not os.path.exists(PNG_MAP):
    raise SystemExit("❌ No existe png_map.csv en esta carpeta")

# --------- blacklist de marcas/clientes ---------
blacklist = {
    # añade las que ya viste
    "aces", "cumbra", "tp", "teleperformance",
    "siemens", "nike", "bbva", "bcp", "scotiabank",
    "interbank", "tottus", "ripley", "saga falabella",
}

# Aprende marcas desde cotizaciones.csv (columna 'empresa')
if os.path.exists(COTIZ):
    try:
        dfc = pd.read_csv(COTIZ)
        if "empresa" in dfc.columns:
            for v in dfc["empresa"].dropna().astype(str).tolist():
                v = v.strip().lower()
                if 2 <= len(v) <= 50:
                    blacklist.add(v)
    except Exception as e:
        print("⚠️ No pude leer cotizaciones.csv:", e)

# compila patrón para quitar marcas al final (con espacios/puntuación de cola)
def build_brand_regex(brands):
    # ordena por largo para capturar frases primero
    brands = sorted({b.strip().lower() for b in brands if b.strip()}, key=len, reverse=True)
    # escapa y une
    esc = [re.escape(b) for b in brands]
    if not esc:
        return None
    return re.compile(rf"(?:\s|[-—,.:])*(?:{'|'.join(esc)})\s*$", re.I)

brand_tail = build_brand_regex(blacklist)

# arreglos de OCR comunes
OCR_FIXES = [
    (re.compile(r"\bedificaci\s+ones\b", re.I), "edificaciones"),
    (re.compile(r"\s{2,}"), " "),                        # espacios duplicados
    (re.compile(r"\s+([,.;:])"), r"\1"),                 # espacio antes de puntuación
]

def limpiar_desc(s: str) -> str:
    if not isinstance(s, str): 
        return ""
    t = s.strip()

    # arreglos OCR
    for pat, rep in OCR_FIXES:
        t = pat.sub(rep, t)

    # quita marca/cliente al final
    if brand_tail:
        t = brand_tail.sub("", t).strip()

    # si aún queda un token suelto en mayúscula al final (posible marca), lo quita
    # ej: "... caja cartón. Aces" -> remueve "Aces"
    t = re.sub(r"(?:\s|[-—,.:])*\b[A-ZÁÉÍÓÚÑ][A-Za-zÁÉÍÓÚÑ&\-/]{1,}\s*$", "", t).strip()

    # limpia puntas y dobles signos
    t = t.strip(" .,-–—")
    t = re.sub(r"\s{2,}", " ", t)
    return t

df = pd.read_csv(PNG_MAP)
if "descripcion" not in df.columns:
    raise SystemExit("❌ png_map.csv no tiene columna 'descripcion'")

# backup
shutil.copyfile(PNG_MAP, BACKUP)

# aplica limpieza y cuenta cambios
orig = df["descripcion"].fillna("").astype(str).tolist()
df["descripcion"] = df["descripcion"].astype(str).apply(limpiar_desc)

cambios = sum(1 for a,b in zip(orig, df["descripcion"]) if (a or "").strip() != (b or "").strip())
df.to_csv(PNG_MAP, index=False, encoding="utf-8")

print(f"✅ Limpieza completada. Filas cambiadas: {cambios}")
print(f"🗂️ Backup en: {BACKUP}")
print("ℹ️ Si algo no te gusta, restaura el backup:")
print(f"   copy {BACKUP} {PNG_MAP}")

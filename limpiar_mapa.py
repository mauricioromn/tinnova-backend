import pandas as pd, re

PNG_MAP = "png_map.csv"
df = pd.read_csv(PNG_MAP)

def limpiar_desc(s: str) -> str:
    if not isinstance(s, str): return ""
    t = s.strip()

    # ejemplos de marcas/clientes a quitar si están al final
    marcas = [
        r"siemens", r"nike", r"teleperformance", r"tp", r"bbva", r"bcp",
        r"scotiabank", r"interbank", r"tottus", r"ripley", r"saga falabella"
    ]
    patron_marcas_final = re.compile(r"(?:\s|-|—|,)?\s*(?:%s)\s*$" % "|".join(marcas), re.I)
    t = patron_marcas_final.sub("", t)

    # normalizaciones varias
    t = re.sub(r"\s+", " ", t)                # espacios duplicados
    t = re.sub(r"\s+([,.;:])", r"\1", t)      # espacio antes de puntuación
    t = t.strip(" .-–—")                      # limpiar puntas
    return t

if "descripcion" in df.columns:
    df["descripcion"] = df["descripcion"].apply(limpiar_desc)
    df.to_csv(PNG_MAP, index=False, encoding="utf-8")
    print("✅ Descripciones limpiadas y guardadas en", PNG_MAP)
else:
    print("❌ png_map.csv no tiene columna 'descripcion'")

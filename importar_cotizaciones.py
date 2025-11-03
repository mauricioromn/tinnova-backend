import os
import re
import fitz  # PyMuPDF
from datetime import datetime

# ---------------------------
# CONFIGURACIÓN DE RUTAS
# ---------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CARPETA_PDFS = os.path.join(BASE_DIR, "CotizacionesAntiguas")

if not os.path.exists(CARPETA_PDFS):
    print(f"❌ No se encontró la carpeta {CARPETA_PDFS}. Crea 'CotizacionesAntiguas' y coloca tus PDFs ahí.")
    exit()

# ---------------------------
# FUNCIÓN: EXTRAER TEXTO DE PDF
# ---------------------------
def extraer_texto_pdf(ruta_pdf):
    """Extrae el texto completo de un archivo PDF."""
    texto = ""
    with fitz.open(ruta_pdf) as doc:
        for pagina in doc:
            texto += pagina.get_text("text") + "\n"
    return texto

# ---------------------------
# FUNCIÓN: LIMPIAR TEXTO
# ---------------------------
def limpiar_texto(texto):
    """Limpia texto eliminando saltos y caracteres duplicados."""
    texto = re.sub(r"\s+", " ", texto)
    return texto.strip()

# ---------------------------
# FUNCIÓN: EXTRAER DATOS DE COTIZACIÓN
# ---------------------------
def extraer_datos(texto):
    datos = {
        "proforma": "Sin número",
        "empresa": "",
        "fecha": "",
        "items": []
    }

    # Buscar número de proforma
    match_proforma = re.search(r"Proforma\s*(\d{1,4}[-–]?\d{0,4}[A-Z]?)", texto, re.IGNORECASE)
    if match_proforma:
        datos["proforma"] = match_proforma.group(1).strip()

    # Buscar empresa
    match_empresa = re.search(r"Empresa:\s*([A-Za-zÁÉÍÓÚÑáéíóú0-9&\.\s]+)", texto)
    if match_empresa:
        datos["empresa"] = match_empresa.group(1).strip()

    # Buscar fecha
    match_fecha = re.search(r"Fecha:\s*([\d]{1,2}\s*/\s*[\d]{1,2}\s*/\s*[\d]{2,4})", texto)
    if match_fecha:
        datos["fecha"] = match_fecha.group(1).strip()

    # ---------------------------
    # DETECCIÓN DE ÍTEMS
    # ---------------------------
    patron_items = re.compile(
        r"(?P<item>\d{1,3})\s+(?P<cant>\d{1,5})\s+(?P<desc>[A-Za-z0-9\s\-\.\,\/°]+?)\s+S\/?\.?\s*(?P<unit>[\d,\.]+)\s+S\/?\.?\s*(?P<total>[\d,\.]+)",
        re.IGNORECASE
    )

    for match in patron_items.finditer(texto):
        cantidad = match.group("cant").replace(",", ".")
        precio_unit = match.group("unit").replace(",", ".")
        precio_total = match.group("total").replace(",", ".")

        # Calcular precio unitario si es 0 o falta
        try:
            cantidad_f = float(cantidad)
            total_f = float(precio_total)
            unit_f = float(precio_unit) if float(precio_unit) > 0 else total_f / cantidad_f
        except:
            cantidad_f = 1
            unit_f = 0
            total_f = 0

        datos["items"].append({
            "item": match.group("item"),
            "cantidad": cantidad_f,
            "descripcion": match.group("desc").strip(),
            "precio_unitario": round(unit_f, 2),
            "precio_total": round(total_f, 2)
        })

    return datos

# ---------------------------
# FUNCIÓN: PROCESAR PDFs
# ---------------------------
def procesar_pdfs():
    archivos_pdf = [f for f in os.listdir(CARPETA_PDFS) if f.lower().endswith(".pdf")]

    if not archivos_pdf:
        print("⚠️ No hay archivos PDF en la carpeta CotizacionesAntiguas.")
        return

    print(f"📦 Procesando {len(archivos_pdf)} archivos PDF...\n")
    resultados = []

    for archivo in archivos_pdf:
        ruta_pdf = os.path.join(CARPETA_PDFS, archivo)
        texto = limpiar_texto(extraer_texto_pdf(ruta_pdf))
        datos = extraer_datos(texto)
        datos["archivo"] = archivo
        resultados.append(datos)

        print(f"✅ Procesado: {archivo}")
        if datos["items"]:
            print(f"   → {len(datos['items'])} ítems detectados.")
        else:
            print("   ⚠️ No se detectaron ítems.\n")

    print("\n📊 Resumen de resultados:")
    print(f"Total de cotizaciones procesadas: {len(resultados)}")

    return resultados


if __name__ == "__main__":
    resultados = procesar_pdfs()
    if resultados:
        print("\n📄 Ejemplo de primera cotización procesada:")
        import json
        print(json.dumps(resultados[0], indent=2, ensure_ascii=False))


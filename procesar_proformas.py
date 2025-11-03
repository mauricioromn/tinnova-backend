import os
import re
import csv
import fitz  # PyMuPDF
from datetime import datetime

# Configuración
DEFAULT_FOLDER = os.path.join(os.getcwd(), "CotizacionesAntiguas")
OUT_CSV = os.path.join(os.getcwd(), "historico_cotizaciones.csv")

def read_pdf_text(pdf_path: str) -> str:
    """Extrae texto del PDF línea por línea."""
    text = []
    with fitz.open(pdf_path) as doc:
        for page in doc:
            page_text = page.get_text("text")
            text.extend(page_text.splitlines())
    return "\n".join(text)

def normalize_text(t: str) -> str:
    """Limpia espacios y normaliza texto."""
    t = re.sub(r"[ \t]+", " ", t)
    t = t.replace(",", ".")
    t = t.replace("S/.", "S/").replace("S/ ", "S/")
    return t.strip()

def parse_money(raw: str):
    if not raw:
        return None
    raw = re.sub(r"[^\d\.]", "", raw)
    try:
        return float(raw)
    except:
        return None

def extract_metadata(text):
    """Extrae metadatos comunes."""
    empresa = re.search(r"Empresa\s*:\s*(.*)", text, re.IGNORECASE)
    atencion = re.search(r"Atenc[ií]on\s*:\s*(.*)", text, re.IGNORECASE)
    fecha = re.search(r"Fecha\s*[:\-]?\s*([0-3]?\d[\/\-][01]?\d[\/\-]\d{2,4})", text)
    return (
        empresa.group(1).strip() if empresa else "No detectado",
        atencion.group(1).strip() if atencion else "",
        fecha.group(1).strip() if fecha else ""
    )

def extract_items_from_text(text):
    """Detecta líneas con cantidad, descripción, precio unitario y total."""
    lines = [l.strip() for l in text.splitlines() if len(l.strip()) > 0]
    patrones = [
        # 1. Ejemplo: "200 Tomatodos logo 1 color S/ 8.50 S/ 1700.00"
        r"(?P<cant>\d{1,5})\s+(?P<desc>.+?)\s+(?:S\/|USD|\$)?\s*(?P<unit>[0-9\.]{1,10})\s+(?:S\/|USD|\$)?\s*(?P<total>[0-9\.]{1,12})",
        # 2. Ejemplo: "Tomatodos logo 200 und S/8.50"
        r"(?P<desc>.+?)\s+(?P<cant>\d{1,5})\s*(?:u|und|unid|unidad|unidades)\b.*?(?:S\/|USD|\$)?\s*(?P<unit>[0-9\.]{1,10})",
    ]
    items = []
    for line in lines:
        for patron in patrones:
            m = re.search(patron, line, re.IGNORECASE)
            if m:
                try:
                    cantidad = int(m.group("cant"))
                except:
                    cantidad = 1
                desc = m.group("desc").strip()
                unit = parse_money(m.group("unit"))
                total = parse_money(m.group("total")) if "total" in m.groupdict() else None
                if not total and unit and cantidad:
                    total = cantidad * unit
                if unit and total and desc:
                    items.append({
                        "cantidad": cantidad,
                        "descripcion": desc,
                        "precio_unitario": round(unit, 2),
                        "precio_total": round(total, 2)
                    })
                break
    return items

def process_pdf(pdf_path):
    text = read_pdf_text(pdf_path)
    text = normalize_text(text)
    empresa, atencion, fecha = extract_metadata(text)
    items = extract_items_from_text(text)
    if len(items) > 0:
        print(f"✅ {os.path.basename(pdf_path)} → {len(items)} ítems")
        for i, it in enumerate(items[:3]):  # muestra primeros 3 ítems detectados
            print("   →", it)
    else:
        print(f"📘 {os.path.basename(pdf_path)} → 0 ítems")
    for it in items:
        it.update({
            "empresa": empresa,
            "atencion": atencion,
            "fecha": fecha,
            "archivo": os.path.basename(pdf_path)
        })
    return items

def main():
    folder = DEFAULT_FOLDER
    pdfs = [os.path.join(folder, f) for f in os.listdir(folder) if f.lower().endswith(".pdf")]
    pdfs.sort()

    all_rows = []
    for pdf in pdfs:
        try:
            items = process_pdf(pdf)
            all_rows.extend(items)
        except Exception as e:
            print(f"⚠️ Error en {pdf}: {e}")

    if not all_rows:
        print("❌ No se detectaron ítems válidos. Revisa formato de PDFs.")
        return

    with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
        fieldnames = ["empresa", "atencion", "fecha", "descripcion", "cantidad", "precio_unitario", "precio_total", "archivo"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in all_rows:
            writer.writerow(r)

    print(f"\n✅ Exportado {len(all_rows)} ítems a {OUT_CSV}")

if __name__ == "__main__":
    main()

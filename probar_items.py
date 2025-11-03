import os
import re
import fitz  # PyMuPDF

# Ruta de tus PDFs
carpeta_pdf = os.path.join(os.getcwd(), "CotizacionesAntiguas")

if not os.path.exists(carpeta_pdf):
    print(f"❌ No se encontró la carpeta: {carpeta_pdf}")
    exit()

# Expresión regular para detectar ítems con descripción y precios
patron_item = re.compile(
    r'(\d{1,3})\s+([A-Za-zÁÉÍÓÚÜÑñ0-9°º,.\-/() ]+?)\s+S?/?\s?(\d+(?:[\.,]\d{1,2})?)\s+S?/?\s?(\d+(?:[\.,]\d{1,2})?)',
    re.IGNORECASE
)

for archivo in os.listdir(carpeta_pdf):
    if archivo.lower().endswith(".pdf"):
        ruta = os.path.join(carpeta_pdf, archivo)
        print(f"\n📘 Analizando: {archivo}\n" + "-"*70)

        doc = fitz.open(ruta)
        texto = ""
        for pagina in doc:
            texto += pagina.get_text("text")

        # Buscar ítems en el texto
        items = patron_item.findall(texto)

        if items:
            print("✅ Ítems detectados:")
            for num, desc, unitario, total in items:
                print(f"• Item {num} | {desc.strip()} | Unit: S/. {unitario} | Total: S/. {total}")
        else:
            print("⚠️ No se detectaron ítems en este PDF.")

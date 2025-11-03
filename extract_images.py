import fitz
import os

def extraer_imagenes_pdf(pdf_path, salida="imagenes_proformas"):
    os.makedirs(salida, exist_ok=True)
    doc = fitz.open(pdf_path)
    for i, page in enumerate(doc):
        for img in page.get_images(full=True):
            xref = img[0]
            base = os.path.basename(pdf_path).replace(".pdf", "")
            pix = fitz.Pixmap(doc, xref)
            if pix.n < 5:  # RGB
                pix.save(os.path.join(salida, f"{base}_p{i}_xref{xref}.png"))
            else:  # CMYK
                pix = fitz.Pixmap(fitz.csRGB, pix)
                pix.save(os.path.join(salida, f"{base}_p{i}_xref{xref}.png"))
            pix = None
    doc.close()
    print(f"✅ Imágenes extraídas de {pdf_path}")

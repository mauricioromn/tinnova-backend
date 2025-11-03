import os
import fitz  # PyMuPDF
import pandas as pd
from tqdm import tqdm
from image_analyzer import crear_base_visual

CARPETA_PDFS = "CotizacionesAntiguas"
ARCHIVO_CSV = "cotizaciones.csv"
CARPETA_IMAGENES = "imagenes_proformas"


def extraer_datos_pdf(path_pdf):
    """
    Extrae datos de productos y precios de una proforma en formato PDF.
    Retorna una lista de diccionarios con los campos estandarizados.
    """
    registros = []
    try:
        with fitz.open(path_pdf) as doc:
            texto_total = "\n".join(page.get_text("text") for page in doc)

            # Extrae imágenes
            for num, page in enumerate(doc):
                for img_index, img in enumerate(page.get_images(full=True)):
                    base_image = doc.extract_image(img[0])
                    image_bytes = base_image["image"]
                    image_ext = base_image["ext"]
                    nombre_img = f"{os.path.splitext(os.path.basename(path_pdf))[0]}_p{num}_{img_index}.{image_ext}"
                    path_img = os.path.join(CARPETA_IMAGENES, nombre_img)
                    with open(path_img, "wb") as f:
                        f.write(image_bytes)

            # Extracción básica (puedes mejorar con regex según tu formato)
            lineas = texto_total.split("\n")
            empresa, fecha = None, None
            for linea in lineas:
                if "Teleperformance" in linea or "Oregon" in linea or "Siemens" in linea:
                    empresa = linea.strip()
                if "/" in linea and any(x in linea for x in ["2021", "2022", "2023", "2024", "2025"]):
                    fecha = linea.strip()

            # Busca patrones tipo "producto – cantidad – precio"
            for i, linea in enumerate(lineas):
                if "S/" in linea or "S/." in linea:
                    descripcion = " ".join(lineas[max(0, i-3):i]).replace("\n", " ")
                    partes = linea.split()
                    try:
                        precio = float(partes[-1].replace("S/.", "").replace("S/", "").replace(",", "."))
                    except:
                        precio = 0
                    cantidad = 1
                    for p in partes:
                        if p.isdigit():
                            cantidad = int(p)
                            break

                    registros.append({
                        "archivo": os.path.basename(path_pdf),
                        "empresa": empresa or "Desconocida",
                        "fecha": fecha or "No especificada",
                        "descripcion": descripcion.strip(),
                        "cantidad": cantidad,
                        "precio_unitario": precio,
                        "precio_total": cantidad * precio
                    })
    except Exception as e:
        print(f"⚠️ Error procesando {path_pdf}: {e}")
    return registros


def actualizar_base():
    """
    Recorre la carpeta de PDFs y actualiza cotizaciones.csv + imágenes.
    """
    if not os.path.exists(CARPETA_PDFS):
        print(f"⚠️ No existe la carpeta '{CARPETA_PDFS}'. Crea o mueve tus proformas allí.")
        return
    if not os.path.exists(CARPETA_IMAGENES):
        os.makedirs(CARPETA_IMAGENES)

    registros_totales = []
    archivos_pdf = [f for f in os.listdir(CARPETA_PDFS) if f.lower().endswith(".pdf")]

    print(f"📂 Procesando {len(archivos_pdf)} archivos PDF...")
    for archivo in tqdm(archivos_pdf):
        path_pdf = os.path.join(CARPETA_PDFS, archivo)
        registros_totales.extend(extraer_datos_pdf(path_pdf))

    if registros_totales:
        df_nuevo = pd.DataFrame(registros_totales)
        if os.path.exists(ARCHIVO_CSV):
            df_existente = pd.read_csv(ARCHIVO_CSV)
            df_final = pd.concat([df_existente, df_nuevo]).drop_duplicates(subset=["archivo", "descripcion"])
        else:
            df_final = df_nuevo

        df_final.to_csv(ARCHIVO_CSV, index=False)
        print(f"✅ Archivo {ARCHIVO_CSV} actualizado con {len(df_final)} registros.")
    else:
        print("⚠️ No se encontraron registros nuevos en los PDF.")

    print("🧩 Actualizando base visual...")
    crear_base_visual()
    print("🎉 Sincronización completa: datos + imágenes + base visual actualizada.")


if __name__ == "__main__":
    actualizar_base()

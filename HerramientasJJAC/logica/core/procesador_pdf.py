# logica/procesador_pdf.py
import pypdf
import os

def _obtener_texto_de_pagina(pagina):
    """Extrae y limpia el texto de una página PDF."""
    try:
        texto = pagina.extract_text()
        # Normalizamos el texto para una mejor comparación:
        # eliminamos espacios en blanco extra y saltos de línea.
        return " ".join(texto.split())
    except Exception:
        # Si la extracción de texto falla, retornamos una cadena vacía.
        return ""

def verificar_fusion_por_contenido(ruta_pdf_destino, ruta_pdf_fuente, paginas_a_verificar=2, min_caracteres=50):
    """
    Verifica si el contenido del 'fuente' ya está en el 'destino' comparando texto.
    
    Args:
        ruta_pdf_destino (str): Ruta al PDF de respuesta glosa.
        ruta_pdf_fuente (str): Ruta al PDF de carta glosa.
        paginas_a_verificar (int): Cuántas de las primeras páginas del 'fuente' se verificarán.
        min_caracteres (int): Longitud mínima de texto para considerar una coincidencia válida.

    Returns:
        bool: True si el contenido ya parece estar fusionado, False en caso contrario.
    """
    try:
        with open(ruta_pdf_destino, 'rb') as f_destino, open(ruta_pdf_fuente, 'rb') as f_fuente:
            lector_destino = pypdf.PdfReader(f_destino)
            lector_fuente = pypdf.PdfReader(f_fuente)
            
            texto_completo_destino = " ".join([_obtener_texto_de_pagina(pagina) for pagina in lector_destino.pages])

            if not texto_completo_destino.strip():
                return False

            for i in range(min(paginas_a_verificar, len(lector_fuente.pages))):
                texto_pagina_fuente = _obtener_texto_de_pagina(lector_fuente.pages[i])

                if texto_pagina_fuente and len(texto_pagina_fuente) > min_caracteres:
                    if texto_pagina_fuente in texto_completo_destino:
                        return True
            
            return False

    except Exception as e:
        print(f"Advertencia: Ocurrió un error durante la verificación de contenido de PDF: {e}. Se procederá a unir por seguridad.")
        return False

def fusionar_pdfs_en_destino(ruta_pdf_destino, rutas_pdf_fuentes):
    """
    Une una lista de PDFs (fuentes) a un PDF existente (destino) usando PdfWriter.
    El archivo destino es SOBRESCRITO.
    """
    escritor = pypdf.PdfWriter()

    lector_destino = pypdf.PdfReader(ruta_pdf_destino)
    for pagina in lector_destino.pages:
        escritor.add_page(pagina)

    for ruta in rutas_pdf_fuentes:
        lector_fuente = pypdf.PdfReader(ruta)
        for pagina in lector_fuente.pages:
            escritor.add_page(pagina)

    with open(ruta_pdf_destino, 'wb') as archivo_salida:
        escritor.write(archivo_salida)

def obtener_cantidad_paginas_pdf(ruta_pdf):
    """Devuelve el número de páginas de un archivo PDF."""
    try:
        with open(ruta_pdf, 'rb') as f:
            lector = pypdf.PdfReader(f)
            return len(lector.pages)
    except Exception:
        return 0

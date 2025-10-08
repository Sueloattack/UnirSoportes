import os
import re
import pypdf # Usaremos pypdf ya que lo tienes en tu procesador_pdf
import shutil
from logica.core import gestor_archivos, procesador_pdf # Reutilizamos tu lógica central

def identificar_archivos_adres_para_separar(archivos_pdf_en_carpeta):
    """
    Función de identificación especializada para este flujo.
    Busca una Epicrisis y una Respuesta Glosa.
    """
    resultados = {
        'epicrisis': None,
        'respuesta_glosa': None,
    }
    
    # Patrón para Epicrisis (robusto para variantes como '...2_EPICRISIS.pdf')
    patron_epicrisis = re.compile(r"^\d+_[A-Z]+\d+.*_EPICRIS(?:IS)?\.pdf$", re.IGNORECASE)
    
    # Patrón para Respuesta Glosa (ahora flexible con espacios)
    # \s* permite cero o más espacios entre la serie y el número
    patron_respuesta = re.compile(r"^(FECR|COEX|FERD|FERR)\s*(\d+)\.pdf$", re.IGNORECASE)
    patron_glosa_rep = re.compile(r"^GLOSA_REP\d*\.pdf$", re.IGNORECASE)
    
    for nombre_archivo in archivos_pdf_en_carpeta:
        # Buscar Epicrisis
        if patron_epicrisis.match(nombre_archivo):
            if not resultados['epicrisis']: # Tomar solo la primera que encuentre
                resultados['epicrisis'] = nombre_archivo
                continue
                
        # Buscar Respuesta Glosa (con o sin espacio)
        match_respuesta = patron_respuesta.match(nombre_archivo)
        if match_respuesta:
            if not resultados['respuesta_glosa']:
                resultados['respuesta_glosa'] = nombre_archivo
                continue

        # Buscar Respuesta Glosa (formato GLOSA_REP)
        if patron_glosa_rep.match(nombre_archivo):
            if not resultados['respuesta_glosa']:
                resultados['respuesta_glosa'] = nombre_archivo
                continue
    
    return resultados['epicrisis'], resultados['respuesta_glosa']


def separar_respuesta_de_epicrisis(carpeta_raiz):
    """
    Función principal que itera, valida y separa los PDFs.
    """
    resultados = {
        'separados': [],
        'no_unidos': [],
        'fallidos': []
    }

    subcarpetas = gestor_archivos.listar_subdirectorios(carpeta_raiz)
    
    print("--- INICIANDO PROCESO DE SEPARACIÓN DE RESPUESTAS ADRES ---")
    
    for ruta_subcarpeta in subcarpetas:
        nombre_subcarpeta = os.path.basename(ruta_subcarpeta)
        print(f"\nAnalizando carpeta: '{nombre_subcarpeta}'...")

        # 1. Identificar archivos clave
        archivos_pdf = gestor_archivos.obtener_archivos_pdf(ruta_subcarpeta)
        nombre_epicrisis, nombre_respuesta = identificar_archivos_adres_para_separar(archivos_pdf)
        
        # 2. Validar que ambos archivos existan
        if not nombre_epicrisis:
            print("  -> ❌ ERROR: No se encontró el archivo Epicrisis.")
            resultados['fallidos'].append({'carpeta': nombre_subcarpeta, 'razon': 'Falta archivo Epicrisis.'})
            continue
        if not nombre_respuesta:
            print("  -> ❌ ERROR: No se encontró el archivo Respuesta Glosa.")
            resultados['fallidos'].append({'carpeta': nombre_subcarpeta, 'razon': 'Falta archivo Respuesta Glosa.'})
            continue

        ruta_epicrisis = os.path.join(ruta_subcarpeta, nombre_epicrisis)
        ruta_respuesta = os.path.join(ruta_subcarpeta, nombre_respuesta)
        
        print(f"  -> Archivos encontrados: '{nombre_epicrisis}' y '{nombre_respuesta}'.")

        # 3. Verificar si la respuesta está realmente unida
        try:
            esta_unido = procesador_pdf.verificar_fusion_por_contenido(
                ruta_pdf_destino=ruta_epicrisis,
                ruta_pdf_fuente=ruta_respuesta
            )
        except Exception as e:
            print(f"  -> ❌ ERROR al leer los PDFs: {e}")
            resultados['fallidos'].append({'carpeta': nombre_subcarpeta, 'razon': f"No se pudieron leer los PDFs: {e}"})
            continue
            
        if not esta_unido:
            print("  -> ⓘ OMITIDO: La Respuesta Glosa no parece estar unida a la Epicrisis.")
            resultados['no_unidos'].append({'carpeta': nombre_subcarpeta})
            continue

        # 4. Proceder con la separación ("cirugía del PDF")
        try:
            print("  -> ✂️ Detectada unión. Procediendo a separar...")
            
            # Contar páginas de la Respuesta para saber cuántas quitar
            num_paginas_respuesta = procesador_pdf.obtener_cantidad_paginas_pdf(ruta_respuesta)
            if num_paginas_respuesta == 0:
                raise ValueError("El archivo de Respuesta Glosa no tiene páginas o no se pudo leer.")

            print(f"  -> La Respuesta Glosa tiene {num_paginas_respuesta} página(s). Se eliminarán del inicio de la Epicrisis.")

            # Crear el nuevo PDF sin las páginas de la respuesta
            lector_epicrisis = pypdf.PdfReader(ruta_epicrisis)
            escritor_nuevo = pypdf.PdfWriter()

            # Añadir solo las páginas de la epicrisis original
            for i in range(num_paginas_respuesta, len(lector_epicrisis.pages)):
                escritor_nuevo.add_page(lector_epicrisis.pages[i])

            # Sobrescribir el archivo Epicrisis original
            with open(ruta_epicrisis, 'wb') as f_salida:
                escritor_nuevo.write(f_salida)
            
            print("  -> ✅ ÉXITO: La Respuesta Glosa fue separada de la Epicrisis.")
            resultados['separados'].append({'carpeta': nombre_subcarpeta})

        except Exception as e:
            print(f"  -> ❌ ERROR durante la separación del PDF: {e}")
            resultados['fallidos'].append({'carpeta': nombre_subcarpeta, 'razon': f"Error al manipular el PDF: {e}"})

    # 5. Reporte Final
    print("\n" + "="*60)
    print("      REPORTE FINAL DE SEPARACIÓN DE RESPUESTAS ADRES")
    print("="*60)
    print(f"✅ Carpetas procesadas con éxito (separación realizada): {len(resultados['separados'])}")
    print(f"ⓘ Carpetas omitidas (la respuesta no estaba unida): {len(resultados['no_unidos'])}")
    print(f"❌ Carpetas con errores (faltan archivos, etc.): {len(resultados['fallidos'])}")
    print("="*60 + "\n")
    
    if resultados['fallidos']:
        print("--- DETALLE DE ERRORES ---")
        for fallo in resultados['fallidos']:
            print(f"  - Carpeta: {fallo['carpeta']} | Razón: {fallo['razon']}")


if __name__ == '__main__':
    # Este es un ejemplo de cómo se ejecutaría el script.
    # Necesitarías tus módulos de lógica en la estructura correcta para que funcione.
    
    # Simula la estructura de carpetas
    if not os.path.exists('logica/core'): os.makedirs('logica/core')
    if not os.path.exists('logica/core/__init__.py'): open('logica/core/__init__.py', 'w').close()
    # Pega tus archivos `gestor_archivos.py` y `procesador_pdf.py` en `logica/core`
    
    raiz = input("Ingresa la ruta a la carpeta con las subcarpetas de ADRES a procesar:\n> ").strip().strip('"')

    if not os.path.isdir(raiz):
        print("❌ La ruta proporcionada no es válida.")
    else:
        separar_respuesta_de_epicrisis(raiz)

    input("\nProceso finalizado. Presiona Enter para salir.")
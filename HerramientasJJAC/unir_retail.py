import os
import shutil
import pypdf
from logica.core import gestor_archivos, procesador_pdf # Reutilizamos tu lógica

def unir_respuestas_a_epicrisis_por_nombre(carpeta_raiz, carpeta_respuestas):
    """
    Función principal que une "Respuestas Glosa" (con nombre de epicrisis) a los
    archivos de epicrisis correspondientes en las subcarpetas de destino.
    """
    resultados = {
        'unidos': [],
        'ya_unidos': [],
        'sin_respuesta': [],
        'sin_epicrisis': [],
        'fallidos': []
    }
    
    print(f"--- INICIANDO PROCESO DE UNIÓN DE RESPUESTAS A EPICRISIS ---")

    # 1. Indexar todas las "respuestas" disponibles por su nombre de archivo.
    print(f"Indexando archivos en la carpeta de respuestas: {carpeta_respuestas}")
    respuestas_disponibles = {
        f: os.path.join(carpeta_respuestas, f) 
        for f in os.listdir(carpeta_respuestas) 
        if f.lower().endswith('.pdf') and 'EPICRIS' in f.upper()
    }
    print(f"-> Se encontraron {len(respuestas_disponibles)} archivos de respuesta (con nombre de epicrisis).\n")

    # 2. Iterar sobre cada subcarpeta en la carpeta raíz de destino.
    subcarpetas = gestor_archivos.listar_subdirectorios(carpeta_raiz)
    
    for ruta_subcarpeta in subcarpetas:
        nombre_subcarpeta = os.path.basename(ruta_subcarpeta)
        print(f"\nAnalizando carpeta: '{nombre_subcarpeta}'...")
        
        # 3. Encontrar el archivo de epicrisis de destino en la subcarpeta.
        nombre_epicrisis_destino = None
        for nombre_archivo in os.listdir(ruta_subcarpeta):
            if nombre_archivo.lower().endswith('.pdf') and 'EPICRIS' in nombre_archivo.upper():
                nombre_epicrisis_destino = nombre_archivo
                break

        if not nombre_epicrisis_destino:
            print("  -> ❌ ERROR: No se encontró un archivo Epicrisis en esta carpeta.")
            resultados['sin_epicrisis'].append({'carpeta': nombre_subcarpeta})
            continue

        # 4. Verificar si la respuesta correspondiente existe en nuestro índice.
        if nombre_epicrisis_destino in respuestas_disponibles:
            ruta_respuesta_origen = respuestas_disponibles[nombre_epicrisis_destino]
            ruta_epicrisis_destino = os.path.join(ruta_subcarpeta, nombre_epicrisis_destino)

            print(f"  -> Se encontró un par: Epicrisis de destino '{nombre_epicrisis_destino}' y Respuesta de origen '{os.path.basename(ruta_respuesta_origen)}'")

            # 5. Verificar si la unión ya fue realizada para evitar duplicados.
            try:
                esta_unido = procesador_pdf.verificar_fusion_por_contenido(
                    ruta_pdf_destino=ruta_epicrisis_destino,
                    ruta_pdf_fuente=ruta_respuesta_origen
                )
                if esta_unido:
                    print("  -> ⓘ OMITIDO: El contenido ya parece estar unido.")
                    resultados['ya_unidos'].append({'carpeta': nombre_subcarpeta})
                    continue
            except Exception as e:
                print(f"  -> ⚠️  ADVERTENCIA: No se pudo verificar el contenido, se intentará la unión. Error: {e}")

            # 6. Realizar la fusión.
            try:
                print("  -> 🔄 Uniendo archivos...")
                
                # Crear el PDF final en memoria
                escritor = pypdf.PdfWriter()

                # Añadir la RESPUESTA primero
                lector_respuesta = pypdf.PdfReader(ruta_respuesta_origen)
                for pagina in lector_respuesta.pages:
                    escritor.add_page(pagina)
                
                # Añadir la EPICRISIS después
                lector_epicrisis = pypdf.PdfReader(ruta_epicrisis_destino)
                for pagina in lector_epicrisis.pages:
                    escritor.add_page(pagina)

                # Sobrescribir el archivo epicrisis de destino con la extensión .pdf minúscula
                base, ext = os.path.splitext(ruta_epicrisis_destino)
                ruta_salida = base + ".pdf"
                
                with open(ruta_salida, 'wb') as f_salida:
                    escritor.write(f_salida)

                if ruta_salida != ruta_epicrisis_destino and os.path.exists(ruta_epicrisis_destino):
                    try:
                        os.remove(ruta_epicrisis_destino)
                    except Exception:
                        pass

                print("  -> ✅ ÉXITO: Los archivos fueron unidos correctamente.")
                resultados['unidos'].append({'carpeta': nombre_subcarpeta, 'archivo': nombre_epicrisis_destino})
            except Exception as e:
                print(f"  -> ❌ ERROR durante la fusión de PDF: {e}")
                resultados['fallidos'].append({'carpeta': nombre_subcarpeta, 'razon': f"Error al unir PDFs: {e}"})

        else:
            print(f"  -> 🟡 No se encontró una respuesta correspondiente para '{nombre_epicrisis_destino}' en la carpeta de origen.")
            resultados['sin_respuesta'].append({'carpeta': nombre_subcarpeta, 'busca': nombre_epicrisis_destino})
            
    # 7. Reporte final
    print("\n" + "="*60)
    print("      REPORTE FINAL DE UNIÓN DE RESPUESTAS A EPICRISIS")
    print("="*60)
    print(f"✅ Carpetas procesadas con éxito (unión realizada): {len(resultados['unidos'])}")
    print(f"ⓘ Carpetas omitidas (ya estaban unidas): {len(resultados['ya_unidos'])}")
    print(f"🟡 Carpetas sin respuesta encontrada en origen: {len(resultados['sin_respuesta'])}")
    print(f"❌ Carpetas con errores (sin epicrisis o fallos): {len(resultados['fallidos']) + len(resultados['sin_epicrisis'])}")
    print("="*60 + "\n")

    if resultados['unidos']:
        print("--- DETALLE DE ÉXITOS ---")
        for exito in resultados['unidos']:
            print(f"  - Carpeta: '{exito['carpeta']}' -> Se unió el par para '{exito['archivo']}'")
        print("\n")

    if resultados['fallidos'] or resultados['sin_epicrisis']:
        print("--- DETALLE DE ERRORES ---")
        for fallo in resultados['fallidos']:
            print(f"  - Carpeta: '{fallo['carpeta']}' | Razón: {fallo['razon']}")
        for fallo in resultados['sin_epicrisis']:
             print(f"  - Carpeta: '{fallo['carpeta']}' | Razón: No se encontró el archivo Epicrisis de destino.")
        print("\n")

    if resultados['sin_respuesta']:
        print("--- DETALLE DE ARCHIVOS SIN PAR ENCONTRADO ---")
        for item in resultados['sin_respuesta']:
            print(f"  - En la carpeta '{item['carpeta']}', no se encontró una respuesta para '{item['busca']}'")


if __name__ == '__main__':
    # Simulación de la estructura para que funcione el 'import'
    if not os.path.exists('logica/core'): os.makedirs('logica/core')
    open('logica/core/__init__.py', 'a').close()
    open('logica/__init__.py', 'a').close()
    # En un entorno real, tus archivos `gestor_archivos.py` y `procesador_pdf.py` estarían en 'logica/core'

    raiz = input("Ruta a la carpeta con subcarpetas que contienen las EPICRISIS de destino:\n> ").strip().strip('"')
    respuestas = input("Ruta a la carpeta con las RESPUESTAS sueltas (con nombre de epicrisis):\n> ").strip().strip('"')
    
    if not os.path.isdir(raiz):
        print("❌ Ruta raíz no válida.")
    elif not os.path.isdir(respuestas):
        print("❌ Ruta de respuestas no válida.")
    else:
        unir_respuestas_a_epicrisis_por_nombre(raiz, respuestas)

    input("\nProceso finalizado. Presiona Enter para salir.")
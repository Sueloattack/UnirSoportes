import os
import re
from pathlib import Path
from logica.core import gestor_archivos
from logica.core import identificador_archivos
from logica.core.procesador_pdf import pypdf

def unir_norma_logic(dir_origen, dir_destino, lista_facturas, progreso_actualizado, proceso_finalizado, error_ocurrido):
    # Diccionario para enviar a ventana de Resultados
    resultados = {'exitosos': [], 'fallidos': [], 'tipo_proceso': 'Norma'}
    
    subcarpetas = gestor_archivos.listar_subdirectorios(dir_origen)
    
    def _extraer_numero_de_cadena(s):
        match = re.search(r'\d+', s)
        return match.group() if match else s.lower()

    subcarpetas.sort(key=lambda path: int(_extraer_numero_de_cadena(os.path.basename(path))) if _extraer_numero_de_cadena(os.path.basename(path)).isdigit() else 99999999)

    if not subcarpetas:
        error_ocurrido.emit("Error: No se encontraron subcarpetas para procesar en el origen.")
        return

    # Si se proporcionó una lista de facturas, filtrar las subcarpetas
    if lista_facturas:
        nums_facturas = [_extraer_numero_de_cadena(f) for f in lista_facturas]
        subcarpetas = [c for c in subcarpetas if _extraer_numero_de_cadena(os.path.basename(c)) in nums_facturas]
        
        if not subcarpetas:
            error_ocurrido.emit("Error: Ninguna carpeta coincidió con el listado de facturas proporcionado.")
            return

    # 1. Identificar Cuenta de Cobro general (PDF en la raíz)
    archivos_raiz = [f for f in Path(dir_origen).iterdir() if f.is_file() and f.name.lower().endswith('.pdf')]
    cuenta_cobro_path = None
    
    if archivos_raiz:
        auditados = [f for f in archivos_raiz if "auditado" in f.name.lower()]
        if auditados:
            cuenta_cobro_path = str(auditados[0])
        else:
            cuenta_cobro_path = str(archivos_raiz[0])

    if not cuenta_cobro_path:
        error_ocurrido.emit("Error crítico: No se encontró ningún PDF en la carpeta raíz (Cuenta de Cobro) para anexar.")
        return

    total = len(subcarpetas)
    
    for i, ruta_carpeta in enumerate(subcarpetas):
        nombre_carpeta = os.path.basename(ruta_carpeta)
        fid = nombre_carpeta
        
        porcentaje = (i + 1) / total * 100
        progreso_actualizado.emit(f"Procesando {nombre_carpeta}...", porcentaje)

        archivos_pdf = gestor_archivos.obtener_archivos_pdf(ruta_carpeta)
        if not archivos_pdf:
            resultados['fallidos'].append({"carpeta": nombre_carpeta, "razon": "Carpeta vacía (sin PDFs)."})
            continue
            
        documentos = identificador_archivos.identificar_documentos_aseguradoras(archivos_pdf, ruta_carpeta)
        
        carta_glosa = documentos['carta_glosa']
        respuesta_glosa = documentos['respuesta_glosa']
        soportes = documentos['soportes']
        
        if not respuesta_glosa:
            resultados['fallidos'].append({"carpeta": nombre_carpeta, "razon": "No se encontró la Respuesta Glosa."})
            continue

        # 2. Buscar archivo Radicado ("RAD", "RADICADO") dentro de la carpeta
        radicado_path = None
        for f_pdf in archivos_pdf:
            if "rad" in f_pdf.lower() or "radicado" in f_pdf.lower():
                radicado_path = os.path.join(ruta_carpeta, f_pdf)
                break

        # Construir la lista prioritaria de hojas a unir (Respuesta -> Radicado -> Cuenta Cobro)
        archivos_a_leer = [respuesta_glosa['path']]
        if radicado_path:
            archivos_a_leer.append(radicado_path)
            
        archivos_a_leer.append(cuenta_cobro_path)

        # Determinar nombre original del destiono o usar el de la respuesta glosa
        nombre_salida = os.path.basename(respuesta_glosa['path'])
        ruta_salida = os.path.join(dir_destino, nombre_salida)
        
        # Evitar sobre-escrituras con sufijo
        if os.path.exists(ruta_salida):
            base, ext = os.path.splitext(nombre_salida)
            contador = 2
            while os.path.exists(os.path.join(dir_destino, f"{base}-{contador}{ext}")):
                contador += 1
            ruta_salida = os.path.join(dir_destino, f"{base}-{contador}{ext}")

        try:
            escritor = pypdf.PdfWriter()
            # Iterar todos los documentos para armar el gran PDF
            for path_archivo in archivos_a_leer:
                lector = pypdf.PdfReader(path_archivo)
                for pag in lector.pages:
                    escritor.add_page(pag)
            
            with open(ruta_salida, "wb") as f_out:
                escritor.write(f_out)
                
            resultados['exitosos'].append({
                "carpeta": nombre_carpeta, 
                "razon": f"✅ Compilación Norma ({len(archivos_a_leer)} docs) guardado en {os.path.basename(ruta_salida)}."
            })
        except Exception as e:
            resultados['fallidos'].append({"carpeta": nombre_carpeta, "razon": f"Error compilando: {e}"})

    proceso_finalizado.emit(resultados)

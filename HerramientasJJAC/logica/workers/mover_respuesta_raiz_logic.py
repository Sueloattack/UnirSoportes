# logica/workers/mover_respuesta_raiz_logic.py
import os
import re
import shutil
from PySide6.QtCore import QObject, Signal

# Patrones para identificar las respuestas de glosa, basados en identificador_archivos.py
PATRON_RESPUESTA_VERIFICABLE = re.compile(r"([A-Z]+)_?(\d+)\.pdf", re.IGNORECASE)
PATRON_RESPUESTA_GLOSA_REP = re.compile(r"GLOSA_REP\d*\.pdf", re.IGNORECASE)
PATRON_RESPUESTA_GLOSA_NUEVO = re.compile(r"resp_glosa\.pdf", re.IGNORECASE)
PATRONES_RESPUESTA = [
    PATRON_RESPUESTA_VERIFICABLE,
    PATRON_RESPUESTA_GLOSA_REP,
    PATRON_RESPUESTA_GLOSA_NUEVO,
]

class MoverRespuestaRaizWorker(QObject):
    """
    Worker para mover archivos de respuesta de glosa de subcarpetas a la carpeta raíz.
    """
    progreso_actualizado = Signal(str, float)
    proceso_finalizado = Signal(dict)

    def __init__(self, ruta_carpeta_raiz):
        super().__init__()
        self.ruta_carpeta_raiz = ruta_carpeta_raiz
        self.esta_cancelado = False

    def ejecutar(self):
        """
        Busca y mueve los archivos de respuesta de glosa a la carpeta raíz, aplicando filtros.
        """
        resultados = {'movidos': [], 'errores': []}
        archivos_movidos_count = 0

        try:
            # 1. Obtener todas las subcarpetas directas
            todas_las_subcarpetas = [d.path for d in os.scandir(self.ruta_carpeta_raiz) if d.is_dir()]
            
            # 2. Aplicar los filtros solicitados
            subcarpetas_filtradas = []
            for ruta_carpeta in todas_las_subcarpetas:
                nombre_carpeta = os.path.basename(ruta_carpeta)
                # Ignorar carpetas DEV o ESCOLAR (insensible a mayúsculas)
                if nombre_carpeta.upper() in ['DEV', 'ESCOLAR']:
                    continue
                # Incluir solo carpetas que empiezan con un número
                if nombre_carpeta[0].isdigit():
                    subcarpetas_filtradas.append(ruta_carpeta)

            total_carpetas = len(subcarpetas_filtradas)
            if total_carpetas == 0:
                resultados['errores'].append({'archivo': 'N/A', 'razon': 'No se encontraron subcarpetas que cumplan con los criterios (empezar con número y no ser DEV/ESCOLAR).'})
                self.proceso_finalizado.emit(resultados)
                return

            for i, carpeta_actual in enumerate(subcarpetas_filtradas):
                if self.esta_cancelado: break

                nombre_carpeta_actual = os.path.basename(carpeta_actual)
                porcentaje = ((i + 1) / total_carpetas) * 100
                self.progreso_actualizado.emit(f"Buscando en: {nombre_carpeta_actual}", porcentaje)

                for nombre_archivo in os.listdir(carpeta_actual):
                    ruta_archivo_origen = os.path.join(carpeta_actual, nombre_archivo)
                    if not os.path.isfile(ruta_archivo_origen): continue

                    if any(patron.match(nombre_archivo) for patron in PATRONES_RESPUESTA):
                        ruta_archivo_destino = os.path.join(self.ruta_carpeta_raiz, nombre_archivo)
                        
                        if os.path.exists(ruta_archivo_destino):
                            error_msg = f"Conflicto: Ya existe '{nombre_archivo}' en la raíz. No se movió."
                            resultados['errores'].append({'archivo': nombre_archivo, 'razon': error_msg})
                            continue

                        shutil.move(ruta_archivo_origen, ruta_archivo_destino)
                        archivos_movidos_count += 1
                        resultados['movidos'].append(f"'{nombre_archivo}' movido desde {nombre_carpeta_actual}.")
        
        except Exception as e:
            resultados['errores'].append({'archivo': 'CRÍTICO', 'razon': str(e)})
        
        if self.esta_cancelado:
            resultados['errores'].append({'archivo': 'N/A', 'razon': 'Proceso cancelado.'})

        self.proceso_finalizado.emit(resultados)

    def cancelar(self):
        self.esta_cancelado = True

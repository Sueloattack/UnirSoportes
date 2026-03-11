# logica/workers/renombrador_logic.py
import os
import re
from PySide6.QtCore import QObject, Signal

from logica.core import gestor_archivos, identificador_archivos

# --- COLORES ---
COLOR_INFO = "#5DADE2"
COLOR_SUCCESS = "#2ECC71"
COLOR_WARNING = "#F39C12"
COLOR_ERROR = "#E74C3C"
COLOR_DEFAULT = "#ECF0F1"

# Patrones para identificar archivos de respuesta de glosa
PATRONES_RESPUESTA = [
    re.compile(r"([A-Z]+)_?(\d+)\.pdf", re.IGNORECASE),
    re.compile(r"GLOSA_REP\d*\.pdf", re.IGNORECASE),
    re.compile(r"resp_glosa\.pdf", re.IGNORECASE)
]

class RenombradorWorker(QObject):
    progreso_actualizado = Signal(str)
    proceso_finalizado = Signal(dict)

    def __init__(self, ruta_carpeta_raiz, modo):
        super().__init__()
        self.ruta_carpeta_raiz = ruta_carpeta_raiz
        self.modo = modo
        self.esta_cancelado = False

    def ejecutar(self):
        self.progreso_actualizado.emit(f"<p style='color:{COLOR_INFO};'>Iniciando modo <b>'{self.modo.upper()}'</b>...</p><p style='color:{COLOR_DEFAULT};'>Directorio: {self.ruta_carpeta_raiz}</p>")
        
        if self.modo == 'escolar':
            self.renombrar_escolares_en_subcarpetas()
        elif self.modo == 'glosa' or self.modo == 'devolucion':
            self.renombrar_respuestas_en_raiz()
        else:
            resultados = {'exitosos': [], 'fallidos': [{'archivo': 'N/A', 'razon': f"Modo '{self.modo}' desconocido."}]}
            self.proceso_finalizado.emit(resultados)

    def renombrar_respuestas_en_raiz(self):
        resultados = {'exitosos': [], 'fallidos': []}
        try:
            archivos_pdf_raiz = [f for f in os.listdir(self.ruta_carpeta_raiz) if f.lower().endswith('.pdf') and os.path.isfile(os.path.join(self.ruta_carpeta_raiz, f))]
            if not archivos_pdf_raiz:
                self.emit_fallo(resultados, "N/A", "No se encontraron archivos .pdf en la carpeta raíz.")
                self.proceso_finalizado.emit(resultados)
                return

            archivos_procesados = 0
            for nombre_archivo in archivos_pdf_raiz:
                if self.esta_cancelado: break
                if any(patron.match(nombre_archivo) for patron in PATRONES_RESPUESTA):
                    archivos_procesados += 1
                    self.procesar_renombrado_raiz(nombre_archivo, resultados)
            
            if archivos_procesados == 0:
                 self.progreso_actualizado.emit(f"<p style='color:{COLOR_WARNING};'>No se encontró ningún archivo que coincida con un patrón de respuesta de glosa.</p>")

        except Exception as e:
            self.emit_fallo(resultados, "CRÍTICO", f"Error inesperado: {e}")
        self.proceso_finalizado.emit(resultados)

    def procesar_renombrado_raiz(self, nombre_original, resultados):
        self.progreso_actualizado.emit(f"<p style='color:{COLOR_DEFAULT};'>Archivo de respuesta encontrado: <b>{nombre_original}</b></p>")
        
        if self.modo == 'glosa':
            prefijo = 'R-800209891-'
            if nombre_original.startswith(prefijo): return self.emit_fallo(resultados, nombre_original, "Ya tiene el prefijo 'R-8002098917-'", 'warning')
            nuevo_nombre = f"{prefijo}{nombre_original}"
        elif self.modo == 'devolucion':
            prefijo = '800209891-'
            if nombre_original.startswith(prefijo): return self.emit_fallo(resultados, nombre_original, "Ya tiene el prefijo '8002098917-'", 'warning')
            nuevo_nombre = f"{prefijo}{nombre_original}"
        else: return

        ruta_original = os.path.join(self.ruta_carpeta_raiz, nombre_original)
        nueva_ruta = os.path.join(self.ruta_carpeta_raiz, nuevo_nombre)
        try:
            os.rename(ruta_original, nueva_ruta)
            mensaje = f"Renombrado: {nombre_original} -> <b>{nuevo_nombre}</b>"
            resultados['exitosos'].append({"archivo": nombre_original, "razon": mensaje})
            self.progreso_actualizado.emit(f"<p style='color:{COLOR_SUCCESS};'>- {mensaje}</p>")
        except Exception as e:
            self.emit_fallo(resultados, nombre_original, f"Error al intentar renombrar: {e}")

    def renombrar_escolares_en_subcarpetas(self):
        resultados = {'exitosos': [], 'fallidos': []}
        try:
            subcarpetas = gestor_archivos.listar_subdirectorios(self.ruta_carpeta_raiz)
            if not subcarpetas:
                self.emit_fallo(resultados, "N/A", "No se encontraron subcarpetas en el directorio raíz.")
                self.proceso_finalizado.emit(resultados)
                return

            for ruta_carpeta in subcarpetas:
                if self.esta_cancelado: break
                nombre_carpeta = os.path.basename(ruta_carpeta)
                self.progreso_actualizado.emit(f"<br><p style='color:{COLOR_DEFAULT};'>Procesando subcarpeta: <b>{nombre_carpeta}</b></p>")

                archivos_pdf = gestor_archivos.obtener_archivos_pdf(ruta_carpeta)
                if not archivos_pdf: continue

                documentos = identificador_archivos.identificar_documentos_aseguradoras(archivos_pdf, ruta_carpeta)
                respuesta_glosa = documentos.get('respuesta_glosa')

                if documentos.get('carta_glosa') and respuesta_glosa:
                    ruta_original = respuesta_glosa['path']
                    nombre_original = os.path.basename(ruta_original)
                    nombre_base, extension = os.path.splitext(nombre_original)
                    sufijo = '_PRG_1'

                    if nombre_base.endswith(sufijo):
                        self.emit_fallo(resultados, nombre_original, "Ya tiene el sufijo '_PRG_1'.", 'warning')
                    else:
                        nuevo_nombre = f"{nombre_base}{sufijo}{extension}"
                        nueva_ruta = os.path.join(ruta_carpeta, nuevo_nombre)
                        try:
                            os.rename(ruta_original, nueva_ruta)
                            mensaje = f"Renombrado: {nombre_original} -> <b>{nuevo_nombre}</b>"
                            resultados['exitosos'].append({"archivo": nombre_original, "razon": mensaje})
                            self.progreso_actualizado.emit(f"<p style='color:{COLOR_SUCCESS};'>- {mensaje}</p>")
                        except Exception as e:
                            self.emit_fallo(resultados, nombre_original, f"Error al renombrar: {e}")
                else:
                    self.emit_fallo(resultados, nombre_carpeta, "No se encontró el par 'carta_glosa' y 'respuesta_glosa'.", 'warning')
        except Exception as e:
            self.emit_fallo(resultados, "CRÍTICO", f"Error inesperado: {e}")
        self.proceso_finalizado.emit(resultados)

    def emit_fallo(self, resultados, archivo, razon, level='error'):
        color = COLOR_ERROR if level == 'error' else COLOR_WARNING
        resultados['fallidos'].append({"archivo": archivo, "razon": razon})
        self.progreso_actualizado.emit(f"<p style='color:{color};'>- {razon} (Archivo/Carpeta: {archivo})</p>")

    def cancelar(self):
        self.esta_cancelado = True

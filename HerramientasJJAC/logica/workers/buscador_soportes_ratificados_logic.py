# logica/logica_traer_soportes_ratificadas.py
import os
import shutil
import re
from PySide6.QtCore import QObject, Signal

from logica.core.identificador_archivos import identificar_documentos_aseguradoras

# --- COLORES OPTIMIZADOS PARA DARK MODE ---
COLOR_INFO = "#5DADE2"      # Azul claro
COLOR_SUCCESS = "#2ECC71"   # Verde brillante
COLOR_WARNING = "#F39C12"   # Naranja
COLOR_ERROR = "#E74C3C"      # Rojo claro
COLOR_DEFAULT = "#ECF0F1"   # Blanco roto

class BuscadorSoportesRatificadosWorker(QObject):
    log_generado = Signal(str)
    progreso_actualizado = Signal(str, float)
    proceso_finalizado = Signal()

    def __init__(self, numeros_factura: list[str], dir_busqueda: str, dir_destino: str):
        super().__init__()
        self.numeros_factura = numeros_factura
        self.dir_busqueda = dir_busqueda
        self.dir_destino = dir_destino
        self.esta_cancelado = False

    def _log(self, mensaje: str, color: str = COLOR_DEFAULT):
        self.log_generado.emit(f"<p style='color:{color}; margin-top:0; margin-bottom:0;'>{mensaje}</p>")

    def ejecutar(self):
        self._log("<b>Iniciando búsqueda y copia de soportes...</b>", COLOR_INFO)
        self._log(f"Directorio de Búsqueda: {self.dir_busqueda}")
        self._log(f"Directorio de Destino: {self.dir_destino}")

        try:
            self.progreso_actualizado.emit("Escaneando directorios...", 0)
            todas_las_carpetas = []
            for dirpath, dirnames, _ in os.walk(self.dir_busqueda):
                for dirname in dirnames:
                    todas_las_carpetas.append(os.path.join(dirpath, dirname))
            self._log(f"Se encontraron {len(todas_las_carpetas)} carpetas en total.", COLOR_INFO)

            total_facturas = len(self.numeros_factura)
            for i, numero in enumerate(self.numeros_factura):
                if self.esta_cancelado: break
                
                numero_limpio = numero.strip()
                porcentaje = ((i + 1) / total_facturas) * 100
                self.progreso_actualizado.emit(f"Procesando factura: {numero_limpio}", porcentaje)

                self._log(f"<br><b>Procesando factura: {numero_limpio}</b>", COLOR_INFO)
                
                carpetas_candidatas = [
                    path for path in todas_las_carpetas 
                    if numero_limpio in os.path.basename(path)
                ]
                
                if not carpetas_candidatas:
                    self._log(f"-> No se encontraron carpetas que contengan '{numero_limpio}'.", COLOR_WARNING)
                    continue

                carpeta_origen_final = None
                if len(carpetas_candidatas) > 1:
                    carpetas_candidatas.sort(key=lambda path: os.path.getmtime(path), reverse=True)
                    self._log(f"-> Se encontraron {len(carpetas_candidatas)} carpetas. Seleccionando la anterior a la más reciente.", COLOR_INFO)
                    carpeta_origen_final = carpetas_candidatas[1]
                elif len(carpetas_candidatas) == 1:
                    self._log("-> Se encontró una única carpeta. Seleccionándola como origen.", COLOR_INFO)
                    carpeta_origen_final = carpetas_candidatas[0]
                else:
                    continue

                # --- CAMBIO: Informar la ruta completa de la carpeta de origen --- 
                self._log(f"-> Carpeta de origen de referencia: <b>{carpeta_origen_final}</b>")
                
                nombre_carpeta_destino = os.path.basename(carpeta_origen_final)
                ruta_destino_subcarpeta = os.path.join(self.dir_destino, nombre_carpeta_destino)

                # La creación de la carpeta se mueve a _copiar_soportes
                self._copiar_soportes(carpeta_origen_final, ruta_destino_subcarpeta, numero_limpio)

        except Exception as e:
            self._log(f"<b>ERROR CRÍTICO:</b> {e}", COLOR_ERROR)
        
        self.progreso_actualizado.emit("Operación completada.", 100)
        self._log("<br><b>✅ Operación completada.</b>", COLOR_SUCCESS)
        self.proceso_finalizado.emit()
        
    def _copiar_soportes(self, ruta_origen: str, ruta_destino: str, numero_factura: str):
        archivos_copiados = 0
        try:
            archivos_pdf_nombres = [f for f in os.listdir(ruta_origen) if f.lower().endswith('.pdf')]
            documentos = identificar_documentos_aseguradoras(archivos_pdf_nombres, ruta_origen)
            soportes_a_copiar = documentos.get('soportes', [])

            # --- CAMBIO: Lógica principal movida aquí ---
            # Si no hay soportes, no hacer nada más.
            if not soportes_a_copiar:
                self._log("-> No se identificaron archivos de soporte para copiar. No se creará la carpeta de destino.")
                return

            # Si hay soportes, AHORA SÍ creamos la carpeta de destino si no existe.
            if not os.path.isdir(ruta_destino):
                try:
                    os.makedirs(ruta_destino)
                    self._log(f"-> Carpeta de destino creada: {os.path.basename(ruta_destino)}", COLOR_INFO)
                except Exception as e:
                    self._log(f"-> ERROR: No se pudo crear la carpeta de destino '{os.path.basename(ruta_destino)}': {e}", COLOR_ERROR)
                    return # No podemos continuar si no se puede crear

            self._log(f"-> Se identificaron {len(soportes_a_copiar)} soportes. Procediendo a copiar...")

            for ruta_completa_origen in soportes_a_copiar:
                nombre_item = os.path.basename(ruta_completa_origen)
                ruta_completa_destino = os.path.join(ruta_destino, nombre_item)
                
                if not os.path.exists(ruta_completa_destino):
                    shutil.copy2(ruta_completa_origen, ruta_completa_destino)
                    archivos_copiados += 1
                else:
                    self._log(f"-> Omitido (ya existe): {nombre_item}", "gray")

            if archivos_copiados > 0:
                self._log(f"-> Se copiaron {archivos_copiados} archivos de soporte.", COLOR_SUCCESS)
            else:
                 self._log("-> No se copiaron nuevos soportes (o ya existían).")
        except Exception as e:
            self._log(f"-> ❌ ERROR al copiar soportes para la factura '{numero_factura}': {e}", COLOR_ERROR)

    def cancelar(self):
        self.esta_cancelado = True

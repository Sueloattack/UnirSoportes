# logica/logica_traer_soportes_ratificadas.py
import os
import shutil
import re
from PySide6.QtCore import QObject, Signal

# --- COLORES OPTIMIZADOS PARA DARK MODE ---
COLOR_INFO = "#5DADE2"      # Azul claro
COLOR_SUCCESS = "#2ECC71"   # Verde brillante
COLOR_WARNING = "#F39C12"   # Naranja
COLOR_ERROR = "#E74C3C"      # Rojo claro
COLOR_DEFAULT = "#ECF0F1"   # Blanco roto

class BuscadorSoportesRatificadosWorker(QObject):
    log_generado = Signal(str)
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
            for numero in self.numeros_factura:
                if self.esta_cancelado: break
                
                self._log(f"<br><b>Buscando soportes para factura: {numero}</b>", COLOR_INFO)
                
                carpetas_origen = self._encontrar_carpetas_origen(numero)
                if not carpetas_origen:
                    self._log(f"-> No se encontraron carpetas de origen para '{numero}'.", COLOR_WARNING)
                    continue
                
                if len(carpetas_origen) > 1:
                    carpetas_origen.sort(key=lambda path: os.path.getmtime(path), reverse=True)
                    self._log(f"-> Se encontraron {len(carpetas_origen)} carpetas. Seleccionando la más reciente:")
                
                carpeta_origen_final = carpetas_origen[0]
                self._log(f"-> Carpeta de origen encontrada: {carpeta_origen_final}")
                
                nombre_carpeta_origen = os.path.basename(carpeta_origen_final)
                ruta_destino_subcarpeta = os.path.join(self.dir_destino, nombre_carpeta_origen)

                if os.path.isdir(ruta_destino_subcarpeta):
                    self._log(f"-> Carpeta de destino encontrada: {ruta_destino_subcarpeta}")
                    self._copiar_contenido(carpeta_origen_final, ruta_destino_subcarpeta, numero)
                else:
                    self._log(f"-> No se encontró la subcarpeta de destino '{nombre_carpeta_origen}'.", COLOR_WARNING)

        except Exception as e:
            self._log(f"<b>ERROR CRÍTICO:</b> {e}", COLOR_ERROR)
        
        self._log("<br><b>✅ Operación completada.</b>", COLOR_SUCCESS)
        self.proceso_finalizado.emit()
        
    def _encontrar_carpetas_origen(self, numero_factura: str) -> list:
        rutas_encontradas = set()
        numero_factura_limpio = numero_factura.strip()

        for nombre_item in os.listdir(self.dir_busqueda):
            ruta_completa = os.path.join(self.dir_busqueda, nombre_item)
            if os.path.isdir(ruta_completa) and numero_factura_limpio in nombre_item:
                rutas_encontradas.add(ruta_completa)

        for dirpath, dirnames, _ in os.walk(self.dir_busqueda):
            for dirname in dirnames:
                if numero_factura_limpio in dirname:
                    rutas_encontradas.add(os.path.join(dirpath, dirname))

        return list(rutas_encontradas)
        
    def _copiar_contenido(self, ruta_origen: str, ruta_destino: str, numero_factura: str):
        archivos_copiados = 0
        try:
            for nombre_item in os.listdir(ruta_origen):
                ruta_completa_origen = os.path.join(ruta_origen, nombre_item)
                if os.path.isfile(ruta_completa_origen):
                    nombre_base, extension = os.path.splitext(nombre_item)
                    nuevo_nombre = f"{nombre_base}-copia{extension}"
                    ruta_completa_destino = os.path.join(ruta_destino, nuevo_nombre)
                    
                    if not os.path.exists(ruta_completa_destino):
                        shutil.copy2(ruta_completa_origen, ruta_completa_destino)
                        archivos_copiados += 1
                    else:
                        self._log(f"-> Omitido (ya existe): {nuevo_nombre}", "gray")

            if archivos_copiados > 0:
                self._log(f"-> Se copiaron {archivos_copiados} archivos a la carpeta de destino.", COLOR_SUCCESS)
            else:
                 self._log("-> No se copiaron nuevos archivos (o ya existían).")
        except Exception as e:
            self._log(f"-> ❌ ERROR al copiar contenido para la factura '{numero_factura}': {e}", COLOR_ERROR)

    def cancelar(self):
        self.esta_cancelado = True
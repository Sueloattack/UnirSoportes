# logica/workers/duplicador_archivos_logic.py
import os
import shutil
from PySide6.QtCore import QObject, Signal

COLOR_INFO = "#5DADE2"
COLOR_SUCCESS = "#2ECC71"
COLOR_ERROR = "#E74C3C"
COLOR_DEFAULT = "#ECF0F1"

class DuplicadorArchivosWorker(QObject):
    progreso_actualizado = Signal(str, float)
    log_generado = Signal(str)
    proceso_finalizado = Signal(dict)

    def __init__(self, ruta_archivo: str, ruta_destino_raiz: str):
        super().__init__()
        self.ruta_archivo = ruta_archivo
        self.ruta_destino_raiz = ruta_destino_raiz
        self.esta_cancelado = False

    def ejecutar(self):
        self.log_generado.emit(f"<p style='color:{COLOR_INFO};'>Iniciando duplicación de archivo...</p>")
        self.log_generado.emit(f"<p style='color:{COLOR_DEFAULT};'>Archivo origen: {self.ruta_archivo}</p>")
        self.log_generado.emit(f"<p style='color:{COLOR_DEFAULT};'>Carpeta raíz destino: {self.ruta_destino_raiz}</p>")

        resultados = {'exitosos': [], 'fallidos': []}

        try:
            if not os.path.isfile(self.ruta_archivo):
                self.log_generado.emit(f"<p style='color:{COLOR_ERROR};'>Error: El archivo de origen no existe.</p>")
                self.proceso_finalizado.emit(resultados)
                return

            if not os.path.isdir(self.ruta_destino_raiz):
                self.log_generado.emit(f"<p style='color:{COLOR_ERROR};'>Error: El directorio de destino no existe o no es válido.</p>")
                self.proceso_finalizado.emit(resultados)
                return

            # List immediate subdirectories
            subdirs = []
            for item in os.listdir(self.ruta_destino_raiz):
                if self.esta_cancelado:
                    break
                item_path = os.path.join(self.ruta_destino_raiz, item)
                if os.path.isdir(item_path):
                    subdirs.append(item_path)

            if not subdirs:
                self.log_generado.emit(f"<p style='color:{COLOR_ERROR};'>No se encontraron subcarpetas en la carpeta de destino.</p>")
                self.proceso_finalizado.emit(resultados)
                return

            self.log_generado.emit(f"<p style='color:{COLOR_INFO};'>Se encontraron {len(subdirs)} subcarpetas para duplicar el archivo.</p>")

            nombre_archivo = os.path.basename(self.ruta_archivo)
            total = len(subdirs)

            for i, folder in enumerate(subdirs):
                if self.esta_cancelado:
                    break

                porcentaje = (i / total) * 100
                self.progreso_actualizado.emit(f"Copiando a: {os.path.basename(folder)}", porcentaje)

                dest_file_path = os.path.join(folder, nombre_archivo)
                try:
                    shutil.copy2(self.ruta_archivo, dest_file_path)
                    msg = f"Copiado con éxito en: <b>{os.path.basename(folder)}</b>"
                    resultados['exitosos'].append(folder)
                    self.log_generado.emit(f"<p style='color:{COLOR_SUCCESS};'>- {msg}</p>")
                except Exception as e:
                    msg = f"Error al copiar en <b>{os.path.basename(folder)}</b>: {e}"
                    resultados['fallidos'].append((folder, str(e)))
                    self.log_generado.emit(f"<p style='color:{COLOR_ERROR};'>- {msg}</p>")

        except Exception as e:
            self.log_generado.emit(f"<p style='color:{COLOR_ERROR};'>Error crítico: {e}</p>")

        self.progreso_actualizado.emit("Finalizado", 100)
        self.proceso_finalizado.emit(resultados)

    def cancelar(self):
        self.esta_cancelado = True

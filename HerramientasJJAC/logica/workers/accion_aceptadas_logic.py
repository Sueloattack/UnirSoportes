# logica/workers/accion_aceptadas_logic.py
import os
import shutil
from PySide6.QtCore import QObject, Signal

# --- COLORES ---
COLOR_INFO = "#5DADE2"
COLOR_SUCCESS = "#2ECC71"
COLOR_WARNING = "#F39C12"
COLOR_ERROR = "#E74C3C"
COLOR_DEFAULT = "#ECF0F1"

class AccionAceptadasWorker(QObject):
    log_generado = Signal(str)
    proceso_finalizado = Signal()

    def __init__(self, rutas_carpetas: list[str], dir_destino: str, accion: str):
        super().__init__()
        self.rutas_carpetas = rutas_carpetas
        self.dir_destino = dir_destino
        self.accion = accion
        self.esta_cancelado = False

    def _log(self, mensaje: str, color: str = COLOR_DEFAULT):
        self.log_generado.emit(f"<p style='color:{color}; margin-top:0; margin-bottom:0;'>{mensaje}</p>")

    def ejecutar(self):
        self._log(f"<b>Iniciando proceso de {self.accion}...</b>", COLOR_INFO)
        self._log(f"Directorio de Destino: {self.dir_destino}")

        if not os.path.exists(self.dir_destino):
            try:
                os.makedirs(self.dir_destino)
                self._log(f"Directorio de destino creado.", COLOR_INFO)
            except Exception as e:
                self._log(f"ERROR CRÍTICO al crear directorio de destino: {e}", COLOR_ERROR)
                self.proceso_finalizado.emit()
                return

        for ruta_origen in self.rutas_carpetas:
            if self.esta_cancelado:
                self._log("Proceso cancelado.", COLOR_WARNING)
                break

            nombre_carpeta = os.path.basename(ruta_origen)
            ruta_destino_completa = os.path.join(self.dir_destino, nombre_carpeta)

            self._log(f"Procesando: <b>{nombre_carpeta}</b>", COLOR_DEFAULT)

            try:
                if os.path.exists(ruta_destino_completa):
                    self._log(f"-> AVISO: La carpeta ya existe en el destino. Se omitirá.", COLOR_WARNING)
                    continue

                if self.accion == 'mover':
                    shutil.move(ruta_origen, ruta_destino_completa)
                    self._log(f"-> Movida exitosamente.", COLOR_SUCCESS)
                elif self.accion == 'copiar':
                    shutil.copytree(ruta_origen, ruta_destino_completa)
                    self._log(f"-> Copiada exitosamente.", COLOR_SUCCESS)

            except Exception as e:
                self._log(f"-> ERROR al {self.accion} la carpeta: {e}", COLOR_ERROR)

        self._log("<br><b>✅ Operación completada.</b>", COLOR_SUCCESS)
        self.proceso_finalizado.emit()

    def cancelar(self):
        self.esta_cancelado = True

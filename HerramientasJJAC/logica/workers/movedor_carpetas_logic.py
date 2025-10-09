# logica/workers/movedor_carpetas_logic.py
import os
import shutil
from PySide6.QtCore import QObject, Signal

# --- COLORES --- 
COLOR_INFO = "#5DADE2"
COLOR_SUCCESS = "#2ECC71"
COLOR_WARNING = "#F39C12"
COLOR_ERROR = "#E74C3C"
COLOR_DEFAULT = "#ECF0F1"

class MovedorCarpetasWorker(QObject):
    log_generado = Signal(str)
    proceso_finalizado = Signal()

    def __init__(self, numeros_factura: list[str], dir_origen: str, dir_destino: str, accion: str = 'mover'):
        super().__init__()
        self.numeros_factura = numeros_factura
        self.dir_origen = dir_origen
        self.dir_destino = dir_destino
        self.accion = accion
        self.esta_cancelado = False
        self.exitos_lista = []
        self.fallos_lista = []

    def _log(self, mensaje: str, color: str = COLOR_DEFAULT):
        self.log_generado.emit(f"<p style='color:{color}; margin-top:0; margin-bottom:0;'>{mensaje}</p>")

    def ejecutar(self):
        self._log(f"<b>Iniciando proceso para {self.accion} carpetas...</b>", COLOR_INFO)
        self._log(f"Directorio de Origen: {self.dir_origen}")
        self._log(f"Directorio de Destino: {self.dir_destino}")

        try:
            subcarpetas_origen = [d for d in os.listdir(self.dir_origen) if os.path.isdir(os.path.join(self.dir_origen, d))]
            self._log(f"Se encontraron {len(subcarpetas_origen)} carpetas en el directorio de origen.", COLOR_INFO)

            for num_factura in self.numeros_factura:
                if self.esta_cancelado:
                    self.fallos_lista.append(f"{num_factura} (cancelado)")
                    continue

                self._log(f"<br><b>Buscando carpeta para factura: {num_factura}</b>", COLOR_DEFAULT)
                
                carpeta_encontrada = None
                for nombre_carpeta in subcarpetas_origen:
                    if nombre_carpeta.startswith(num_factura):
                        carpeta_encontrada = nombre_carpeta
                        break
                
                if carpeta_encontrada:
                    ruta_origen_completa = os.path.join(self.dir_origen, carpeta_encontrada)
                    ruta_destino_completa = os.path.join(self.dir_destino, carpeta_encontrada)
                    self._log(f"-> Carpeta encontrada: <b>{carpeta_encontrada}</b>", COLOR_SUCCESS)
                    
                    try:
                        if not os.path.exists(self.dir_destino):
                            os.makedirs(self.dir_destino)
                            self._log(f"-> Directorio de destino creado.", COLOR_INFO)

                        if os.path.exists(ruta_destino_completa):
                            self._log(f"-> AVISO: La carpeta ya existe en el destino. Se omitirá.", COLOR_WARNING)
                            self.fallos_lista.append(f"{num_factura} (ya existe en destino)")
                        else:
                            if self.accion == 'mover':
                                shutil.move(ruta_origen_completa, ruta_destino_completa)
                                self._log(f"-> Movida exitosamente a: <b>{self.dir_destino}</b>", COLOR_SUCCESS)
                            else: # accion == 'copiar'
                                shutil.copytree(ruta_origen_completa, ruta_destino_completa)
                                self._log(f"-> Copiada exitosamente a: <b>{self.dir_destino}</b>", COLOR_SUCCESS)
                            self.exitos_lista.append(f"{num_factura} -> {carpeta_encontrada}")

                    except Exception as e:
                        self._log(f"-> ERROR al {self.accion} la carpeta '{carpeta_encontrada}': {e}", COLOR_ERROR)
                        self.fallos_lista.append(f"{num_factura} (error al {self.accion})")
                else:
                    self._log(f"-> No se encontró ninguna carpeta que comience con '{num_factura}'.", COLOR_WARNING)
                    self.fallos_lista.append(f"{num_factura} (no encontrada)")

        except Exception as e:
            self._log(f"<b>ERROR CRÍTICO durante la ejecución:</b> {e}", COLOR_ERROR)
        
        # --- RESUMEN FINAL ---
        self._log(f"<br><b>--- RESUMEN ---</b>", COLOR_INFO)
        self._log(f"<b>Carpetas procesadas exitosamente ({len(self.exitos_lista)}):</b>", COLOR_SUCCESS)
        for exito in self.exitos_lista:
            self._log(f"- {exito}", COLOR_SUCCESS)
        
        self._log(f"<br><b>Carpetas no procesadas o con error ({len(self.fallos_lista)}):</b>", COLOR_WARNING)
        for fallo in self.fallos_lista:
            self._log(f"- {fallo}", COLOR_WARNING)

        self._log("<br><b>✅ Operación completada.</b>", COLOR_SUCCESS)
        self.proceso_finalizado.emit()

    def cancelar(self):
        self.esta_cancelado = True

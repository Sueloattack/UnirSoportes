import os
import shutil
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

from PySide6.QtCore import QObject, Signal


COLOR_INFO = "#5DADE2"
COLOR_SUCCESS = "#2ECC71"
COLOR_WARNING = "#F39C12"
COLOR_ERROR = "#E74C3C"
COLOR_DEFAULT = "#ECF0F1"


class MoverArchivosWorker(QObject):
    log_generado = Signal(str)
    progreso_actualizado = Signal(str, float)
    proceso_finalizado = Signal(dict)

    def __init__(self, facturas: list[str], dir_origen: str, dir_destino: str, accion: str = "mover"):
        super().__init__()
        self.facturas = [factura.strip().upper() for factura in facturas if factura.strip()]
        self.dir_origen = dir_origen
        self.dir_destino = dir_destino
        self.accion = accion
        self.esta_cancelado = False
        self._estado_lock = threading.Lock()
        self._archivos_reservados = set()
        self._facturas_completadas = 0
        self._resumen = {
            "facturas_con_coincidencias": 0,
            "facturas_sin_coincidencias": 0,
            "archivos_procesados": 0,
            "archivos_omitidos": 0,
            "errores": 0,
        }
        self._exitos_lista = []
        self._fallos_lista = []

    def _log(self, mensaje: str, color: str = COLOR_DEFAULT):
        self.log_generado.emit(f"<p style='color:{color}; margin-top:0; margin-bottom:0;'>{mensaje}</p>")

    def ejecutar(self):
        self._log(f"<b>Iniciando proceso para {self.accion} PDFs por factura...</b>", COLOR_INFO)
        self._log(f"Directorio de origen: {self.dir_origen}")
        self._log(f"Directorio de destino: {self.dir_destino}")
        self.progreso_actualizado.emit("Indexando PDFs del origen...", 0)

        try:
            pdfs_indexados = self._indexar_pdfs()
            self._log(f"Se indexaron {len(pdfs_indexados)} PDFs en el origen.", COLOR_INFO)

            if not pdfs_indexados:
                self._log("No se encontraron PDFs en la carpeta de origen.", COLOR_WARNING)
                self._resumen["facturas_sin_coincidencias"] = len(self.facturas)
                self._emitir_resumen_final()
                return

            os.makedirs(self.dir_destino, exist_ok=True)
            max_workers = self._calcular_max_workers(len(self.facturas))
            self._log(f"Se usarán hasta <b>{max_workers}</b> hilos de trabajo.", COLOR_INFO)

            with ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="mover-archivos") as executor:
                futuros = {
                    executor.submit(self._procesar_factura, factura, pdfs_indexados): factura
                    for factura in self.facturas
                }

                for futuro in as_completed(futuros):
                    factura = futuros[futuro]
                    try:
                        futuro.result()
                    except Exception as error:
                        with self._estado_lock:
                            self._resumen["errores"] += 1
                            self._fallos_lista.append(f"{factura} (error en hilo)")
                        self._log(f"<b>ERROR EN HILO {factura}:</b> {error}", COLOR_ERROR)
                    finally:
                        self._marcar_factura_completada(factura)

        except Exception as error:
            with self._estado_lock:
                self._resumen["errores"] += 1
            self._log(f"<b>ERROR CRÍTICO:</b> {error}", COLOR_ERROR)

        self._emitir_resumen_final()

    def _indexar_pdfs(self) -> list[tuple[str, str]]:
        pdfs = []
        for root, _dirs, files in os.walk(self.dir_origen):
            if self.esta_cancelado:
                break
            for filename in files:
                if not filename.lower().endswith(".pdf"):
                    continue
                ruta_completa = os.path.join(root, filename)
                pdfs.append((filename.upper(), ruta_completa))
        return pdfs

    def _procesar_factura(self, factura: str, pdfs_indexados: list[tuple[str, str]]):
        coincidencias = [ruta for nombre, ruta in pdfs_indexados if factura in nombre]

        if not coincidencias:
            with self._estado_lock:
                self._resumen["facturas_sin_coincidencias"] += 1
                self._fallos_lista.append(f"{factura} (sin PDFs)")
            self._log(f"<br><b>{factura}</b>: no se encontraron PDFs coincidentes.", COLOR_WARNING)
            return

        archivos_movidos = 0
        archivos_omitidos = 0
        errores_factura = 0

        self._log(
            f"<br><b>{factura}</b>: se encontraron {len(coincidencias)} PDFs coincidentes.",
            COLOR_INFO,
        )

        for ruta_origen in coincidencias:
            if self.esta_cancelado:
                return

            ruta_origen_norm = os.path.normcase(os.path.abspath(ruta_origen))
            nombre_archivo = os.path.basename(ruta_origen)
            ruta_destino = os.path.join(self.dir_destino, nombre_archivo)

            with self._estado_lock:
                if ruta_origen_norm in self._archivos_reservados:
                    archivos_omitidos += 1
                    self._resumen["archivos_omitidos"] += 1
                    self._log(
                        f"-> Omitido para {factura}: {nombre_archivo} ya fue tomado por otra coincidencia.",
                        COLOR_WARNING,
                    )
                    continue
                self._archivos_reservados.add(ruta_origen_norm)

            try:
                if os.path.exists(ruta_destino):
                    archivos_omitidos += 1
                    with self._estado_lock:
                        self._resumen["archivos_omitidos"] += 1
                    self._log(
                        f"-> Omitido para {factura}: ya existe en destino {nombre_archivo}.",
                        COLOR_WARNING,
                    )
                    continue

                if self.accion == "mover":
                    shutil.move(ruta_origen, ruta_destino)
                else:
                    shutil.copy2(ruta_origen, ruta_destino)

                archivos_movidos += 1
                with self._estado_lock:
                    self._resumen["archivos_procesados"] += 1
                self._log(f"-> {self.accion.title()} OK para {factura}: <b>{nombre_archivo}</b>", COLOR_SUCCESS)

            except Exception as error:
                errores_factura += 1
                with self._estado_lock:
                    self._resumen["errores"] += 1
                self._log(
                    f"-> ERROR para {factura} con {nombre_archivo}: {error}",
                    COLOR_ERROR,
                )

        with self._estado_lock:
            if archivos_movidos > 0:
                self._resumen["facturas_con_coincidencias"] += 1
                self._exitos_lista.append(f"{factura} ({archivos_movidos} archivos)")
            else:
                self._resumen["facturas_sin_coincidencias"] += 1
                detalle = f"{factura} (solo omitidos" + (f", {errores_factura} errores" if errores_factura else "") + ")"
                self._fallos_lista.append(detalle)

        if archivos_movidos == 0 and archivos_omitidos > 0:
            self._log(
                f"-> {factura}: hubo coincidencias, pero no se procesó ningún archivo nuevo.",
                COLOR_WARNING,
            )

    def _marcar_factura_completada(self, factura: str):
        with self._estado_lock:
            self._facturas_completadas += 1
            completadas = self._facturas_completadas
            total = max(len(self.facturas), 1)

        porcentaje = (completadas / total) * 100
        self.progreso_actualizado.emit(
            f"Procesadas {completadas} de {total} facturas. Última: {factura}",
            porcentaje,
        )

    def _emitir_resumen_final(self):
        self.progreso_actualizado.emit("Operación completada.", 100)
        self._log("<br><b>--- RESUMEN ---</b>", COLOR_INFO)
        self._log(
            f"<b>Facturas con coincidencias ({self._resumen['facturas_con_coincidencias']}):</b>",
            COLOR_SUCCESS,
        )
        for exito in self._exitos_lista:
            self._log(f"- {exito}", COLOR_SUCCESS)

        self._log(
            f"<br><b>Facturas sin coincidencias o sin archivos nuevos ({self._resumen['facturas_sin_coincidencias']}):</b>",
            COLOR_WARNING,
        )
        for fallo in self._fallos_lista:
            self._log(f"- {fallo}", COLOR_WARNING)

        self._log(
            (
                f"<br><b>Archivos procesados:</b> {self._resumen['archivos_procesados']}<br>"
                f"<b>Archivos omitidos:</b> {self._resumen['archivos_omitidos']}<br>"
                f"<b>Errores:</b> {self._resumen['errores']}"
            ),
            COLOR_INFO,
        )
        self._log("<br><b>✅ Operación completada.</b>", COLOR_SUCCESS)
        self.proceso_finalizado.emit(dict(self._resumen))

    def _calcular_max_workers(self, total_facturas: int) -> int:
        if total_facturas <= 1:
            return 1
        cpu_count = os.cpu_count() or 4
        return max(1, min(total_facturas, cpu_count, 8))

    def cancelar(self):
        self.esta_cancelado = True
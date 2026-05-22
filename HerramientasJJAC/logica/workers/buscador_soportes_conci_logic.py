# logica/workers/buscador_soportes_conci_logic.py
import os
import shutil
import re
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from PySide6.QtCore import QObject, Signal

# --- COLORES OPTIMIZADOS PARA DARK MODE ---
COLOR_INFO = "#5DADE2"      # Azul claro
COLOR_SUCCESS = "#2ECC71"   # Verde brillante
COLOR_WARNING = "#F39C12"   # Naranja
COLOR_ERROR = "#E74C3C"      # Rojo claro
COLOR_DEFAULT = "#ECF0F1"   # Blanco roto

class BuscadorSoportesConciWorker(QObject):
    log_generado = Signal(str)
    progreso_actualizado = Signal(str, float)
    proceso_finalizado = Signal()

    def __init__(self, facturas_con_serie: list[str], dir_busqueda: str, dir_destino: str):
        super().__init__()
        self.facturas_con_serie = facturas_con_serie
        self.dir_busqueda = dir_busqueda
        self.dir_destino = dir_destino
        self.esta_cancelado = False
        self.exitos_lista = []
        self.fallos_lista = []
        self._estado_lock = threading.Lock()
        self._facturas_completadas = 0
        self._total_facturas = 0

    def _log(self, mensaje: str, color: str = COLOR_DEFAULT):
        self.log_generado.emit(f"<p style='color:{color}; margin-top:0; margin-bottom:0;'>{mensaje}</p>")

    def _normalizar_factura(self, factura_input: str) -> tuple[str, str] | None:
        match = re.match(r'([a-zA-Z]+)(\d+)', factura_input.strip())
        if not match:
            return None
        serie, numero_factura = match.groups()
        return serie.upper(), numero_factura

    def _calcular_max_workers(self, total_facturas: int) -> int:
        if total_facturas <= 1:
            return 1
        return min(12, max(2, min(total_facturas, os.cpu_count() or 4)))

    def _registrar_exito(self, mensaje: str):
        with self._estado_lock:
            self.exitos_lista.append(mensaje)

    def _registrar_fallo(self, mensaje: str):
        with self._estado_lock:
            self.fallos_lista.append(mensaje)

    def _marcar_factura_completada(self, factura_limpia: str):
        with self._estado_lock:
            self._facturas_completadas += 1
            completadas = self._facturas_completadas
            total = self._total_facturas or 1
        porcentaje = (completadas / total) * 100
        self.progreso_actualizado.emit(f"Procesadas {completadas}/{total}: {factura_limpia}", porcentaje)

    def ejecutar(self):
        self._log("<b>Iniciando búsqueda de soportes CONCI...</b>", COLOR_INFO)
        self._log(f"Directorio de Búsqueda: {self.dir_busqueda}")
        self._log(f"Directorio de Destino: {self.dir_destino}")

        try:
            # 1. INDEXACIÓN DE CARPETAS
            self._log("Creando índice de carpetas...", COLOR_INFO)
            self.progreso_actualizado.emit("Indexando...", 0)
            
            indice_carpetas = {}
            for dirpath, dirnames, _ in os.walk(self.dir_busqueda):
                if self.esta_cancelado:
                    self._log("-> Cancelación solicitada durante la indexación.", COLOR_WARNING)
                    break
                for dirname in dirnames:
                    indice_carpetas.setdefault(dirname, []).append(os.path.join(dirpath, dirname))

            if self.esta_cancelado:
                self.proceso_finalizado.emit()
                return
            
            self._log(f"Se indexaron {len(indice_carpetas)} nombres de carpetas únicos.", COLOR_SUCCESS)

            self._total_facturas = len([factura for factura in self.facturas_con_serie if factura.strip()])
            self._facturas_completadas = 0
            max_workers = self._calcular_max_workers(self._total_facturas)
            self._log(f"Se usarán hasta <b>{max_workers}</b> hilos de trabajo en CONCI.", COLOR_INFO)

            with ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="conci-worker") as executor:
                futuros = {
                    executor.submit(self._procesar_factura_conci, factura.strip(), indice_carpetas): factura.strip()
                    for factura in self.facturas_con_serie
                    if factura.strip()
                }
                for futuro in as_completed(futuros):
                    factura_limpia = futuros[futuro]
                    try:
                        futuro.result()
                    except Exception as e:
                        self._registrar_fallo(f"{factura_limpia} (error en hilo)")
                        self._log(f"<b>ERROR EN HILO {factura_limpia}:</b> {e}", COLOR_ERROR)

        except Exception as e:
            self._log(f"<b>ERROR CRÍTICO:</b> {e}", COLOR_ERROR)

        # RESUMEN
        self.progreso_actualizado.emit("Finalizado", 100)
        self._log(f"<br><b>--- RESUMEN ---</b>", COLOR_INFO)
        self._log(f"<b>Procesados con hallazgos ({len(self.exitos_lista)}):</b>", COLOR_SUCCESS)
        for item in self.exitos_lista:
            self._log(f"- {item}", COLOR_SUCCESS)
        
        self._log(f"<br><b>Sin hallazgos o errores ({len(self.fallos_lista)}):</b>", COLOR_WARNING)
        for item in self.fallos_lista:
            self._log(f"- {item}", COLOR_WARNING)
            
        self.proceso_finalizado.emit()

    def _procesar_factura_conci(self, factura_limpia: str, indice_carpetas: dict):
        try:
            if self.esta_cancelado:
                self._registrar_fallo(f"{factura_limpia} (cancelado)")
                return

            self._log(f"<br><b>Procesando: {factura_limpia}</b>", COLOR_INFO)
            normalizada = self._normalizar_factura(factura_limpia)
            if not normalizada:
                self._log(f"-> Formato inválido '{factura_limpia}'. Se espera SERIENUMERO.", COLOR_WARNING)
                self._registrar_fallo(f"{factura_limpia} (formato inválido)")
                return

            serie, numero_factura = normalizada
            rutas_encontradas = indice_carpetas.get(numero_factura)
            if not rutas_encontradas:
                self._log(f"-> No se encontró carpeta para '{numero_factura}'.", COLOR_WARNING)
                self._registrar_fallo(f"{factura_limpia} (carpeta no encontrada)")
                return

            carpeta_seleccionada = min(rutas_encontradas, key=os.path.getctime)
            if len(rutas_encontradas) > 1:
                self._log(
                    f"-> Se encontraron {len(rutas_encontradas)} carpetas. Seleccionando la más antigua: {os.path.basename(carpeta_seleccionada)}",
                    COLOR_INFO,
                )

            self._log(f"-> Analizando carpeta: <b>{carpeta_seleccionada}</b>")
            encontrados = self._procesar_contenido_carpeta(carpeta_seleccionada, serie, numero_factura)

            total_encontrados = len(encontrados['cartas']) + len(encontrados['respuestas']) + len(encontrados['soportes'])
            if total_encontrados > 0:
                self._registrar_exito(
                    f"{factura_limpia}: C={len(encontrados['cartas'])}, R={len(encontrados['respuestas'])}, S={len(encontrados['soportes'])}"
                )
            else:
                self._registrar_fallo(f"{factura_limpia} (carpeta vacía o sin coincidencias)")
        finally:
            self._marcar_factura_completada(factura_limpia)

    def _construir_nombre_destino(self, prefijo: str, indice: int | None, nombre_original: str) -> str:
        if indice is None:
            return f"{prefijo}__{nombre_original}"
        return f"{prefijo}_{indice:02d}__{nombre_original}"

    def _copiar_archivo_categorizado(self, ruta_origen: str, ruta_destino_factura: str, prefijo: str, indice: int | None = None):
        if self.esta_cancelado:
            return None

        nombre_original = os.path.basename(ruta_origen)
        nombre_base, extension = os.path.splitext(self._construir_nombre_destino(prefijo, indice, nombre_original))
        ruta_destino = os.path.join(ruta_destino_factura, f"{nombre_base}{extension}")
        consecutivo = 1
        while os.path.exists(ruta_destino):
            ruta_destino = os.path.join(ruta_destino_factura, f"{nombre_base}_{consecutivo}{extension}")
            consecutivo += 1

        shutil.copy2(ruta_origen, ruta_destino)
        return os.path.basename(ruta_destino)

    def _procesar_contenido_carpeta(self, ruta_carpeta, serie, numero):
        """Clasifica y copia archivos según patrones CONCI."""
        resultados = {'cartas': [], 'respuestas': [], 'soportes': []}
        if self.esta_cancelado:
            return resultados
        
        archivos = sorted(
            [f for f in os.listdir(ruta_carpeta) if os.path.isfile(os.path.join(ruta_carpeta, f))]
        )
        
        # Patrones
        # Carta: RADICADO-SERIE-NUMERO-ASEGURADORA.pdf (contiene serie y numero separados por guiones)
        patron_carta = re.compile(rf".*-{serie}-{numero}-.*\.pdf$", re.IGNORECASE)
        
        # Respuesta: SERIENUMERO.pdf, resp_glosa, GLOSA_REP
        nombre_exacto_respuesta = f"{serie}{numero}.pdf".lower()
        
        for archivo in archivos:
            if self.esta_cancelado:
                return resultados
            if not archivo.lower().endswith('.pdf'):
                continue

            nombre_lower = archivo.lower()
            ruta_archivo = os.path.join(ruta_carpeta, archivo)

            if patron_carta.match(archivo):
                resultados['cartas'].append(ruta_archivo)
            elif (
                nombre_lower == nombre_exacto_respuesta
                or "resp_glosa" in nombre_lower
                or "glosa_rep" in nombre_lower
            ):
                resultados['respuestas'].append(ruta_archivo)
            else:
                resultados['soportes'].append(ruta_archivo)

        # 4. Copiar a destino
        if self.esta_cancelado:
            return resultados
        ruta_destino_factura = os.path.join(self.dir_destino, numero)
        if not os.path.exists(ruta_destino_factura):
            os.makedirs(ruta_destino_factura, exist_ok=True)

        if resultados['cartas']:
            for indice, carta in enumerate(resultados['cartas'], 1):
                if self.esta_cancelado:
                    return resultados
                nombre_destino = self._copiar_archivo_categorizado(carta, ruta_destino_factura, 'CARTA', indice)
                self._log(f"  -> Carta encontrada: {nombre_destino}", COLOR_SUCCESS)
        else:
            self._log(f"  -> ❌ Falta Carta Glosa", COLOR_WARNING)

        if resultados['respuestas']:
            for indice, respuesta in enumerate(resultados['respuestas'], 1):
                if self.esta_cancelado:
                    return resultados
                nombre_destino = self._copiar_archivo_categorizado(respuesta, ruta_destino_factura, 'RESPUESTA', indice)
                self._log(f"  -> Respuesta encontrada: {nombre_destino}", COLOR_SUCCESS)
        else:
            self._log(f"  -> ❌ Falta Respuesta Glosa", COLOR_WARNING)

        if resultados['soportes']:
            for indice, soporte in enumerate(resultados['soportes'], 1):
                if self.esta_cancelado:
                    return resultados
                self._copiar_archivo_categorizado(soporte, ruta_destino_factura, 'SOPORTE', indice)
            self._log(f"  -> {len(resultados['soportes'])} soportes copiados.", COLOR_SUCCESS)
        else:
            self._log(f"  -> ⚠️ No se encontraron soportes adicionales.", "gray")
            
        return resultados

    def cancelar(self):
        self._log("<b>Cancelación solicitada. Finalizando proceso CONCI...</b>", COLOR_WARNING)
        self.esta_cancelado = True

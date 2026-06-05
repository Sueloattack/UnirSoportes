# logica/workers/buscador_soportes_nuevos_logic.py
import os
import shutil
import re
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime

from PySide6.QtCore import QObject, Signal

from api_gema import query_api_gema

# --- COLORES OPTIMIZADOS PARA DARK MODE ---
COLOR_INFO = "#5DADE2"      # Azul claro
COLOR_SUCCESS = "#2ECC71"   # Verde brillante
COLOR_WARNING = "#F39C12"   # Naranja
COLOR_ERROR = "#E74C3C"      # Rojo claro
COLOR_DEFAULT = "#ECF0F1"   # Blanco roto

EXTENSIONES_SOPORTE = ('.pdf',)
PREFIJOS_RENOMBRADOS = ('CRC', 'DQX', 'EPI', 'FEV', 'HAM', 'HAU', 'PDE', 'RAN', 'FURIPS')
MESES = {
    1: '01 ENERO',
    2: '02 FEBRERO',
    3: '03 MARZO',
    4: '04 ABRIL',
    5: '05 MAYO',
    6: '06 JUNIO',
    7: '07 JULIO',
    8: '08 AGOSTO',
    9: '09 SEPTIEMBRE',
    10: '10 OCTUBRE',
    11: '11 NOVIEMBRE',
    12: '12 DICIEMBRE',
}

class BuscadorSoportesNuevosWorker(QObject):
    log_generado = Signal(str)
    progreso_actualizado = Signal(str, float)
    proceso_finalizado = Signal()

    def __init__(self, facturas_con_serie: list[str], dir_busqueda: str, dir_destino: str, solo_factura: bool = False, buscar_cuenta_cobro: bool = False):
        super().__init__()
        self.facturas_con_serie = facturas_con_serie
        self.dir_busqueda = dir_busqueda
        self.dir_destino = dir_destino
        self.solo_factura = solo_factura
        self.buscar_cuenta_cobro = buscar_cuenta_cobro
        self.esta_cancelado = False
        self.exitos_lista = []
        self.fallos_lista = []
        self.contextos_busqueda = {}
        self.rutas_preferidas = {}
        self.alcances_preferidos = {}
        self._estado_lock = threading.Lock()
        self._cache_lock = threading.Lock()
        self._indice_archivos_cache = {}
        self._indice_carpetas_cache = {}
        self._indice_archivos_eventos = {}
        self._indice_carpetas_eventos = {}
        self._facturas_completadas = 0
        self._total_facturas = 0

    def _log(self, mensaje: str, color: str = COLOR_DEFAULT):
        self.log_generado.emit(f"<p style='color:{color}; margin-top:0; margin-bottom:0;'>{mensaje}</p>")

    def ejecutar(self):
        if self.buscar_cuenta_cobro:
            self._ejecutar_buscar_cuenta_cobro()
            return

        self._log("<b>Iniciando búsqueda y copia de soportes NUEVOS...</b>", COLOR_INFO)
        self._log(f"Directorio de Búsqueda: {self.dir_busqueda}")
        self._log(f"Directorio de Destino: {self.dir_destino}")

        try:
            self._total_facturas = len(self.facturas_con_serie)
            self._facturas_completadas = 0
            max_workers = self._calcular_max_workers(self._total_facturas)
            self._log("<br><b>--- PREPARACIÓN Y BÚSQUEDA PARALELA POR FACTURA ---</b>", COLOR_INFO)
            self._log(f"Se usarán hasta <b>{max_workers}</b> hilos de trabajo.", COLOR_INFO)

            with ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="nu-worker") as executor:
                futuros = {
                    executor.submit(self._procesar_factura_completa, factura.strip()): factura.strip()
                    for factura in self.facturas_con_serie
                    if factura.strip()
                }
                for futuro in as_completed(futuros):
                    factura = futuros[futuro]
                    try:
                        futuro.result()
                    except Exception as e:
                        self._registrar_fallo(f"{factura} (error en hilo)")
                        self._log(f"<b>ERROR EN HILO {factura}:</b> {e}", COLOR_ERROR)

        except Exception as e:
            self._log(f"<b>ERROR CRÍTICO:</b> {e}", COLOR_ERROR)
        
        # --- RESUMEN FINAL ---
        self.progreso_actualizado.emit("Operación completada.", 100)
        self._log(f"<br><b>--- RESUMEN ---</b>", COLOR_INFO)
        self._log(f"<b>Facturas con soportes encontrados ({len(self.exitos_lista)}):</b>", COLOR_SUCCESS)
        for exito in self.exitos_lista:
            self._log(f"- {exito}", COLOR_SUCCESS)
        
        self._log(f"<br><b>Facturas sin soportes o con error ({len(self.fallos_lista)}):</b>", COLOR_WARNING)
        for fallo in self.fallos_lista:
            self._log(f"- {fallo}", COLOR_WARNING)

        self._log("<br><b>✅ Operación completada.</b>", COLOR_SUCCESS)
        self.proceso_finalizado.emit()

    def _normalizar_factura(self, factura_input: str) -> tuple[str, str] | None:
        match = re.match(r'([a-zA-Z]+)(\d+)', factura_input.strip())
        if not match:
            return None
        serie, numero_factura = match.groups()
        return serie.upper(), numero_factura

    def _valor_campo(self, fila: dict, *nombres: str):
        normalizada = {str(k).lower(): v for k, v in fila.items()}
        for nombre in nombres:
            valor = normalizada.get(nombre.lower())
            if valor not in (None, ''):
                return valor
        return None

    def _parsear_fecha(self, valor_fecha):
        if isinstance(valor_fecha, datetime):
            return valor_fecha.date()
        if isinstance(valor_fecha, date):
            return valor_fecha
        if not valor_fecha:
            return None
        texto = str(valor_fecha).strip()
        for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y', '%m/%d/%Y', '%Y/%m/%d', '%d/%m/%Y %H:%M:%S'):
            try:
                return datetime.strptime(texto, fmt).date()
            except ValueError:
                continue
        return None

    def _formatear_fecha(self, valor_fecha) -> str:
        fecha = self._parsear_fecha(valor_fecha)
        if not fecha:
            return 'sin fecha'
        return fecha.strftime('%d/%m/%Y')

    def _calcular_max_workers(self, total_facturas: int) -> int:
        if total_facturas <= 1:
            return 1
        return min(12, max(2, min(total_facturas, os.cpu_count() or 4)))

    def _extraer_numero_mes(self, nombre_carpeta: str) -> int:
        coincidencia = re.match(r'(\d{2})', nombre_carpeta.strip())
        if not coincidencia:
            return 0
        try:
            return int(coincidencia.group(1))
        except ValueError:
            return 0

    def _listar_meses_ordenados(self, carpeta_anio: str) -> list[str]:
        if not os.path.isdir(carpeta_anio):
            return []
        rutas_mes = []
        try:
            for nombre in os.listdir(carpeta_anio):
                ruta = os.path.join(carpeta_anio, nombre)
                if os.path.isdir(ruta):
                    rutas_mes.append(ruta)
        except (PermissionError, FileNotFoundError):
            return []
        return sorted(
            rutas_mes,
            key=lambda ruta: (self._extraer_numero_mes(os.path.basename(ruta)), os.path.getmtime(ruta)),
            reverse=True,
        )

    def _listar_anios_ordenados(self, carpeta_raiz: str) -> list[str]:
        if not os.path.isdir(carpeta_raiz):
            return []
        rutas_anio = []
        try:
            for nombre in os.listdir(carpeta_raiz):
                ruta = os.path.join(carpeta_raiz, nombre)
                if os.path.isdir(ruta) and nombre.isdigit() and len(nombre) == 4:
                    rutas_anio.append(ruta)
        except (PermissionError, FileNotFoundError):
            return []
        return sorted(rutas_anio, key=lambda ruta: int(os.path.basename(ruta)), reverse=True)

    def _obtener_segmentos_busqueda(self, base_busqueda: str, alcance_busqueda: str, etiqueta_ambito: str):
        if etiqueta_ambito != 'FASE 6' or alcance_busqueda not in {'anio', 'raiz'}:
            return [(base_busqueda, alcance_busqueda)]

        if alcance_busqueda == 'anio':
            meses = self._listar_meses_ordenados(base_busqueda)
            if meses:
                return [(ruta_mes, 'mes') for ruta_mes in meses]
            return [(base_busqueda, 'anio')]

        anios = self._listar_anios_ordenados(base_busqueda)
        segmentos = []
        for ruta_anio in anios:
            meses = self._listar_meses_ordenados(ruta_anio)
            if meses:
                segmentos.extend((ruta_mes, 'mes') for ruta_mes in meses)
            else:
                segmentos.append((ruta_anio, 'anio'))
        return segmentos or [(base_busqueda, 'raiz')]

    def _fecha_gema_util(self, fecha_radicacion: date | None) -> bool:
        return bool(fecha_radicacion and fecha_radicacion.year >= 2000)

    def _radicacion_gema_util(self, radicacion: str) -> bool:
        texto = str(radicacion).strip()
        if not texto:
            return False
        try:
            return int(texto) > 0
        except ValueError:
            return texto not in {'-2', '0'}

    def _consultar_gema_factura(self, serie: str, numero_factura: str):
        anio_actual = date.today().year % 100
        for anio in range(anio_actual, max(anio_actual - 8, -1), -1):
            ruta_tabla = f"GEMA10.D/VENTAS/DATOS/VTFACC{anio:02d}"
            consulta = f"radicacion, fech_rad, serie, docn FROM [{ruta_tabla}] WHERE serie = '{serie}' AND docn = {numero_factura}"
            try:
                filas = query_api_gema(consulta)
            except Exception:
                continue
            if not filas:
                continue

            fila = filas[0]
            radicacion = str(fila.get('radicacion', '')).strip()
            fecha_radicacion = fila.get('fech_rad', '')

            if not (radicacion and fecha_radicacion):
                continue

            return {
                'tabla': ruta_tabla,
                'radicacion': radicacion,
                'fecha': self._parsear_fecha(fecha_radicacion),
            }
        return None

    def _buscar_carpeta_en(self, carpeta_padre: str, radicacion: str) -> str | None:
        if not os.path.isdir(carpeta_padre):
            return None
        candidatos = []
        for nombre in os.listdir(carpeta_padre):
            if self.esta_cancelado:
                return None
            ruta = os.path.join(carpeta_padre, nombre)
            if not os.path.isdir(ruta):
                continue
            nombre_lower = nombre.lower()
            if nombre == radicacion or nombre_lower == f"cuenta {radicacion}".lower() or radicacion in nombre:
                candidatos.append(ruta)
        if not candidatos:
            return None
        return max(candidatos, key=os.path.getmtime)

    def _resolver_carpeta_anio(self, fecha_radicacion: date | None) -> str | None:
        if not self._fecha_gema_util(fecha_radicacion):
            return None
        carpeta_anio = os.path.join(self.dir_busqueda, str(fecha_radicacion.year))
        if os.path.isdir(carpeta_anio):
            return carpeta_anio
        return None

    def _resolver_carpeta_mes(self, carpeta_anio: str | None, mes_buscado: int) -> str | None:
        if not carpeta_anio or not os.path.isdir(carpeta_anio):
            return None
        try:
            for nombre_mes_actual in os.listdir(carpeta_anio):
                ruta_mes = os.path.join(carpeta_anio, nombre_mes_actual)
                if not os.path.isdir(ruta_mes):
                    continue
                if f"{mes_buscado:02d}" in nombre_mes_actual:
                    return ruta_mes
        except (PermissionError, FileNotFoundError):
            return None
        return None

    def _resolver_ubicaciones_gema(self, radicacion: str, fecha_radicacion: date | None):
        carpeta_anio = self._resolver_carpeta_anio(fecha_radicacion)
        if not carpeta_anio:
            return {
                'ruta_local': None,
                'alcance_local': None,
                'ruta_fallback': self.dir_busqueda,
                'alcance_fallback': 'raiz',
                'origen_ruta': 'sin_local',
                'motivo_fallback': 'sin_carpeta_anio',
            }

        carpeta_cuenta = self._buscar_carpeta_en(carpeta_anio, radicacion)
        if carpeta_cuenta:
            return {
                'ruta_local': carpeta_cuenta,
                'alcance_local': 'cuenta',
                'ruta_fallback': carpeta_anio,
                'alcance_fallback': 'anio',
                'origen_ruta': 'cuenta',
                'motivo_fallback': 'fase6_sobre_anio',
            }

        carpeta_mes = self._resolver_carpeta_mes(carpeta_anio, fecha_radicacion.month)
        if carpeta_mes:
            carpeta_cuenta_mes = self._buscar_carpeta_en(carpeta_mes, radicacion)
            if carpeta_cuenta_mes:
                return {
                    'ruta_local': carpeta_cuenta_mes,
                    'alcance_local': 'cuenta',
                    'ruta_fallback': carpeta_anio,
                    'alcance_fallback': 'anio',
                    'origen_ruta': 'cuenta',
                    'motivo_fallback': 'fase6_sobre_anio',
                }
            return {
                'ruta_local': carpeta_mes,
                'alcance_local': 'mes',
                'ruta_fallback': carpeta_anio,
                'alcance_fallback': 'anio',
                'origen_ruta': 'mes',
                'motivo_fallback': 'fase6_sobre_anio',
            }

        return {
            'ruta_local': carpeta_anio,
            'alcance_local': 'anio',
            'ruta_fallback': self.dir_busqueda,
            'alcance_fallback': 'raiz',
            'origen_ruta': 'anio',
            'motivo_fallback': 'fase6_sobre_raiz',
        }

    def _resolver_contexto_factura(self, factura_limpia: str):
        normalizada = self._normalizar_factura(factura_limpia)
        if not normalizada:
            contexto = {
                'factura': factura_limpia,
                'normalizada': None,
                'info_gema': None,
                'ruta_local': None,
                'alcance_local': None,
                'ruta_fallback': self.dir_busqueda,
                'alcance_fallback': 'raiz',
                'origen_ruta': 'sin_local',
                'motivo_fallback': 'formato_invalido',
            }
            self._log(
                f"-> {factura_limpia}: formato inválido. Se marcará como no encontrada.",
                COLOR_WARNING,
            )
            return contexto

        serie, numero_factura = normalizada
        try:
            info = self._consultar_gema_factura(serie, numero_factura)
        except Exception as e:
            contexto = {
                'factura': factura_limpia,
                'normalizada': normalizada,
                'info_gema': None,
                'ruta_local': None,
                'alcance_local': None,
                'ruta_fallback': self.dir_busqueda,
                'alcance_fallback': 'raiz',
                'origen_ruta': 'sin_local',
                'motivo_fallback': 'error_gema',
            }
            self._log(
                f"-> {factura_limpia}: fallo consultando GEMA ({e}). Se marcará como no encontrada.",
                COLOR_WARNING,
            )
            return contexto

        if not info:
            contexto = {
                'factura': factura_limpia,
                'normalizada': normalizada,
                'info_gema': None,
                'ruta_local': None,
                'alcance_local': None,
                'ruta_fallback': self.dir_busqueda,
                'alcance_fallback': 'raiz',
                'origen_ruta': 'sin_local',
                'motivo_fallback': 'sin_coincidencia_gema',
            }
            self._log(
                f"-> {factura_limpia}: sin coincidencia en GEMA. Se marcará como no encontrada.",
                COLOR_WARNING,
            )
            return contexto

        radicacion = str(info['radicacion']).strip()
        fecha = info['fecha']
        fecha_txt = self._formatear_fecha(fecha)

        if not self._radicacion_gema_util(radicacion) or not self._fecha_gema_util(fecha):
            contexto = {
                'factura': factura_limpia,
                'normalizada': normalizada,
                'info_gema': info,
                'ruta_local': None,
                'alcance_local': None,
                'ruta_fallback': self.dir_busqueda,
                'alcance_fallback': 'raiz',
                'origen_ruta': 'sin_local',
                'motivo_fallback': 'gema_sin_cuenta_util',
            }
            self._log(
                f"-> {factura_limpia}: GEMA devolvió cuenta {radicacion} / fecha {fecha_txt}. "
                f"No hay una cuenta útil; se marcará como no encontrada.",
                COLOR_WARNING,
            )
            return contexto

        ubicaciones = self._resolver_ubicaciones_gema(radicacion, fecha)
        contexto = {
            'factura': factura_limpia,
            'normalizada': normalizada,
            'info_gema': info,
            **ubicaciones,
        }

        if ubicaciones['ruta_local']:
            alcance_local = ubicaciones['alcance_local']
            alcance_fallback = ubicaciones['alcance_fallback']
            detalle_fallback = os.path.basename(ubicaciones['ruta_fallback']) if ubicaciones['ruta_fallback'] else 'raíz'
            self._log(
                f"-> {factura_limpia}: ruta local por GEMA en <b>{os.path.basename(ubicaciones['ruta_local'])}</b> "
                f"[{alcance_local}] y fallback en <b>{detalle_fallback}</b> [{alcance_fallback}] ({info['tabla']}).",
                COLOR_SUCCESS,
            )
        else:
            self._log(
                f"-> {factura_limpia}: GEMA devolvió cuenta {radicacion} / fecha {fecha_txt}, "
                f"pero no se pudo ubicar una ruta local. Se marcará como no encontrada.",
                COLOR_WARNING,
            )
        return contexto

    def _resolver_contextos_busqueda(self):
        contextos = {}
        self._log("<br><b>--- PREPARACIÓN: Resolviendo año, mes y cuenta desde GEMA ---</b>", COLOR_INFO)
        for factura in self.facturas_con_serie:
            factura_limpia = factura.strip()
            contextos[factura_limpia] = self._resolver_contexto_factura(factura_limpia)
        return contextos

    def _deduplicar_facturas(self, facturas: list[str]):
        deduplicadas = []
        vistas = set()
        for factura in facturas:
            if factura in vistas:
                continue
            deduplicadas.append(factura)
            vistas.add(factura)
        return deduplicadas

    def _agrupar_facturas_por_ruta(self, facturas: list[str], rutas_preferidas: dict | None = None, alcances_preferidos: dict | None = None):
        agrupadas = {}
        rutas = rutas_preferidas or self.rutas_preferidas
        alcances = alcances_preferidos or self.alcances_preferidos
        for factura in facturas:
            ruta = rutas.get(factura, self.dir_busqueda)
            alcance = alcances.get(factura, 'raiz')
            agrupadas.setdefault((ruta, alcance), []).append(factura)
        return agrupadas

    def _obtener_indice_archivos(self, directorio_base: str, alcance_busqueda: str):
        clave = (directorio_base, alcance_busqueda)
        with self._cache_lock:
            indice = self._indice_archivos_cache.get(clave)
            evento = self._indice_archivos_eventos.get(clave)
            if indice is not None:
                return indice
            if evento is None:
                evento = threading.Event()
                self._indice_archivos_eventos[clave] = evento
                construir = True
            else:
                construir = False

        if not construir:
            evento.wait()
            with self._cache_lock:
                return self._indice_archivos_cache.get(clave, {})

        try:
            indice = self._crear_indice_archivos(directorio_base, alcance_busqueda)
        finally:
            with self._cache_lock:
                if 'indice' in locals():
                    self._indice_archivos_cache[clave] = indice
                self._indice_archivos_eventos.pop(clave, None)
                evento.set()
        return indice

    def _obtener_indice_carpetas(self, directorio_base: str):
        with self._cache_lock:
            indice = self._indice_carpetas_cache.get(directorio_base)
            evento = self._indice_carpetas_eventos.get(directorio_base)
            if indice is not None:
                return indice
            if evento is None:
                evento = threading.Event()
                self._indice_carpetas_eventos[directorio_base] = evento
                construir = True
            else:
                construir = False

        if not construir:
            evento.wait()
            with self._cache_lock:
                return self._indice_carpetas_cache.get(directorio_base, {})

        indice_carpetas = {}
        try:
            for dirpath, dirnames, _ in os.walk(directorio_base):
                if self.esta_cancelado:
                    break
                for dirname in dirnames:
                    indice_carpetas.setdefault(dirname, []).append(os.path.join(dirpath, dirname))
        finally:
            with self._cache_lock:
                self._indice_carpetas_cache[directorio_base] = indice_carpetas
                self._indice_carpetas_eventos.pop(directorio_base, None)
                evento.set()
        return indice_carpetas

    def _registrar_exito(self, mensaje: str):
        with self._estado_lock:
            self.exitos_lista.append(mensaje)

    def _registrar_fallo(self, mensaje: str):
        with self._estado_lock:
            self.fallos_lista.append(mensaje)

    def _marcar_factura_completada(self, factura: str):
        with self._estado_lock:
            self._facturas_completadas += 1
            completadas = self._facturas_completadas
            total = self._total_facturas or 1
        porcentaje = (completadas / total) * 100
        self.progreso_actualizado.emit(f"Procesadas {completadas}/{total}: {factura}", porcentaje)

    def _procesar_factura_completa(self, factura_limpia: str):
        try:
            if self.esta_cancelado:
                self._registrar_fallo(f"{factura_limpia} (cancelado)")
                return

            contexto = self._resolver_contexto_factura(factura_limpia)
            with self._estado_lock:
                self.contextos_busqueda[factura_limpia] = contexto

            pendientes = [factura_limpia]
            if contexto.get('ruta_local') and not self.esta_cancelado:
                pendientes = self._ejecutar_pipeline_fases(
                    pendientes,
                    usar_fallback=False,
                    etiqueta_ambito='LOCAL',
                    porcentaje_inicio=0,
                    porcentaje_fin=85,
                    registrar_fallos_finales=False,
                    rutas_preferidas={factura_limpia: contexto.get('ruta_local') or self.dir_busqueda},
                    alcances_preferidos={factura_limpia: contexto.get('alcance_local') or 'raiz'},
                )

            if pendientes and not self.esta_cancelado:
                if contexto.get('ruta_local'):
                    self._log(
                        f"-> {factura_limpia}: sin hallazgos en ruta local. Iniciando búsqueda fallback sobre "
                        f"<b>{os.path.basename(contexto.get('ruta_fallback') or self.dir_busqueda)}</b>.",
                        COLOR_WARNING,
                    )
                else:
                    self._log(
                        f"-> {factura_limpia}: sin ruta local útil. Se intentará la búsqueda fallback antes de marcarla como no encontrada.",
                        COLOR_WARNING,
                    )

                self._ejecutar_pipeline_fases(
                    pendientes,
                    usar_fallback=True,
                    etiqueta_ambito='FASE 6',
                    porcentaje_inicio=85,
                    porcentaje_fin=99,
                    registrar_fallos_finales=True,
                    rutas_preferidas={factura_limpia: contexto.get('ruta_fallback') or self.dir_busqueda},
                    alcances_preferidos={factura_limpia: contexto.get('alcance_fallback') or 'raiz'},
                )
        finally:
            self._marcar_factura_completada(factura_limpia)

    def _ejecutar_pipeline_fases(
        self,
        facturas: list[str],
        usar_fallback: bool,
        etiqueta_ambito: str,
        porcentaje_inicio: float,
        porcentaje_fin: float,
        registrar_fallos_finales: bool,
        rutas_preferidas: dict | None = None,
        alcances_preferidos: dict | None = None,
    ):
        if not facturas:
            return []

        if rutas_preferidas is None or alcances_preferidos is None:
            rutas_preferidas = {}
            alcances_preferidos = {}
            for factura in facturas:
                contexto = self.contextos_busqueda.get(factura, {})
                if usar_fallback:
                    rutas_preferidas[factura] = contexto.get('ruta_fallback') or self.dir_busqueda
                    alcances_preferidos[factura] = contexto.get('alcance_fallback') or 'raiz'
                else:
                    rutas_preferidas[factura] = contexto.get('ruta_local') or self.dir_busqueda
                    alcances_preferidos[factura] = contexto.get('alcance_local') or 'raiz'
        pendientes = facturas
        rango_total = porcentaje_fin - porcentaje_inicio

        pendientes = self._ejecutar_estrategia_renombrados(
            pendientes,
            etiqueta_ambito,
            porcentaje_inicio,
            porcentaje_inicio + (rango_total * 0.20),
            rutas_preferidas,
            alcances_preferidos,
        )

        if not self.esta_cancelado and pendientes:
            pendientes = self._ejecutar_estrategia_a(
                pendientes,
                etiqueta_ambito,
                porcentaje_inicio + (rango_total * 0.20),
                porcentaje_inicio + (rango_total * 0.45),
                rutas_preferidas,
                alcances_preferidos,
            )

        if not self.esta_cancelado and pendientes:
            pendientes = self._ejecutar_estrategia_numeros_origen(
                pendientes,
                etiqueta_ambito,
                porcentaje_inicio + (rango_total * 0.45),
                porcentaje_inicio + (rango_total * 0.65),
                rutas_preferidas,
            )

        if not self.esta_cancelado and pendientes:
            pendientes = self._ejecutar_estrategia_b(
                pendientes,
                etiqueta_ambito,
                porcentaje_inicio + (rango_total * 0.65),
                porcentaje_inicio + (rango_total * 0.82),
                rutas_preferidas,
                alcances_preferidos,
            )

        if not self.esta_cancelado and pendientes:
            pendientes = self._ejecutar_nueva_estrategia_sop1(
                pendientes,
                etiqueta_ambito,
                porcentaje_inicio + (rango_total * 0.82),
                porcentaje_fin,
                registrar_fallos_finales,
                rutas_preferidas,
                alcances_preferidos,
            )

        return pendientes

    def _crear_indice_archivos(self, directorio_base: str, alcance_busqueda: str = 'auto'):
        """
        Crea índice de archivos. Si directorio_base es una carpeta específica de cuenta,
        indexa solo 2 niveles de profundidad. Si es la búsqueda general, indexa recursivamente.
        """
        indice_archivos = {}
        
        # Solo una carpeta de cuenta usa un índice acotado; mes, año y raíz deben ser recursivos.
        es_carpeta_especifica = alcance_busqueda == 'cuenta' if alcance_busqueda != 'auto' else "CUENTA" in directorio_base
        max_profundidad = 2 if es_carpeta_especifica else float('inf')
        
        def indexar_recursivo(dirpath, profundidad_actual=0):
            if self.esta_cancelado:
                return
            if profundidad_actual > max_profundidad:
                return
            try:
                for item in os.listdir(dirpath):
                    if self.esta_cancelado:
                        return
                    ruta_completa = os.path.join(dirpath, item)
                    if os.path.isfile(ruta_completa) and item.lower().endswith(EXTENSIONES_SOPORTE):
                        nombre_sin_ext, _ = os.path.splitext(item)
                        indice_archivos.setdefault(nombre_sin_ext.lower(), []).append(ruta_completa)
                    elif os.path.isdir(ruta_completa) and profundidad_actual < max_profundidad:
                        indexar_recursivo(ruta_completa, profundidad_actual + 1)
            except PermissionError:
                pass
        
        indexar_recursivo(directorio_base)
        return indice_archivos

    def _ordenar_soportes_priorizando_pdf(self, rutas_encontradas: list[str]):
        """Ordena soportes por fecha (más reciente primero) priorizando PDF sobre otros formatos."""
        unicos = sorted(set(rutas_encontradas), key=os.path.getmtime, reverse=True)
        pdfs = [ruta for ruta in unicos if ruta.lower().endswith('.pdf')]
        complementarios = [ruta for ruta in unicos if not ruta.lower().endswith('.pdf')]
        return pdfs, complementarios

    def _normalizar_nombre_busqueda(self, texto: str) -> str:
        return re.sub(r'[^a-z0-9]+', '_', texto.lower()).strip('_')

    def _prioridad_factura_principal(self, ruta_archivo: str, factura_buscada: str):
        nombre_base = os.path.splitext(os.path.basename(ruta_archivo))[0]
        nombre_normalizado = self._normalizar_nombre_busqueda(nombre_base)
        factura_normalizada = self._normalizar_nombre_busqueda(factura_buscada)
        claves_descartadas = (
            'furips', 'sop_1', 'hc', 'epicrisis', 'rips', 'cuv',
            'crc', 'dqx', 'epi', 'fev', 'ham', 'hau', 'pde', 'pdx', 'ran',
        )

        if nombre_normalizado == factura_normalizada:
            return 0

        if nombre_normalizado in {
            f"factura_{factura_normalizada}",
            f"{factura_normalizada}_factura",
        }:
            return 1

        if (
            factura_normalizada in nombre_normalizado
            and 'factura' in nombre_normalizado
            and not any(clave in nombre_normalizado for clave in claves_descartadas)
        ):
            return 2

        return None

    def _seleccionar_archivos_para_copia(self, factura_buscada: str, rutas_candidatas: list[str]):
        if not self.solo_factura:
            return rutas_candidatas

        priorizados = []
        for ruta in rutas_candidatas:
            prioridad = self._prioridad_factura_principal(ruta, factura_buscada)
            if prioridad is None:
                continue
            priorizados.append((prioridad, -os.path.getmtime(ruta), ruta))

        if not priorizados:
            return []

        priorizados.sort()
        return [priorizados[0][2]]

    def _obtener_directorio_destino(self, factura_buscada: str, numero_factura: str | None = None) -> str:
        if self.solo_factura:
            return self.dir_destino

        if numero_factura:
            return os.path.join(self.dir_destino, numero_factura)

        return self._encontrar_subcarpeta_destino(factura_buscada)

    def _ejecutar_estrategia_a(
        self,
        facturas_a_buscar: list[str] = None,
        etiqueta_ambito: str = 'LOCAL',
        porcentaje_inicio: float = 25,
        porcentaje_fin: float = 50,
        rutas_preferidas: dict | None = None,
        alcances_preferidos: dict | None = None,
    ):
        self._log(f"<br><b>--- FASE 2 {etiqueta_ambito}: Iniciando Estrategia A (Búsqueda por Carpetas) ---</b>", COLOR_INFO)
        if facturas_a_buscar is None:
            facturas_a_buscar = self.facturas_con_serie
        facturas_no_encontradas = []
        total_facturas = len(facturas_a_buscar)
        procesadas = 0
        facturas_reportadas = set()

        for (base_busqueda, alcance_busqueda), facturas in self._agrupar_facturas_por_ruta(facturas_a_buscar, rutas_preferidas, alcances_preferidos).items():
            segmentos = self._obtener_segmentos_busqueda(base_busqueda, alcance_busqueda, etiqueta_ambito)
            pendientes = list(facturas)

            if etiqueta_ambito == 'FASE 6' and len(segmentos) > 1:
                self._log(
                    f"-> Fase 6 evaluará <b>{len(segmentos)}</b> segmentos ordenados del más reciente al más antiguo.",
                    COLOR_INFO,
                )

            for ruta_segmento, alcance_segmento in segmentos:
                if not pendientes or self.esta_cancelado:
                    break

                es_carpeta_especifica = alcance_segmento == 'cuenta'

                if es_carpeta_especifica:
                    self._log(f"Indexando archivos en carpeta específica: <b>{ruta_segmento}</b>", COLOR_INFO)
                    indice_archivos = self._obtener_indice_archivos(ruta_segmento, alcance_segmento)
                    self._log(f"Se indexaron {len(indice_archivos)} nombres de archivos en esta carpeta.", COLOR_SUCCESS)
                    pendientes_siguiente = []

                    for factura_input in pendientes:
                        factura_limpia = factura_input.strip()
                        if factura_limpia not in facturas_reportadas:
                            procesadas += 1
                            facturas_reportadas.add(factura_limpia)
                        if self.esta_cancelado:
                            self.fallos_lista.append(f"{factura_limpia} (cancelado)")
                            continue

                        porcentaje = porcentaje_inicio + (procesadas / total_facturas) * (porcentaje_fin - porcentaje_inicio)
                        self.progreso_actualizado.emit(f"Fase 2 {etiqueta_ambito}: {factura_limpia}", porcentaje)
                        self._log(f"<br><b>Procesando (A - {etiqueta_ambito}): {factura_limpia}</b>", COLOR_INFO)

                        normalizada = self._normalizar_factura(factura_limpia)
                        if not normalizada:
                            self._log("-> Formato no válido.", COLOR_WARNING)
                            facturas_no_encontradas.append(factura_limpia)
                            continue

                        serie, numero_factura = normalizada
                        self._log(f"-> Serie: '{serie}', Número: '{numero_factura}'")
                        rutas_encontradas = []
                        for clave, rutas_valor in indice_archivos.items():
                            if serie.lower() in clave and numero_factura.lower() in clave:
                                rutas_encontradas.extend(rutas_valor)

                        if not rutas_encontradas:
                            pendientes_siguiente.append(factura_limpia)
                            continue

                        pdfs, complementarios = self._ordenar_soportes_priorizando_pdf(rutas_encontradas)
                        if not pdfs:
                            pendientes_siguiente.append(factura_limpia)
                            continue

                        archivos_encontrados = pdfs + complementarios
                        archivos_encontrados = self._seleccionar_archivos_para_copia(factura_limpia, archivos_encontrados)
                        if not archivos_encontrados:
                            self._log("-> Modo solo factura: no se identificó un PDF principal en esta carpeta GEMA.", COLOR_WARNING)
                            pendientes_siguiente.append(factura_limpia)
                            continue
                        self._log(
                            f"-> Se encontraron <b>{len(archivos_encontrados)}</b> soportes en carpeta GEMA "
                            f"(PDF: {len(pdfs)}, complementarios: {len(complementarios)}).",
                            COLOR_SUCCESS,
                        )
                        ruta_destino_subcarpeta = self._obtener_directorio_destino(factura_limpia, numero_factura)
                        for archivo_encontrado in archivos_encontrados:
                            self._log(f"-> Copiando: <b>{os.path.basename(archivo_encontrado)}</b>", COLOR_SUCCESS)
                            self._copiar_soporte_desde_archivo(archivo_encontrado, ruta_destino_subcarpeta, factura_limpia)
                        self._registrar_exito(f"{factura_limpia} ({len(archivos_encontrados)} soportes en GEMA)")

                    pendientes = pendientes_siguiente
                    continue

                self._log(f"Indexando carpetas en: <b>{ruta_segmento}</b>", COLOR_INFO)
                indice_carpetas = self._obtener_indice_carpetas(ruta_segmento)
                self._log(f"Se indexaron {len(indice_carpetas)} nombres de carpetas únicos en esta ruta.", COLOR_SUCCESS)
                pendientes_siguiente = []

                for factura_input in pendientes:
                    factura_limpia = factura_input.strip()
                    if factura_limpia not in facturas_reportadas:
                        procesadas += 1
                        facturas_reportadas.add(factura_limpia)
                    if self.esta_cancelado:
                        self.fallos_lista.append(f"{factura_limpia} (cancelado)")
                        continue

                    porcentaje = porcentaje_inicio + (procesadas / total_facturas) * (porcentaje_fin - porcentaje_inicio)
                    self.progreso_actualizado.emit(f"Fase 2 {etiqueta_ambito}: {factura_limpia}", porcentaje)
                    self._log(f"<br><b>Procesando (A - {etiqueta_ambito}): {factura_limpia}</b>", COLOR_INFO)

                    normalizada = self._normalizar_factura(factura_limpia)
                    if not normalizada:
                        self._log("-> Formato no válido.", COLOR_WARNING)
                        facturas_no_encontradas.append(factura_limpia)
                        continue

                    serie, numero_factura = normalizada
                    self._log(f"-> Serie: '{serie}', Número: '{numero_factura}'")
                    rutas_encontradas = indice_carpetas.get(numero_factura)

                    if not rutas_encontradas:
                        pendientes_siguiente.append(factura_limpia)
                        continue

                    carpetas_validas = []
                    for ruta in rutas_encontradas:
                        try:
                            archivos_en_carpeta = [f for f in os.listdir(ruta) if os.path.isfile(os.path.join(ruta, f))]
                            contiene_serie = any(serie.lower() in nombre.lower() for nombre in archivos_en_carpeta)

                            if contiene_serie and self._es_carpeta_valida(ruta):
                                carpetas_validas.append(ruta)
                            elif not contiene_serie:
                                self._log(f"-> Carpeta '{os.path.basename(ruta)}' descartada: no contiene la serie '{serie}'.", "gray")
                        except Exception as e:
                            self._log(f"-> Error procesando carpeta '{os.path.basename(ruta)}': {e}", COLOR_ERROR)

                    if not carpetas_validas:
                        pendientes_siguiente.append(factura_limpia)
                        continue

                    carpeta_encontrada = max(carpetas_validas, key=os.path.getmtime)
                    if len(carpetas_validas) > 1:
                        self._log(f"-> AVISO: Se encontraron {len(carpetas_validas)} carpetas válidas para '{numero_factura}'. Se usará la más reciente: {os.path.basename(carpeta_encontrada)}", COLOR_WARNING)

                    self._log(f"-> Soportes encontrados en: <b>{carpeta_encontrada}</b>", COLOR_SUCCESS)
                    ruta_destino_subcarpeta = self._obtener_directorio_destino(factura_limpia, numero_factura)

                    if self.solo_factura:
                        rutas_candidatas = [
                            os.path.join(carpeta_encontrada, nombre_archivo)
                            for nombre_archivo in os.listdir(carpeta_encontrada)
                            if os.path.isfile(os.path.join(carpeta_encontrada, nombre_archivo))
                            and nombre_archivo.lower().endswith('.pdf')
                        ]
                        archivos_encontrados = self._seleccionar_archivos_para_copia(factura_limpia, rutas_candidatas)
                        if not archivos_encontrados:
                            self._log("-> Modo solo factura: la carpeta encontrada no contiene una factura principal identificable.", COLOR_WARNING)
                            pendientes_siguiente.append(factura_limpia)
                            continue
                        for archivo_encontrado in archivos_encontrados:
                            self._log(f"-> Copiando factura principal: <b>{os.path.basename(archivo_encontrado)}</b>", COLOR_SUCCESS)
                            self._copiar_soporte_desde_archivo(archivo_encontrado, ruta_destino_subcarpeta, factura_limpia)
                        self._registrar_exito(f"{factura_limpia} ({len(archivos_encontrados)} factura principal por carpeta)")
                    else:
                        self._copiar_soportes_desde_carpeta(carpeta_encontrada, ruta_destino_subcarpeta, factura_limpia)
                        self._registrar_exito(f"{factura_limpia} (por carpeta)")

                pendientes = pendientes_siguiente

            for factura_limpia in pendientes:
                self._log("-> No se encontró coincidencia en los segmentos evaluados. Pasando a Fase 3.", COLOR_WARNING)
                facturas_no_encontradas.append(factura_limpia)

        return facturas_no_encontradas

    def _ejecutar_estrategia_renombrados(
        self,
        facturas_a_buscar: list[str],
        etiqueta_ambito: str = 'LOCAL',
        porcentaje_inicio: float = 0,
        porcentaje_fin: float = 20,
        rutas_preferidas: dict | None = None,
        alcances_preferidos: dict | None = None,
    ):
        self._log(
            f"<br><b>--- FASE 1 {etiqueta_ambito}: Iniciando búsqueda por nombres renombrados (Resolución 2284) ---</b>",
            COLOR_INFO,
        )
        facturas_no_encontradas = []
        total_facturas = len(facturas_a_buscar)
        procesadas = 0
        facturas_reportadas = set()

        for (base_busqueda, alcance_busqueda), facturas in self._agrupar_facturas_por_ruta(facturas_a_buscar, rutas_preferidas, alcances_preferidos).items():
            segmentos = self._obtener_segmentos_busqueda(base_busqueda, alcance_busqueda, etiqueta_ambito)
            pendientes = list(facturas)

            if etiqueta_ambito == 'FASE 6' and len(segmentos) > 1:
                self._log(
                    f"-> Fase 6 evaluará <b>{len(segmentos)}</b> segmentos ordenados del más reciente al más antiguo.",
                    COLOR_INFO,
                )

            for ruta_segmento, alcance_segmento in segmentos:
                if not pendientes or self.esta_cancelado:
                    break

                es_especifica = alcance_segmento == 'cuenta'
                tipo_busqueda = "ESPECÍFICA (2 niveles)" if es_especifica else "GENERAL (recursiva)"
                self._log(f"Creando índice de archivos en: <b>{ruta_segmento}</b> [Búsqueda {tipo_busqueda}]", COLOR_INFO)
                indice_archivos = self._obtener_indice_archivos(ruta_segmento, alcance_segmento)
                self._log(f"Se indexaron {len(indice_archivos)} nombres de archivos para fase 2.", COLOR_SUCCESS)
                pendientes_siguiente = []

                for factura_input in pendientes:
                    factura_limpia = factura_input.strip()
                    if factura_limpia not in facturas_reportadas:
                        procesadas += 1
                        facturas_reportadas.add(factura_limpia)
                    if self.esta_cancelado:
                        continue
                    porcentaje = porcentaje_inicio + (procesadas / total_facturas) * (porcentaje_fin - porcentaje_inicio)
                    self.progreso_actualizado.emit(f"Fase 1 {etiqueta_ambito}: {factura_limpia}", porcentaje)
                    self._log(f"<br><b>Procesando (Renombrados - {etiqueta_ambito}): {factura_limpia}</b>", COLOR_INFO)

                    normalizada = self._normalizar_factura(factura_limpia)
                    numero_factura_local = normalizada[1] if normalizada else factura_limpia
                    candidatos = [f"{prefijo}_{numero_factura_local}".lower() for prefijo in PREFIJOS_RENOMBRADOS]
                    rutas_encontradas = []
                    for clave, rutas_valor in indice_archivos.items():
                        for candidato in candidatos:
                            if clave.startswith(candidato):
                                rutas_encontradas.extend(rutas_valor)
                                break

                    if not rutas_encontradas:
                        pendientes_siguiente.append(factura_limpia)
                        continue

                    pdfs, complementarios = self._ordenar_soportes_priorizando_pdf(rutas_encontradas)
                    if not pdfs:
                        pendientes_siguiente.append(factura_limpia)
                        continue

                    archivos_encontrados = pdfs + complementarios
                    archivos_encontrados = self._seleccionar_archivos_para_copia(factura_limpia, archivos_encontrados)
                    if not archivos_encontrados:
                        self._log("-> Modo solo factura: no se identificó una factura principal entre los archivos renombrados.", COLOR_WARNING)
                        pendientes_siguiente.append(factura_limpia)
                        continue
                    ruta_destino_especifica = self._obtener_directorio_destino(factura_limpia, numero_factura_local)
                    self._log(
                        f"-> Se encontraron <b>{len(archivos_encontrados)}</b> soportes renombrados para {factura_limpia} "
                        f"(PDF: {len(pdfs)}, complementarios: {len(complementarios)}).",
                        COLOR_SUCCESS,
                    )
                    for archivo_encontrado in archivos_encontrados:
                        self._log(f"-> Copiando soporte renombrado: <b>{archivo_encontrado}</b>", COLOR_SUCCESS)
                        self._copiar_soporte_desde_archivo(archivo_encontrado, ruta_destino_especifica, factura_limpia)
                    self._registrar_exito(f"{factura_limpia} ({len(archivos_encontrados)} soportes por renombrado 2284)")

                pendientes = pendientes_siguiente

            for factura_limpia in pendientes:
                self._log("-> No se encontró soporte renombrado. Pasando a Fase 3.", COLOR_WARNING)
                facturas_no_encontradas.append(factura_limpia)

        return facturas_no_encontradas

    def _ejecutar_estrategia_numeros_origen(
        self,
        facturas_a_buscar: list[str],
        etiqueta_ambito: str = 'LOCAL',
        porcentaje_inicio: float = 50,
        porcentaje_fin: float = 62,
        rutas_preferidas: dict | None = None,
    ):
        """
        FASE 3: Búsqueda por Números / ORIGEN.
        Si dentro de la carpeta de la cuenta existe una carpeta 'ORIGEN',
        busca dentro de ella una subcarpeta cuyo nombre sea el número de la factura
        y copia todos los PDFs que encuentre ahí.
        """
        self._log(f"<br><b>--- FASE 3 {etiqueta_ambito}: Iniciando Búsqueda por Números en carpeta ORIGEN ---</b>", COLOR_INFO)
        facturas_no_encontradas = []
        total_facturas = len(facturas_a_buscar)
        procesadas = 0

        for factura_input in facturas_a_buscar:
            factura_limpia = factura_input.strip()
            procesadas += 1
            if self.esta_cancelado:
                self.fallos_lista.append(f"{factura_limpia} (cancelado)")
                continue

            porcentaje = porcentaje_inicio + (procesadas / total_facturas) * (porcentaje_fin - porcentaje_inicio)
            self.progreso_actualizado.emit(f"Fase 3 {etiqueta_ambito}: {factura_limpia}", porcentaje)
            self._log(f"<br><b>Procesando (ORIGEN - {etiqueta_ambito}): {factura_limpia}</b>", COLOR_INFO)

            normalizada = self._normalizar_factura(factura_limpia)
            if not normalizada:
                self._log("-> Formato no válido. Pasando a Fase 4.", COLOR_WARNING)
                facturas_no_encontradas.append(factura_limpia)
                continue

            _, numero_factura = normalizada
            base_busqueda = (rutas_preferidas or self.rutas_preferidas).get(factura_limpia, self.dir_busqueda)

            # Buscar la carpeta ORIGEN dentro de la cuenta
            ruta_origen = os.path.join(base_busqueda, "ORIGEN")
            if not os.path.isdir(ruta_origen):
                self._log(f"-> No existe carpeta 'ORIGEN' en {base_busqueda}. Pasando a Fase 4.", COLOR_WARNING)
                facturas_no_encontradas.append(factura_limpia)
                continue

            # Buscar subcarpeta con el número de la factura dentro de ORIGEN
            ruta_subcarpeta_factura = os.path.join(ruta_origen, numero_factura)
            if not os.path.isdir(ruta_subcarpeta_factura):
                self._log(f"-> No existe subcarpeta '{numero_factura}' dentro de ORIGEN. Pasando a Fase 4.", COLOR_WARNING)
                facturas_no_encontradas.append(factura_limpia)
                continue

            # Listar y copiar PDFs de la subcarpeta
            pdfs_encontrados = [
                os.path.join(ruta_subcarpeta_factura, f)
                for f in os.listdir(ruta_subcarpeta_factura)
                if f.lower().endswith('.pdf') and os.path.isfile(os.path.join(ruta_subcarpeta_factura, f))
            ]

            if not pdfs_encontrados:
                self._log(f"-> La carpeta ORIGEN/{numero_factura} existe pero no tiene PDFs. Pasando a Fase 4.", COLOR_WARNING)
                facturas_no_encontradas.append(factura_limpia)
                continue

            pdfs_encontrados = self._seleccionar_archivos_para_copia(factura_limpia, pdfs_encontrados)
            if not pdfs_encontrados:
                self._log(f"-> Modo solo factura: ORIGEN/{numero_factura} no contiene una factura principal identificable. Pasando a Fase 4.", COLOR_WARNING)
                facturas_no_encontradas.append(factura_limpia)
                continue

            self._log(
                f"-> Se encontraron <b>{len(pdfs_encontrados)}</b> PDFs en ORIGEN/{numero_factura}.",
                COLOR_SUCCESS,
            )
            ruta_destino_factura = self._obtener_directorio_destino(factura_limpia, numero_factura)
            for pdf_path in pdfs_encontrados:
                self._log(f"-> Copiando: <b>{os.path.basename(pdf_path)}</b>", COLOR_SUCCESS)
                self._copiar_soporte_desde_archivo(pdf_path, ruta_destino_factura, factura_limpia)
            self._registrar_exito(f"{factura_limpia} ({len(pdfs_encontrados)} soportes en ORIGEN)")

        return facturas_no_encontradas

    def _ejecutar_nueva_estrategia_sop1(
        self,
        facturas_a_buscar: list[str],
        etiqueta_ambito: str = 'LOCAL',
        porcentaje_inicio: float = 87,
        porcentaje_fin: float = 100,
        registrar_fallos_finales: bool = True,
        rutas_preferidas: dict | None = None,
        alcances_preferidos: dict | None = None,
    ):
        self._log(
            f"<br><b>--- FASE 5 {etiqueta_ambito}: Iniciando Estrategia SOP1 (Búsqueda por Patrón _SOP_1) ---</b>",
            COLOR_INFO,
        )
        facturas_no_encontradas = []
        total_facturas = len(facturas_a_buscar)
        procesadas = 0
        facturas_reportadas = set()

        for (base_busqueda, alcance_busqueda), facturas in self._agrupar_facturas_por_ruta(facturas_a_buscar, rutas_preferidas, alcances_preferidos).items():
            segmentos = self._obtener_segmentos_busqueda(base_busqueda, alcance_busqueda, etiqueta_ambito)
            pendientes = list(facturas)

            if etiqueta_ambito == 'FASE 6' and len(segmentos) > 1:
                self._log(
                    f"-> Fase 6 evaluará <b>{len(segmentos)}</b> segmentos ordenados del más reciente al más antiguo.",
                    COLOR_INFO,
                )

            for ruta_segmento, alcance_segmento in segmentos:
                if not pendientes or self.esta_cancelado:
                    break

                es_especifica = alcance_segmento == 'cuenta'
                tipo_busqueda = "ESPECÍFICA (2 niveles)" if es_especifica else "GENERAL (recursiva)"
                self._log(f"Creando índice de archivos en: <b>{ruta_segmento}</b> [Búsqueda {tipo_busqueda}]", COLOR_INFO)
                indice_archivos = self._obtener_indice_archivos(ruta_segmento, alcance_segmento)
                self._log(f"Se indexaron {len(indice_archivos)} nombres de archivos para SOP1.", COLOR_SUCCESS)
                pendientes_siguiente = []

                for factura_input in pendientes:
                    factura_limpia = factura_input.strip()
                    if factura_limpia not in facturas_reportadas:
                        procesadas += 1
                        facturas_reportadas.add(factura_limpia)
                    if self.esta_cancelado:
                        self.fallos_lista.append(f"{factura_limpia} (cancelado)")
                        continue

                    porcentaje = porcentaje_inicio + (procesadas / total_facturas) * (porcentaje_fin - porcentaje_inicio)
                    self.progreso_actualizado.emit(f"Fase 5 {etiqueta_ambito}: {factura_limpia}", porcentaje)
                    self._log(f"<br><b>Procesando (SOP1 - {etiqueta_ambito}): {factura_limpia}</b>", COLOR_INFO)

                    nombre_archivo_buscar = f"{factura_limpia}_sop_1".lower()
                    rutas_encontradas = indice_archivos.get(nombre_archivo_buscar)

                    if not rutas_encontradas:
                        pendientes_siguiente.append(factura_limpia)
                        continue

                    pdfs, complementarios = self._ordenar_soportes_priorizando_pdf(rutas_encontradas)
                    if not pdfs:
                        pendientes_siguiente.append(factura_limpia)
                        continue

                    archivos_encontrados = pdfs + complementarios
                    archivos_encontrados = self._seleccionar_archivos_para_copia(factura_limpia, archivos_encontrados)
                    if not archivos_encontrados:
                        self._log("-> Modo solo factura: el patrón _SOP_1 no corresponde a una factura principal. Continuando.", COLOR_WARNING)
                        pendientes_siguiente.append(factura_limpia)
                        continue
                    self._log(
                        f"-> Soportes encontrados para SOP1: {len(archivos_encontrados)} "
                        f"(PDF: {len(pdfs)}, complementarios: {len(complementarios)}).",
                        COLOR_SUCCESS,
                    )
                    ruta_destino_especifica = self._obtener_directorio_destino(factura_limpia, numero_factura)
                    self._log(f"-> Carpeta destino determinada: {os.path.basename(ruta_destino_especifica)}", COLOR_INFO)

                    for archivo_encontrado in archivos_encontrados:
                        self._log(f"-> Copiando soporte SOP1: <b>{archivo_encontrado}</b>", COLOR_SUCCESS)
                        self._copiar_soporte_desde_archivo(archivo_encontrado, ruta_destino_especifica, factura_limpia)
                    self._registrar_exito(f"{factura_limpia} ({len(archivos_encontrados)} soportes por patrón _SOP_1)")

                pendientes = pendientes_siguiente

            for factura_limpia in pendientes:
                mensaje = f"-> No se encontró archivo con el patrón '{factura_limpia.lower()}_sop_1'."
                if not registrar_fallos_finales:
                    mensaje += " Se mantiene pendiente dentro del flujo actual."
                self._log(mensaje, COLOR_WARNING)
                facturas_no_encontradas.append(factura_limpia)
                if registrar_fallos_finales:
                    self._registrar_fallo(f"{factura_limpia} (sin soporte)")

        return facturas_no_encontradas

    def _ejecutar_estrategia_b(
        self,
        facturas_a_buscar: list[str],
        etiqueta_ambito: str = 'LOCAL',
        porcentaje_inicio: float = 62,
        porcentaje_fin: float = 74,
        rutas_preferidas: dict | None = None,
        alcances_preferidos: dict | None = None,
    ):
        self._log(f"<br><b>--- FASE 4 {etiqueta_ambito}: Iniciando Estrategia B (Búsqueda por nombre exacto) ---</b>", COLOR_INFO)
        facturas_no_encontradas = []
        total_facturas_b = len(facturas_a_buscar)
        procesadas = 0
        facturas_reportadas = set()

        for (base_busqueda, alcance_busqueda), facturas in self._agrupar_facturas_por_ruta(facturas_a_buscar, rutas_preferidas, alcances_preferidos).items():
            segmentos = self._obtener_segmentos_busqueda(base_busqueda, alcance_busqueda, etiqueta_ambito)
            pendientes = list(facturas)

            if etiqueta_ambito == 'FASE 6' and len(segmentos) > 1:
                self._log(
                    f"-> Fase 6 evaluará <b>{len(segmentos)}</b> segmentos ordenados del más reciente al más antiguo.",
                    COLOR_INFO,
                )

            for ruta_segmento, alcance_segmento in segmentos:
                if not pendientes or self.esta_cancelado:
                    break

                es_especifica = alcance_segmento == 'cuenta'
                tipo_busqueda = "ESPECÍFICA (2 niveles)" if es_especifica else "GENERAL (recursiva)"
                self._log(f"Creando índice de archivos en: <b>{ruta_segmento}</b> [Búsqueda {tipo_busqueda}]", COLOR_INFO)
                indice_archivos = self._obtener_indice_archivos(ruta_segmento, alcance_segmento)
                self._log(f"Se indexaron {len(indice_archivos)} nombres de archivos únicos.", COLOR_SUCCESS)
                pendientes_siguiente = []

                for factura_input in pendientes:
                    factura_limpia = factura_input.strip()
                    if factura_limpia not in facturas_reportadas:
                        procesadas += 1
                        facturas_reportadas.add(factura_limpia)
                    if self.esta_cancelado:
                        self.fallos_lista.append(f"{factura_limpia} (cancelado)")
                        continue

                    porcentaje = porcentaje_inicio + (procesadas / total_facturas_b) * (porcentaje_fin - porcentaje_inicio)
                    self.progreso_actualizado.emit(f"Fase 4 {etiqueta_ambito}: {factura_limpia}", porcentaje)
                    self._log(f"<br><b>Procesando (B - {etiqueta_ambito}): {factura_limpia}</b>", COLOR_INFO)

                    rutas_encontradas = indice_archivos.get(factura_limpia.lower())
                    if not rutas_encontradas:
                        pendientes_siguiente.append(factura_limpia)
                        continue

                    pdfs, complementarios = self._ordenar_soportes_priorizando_pdf(rutas_encontradas)
                    if not pdfs:
                        pendientes_siguiente.append(factura_limpia)
                        continue

                    archivos_encontrados = pdfs + complementarios
                    archivos_encontrados = self._seleccionar_archivos_para_copia(factura_limpia, archivos_encontrados)
                    if not archivos_encontrados:
                        self._log("-> Modo solo factura: no se identificó una factura principal por nombre exacto.", COLOR_WARNING)
                        pendientes_siguiente.append(factura_limpia)
                        continue
                    self._log(
                        f"-> Soportes encontrados por nombre exacto: {len(archivos_encontrados)} "
                        f"(PDF: {len(pdfs)}, complementarios: {len(complementarios)}).",
                        COLOR_SUCCESS,
                    )
                    normalizada = self._normalizar_factura(factura_limpia)
                    numero_factura = normalizada[1] if normalizada else None
                    ruta_destino_especifica = self._obtener_directorio_destino(factura_limpia, numero_factura)
                    self._log(f"-> Carpeta destino determinada: {os.path.basename(ruta_destino_especifica)}", COLOR_INFO)

                    for archivo_encontrado in archivos_encontrados:
                        self._log(f"-> Copiando soporte por nombre exacto: <b>{archivo_encontrado}</b>", COLOR_SUCCESS)
                        self._copiar_soporte_desde_archivo(archivo_encontrado, ruta_destino_especifica, factura_limpia)
                    self._registrar_exito(f"{factura_limpia} ({len(archivos_encontrados)} soportes por archivo exacto)")

                pendientes = pendientes_siguiente

            for factura_limpia in pendientes:
                self._log("-> No se encontró archivo con ese nombre. Pasando a Fase 5.", COLOR_WARNING)
                facturas_no_encontradas.append(factura_limpia)

        return facturas_no_encontradas

    def _es_carpeta_valida(self, ruta_carpeta: str) -> bool:
        """Verifica si una carpeta contiene solo archivos con extensiones permitidas."""
        try:
            # Lista solo los archivos, ignorando subdirectorios
            archivos = [f for f in os.listdir(ruta_carpeta) if os.path.isfile(os.path.join(ruta_carpeta, f))]
            
            # Si no hay archivos, no es válida para nuestro propósito
            if not archivos:
                self._log(f"-> Carpeta '{os.path.basename(ruta_carpeta)}' descartada por estar vacía.", "gray")
                return False

            # Verifica que todos los archivos tengan una extensión permitida
            for nombre_archivo in archivos:
                if not nombre_archivo.lower().endswith(EXTENSIONES_SOPORTE):
                    self._log(f"-> Carpeta '{os.path.basename(ruta_carpeta)}' descartada por contenido no válido: {nombre_archivo}", "gray")
                    return False
            
            return True # Todos los archivos son válidos
        except Exception as e:
            self._log(f"-> Error al validar carpeta '{os.path.basename(ruta_carpeta)}': {e}", COLOR_ERROR)
            return False

    def _encontrar_subcarpeta_destino(self, factura_buscada: str) -> str:
        match = re.match(r'([a-zA-Z]+)(\d+)', factura_buscada)
        if not match:
            self._log(f"-> AVISO: No se pudo extraer el número de la factura '{factura_buscada}' para buscar subcarpeta. Se usará el destino raíz.", COLOR_WARNING)
            return self.dir_destino

        numero_factura = match.groups()[1]

        try:
            for nombre_subcarpeta in os.listdir(self.dir_destino):
                ruta_subcarpeta = os.path.join(self.dir_destino, nombre_subcarpeta)
                if os.path.isdir(ruta_subcarpeta) and nombre_subcarpeta == numero_factura:
                    return ruta_subcarpeta
        except FileNotFoundError:
            return self.dir_destino

        self._log(f"-> AVISO: No se encontró subcarpeta con el número '{numero_factura}'. Se usará el directorio destino raíz.", COLOR_WARNING)
        return self.dir_destino

    def _copiar_soportes_desde_carpeta(self, ruta_origen: str, ruta_destino: str, factura_info: str):
        archivos_copiados = 0
        try:
            if self.esta_cancelado:
                return
            if not os.path.isdir(ruta_destino):
                os.makedirs(ruta_destino)
                self._log(f"-> Carpeta de destino creada: {os.path.basename(ruta_destino)}", COLOR_INFO)

            for nombre_item in os.listdir(ruta_origen):
                if self.esta_cancelado:
                    return
                ruta_completa_origen = os.path.join(ruta_origen, nombre_item)
                if os.path.isfile(ruta_completa_origen):
                    # --- SOLO PDF ---
                    if not nombre_item.lower().endswith('.pdf'):
                        self._log(f"-> Omitido (no es PDF): {nombre_item}", "gray")
                        continue
                    # ---------------

                    ruta_completa_destino = os.path.join(ruta_destino, nombre_item)
                    if not os.path.exists(ruta_completa_destino):
                        shutil.copy2(ruta_completa_origen, ruta_completa_destino)
                        archivos_copiados += 1
                    else:
                        self._log(f"-> Omitido (ya existe): {nombre_item}", "gray")
            
            if archivos_copiados > 0:
                self._log(f"-> Se copiaron {archivos_copiados} archivos de la carpeta.", COLOR_SUCCESS)
            else:
                self._log("-> No se copiaron nuevos archivos de la carpeta (o ya existían).", COLOR_DEFAULT)
        except Exception as e:
            self._log(f"-> ❌ ERROR al copiar de carpeta para '{factura_info}': {e}", COLOR_ERROR)

    def _copiar_soporte_desde_archivo(self, ruta_origen: str, dir_destino: str, factura_buscada: str):
        try:
            if self.esta_cancelado:
                return
            if not os.path.isdir(dir_destino):
                os.makedirs(dir_destino, exist_ok=True)
            nombre_original = os.path.basename(ruta_origen)
            nombre_base, extension = os.path.splitext(nombre_original)
            prioridad_factura = self._prioridad_factura_principal(ruta_origen, factura_buscada)

            # Lógica de renombrado
            if self.solo_factura and prioridad_factura is not None:
                nuevo_nombre = f"{factura_buscada}{extension}"
                self._log(f"-> Archivo principal identificado para la factura. Renombrando a: {nuevo_nombre}", COLOR_INFO)
            elif nombre_base.lower() == factura_buscada.lower():
                nuevo_nombre = f"{nombre_base}-soporte{extension}"
                self._log(f"-> El nombre del archivo coincide con la factura. Renombrando a: {nuevo_nombre}", COLOR_INFO)
            else:
                nuevo_nombre = nombre_original

            ruta_destino_final = os.path.join(dir_destino, nuevo_nombre)

            if not os.path.exists(ruta_destino_final):
                shutil.copy2(ruta_origen, ruta_destino_final)
                self._log(f"-> Se copió el archivo: {nuevo_nombre}", COLOR_SUCCESS)
            else:
                self._log(f"-> Omitido (ya existe): {nuevo_nombre}", "gray")

        except Exception as e:
            self._log(f"-> ❌ ERROR al copiar archivo para '{factura_buscada}': {e}", COLOR_ERROR)


    def cancelar(self):
        self._log("<b>Cancelación solicitada. Finalizando proceso NU...</b>", COLOR_WARNING)
        self.esta_cancelado = True

    def _ejecutar_buscar_cuenta_cobro(self):
        self._log("<b>Iniciando búsqueda de cuentas de cobro de facturación...</b>", COLOR_INFO)
        self._log(f"Directorio de Búsqueda: {self.dir_busqueda}")
        self._log(f"Directorio de Destino: {self.dir_destino}")

        # Parse input lines
        unique_cuentas = {}
        pending_date = None  # Stores (year, month, day)
        self._log(f"Cantidad de líneas leídas: {len(self.facturas_con_serie)}")
        for line in self.facturas_con_serie:
            line_str = line.strip()
            if not line_str:
                continue
            self._log(f"Analizando línea: {repr(line_str)}")
            # Ignore headers
            if any(header in line_str.lower() for header in ("fecha", "radicación", "cuenta", "cobro", "factura")):
                self._log(f"-> Línea omitida por cabecera", COLOR_WARNING)
                continue
            
            match_date = re.search(r'(\d{1,2})[/-](\d{1,2})[/-](\d{4})', line_str)
            if match_date:
                day = int(match_date.group(1))
                month = int(match_date.group(2))
                year = int(match_date.group(3))
                
                date_str = match_date.group(0)
                line_without_date = line_str.replace(date_str, "")
                numbers = re.findall(r'\b\d+\b', line_without_date)
                if numbers:
                    # Date and account number on the same line
                    cuenta = numbers[0]
                    if cuenta not in unique_cuentas:
                        unique_cuentas[cuenta] = (year, month, day)
                        self._log(f"Registrada cuenta: <b>{cuenta}</b> (Fecha: {day:02d}/{month:02d}/{year})", COLOR_DEFAULT)
                    else:
                        self._log(f"-> Cuenta {cuenta} duplicada, omitida.")
                    pending_date = None
                else:
                    # Only date on this line, save it for the next line
                    pending_date = (year, month, day)
                    self._log(f"-> Fecha detectada: {day:02d}/{month:02d}/{year}. Esperando número de cuenta en la siguiente línea...")
            else:
                # No date on this line. Check if there's an account number and a pending date
                numbers = re.findall(r'\b\d+\b', line_str)
                if numbers and pending_date:
                    cuenta = numbers[0]
                    year, month, day = pending_date
                    if cuenta not in unique_cuentas:
                        unique_cuentas[cuenta] = (year, month, day)
                        self._log(f"Registrada cuenta (líneas continuas): <b>{cuenta}</b> (Fecha: {day:02d}/{month:02d}/{year})", COLOR_DEFAULT)
                    else:
                        self._log(f"-> Cuenta {cuenta} duplicada, omitida.")
                    pending_date = None
                else:
                    self._log(f"-> Línea omitida: no coincide con fecha y no hay fecha pendiente anterior para asociar este número.", COLOR_WARNING)
        
        total_cuentas = len(unique_cuentas)
        if total_cuentas == 0:
            self._log("No se encontraron cuentas de cobro válidas para procesar.", COLOR_WARNING)
            self.progreso_actualizado.emit("Finalizado", 100)
            self.proceso_finalizado.emit()
            return

        self._total_facturas = total_cuentas
        self._facturas_completadas = 0
        
        for i, (cuenta, (year, month, day)) in enumerate(unique_cuentas.items()):
            if self.esta_cancelado:
                break
            
            porcentaje = (i / total_cuentas) * 100
            self.progreso_actualizado.emit(f"Buscando cuenta: {cuenta}", porcentaje)
            self._log(f"<br><b>Procesando cuenta de cobro: {cuenta}</b> (Año: {year}, Mes: {month})", COLOR_INFO)
            
            found_files = []
            
            # 1. Look in the expected folder: W:\CUENTAS DE COBRO\<year>\<month_subfolder>
            year_dir = os.path.join(self.dir_busqueda, str(year))
            month_dir = None
            if os.path.isdir(year_dir):
                month_name = MESES.get(month)
                try:
                    for item in os.listdir(year_dir):
                        item_path = os.path.join(year_dir, item)
                        if os.path.isdir(item_path):
                            if month_name and item.upper().startswith(month_name):
                                month_dir = item_path
                                break
                            elif item.startswith(f"{month:02d}"):
                                month_dir = item_path
                                break
                except Exception as e:
                    self._log(f"Error listando año {year}: {e}", COLOR_ERROR)
            
            prefix_to_match = f"290-1-{cuenta}".lower()
            
            if month_dir and os.path.isdir(month_dir):
                self._log(f"Buscando en carpeta esperada: {month_dir}")
                try:
                    for file_name in os.listdir(month_dir):
                        file_path = os.path.join(month_dir, file_name)
                        if os.path.isfile(file_path):
                            if file_name.lower().startswith(prefix_to_match) and file_name.lower().endswith(".pdf"):
                                found_files.append(file_path)
                except Exception as e:
                    self._log(f"Error listando mes {month}: {e}", COLOR_ERROR)
            
            # 2. Fallback: search recursively in the year directory
            if not found_files and os.path.isdir(year_dir):
                self._log(f"No se encontró en carpeta de mes. Buscando en todo el año {year}...", COLOR_WARNING)
                try:
                    for root, dirs, files in os.walk(year_dir):
                        if self.esta_cancelado:
                            break
                        for file_name in files:
                            if file_name.lower().startswith(prefix_to_match) and file_name.lower().endswith(".pdf"):
                                found_files.append(os.path.join(root, file_name))
                except Exception as e:
                    self._log(f"Error buscando en año {year}: {e}", COLOR_ERROR)
            
            # 3. Fallback: search recursively in the entire search root directory
            if not found_files and os.path.isdir(self.dir_busqueda):
                self._log(f"No se encontró en el año {year}. Buscando en toda la raíz {self.dir_busqueda}...", COLOR_WARNING)
                try:
                    for root, dirs, files in os.walk(self.dir_busqueda):
                        if self.esta_cancelado:
                            break
                        for file_name in files:
                            if file_name.lower().startswith(prefix_to_match) and file_name.lower().endswith(".pdf"):
                                found_files.append(os.path.join(root, file_name))
                except Exception as e:
                    self._log(f"Error buscando en raíz {self.dir_busqueda}: {e}", COLOR_ERROR)
                            
            if found_files:
                found_files = sorted(list(set(found_files)))
                self._log(f"Encontrados <b>{len(found_files)}</b> archivos para la cuenta {cuenta}:", COLOR_SUCCESS)
                for f in found_files:
                    self._log(f"- {os.path.basename(f)}", COLOR_SUCCESS)
                
                try:
                    if not os.path.isdir(self.dir_destino):
                        os.makedirs(self.dir_destino, exist_ok=True)
                    
                    copied_any = False
                    for file_path in found_files:
                        dest_path = os.path.join(self.dir_destino, os.path.basename(file_path))
                        if not os.path.exists(dest_path):
                            shutil.copy2(file_path, dest_path)
                            self._log(f"Copiado con éxito: {os.path.basename(file_path)}", COLOR_SUCCESS)
                            copied_any = True
                        else:
                            self._log(f"Omitido, ya existe en destino: {os.path.basename(file_path)}", COLOR_DEFAULT)
                            copied_any = True
                            
                    if copied_any:
                        self._registrar_exito(f"Cuenta {cuenta} (copiada)")
                    else:
                        self._registrar_fallo(f"Cuenta {cuenta} (error al copiar)")
                except Exception as e:
                    self._log(f"Error al copiar archivos para la cuenta {cuenta}: {e}", COLOR_ERROR)
                    self._registrar_fallo(f"Cuenta {cuenta} (error copia)")
            else:
                self._log(f"❌ No se encontró ningún documento para la cuenta {cuenta} (patrón '290-1-{cuenta}')", COLOR_ERROR)
                self._registrar_fallo(f"Cuenta {cuenta} (no encontrada)")
                
            self._facturas_completadas += 1
            
        self.progreso_actualizado.emit("Operación completada.", 100)
        self._log(f"<br><b>--- RESUMEN ---</b>", COLOR_INFO)
        self._log(f"<b>Cuentas de cobro encontradas ({len(self.exitos_lista)}):</b>", COLOR_SUCCESS)
        for exito in self.exitos_lista:
            self._log(f"- {exito}", COLOR_SUCCESS)
        
        self._log(f"<br><b>Cuentas de cobro no encontradas ({len(self.fallos_lista)}):</b>", COLOR_WARNING)
        for fallo in self.fallos_lista:
            self._log(f"- {fallo}", COLOR_WARNING)

        self._log("<br><b>✅ Operación completada.</b>", COLOR_SUCCESS)
        self.proceso_finalizado.emit()

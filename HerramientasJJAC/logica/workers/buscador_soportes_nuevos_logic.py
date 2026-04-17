# logica/workers/buscador_soportes_nuevos_logic.py
import os
import shutil
import re
from datetime import date, datetime

from PySide6.QtCore import QObject, Signal

from api_gema import query_api_gema

# --- COLORES OPTIMIZADOS PARA DARK MODE ---
COLOR_INFO = "#5DADE2"      # Azul claro
COLOR_SUCCESS = "#2ECC71"   # Verde brillante
COLOR_WARNING = "#F39C12"   # Naranja
COLOR_ERROR = "#E74C3C"      # Rojo claro
COLOR_DEFAULT = "#ECF0F1"   # Blanco roto

EXTENSIONES_SOPORTE = ('.pdf', '.png', '.jpg', '.jpeg', '.gif', '.bmp', '.tiff', '.json')
PREFIJOS_RENOMBRADOS = ('EPI', 'FEV', 'PDX', 'FURIPS')
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

    def __init__(self, facturas_con_serie: list[str], dir_busqueda: str, dir_destino: str):
        super().__init__()
        self.facturas_con_serie = facturas_con_serie
        self.dir_busqueda = dir_busqueda
        self.dir_destino = dir_destino
        self.esta_cancelado = False
        self.exitos_lista = []
        self.fallos_lista = []
        self.rutas_preferidas = {}

    def _log(self, mensaje: str, color: str = COLOR_DEFAULT):
        self.log_generado.emit(f"<p style='color:{color}; margin-top:0; margin-bottom:0;'>{mensaje}</p>")

    def ejecutar(self):
        self._log("<b>Iniciando búsqueda y copia de soportes NUEVOS...</b>", COLOR_INFO)
        self._log(f"Directorio de Búsqueda: {self.dir_busqueda}")
        self._log(f"Directorio de Destino: {self.dir_destino}")

        try:
            self.rutas_preferidas = self._resolver_rutas_preferidas()

            # --- FASE 1: ESTRATEGIA A (Búsqueda por carpetas) ---
            facturas_para_estrategia_renombrados = self._ejecutar_estrategia_a()

            # --- FASE 2: RENOMBRADOS RESOLUCIÓN 2284 ---
            facturas_para_estrategia_b = []
            if not self.esta_cancelado and facturas_para_estrategia_renombrados:
                facturas_para_estrategia_b = self._ejecutar_estrategia_renombrados(facturas_para_estrategia_renombrados)

            # --- FASE 3: ESTRATEGIA B (Búsqueda por nombre exacto) ---
            facturas_para_estrategia_sop1 = []
            if not self.esta_cancelado and facturas_para_estrategia_b:
                facturas_para_estrategia_sop1 = self._ejecutar_estrategia_b(facturas_para_estrategia_b)

            # --- FASE 4: ESTRATEGIA SOP1 (Búsqueda por patrón _SOP_1) ---
            if not self.esta_cancelado and facturas_para_estrategia_sop1:
                self._ejecutar_nueva_estrategia_sop1(facturas_para_estrategia_sop1)

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
            ruta = os.path.join(carpeta_padre, nombre)
            if not os.path.isdir(ruta):
                continue
            nombre_lower = nombre.lower()
            if nombre == radicacion or nombre_lower == f"cuenta {radicacion}".lower() or radicacion in nombre:
                candidatos.append(ruta)
        if not candidatos:
            return None
        return max(candidatos, key=os.path.getmtime)

    def _resolver_carpeta_cuenta(self, radicacion: str, fecha_radicacion: date | None) -> str | None:
        if not fecha_radicacion:
            return None
        carpeta_anio = os.path.join(self.dir_busqueda, str(fecha_radicacion.year))
        carpeta_mes = os.path.join(carpeta_anio, MESES.get(fecha_radicacion.month, ''))

        for base in (carpeta_mes, carpeta_anio):
            encontrada = self._buscar_carpeta_en(base, radicacion)
            if encontrada:
                return encontrada

        if os.path.isdir(carpeta_mes):
            for dirpath, dirnames, _ in os.walk(carpeta_mes):
                for dirname in dirnames:
                    if dirname == radicacion or dirname.lower() == f"cuenta {radicacion}".lower() or radicacion in dirname:
                        return os.path.join(dirpath, dirname)
        return None

    def _resolver_rutas_preferidas(self):
        rutas = {}
        self._log("<br><b>--- PREPARACIÓN: Resolviendo año, mes y cuenta desde GEMA ---</b>", COLOR_INFO)
        for factura in self.facturas_con_serie:
            factura_limpia = factura.strip()
            normalizada = self._normalizar_factura(factura_limpia)
            if not normalizada:
                rutas[factura_limpia] = self.dir_busqueda
                continue

            serie, numero_factura = normalizada
            try:
                info = self._consultar_gema_factura(serie, numero_factura)
            except Exception as e:
                self._log(f"-> {factura_limpia}: fallo consultando GEMA ({e}). Se usará búsqueda general.", COLOR_WARNING)
                rutas[factura_limpia] = self.dir_busqueda
                continue

            if not info:
                self._log(f"-> {factura_limpia}: sin coincidencia en GEMA. Se usará búsqueda general.", COLOR_WARNING)
                rutas[factura_limpia] = self.dir_busqueda
                continue

            carpeta_cuenta = self._resolver_carpeta_cuenta(info['radicacion'], info['fecha'])
            if carpeta_cuenta:
                rutas[factura_limpia] = carpeta_cuenta
                self._log(
                    f"-> {factura_limpia}: GEMA encontró cuenta <b>{info['radicacion']}</b> "
                    f"en <b>{os.path.basename(carpeta_cuenta)}</b> ({info['tabla']}).",
                    COLOR_SUCCESS,
                )
            else:
                rutas[factura_limpia] = self.dir_busqueda
                fecha_txt = info['fecha'].strftime('%d/%m/%Y') if info['fecha'] else 'sin fecha'
                self._log(
                    f"-> {factura_limpia}: GEMA devolvió cuenta {info['radicacion']} / fecha {fecha_txt}, "
                    f"pero no se encontró la carpeta. Se usará búsqueda general.",
                    COLOR_WARNING,
                )
        return rutas

    def _agrupar_facturas_por_ruta(self, facturas: list[str]):
        agrupadas = {}
        for factura in facturas:
            ruta = self.rutas_preferidas.get(factura, self.dir_busqueda)
            agrupadas.setdefault(ruta, []).append(factura)
        return agrupadas

    def _crear_indice_archivos(self, directorio_base: str):
        indice_archivos = {}
        for dirpath, _, filenames in os.walk(directorio_base):
            for filename in filenames:
                if filename.lower().endswith(EXTENSIONES_SOPORTE):
                    nombre_sin_ext, _ = os.path.splitext(filename)
                    indice_archivos.setdefault(nombre_sin_ext.lower(), []).append(os.path.join(dirpath, filename))
        return indice_archivos

    def _ejecutar_estrategia_a(self):
        self._log("<br><b>--- FASE 1: Iniciando Estrategia A (Búsqueda por Carpetas) ---</b>", COLOR_INFO)
        facturas_no_encontradas = []
        total_facturas = len(self.facturas_con_serie)

        procesadas = 0
        for base_busqueda, facturas in self._agrupar_facturas_por_ruta(self.facturas_con_serie).items():
            self._log(f"Indexando carpetas en: <b>{base_busqueda}</b>", COLOR_INFO)
            indice_carpetas = {}
            for dirpath, dirnames, _ in os.walk(base_busqueda):
                for dirname in dirnames:
                    indice_carpetas.setdefault(dirname, []).append(os.path.join(dirpath, dirname))

            self._log(f"Se indexaron {len(indice_carpetas)} nombres de carpetas únicos en esta ruta.", COLOR_SUCCESS)

            for factura_input in facturas:
                factura_limpia = factura_input.strip()
                procesadas += 1
                if self.esta_cancelado:
                    self.fallos_lista.append(f"{factura_limpia} (cancelado)")
                    continue

                porcentaje = ((procesadas) / total_facturas) * 25
                self.progreso_actualizado.emit(f"Fase 1: {factura_limpia}", porcentaje)
                self._log(f"<br><b>Procesando (A): {factura_limpia}</b>", COLOR_INFO)

                normalizada = self._normalizar_factura(factura_limpia)
                if not normalizada:
                    self._log("-> Formato no válido.", COLOR_WARNING)
                    facturas_no_encontradas.append(factura_limpia)
                    continue

                serie, numero_factura = normalizada
                self._log(f"-> Serie: '{serie}', Número: '{numero_factura}'")

                rutas_encontradas = indice_carpetas.get(numero_factura)

                if not rutas_encontradas:
                    self._log(f"-> No se encontró carpeta con el número '{numero_factura}'. Pasando a Fase 2.", COLOR_WARNING)
                    facturas_no_encontradas.append(factura_limpia)
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
                    self._log(f"-> Se encontraron {len(rutas_encontradas)} carpetas para '{numero_factura}', pero ninguna cumplió los criterios. Pasando a Fase 2.", COLOR_WARNING)
                    facturas_no_encontradas.append(factura_limpia)
                    continue

                carpeta_encontrada = max(carpetas_validas, key=os.path.getmtime)
                if len(carpetas_validas) > 1:
                    self._log(f"-> AVISO: Se encontraron {len(carpetas_validas)} carpetas válidas para '{numero_factura}'. Se usará la más reciente: {os.path.basename(carpeta_encontrada)}", COLOR_WARNING)

                self._log(f"-> Soportes encontrados en: <b>{carpeta_encontrada}</b>", COLOR_SUCCESS)
                ruta_destino_subcarpeta = os.path.join(self.dir_destino, numero_factura)
                self._copiar_soportes_desde_carpeta(carpeta_encontrada, ruta_destino_subcarpeta, factura_limpia)
                self.exitos_lista.append(f"{factura_limpia} (por carpeta)")

        return facturas_no_encontradas

    def _ejecutar_estrategia_renombrados(self, facturas_a_buscar: list[str]):
        self._log("<br><b>--- FASE 2: Iniciando búsqueda por nombres renombrados (Resolución 2284) ---</b>", COLOR_INFO)
        facturas_no_encontradas = []
        total_facturas = len(facturas_a_buscar)
        procesadas = 0

        for base_busqueda, facturas in self._agrupar_facturas_por_ruta(facturas_a_buscar).items():
            self._log(f"Creando índice de archivos renombrados en: <b>{base_busqueda}</b>", COLOR_INFO)
            indice_archivos = self._crear_indice_archivos(base_busqueda)
            self._log(f"Se indexaron {len(indice_archivos)} nombres de archivos para fase 2.", COLOR_SUCCESS)

            for factura_input in facturas:
                factura_limpia = factura_input.strip()
                procesadas += 1
                porcentaje = 25 + (procesadas / total_facturas) * 25
                self.progreso_actualizado.emit(f"Fase 2: {factura_limpia}", porcentaje)
                self._log(f"<br><b>Procesando (Renombrados): {factura_limpia}</b>", COLOR_INFO)

                candidatos = [f"{prefijo}_800209891_{factura_limpia}".lower() for prefijo in PREFIJOS_RENOMBRADOS]
                rutas_encontradas = []
                for candidato in candidatos:
                    rutas_encontradas.extend(indice_archivos.get(candidato, []))

                if not rutas_encontradas:
                    self._log("-> No se encontró soporte renombrado. Pasando a Fase 3.", COLOR_WARNING)
                    facturas_no_encontradas.append(factura_limpia)
                    continue

                archivos_encontrados = sorted(set(rutas_encontradas), key=os.path.getmtime, reverse=True)
                ruta_destino_especifica = self._encontrar_subcarpeta_destino(factura_limpia)
                self._log(
                    f"-> Se encontraron <b>{len(archivos_encontrados)}</b> soportes renombrados para {factura_limpia}.",
                    COLOR_SUCCESS,
                )
                for archivo_encontrado in archivos_encontrados:
                    self._log(f"-> Copiando soporte renombrado: <b>{archivo_encontrado}</b>", COLOR_SUCCESS)
                    self._copiar_soporte_desde_archivo(archivo_encontrado, ruta_destino_especifica, factura_limpia)
                self.exitos_lista.append(f"{factura_limpia} ({len(archivos_encontrados)} soportes por renombrado 2284)")

        return facturas_no_encontradas

    def _ejecutar_nueva_estrategia_sop1(self, facturas_a_buscar: list[str]):
        self._log("<br><b>--- FASE 4: Iniciando Estrategia SOP1 (Búsqueda por Patrón _SOP_1) ---</b>", COLOR_INFO)
        facturas_no_encontradas = []
        total_facturas = len(facturas_a_buscar)
        procesadas = 0

        for base_busqueda, facturas in self._agrupar_facturas_por_ruta(facturas_a_buscar).items():
            self._log("Creando índice de archivos para SOP1... Esto puede tardar un momento.", COLOR_INFO)
            indice_archivos = self._crear_indice_archivos(base_busqueda)
            self._log(f"Se indexaron {len(indice_archivos)} nombres de archivos para SOP1.", COLOR_SUCCESS)

            for factura_input in facturas:
                factura_limpia = factura_input.strip()
                procesadas += 1
                if self.esta_cancelado:
                    self.fallos_lista.append(f"{factura_limpia} (cancelado)")
                    continue

                porcentaje = 75 + (procesadas / total_facturas) * 25
                self.progreso_actualizado.emit(f"Fase 4: {factura_limpia}", porcentaje)
                self._log(f"<br><b>Procesando (SOP1): {factura_limpia}</b>", COLOR_INFO)

                nombre_archivo_buscar = f"{factura_limpia}_sop_1".lower()
                rutas_encontradas = indice_archivos.get(nombre_archivo_buscar)

                if not rutas_encontradas:
                    self._log(f"-> No se encontró archivo con el patrón '{nombre_archivo_buscar}'.", COLOR_WARNING)
                    facturas_no_encontradas.append(factura_limpia)
                    self.fallos_lista.append(f"{factura_limpia} (sin soporte)")
                    continue

                archivo_encontrado = max(rutas_encontradas, key=os.path.getmtime)
                if len(rutas_encontradas) > 1:
                    self._log(f"-> AVISO: Se encontraron {len(rutas_encontradas)} archivos para '{nombre_archivo_buscar}'. Se usará el más reciente: {archivo_encontrado}", COLOR_WARNING)

                self._log(f"-> Soporte encontrado en: <b>{archivo_encontrado}</b>", COLOR_SUCCESS)
                ruta_destino_especifica = self._encontrar_subcarpeta_destino(factura_limpia)
                self._log(f"-> Carpeta destino determinada: {os.path.basename(ruta_destino_especifica)}", COLOR_INFO)

                self._copiar_soporte_desde_archivo(archivo_encontrado, ruta_destino_especifica, factura_limpia)
                self.exitos_lista.append(f"{factura_limpia} (por patrón _SOP_1)")

        return facturas_no_encontradas

    def _ejecutar_estrategia_b(self, facturas_a_buscar: list[str]):
        self._log("<br><b>--- FASE 3: Iniciando Estrategia B (Búsqueda por nombre exacto) ---</b>", COLOR_INFO)
        facturas_no_encontradas = []
        total_facturas_b = len(facturas_a_buscar)
        procesadas = 0
        for base_busqueda, facturas in self._agrupar_facturas_por_ruta(facturas_a_buscar).items():
            self._log("Creando índice de archivos... Esto puede tardar un momento.", COLOR_INFO)
            indice_archivos = self._crear_indice_archivos(base_busqueda)
            self._log(f"Se indexaron {len(indice_archivos)} nombres de archivos únicos.", COLOR_SUCCESS)

            for factura_input in facturas:
                factura_limpia = factura_input.strip()
                procesadas += 1
                if self.esta_cancelado:
                    self.fallos_lista.append(f"{factura_limpia} (cancelado)")
                    continue

                porcentaje = 50 + (procesadas / total_facturas_b) * 25
                self.progreso_actualizado.emit(f"Fase 3: {factura_limpia}", porcentaje)
                self._log(f"<br><b>Procesando (B): {factura_limpia}</b>", COLOR_INFO)

                rutas_encontradas = indice_archivos.get(factura_limpia.lower())

                if not rutas_encontradas:
                    self._log("-> No se encontró archivo con ese nombre. Pasando a Fase 4.", COLOR_WARNING)
                    facturas_no_encontradas.append(factura_limpia)
                    continue

                archivo_encontrado = max(rutas_encontradas, key=os.path.getmtime)
                if len(rutas_encontradas) > 1:
                    self._log(f"-> AVISO: Se encontraron {len(rutas_encontradas)} archivos para '{factura_limpia}'. Se usará el más reciente: {archivo_encontrado}", COLOR_WARNING)

                self._log(f"-> Soporte encontrado en: <b>{archivo_encontrado}</b>", COLOR_SUCCESS)
                ruta_destino_especifica = self._encontrar_subcarpeta_destino(factura_limpia)
                self._log(f"-> Carpeta destino determinada: {os.path.basename(ruta_destino_especifica)}", COLOR_INFO)

                self._copiar_soporte_desde_archivo(archivo_encontrado, ruta_destino_especifica, factura_limpia)
                self.exitos_lista.append(f"{factura_limpia} (por archivo exacto)")

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
            if not os.path.isdir(ruta_destino):
                os.makedirs(ruta_destino)
                self._log(f"-> Carpeta de destino creada: {os.path.basename(ruta_destino)}", COLOR_INFO)

            for nombre_item in os.listdir(ruta_origen):
                ruta_completa_origen = os.path.join(ruta_origen, nombre_item)
                if os.path.isfile(ruta_completa_origen):
                    # --- FILTRO DE EXTENSIONES ---
                    if not nombre_item.lower().endswith(EXTENSIONES_SOPORTE):
                        self._log(f"-> Omitido (formato no permitido): {nombre_item}", "gray")
                        continue
                    # ---------------------------

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
            nombre_original = os.path.basename(ruta_origen)
            nombre_base, extension = os.path.splitext(nombre_original)

            # Lógica de renombrado
            if nombre_base.lower() == factura_buscada.lower():
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
        self.esta_cancelado = True

# logica/workers/buscador_soportes_nuevos_logic.py
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

    def _log(self, mensaje: str, color: str = COLOR_DEFAULT):
        self.log_generado.emit(f"<p style='color:{color}; margin-top:0; margin-bottom:0;'>{mensaje}</p>")

    def ejecutar(self):
        self._log("<b>Iniciando búsqueda y copia de soportes NUEVOS...</b>", COLOR_INFO)
        self._log(f"Directorio de Búsqueda: {self.dir_busqueda}")
        self._log(f"Directorio de Destino: {self.dir_destino}")

        try:
            # --- FASE 1: ESTRATEGIA A (Búsqueda por carpetas) ---
            facturas_para_estrategia_b = self._ejecutar_estrategia_a()

            # --- FASE 2: ESTRATEGIA B (Búsqueda por archivos) ---
            if not self.esta_cancelado and facturas_para_estrategia_b:
                self._ejecutar_estrategia_b(facturas_para_estrategia_b)

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

    def _ejecutar_estrategia_a(self):
        self._log("<br><b>--- FASE 1: Iniciando Estrategia A (Búsqueda por Carpetas) ---</b>", COLOR_INFO)
        self._log("Creando índice de carpetas... Esto puede tardar un momento.", COLOR_INFO)
        self.progreso_actualizado.emit("Escaneando directorios (Fase 1)...", 0)
        
        indice_carpetas = {}
        for dirpath, dirnames, _ in os.walk(self.dir_busqueda):
            for dirname in dirnames:
                indice_carpetas.setdefault(dirname, []).append(os.path.join(dirpath, dirname))
        
        self._log(f"Se indexaron {len(indice_carpetas)} nombres de carpetas únicos.", COLOR_SUCCESS)
        
        facturas_no_encontradas = []
        total_facturas = len(self.facturas_con_serie)

        for i, factura_input in enumerate(self.facturas_con_serie):
            factura_limpia = factura_input.strip()
            if self.esta_cancelado:
                self.fallos_lista.append(f"{factura_limpia} (cancelado)")
                continue

            porcentaje = ((i + 1) / total_facturas) * 50  # La fase 1 ocupa el 50% del progreso
            self.progreso_actualizado.emit(f"Fase 1: {factura_limpia}", porcentaje)
            self._log(f"<br><b>Procesando (A): {factura_limpia}</b>", COLOR_INFO)

            match = re.match(r'([a-zA-Z]+)(\d+)', factura_limpia)
            if not match:
                self._log("-> Formato no válido.", COLOR_WARNING)
                facturas_no_encontradas.append(factura_limpia)
                continue
            
            serie, numero_factura = match.groups()
            self._log(f"-> Serie: '{serie}', Número: '{numero_factura}'")

            rutas_encontradas = indice_carpetas.get(numero_factura)
            
            if not rutas_encontradas:
                self._log(f"-> No se encontró carpeta con el número '{numero_factura}'. Pasando a Estrategia B.", COLOR_WARNING)
                facturas_no_encontradas.append(factura_limpia)
                continue
            
            carpeta_encontrada = rutas_encontradas[0]
            if len(rutas_encontradas) > 1:
                self._log(f"-> AVISO: Se encontraron {len(rutas_encontradas)} carpetas para '{numero_factura}'. Se usará la más reciente.", COLOR_WARNING)
                carpeta_encontrada = max(rutas_encontradas, key=os.path.getmtime)

            archivos_en_carpeta = os.listdir(carpeta_encontrada)
            if not any(serie.lower() in nombre_archivo.lower() for nombre_archivo in archivos_en_carpeta):
                self._log(f"-> La serie '{serie}' no fue encontrada en los archivos de la carpeta. Pasando a Estrategia B.", COLOR_WARNING)
                facturas_no_encontradas.append(factura_limpia)
                continue

            self._log(f"-> Soportes encontrados en: <b>{carpeta_encontrada}</b>", COLOR_SUCCESS)
            self._log(f"-> Serie '{serie}' verificada. Copiando soportes.", COLOR_SUCCESS)
            
            ruta_destino_subcarpeta = os.path.join(self.dir_destino, numero_factura)
            self._copiar_soportes_desde_carpeta(carpeta_encontrada, ruta_destino_subcarpeta, factura_limpia)
            self.exitos_lista.append(f"{factura_limpia} (por carpeta)")

        return facturas_no_encontradas

    def _ejecutar_estrategia_b(self, facturas_a_buscar: list[str]):
        self._log("<br><b>--- FASE 2: Iniciando Estrategia B (Búsqueda por Archivos PDF) ---</b>", COLOR_INFO)
        self._log("Creando índice de archivos... Esto puede tardar un momento.", COLOR_INFO)
        self.progreso_actualizado.emit("Escaneando archivos (Fase 2)...", 50)

        indice_archivos = {}
        for dirpath, _, filenames in os.walk(self.dir_busqueda):
            for filename in filenames:
                if filename.lower().endswith('.pdf'):
                    nombre_sin_ext, _ = os.path.splitext(filename)
                    indice_archivos.setdefault(nombre_sin_ext.lower(), []).append(os.path.join(dirpath, filename))
        
        self._log(f"Se indexaron {len(indice_archivos)} nombres de archivos PDF únicos.", COLOR_SUCCESS)
        
        total_facturas_b = len(facturas_a_buscar)
        for i, factura_input in enumerate(facturas_a_buscar):
            factura_limpia = factura_input.strip()
            if self.esta_cancelado:
                self.fallos_lista.append(f"{factura_limpia} (cancelado)")
                continue

            porcentaje = 50 + ((i + 1) / total_facturas_b) * 50
            self.progreso_actualizado.emit(f"Fase 2: {factura_limpia}", porcentaje)
            self._log(f"<br><b>Procesando (B): {factura_limpia}</b>", COLOR_INFO)

            rutas_encontradas = indice_archivos.get(factura_limpia.lower())

            if not rutas_encontradas:
                self._log("-> No se encontró archivo PDF con ese nombre.", COLOR_WARNING)
                self.fallos_lista.append(f"{factura_limpia} (archivo no encontrado)")
                continue

            archivo_encontrado = rutas_encontradas[-1] # Tomar el último encontrado
            if len(rutas_encontradas) > 1:
                self._log(f"-> AVISO: Se encontraron {len(rutas_encontradas)} archivos para '{factura_limpia}'. Se usará el último: {archivo_encontrado}", COLOR_WARNING)
            
            self._log(f"-> Soporte encontrado en: <b>{archivo_encontrado}</b>", COLOR_SUCCESS)
            
            # Encontrar la subcarpeta de destino correcta
            ruta_destino_especifica = self._encontrar_subcarpeta_destino(factura_limpia)
            self._log(f"-> Carpeta destino determinada: {os.path.basename(ruta_destino_especifica)}", COLOR_INFO)

            self._copiar_soporte_desde_archivo(archivo_encontrado, ruta_destino_especifica, factura_limpia)
            self.exitos_lista.append(f"{factura_limpia} (por archivo)")

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
                    ruta_completa_destino = os.path.join(ruta_destino, nombre_item)
                    if not os.path.exists(ruta_completa_destino):
                        shutil.copy2(ruta_completa_origen, ruta_completa_destino)
                        archivos_copiados += 1
                    else:
                        self._log(f"-> Omitido (ya existe): {nombre_item}", "gray")
            
            if archivos_copiados > 0:
                self._log(f"-> Se copiaron {archivos_copiados} archivos de la carpeta.", COLOR_SUCCESS)
            else:
                self._log("-> No se copiaron nuevos archivos de la carpeta (o ya existían).")
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

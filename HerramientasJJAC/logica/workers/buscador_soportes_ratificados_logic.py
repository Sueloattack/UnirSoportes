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
        self._log("<b>Iniciando búsqueda y copia de soportes RATIFICADOS (R2)...</b>", COLOR_INFO)
        self._log(f"Directorio de Búsqueda: {self.dir_busqueda}")
        self._log(f"Directorio de Destino: {self.dir_destino}")

        try:
            # 1. FASE DE INDEXACIÓN
            self._log("Creando índice de carpetas...", COLOR_INFO)
            self.progreso_actualizado.emit("Escaneando directorios...", 0)
            
            indice_carpetas = {}
            for dirpath, dirnames, _ in os.walk(self.dir_busqueda):
                for dirname in dirnames:
                    indice_carpetas.setdefault(dirname, []).append(os.path.join(dirpath, dirname))
            
            self._log(f"Se indexaron {len(indice_carpetas)} nombres de carpetas únicos.", COLOR_SUCCESS)

            # 2. FASE DE PROCESAMIENTO
            total_facturas = len(self.facturas_con_serie)
            for i, factura_input in enumerate(self.facturas_con_serie):
                factura_limpia = factura_input.strip()
                if self.esta_cancelado: 
                    self.fallos_lista.append(f"{factura_limpia} (cancelado)")
                    continue

                porcentaje = ((i + 1) / total_facturas) * 100
                self.progreso_actualizado.emit(f"Procesando: {factura_limpia}", porcentaje)
                self._log(f"<br><b>Procesando: {factura_limpia}</b>", COLOR_INFO)

                match = re.match(r'([a-zA-Z]+)(\d+)', factura_limpia)
                if not match:
                    self._log(f"-> Formato no válido. Se esperaba 'SERIENUMERO'.", COLOR_WARNING)
                    self.fallos_lista.append(f"{factura_limpia} (formato no válido)")
                    continue
                
                serie, numero_factura = match.groups()
                self._log(f"-> Serie: '{serie}', Número: '{numero_factura}'")

                rutas_encontradas = indice_carpetas.get(numero_factura)
                
                if not rutas_encontradas:
                    self._log(f"-> No se encontró carpeta con el número '{numero_factura}'.", COLOR_WARNING)
                    self.fallos_lista.append(f"{factura_limpia} (carpeta no encontrada)")
                    continue
                
                # --- LÓGICA DE SELECCIÓN PARA R2 ---
                carpeta_origen_final = None
                if len(rutas_encontradas) > 1:
                    rutas_encontradas.sort(key=os.path.getmtime, reverse=True) # Ordenar de más nueva a más vieja
                    self._log(f"-> Se encontraron {len(rutas_encontradas)} carpetas. Seleccionando la penúltima.", COLOR_INFO)
                    carpeta_origen_final = rutas_encontradas[1] # La penúltima
                elif len(rutas_encontradas) == 1:
                    self._log("-> Se encontró una única carpeta.", COLOR_INFO)
                    carpeta_origen_final = rutas_encontradas[0]
                else:
                    self.fallos_lista.append(f"{factura_limpia} (error inesperado)")
                    continue
                
                self._log(f"-> Usando carpeta de origen: <b>{carpeta_origen_final}</b>")

                # Verificación de serie
                archivos_en_carpeta = os.listdir(carpeta_origen_final)
                if not any(serie.lower() in nombre_archivo.lower() for nombre_archivo in archivos_en_carpeta):
                    self._log(f"-> La serie '{serie}' no fue encontrada en los archivos. Omitiendo.", COLOR_WARNING)
                    self.fallos_lista.append(f"{factura_limpia} (serie no coincide)")
                    continue

                self._log(f"-> Serie '{serie}' verificada. Copiando soportes.", COLOR_SUCCESS)
                
                # Pasamos el número de factura para que la subcarpeta de destino se llame así
                self._copiar_soportes(carpeta_origen_final, self.dir_destino, numero_factura)
                self.exitos_lista.append(factura_limpia)

        except Exception as e:
            self._log(f"<b>ERROR CRÍTICO:</b> {e}", COLOR_ERROR)
        
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
        
    def _copiar_soportes(self, ruta_origen: str, dir_destino_general: str, numero_factura: str):
        archivos_copiados = 0
        try:
            # Identificar solo los archivos que son soportes (Filtrando estrictamente PDF)
            archivos_pdf_nombres = [f for f in os.listdir(ruta_origen) if f.lower().endswith('.pdf')]
            documentos = identificar_documentos_aseguradoras(archivos_pdf_nombres, ruta_origen)
            soportes_a_copiar = documentos.get('soportes', [])

            if not soportes_a_copiar:
                self._log("-> No se identificaron archivos de soporte específicos para copiar.")
                return

            # Crear la carpeta de destino final con el número de factura
            ruta_destino_especifica = os.path.join(dir_destino_general, numero_factura)
            if not os.path.isdir(ruta_destino_especifica):
                os.makedirs(ruta_destino_especifica)
                self._log(f"-> Carpeta de destino creada: {numero_factura}", COLOR_INFO)

            self._log(f"-> Se identificaron {len(soportes_a_copiar)} soportes específicos. Copiando...", COLOR_INFO)

            for ruta_completa_origen in soportes_a_copiar:
                # DOBLE VERIFICACIÓN: Solo copiar si es PDF
                if not ruta_completa_origen.lower().endswith('.pdf'):
                    continue

                nombre_item = os.path.basename(ruta_completa_origen)
                ruta_completa_destino = os.path.join(ruta_destino_especifica, nombre_item)
                
                if not os.path.exists(ruta_completa_destino):
                    shutil.copy2(ruta_completa_origen, ruta_completa_destino)
                    archivos_copiados += 1
                else:
                    self._log(f"-> Omitido (ya existe): {nombre_item}", "gray")

            if archivos_copiados > 0:
                self._log(f"-> Se copiaron {archivos_copiados} archivos de soporte.", COLOR_SUCCESS)
            else:
                 self._log("-> No se copiaron nuevos soportes (todos existían).")
        except Exception as e:
            self._log(f"-> ❌ ERROR al copiar soportes para la factura '{numero_factura}': {e}", COLOR_ERROR)

    def cancelar(self):
        self.esta_cancelado = True

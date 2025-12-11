# logica/workers/buscador_soportes_conci_logic.py
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

    def _log(self, mensaje: str, color: str = COLOR_DEFAULT):
        self.log_generado.emit(f"<p style='color:{color}; margin-top:0; margin-bottom:0;'>{mensaje}</p>")

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
                for dirname in dirnames:
                    indice_carpetas.setdefault(dirname, []).append(os.path.join(dirpath, dirname))
            
            self._log(f"Se indexaron {len(indice_carpetas)} nombres de carpetas únicos.", COLOR_SUCCESS)

            total_facturas = len(self.facturas_con_serie)
            
            for i, factura_input in enumerate(self.facturas_con_serie):
                factura_limpia = factura_input.strip()
                if self.esta_cancelado:
                    break

                porcentaje = ((i + 1) / total_facturas) * 100
                self.progreso_actualizado.emit(f"Procesando: {factura_limpia}", porcentaje)
                self._log(f"<br><b>Procesando: {factura_limpia}</b>", COLOR_INFO)

                # Extraer Serie y Número
                match = re.match(r'([a-zA-Z]+)(\d+)', factura_limpia)
                if not match:
                    self._log(f"-> Formato inválido '{factura_limpia}'. Se espera SERIENUMERO.", COLOR_WARNING)
                    self.fallos_lista.append(f"{factura_limpia} (formato inválido)")
                    continue
                
                serie, numero_factura = match.groups()
                serie = serie.upper()
                
                # 2. BUSCAR CARPETA (MÁS ANTIGUA)
                rutas_encontradas = indice_carpetas.get(numero_factura)
                
                if not rutas_encontradas:
                    self._log(f"-> No se encontró carpeta para '{numero_factura}'.", COLOR_WARNING)
                    self.fallos_lista.append(f"{factura_limpia} (carpeta no encontrada)")
                    continue
                
                # Seleccionar la más antigua
                carpeta_seleccionada = min(rutas_encontradas, key=os.path.getctime)
                if len(rutas_encontradas) > 1:
                    self._log(f"-> Se encontraron {len(rutas_encontradas)} carpetas. Seleccionando la más antigua: {os.path.basename(carpeta_seleccionada)}", COLOR_INFO)
                
                self._log(f"-> Analizando carpeta: <b>{carpeta_seleccionada}</b>")
                
                # 3. CLASIFICAR Y COPIAR ARCHIVOS
                encontrados = self._procesar_contenido_carpeta(carpeta_seleccionada, serie, numero_factura)
                
                if encontrados['carta'] or encontrados['respuesta'] or encontrados['soportes']:
                    c_str = "Si" if encontrados['carta'] else "No"
                    r_str = "Si" if encontrados['respuesta'] else "No"
                    self.exitos_lista.append(f"{factura_limpia}: C={c_str}, R={r_str}, S={len(encontrados['soportes'])}")
                else:
                    self.fallos_lista.append(f"{factura_limpia} (carpeta vacía o sin coincidencias)")

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

    def _procesar_contenido_carpeta(self, ruta_carpeta, serie, numero):
        """Clasifica y copia archivos según patrones CONCI."""
        resultados = {'carta': None, 'respuesta': None, 'soportes': []}
        
        archivos = [f for f in os.listdir(ruta_carpeta) if os.path.isfile(os.path.join(ruta_carpeta, f))]
        
        # Patrones
        # Carta: RADICADO-SERIE-NUMERO-ASEGURADORA.pdf (contiene serie y numero separados por guiones)
        patron_carta = re.compile(rf".*-{serie}-{numero}-.*\.pdf$", re.IGNORECASE)
        
        # Respuesta: SERIENUMERO.pdf, resp_glosa, GLOSA_REP
        nombre_exacto_respuesta = f"{serie}{numero}.pdf".lower()
        
        archivos_identificados = set()

        # 1. Identificar Carta
        for archivo in archivos:
            if patron_carta.match(archivo):
                resultados['carta'] = os.path.join(ruta_carpeta, archivo)
                archivos_identificados.add(archivo)
                break # Solo una carta
        
        # 2. Identificar Respuesta
        for archivo in archivos:
            if archivo in archivos_identificados: continue
            
            nombre_lower = archivo.lower()
            if (nombre_lower == nombre_exacto_respuesta or 
                "resp_glosa" in nombre_lower or 
                "glosa_rep" in nombre_lower):
                resultados['respuesta'] = os.path.join(ruta_carpeta, archivo)
                archivos_identificados.add(archivo)
                break # Solo una respuesta prioritaria
                
        # 3. Identificar Soportes (Todo lo demás PDF)
        for archivo in archivos:
            if archivo in archivos_identificados: continue
            if archivo.lower().endswith('.pdf'):
                resultados['soportes'].append(os.path.join(ruta_carpeta, archivo))

        # 4. Copiar a destino
        ruta_destino_factura = os.path.join(self.dir_destino, numero)
        if not os.path.exists(ruta_destino_factura):
            os.makedirs(ruta_destino_factura)
            
        if resultados['carta']:
            shutil.copy2(resultados['carta'], os.path.join(ruta_destino_factura, os.path.basename(resultados['carta'])))
            self._log(f"  -> Carta encontrada: {os.path.basename(resultados['carta'])}", COLOR_SUCCESS)
        else:
            self._log(f"  -> ❌ Falta Carta Glosa", COLOR_WARNING)

        if resultados['respuesta']:
            shutil.copy2(resultados['respuesta'], os.path.join(ruta_destino_factura, os.path.basename(resultados['respuesta'])))
            self._log(f"  -> Respuesta encontrada: {os.path.basename(resultados['respuesta'])}", COLOR_SUCCESS)
        else:
            self._log(f"  -> ❌ Falta Respuesta Glosa", COLOR_WARNING)

        if resultados['soportes']:
            for soporte in resultados['soportes']:
                shutil.copy2(soporte, os.path.join(ruta_destino_factura, os.path.basename(soporte)))
            self._log(f"  -> {len(resultados['soportes'])} soportes copiados.", COLOR_SUCCESS)
        else:
            self._log(f"  -> ⚠️ No se encontraron soportes adicionales.", "gray")
            
        return resultados

    def cancelar(self):
        self.esta_cancelado = True

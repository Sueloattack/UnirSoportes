# logica/workers/renombrador_logic.py
import os
import re
from PySide6.QtCore import QObject, Signal

from logica.core import gestor_archivos, identificador_archivos

# --- COLORES ---
COLOR_INFO = "#5DADE2"
COLOR_SUCCESS = "#2ECC71"
COLOR_WARNING = "#F39C12"
COLOR_ERROR = "#E74C3C"
COLOR_DEFAULT = "#ECF0F1"

# Patrones para identificar archivos de respuesta de glosa
PATRONES_RESPUESTA = [
    re.compile(r"([A-Z]+)_?(\d+)\.pdf", re.IGNORECASE),
    re.compile(r"GLOSA_REP\d*\.pdf", re.IGNORECASE),
    re.compile(r"resp_glosa\.pdf", re.IGNORECASE)
]

class RenombradorWorker(QObject):
    progreso_actualizado = Signal(str)
    proceso_finalizado = Signal(dict)

    def __init__(self, ruta_carpeta_raiz, modo):
        super().__init__()
        self.ruta_carpeta_raiz = ruta_carpeta_raiz
        self.modo = modo
        self.esta_cancelado = False

    def ejecutar(self):
        self.progreso_actualizado.emit(f"<p style='color:{COLOR_INFO};'>Iniciando modo <b>'{self.modo.upper()}'</b>...</p><p style='color:{COLOR_DEFAULT};'>Directorio: {self.ruta_carpeta_raiz}</p>")
        
        if self.modo == 'escolar':
            self.renombrar_escolares_en_subcarpetas()
        elif self.modo == 'sura-arl':
            self.renombrar_carpetas_sura_arl()
        elif self.modo == 'glosa' or self.modo == 'devolucion':
            self.renombrar_respuestas_en_raiz()
        elif self.modo == 'json':
            self.renombrar_json_en_raiz()
        elif self.modo == 'json_cascada':
            self.procesar_json_cascada_y_carpetas()
        elif self.modo == 'validar_aeo':
            self.validar_aeo_en_jsons()
        else:
            resultados = {'exitosos': [], 'fallidos': [{'archivo': 'N/A', 'razon': f"Modo '{self.modo}' desconocido."}]}
            self.proceso_finalizado.emit(resultados)

    def _construir_ruta_carpeta_unica(self, ruta_padre: str, nombre_objetivo: str, ruta_actual: str) -> str:
        ruta_base = os.path.join(ruta_padre, nombre_objetivo)
        if os.path.normcase(ruta_base) == os.path.normcase(ruta_actual):
            return ruta_actual

        if not os.path.exists(ruta_base):
            return ruta_base

        consecutivo = 1
        while True:
            ruta_candidata = os.path.join(ruta_padre, f"{nombre_objetivo}_{consecutivo}")
            if os.path.normcase(ruta_candidata) == os.path.normcase(ruta_actual) or not os.path.exists(ruta_candidata):
                return ruta_candidata
            consecutivo += 1

    def renombrar_respuestas_en_raiz(self):
        resultados = {'exitosos': [], 'fallidos': []}
        try:
            archivos_pdf_raiz = [f for f in os.listdir(self.ruta_carpeta_raiz) if f.lower().endswith('.pdf') and os.path.isfile(os.path.join(self.ruta_carpeta_raiz, f))]
            if not archivos_pdf_raiz:
                self.emit_fallo(resultados, "N/A", "No se encontraron archivos .pdf en la carpeta raíz.")
                self.proceso_finalizado.emit(resultados)
                return

            archivos_procesados = 0
            for nombre_archivo in archivos_pdf_raiz:
                if self.esta_cancelado: break
                if any(patron.match(nombre_archivo) for patron in PATRONES_RESPUESTA):
                    archivos_procesados += 1
                    self.procesar_renombrado_raiz(nombre_archivo, resultados)
            
            if archivos_procesados == 0:
                 self.progreso_actualizado.emit(f"<p style='color:{COLOR_WARNING};'>No se encontró ningún archivo que coincida con un patrón de respuesta de glosa.</p>")

        except Exception as e:
            self.emit_fallo(resultados, "CRÍTICO", f"Error inesperado: {e}")
        self.proceso_finalizado.emit(resultados)

    def procesar_renombrado_raiz(self, nombre_original, resultados):
        self.progreso_actualizado.emit(f"<p style='color:{COLOR_DEFAULT};'>Archivo de respuesta encontrado: <b>{nombre_original}</b></p>")
        
        if self.modo == 'glosa':
            prefijo = 'R-800209891-'
            if nombre_original.startswith(prefijo): return self.emit_fallo(resultados, nombre_original, "Ya tiene el prefijo 'R-8002098917-'", 'warning')
            nuevo_nombre = f"{prefijo}{nombre_original}"
        elif self.modo == 'devolucion':
            prefijo = '800209891-'
            if nombre_original.startswith(prefijo): return self.emit_fallo(resultados, nombre_original, "Ya tiene el prefijo '8002098917-'", 'warning')
            nuevo_nombre = f"{prefijo}{nombre_original}"
        else: return

        ruta_original = os.path.join(self.ruta_carpeta_raiz, nombre_original)
        nueva_ruta = os.path.join(self.ruta_carpeta_raiz, nuevo_nombre)
        try:
            os.rename(ruta_original, nueva_ruta)
            mensaje = f"Renombrado: {nombre_original} -> <b>{nuevo_nombre}</b>"
            resultados['exitosos'].append({"archivo": nombre_original, "razon": mensaje})
            self.progreso_actualizado.emit(f"<p style='color:{COLOR_SUCCESS};'>- {mensaje}</p>")
        except Exception as e:
            self.emit_fallo(resultados, nombre_original, f"Error al intentar renombrar: {e}")

    def renombrar_escolares_en_subcarpetas(self):
        resultados = {'exitosos': [], 'fallidos': []}
        try:
            subcarpetas = gestor_archivos.listar_subdirectorios(self.ruta_carpeta_raiz)
            if not subcarpetas:
                self.emit_fallo(resultados, "N/A", "No se encontraron subcarpetas en el directorio raíz.")
                self.proceso_finalizado.emit(resultados)
                return

            for ruta_carpeta in subcarpetas:
                if self.esta_cancelado: break
                nombre_carpeta = os.path.basename(ruta_carpeta)
                self.progreso_actualizado.emit(f"<br><p style='color:{COLOR_DEFAULT};'>Procesando subcarpeta: <b>{nombre_carpeta}</b></p>")

                archivos_pdf = gestor_archivos.obtener_archivos_pdf(ruta_carpeta)
                if not archivos_pdf: continue

                documentos = identificador_archivos.identificar_documentos_aseguradoras(archivos_pdf, ruta_carpeta)
                respuesta_glosa = documentos.get('respuesta_glosa')

                if documentos.get('carta_glosa') and respuesta_glosa:
                    ruta_original = respuesta_glosa['path']
                    nombre_original = os.path.basename(ruta_original)
                    nombre_base, extension = os.path.splitext(nombre_original)
                    sufijo = '_PRG_1'

                    if nombre_base.endswith(sufijo):
                        self.emit_fallo(resultados, nombre_original, "Ya tiene el sufijo '_PRG_1'.", 'warning')
                    else:
                        nuevo_nombre = f"{nombre_base}{sufijo}{extension}"
                        nueva_ruta = os.path.join(ruta_carpeta, nuevo_nombre)
                        try:
                            os.rename(ruta_original, nueva_ruta)
                            mensaje = f"Renombrado: {nombre_original} -> <b>{nuevo_nombre}</b>"
                            resultados['exitosos'].append({"archivo": nombre_original, "razon": mensaje})
                            self.progreso_actualizado.emit(f"<p style='color:{COLOR_SUCCESS};'>- {mensaje}</p>")
                        except Exception as e:
                            self.emit_fallo(resultados, nombre_original, f"Error al renombrar: {e}")
                else:
                    self.emit_fallo(resultados, nombre_carpeta, "No se encontró el par 'carta_glosa' y 'respuesta_glosa'.", 'warning')
        except Exception as e:
            self.emit_fallo(resultados, "CRÍTICO", f"Error inesperado: {e}")
        self.proceso_finalizado.emit(resultados)

    def renombrar_carpetas_sura_arl(self):
        resultados = {'exitosos': [], 'fallidos': []}
        try:
            subcarpetas = gestor_archivos.listar_subdirectorios(self.ruta_carpeta_raiz)
            if not subcarpetas:
                self.emit_fallo(resultados, "N/A", "No se encontraron subcarpetas en el directorio raíz.")
                self.proceso_finalizado.emit(resultados)
                return

            for ruta_carpeta in subcarpetas:
                if self.esta_cancelado:
                    break

                nombre_carpeta = os.path.basename(ruta_carpeta)
                self.progreso_actualizado.emit(
                    f"<br><p style='color:{COLOR_DEFAULT};'>Procesando subcarpeta SURA-ARL: <b>{nombre_carpeta}</b></p>"
                )

                archivos_pdf = gestor_archivos.obtener_archivos_pdf(ruta_carpeta)
                if not archivos_pdf:
                    self.emit_fallo(resultados, nombre_carpeta, "No se encontraron PDF dentro de la carpeta.", 'warning')
                    continue

                documentos = identificador_archivos.identificar_documentos_aseguradoras(archivos_pdf, ruta_carpeta)
                respuesta_glosa = documentos.get('respuesta_glosa')
                if not respuesta_glosa:
                    self.emit_fallo(resultados, nombre_carpeta, "No se encontró respuesta glosa dentro de la carpeta.", 'warning')
                    continue

                nombre_objetivo = os.path.splitext(os.path.basename(respuesta_glosa['path']))[0].strip()
                if not nombre_objetivo:
                    self.emit_fallo(resultados, nombre_carpeta, "La respuesta glosa no produjo un nombre válido para la carpeta.", 'warning')
                    continue

                ruta_padre = os.path.dirname(ruta_carpeta)
                ruta_destino = self._construir_ruta_carpeta_unica(ruta_padre, nombre_objetivo, ruta_carpeta)

                if os.path.normcase(ruta_destino) == os.path.normcase(ruta_carpeta):
                    self.emit_fallo(resultados, nombre_carpeta, "La carpeta ya tiene el nombre objetivo.", 'warning')
                    continue

                try:
                    os.rename(ruta_carpeta, ruta_destino)
                    mensaje = f"Renombrada carpeta: {nombre_carpeta} -> <b>{os.path.basename(ruta_destino)}</b>"
                    resultados['exitosos'].append({"archivo": nombre_carpeta, "razon": mensaje})
                    self.progreso_actualizado.emit(f"<p style='color:{COLOR_SUCCESS};'>- {mensaje}</p>")
                except Exception as e:
                    self.emit_fallo(resultados, nombre_carpeta, f"Error al renombrar la carpeta: {e}")
        except Exception as e:
            self.emit_fallo(resultados, "CRÍTICO", f"Error inesperado: {e}")
        self.proceso_finalizado.emit(resultados)

    def renombrar_json_en_raiz(self):
        resultados = {'exitosos': [], 'fallidos': []}
        nit_coex = "730010082602"
        nit_general = "730010082601"

        patron_resultadosmsps = re.compile(r"^resultadosmsps_([^_]+)_id.*_a_cuv\.json$", re.IGNORECASE)
        patron_simple = re.compile(r"^([a-zA-Z0-9]+)\.json$", re.IGNORECASE)

        try:
            if not os.path.isdir(self.ruta_carpeta_raiz):
                self.emit_fallo(resultados, "N/A", "La ruta seleccionada no existe o no es un directorio.")
                self.proceso_finalizado.emit(resultados)
                return

            archivos = os.listdir(self.ruta_carpeta_raiz)
            if not archivos:
                self.emit_fallo(resultados, "N/A", "No se encontraron archivos en la carpeta raíz.", 'warning')
                self.proceso_finalizado.emit(resultados)
                return

            for archivo in archivos:
                if self.esta_cancelado:
                    break

                ruta_origen = os.path.join(self.ruta_carpeta_raiz, archivo)
                if not os.path.isfile(ruta_origen):
                    continue

                nuevo_nombre = None
                match_resultadosmsps = patron_resultadosmsps.match(archivo)

                if match_resultadosmsps:
                    identificador_original = match_resultadosmsps.group(1)
                    identificador = identificador_original.upper()
                    nit = nit_coex if 'coex' in identificador_original.lower() else nit_general
                    nuevo_nombre = f"{nit}_{identificador}_CUV.json"
                else:
                    match_simple = patron_simple.match(archivo)
                    if not match_simple:
                        continue

                    if archivo.lower().startswith('resultadosmsps'):
                        continue

                    identificador_original = match_simple.group(1)
                    identificador = identificador_original.upper()
                    nit = nit_coex if 'coex' in identificador_original.lower() else nit_general
                    nuevo_nombre = f"{nit}_{identificador}_RIP.json"

                if not nuevo_nombre or archivo == nuevo_nombre:
                    continue

                ruta_destino = os.path.join(self.ruta_carpeta_raiz, nuevo_nombre)
                if os.path.exists(ruta_destino):
                    self.emit_fallo(resultados, archivo, f"[OMITIDO] El destino ya existe: {nuevo_nombre}", 'warning')
                    continue

                try:
                    os.rename(ruta_origen, ruta_destino)
                    mensaje = f"Renombrado JSON: {archivo} -> <b>{nuevo_nombre}</b>"
                    resultados['exitosos'].append({"archivo": archivo, "razon": mensaje})
                    self.progreso_actualizado.emit(f"<p style='color:{COLOR_SUCCESS};'>- {mensaje}</p>")
                except Exception as e:
                    self.emit_fallo(resultados, archivo, f"Error al renombrar JSON: {e}")

            if self.esta_cancelado:
                self.progreso_actualizado.emit(f"<p style='color:{COLOR_WARNING};'>Proceso cancelado por el usuario.</p>")

        except Exception as e:
            self.emit_fallo(resultados, "CRÍTICO", f"Error inesperado en modo JSON: {e}")

        self.proceso_finalizado.emit(resultados)

    def emit_fallo(self, resultados, archivo, razon, level='error'):
        color = COLOR_ERROR if level == 'error' else COLOR_WARNING
        resultados['fallidos'].append({"archivo": archivo, "razon": razon})
        self.progreso_actualizado.emit(f"<p style='color:{color};'>- {razon} (Archivo/Carpeta: {archivo})</p>")

    def cancelar(self):
        self.esta_cancelado = True

    def procesar_json_cascada_y_carpetas(self):
        import json
        resultados = {'exitosos': [], 'fallidos': []}
        try:
            if not os.path.isdir(self.ruta_carpeta_raiz):
                self.emit_fallo(resultados, "N/A", "La ruta seleccionada no existe o no es un directorio.")
                self.proceso_finalizado.emit(resultados)
                return

            # Escanear recursivamente todos los JSONs en la raíz y subcarpetas
            todos_archivos = []
            for root, dirs, files in os.walk(self.ruta_carpeta_raiz):
                if self.esta_cancelado:
                    break
                for f in files:
                    if f.lower().endswith('.json'):
                        todos_archivos.append(os.path.join(root, f))

            if not todos_archivos:
                self.emit_fallo(resultados, "N/A", "No se encontraron archivos JSON en la carpeta ni en sus subcarpetas.", 'warning')
                self.proceso_finalizado.emit(resultados)
                return

            # Separar archivos base de los resultadosmsps
            base_jsons = []
            results_jsons = []
            for filepath in todos_archivos:
                filename = os.path.basename(filepath)
                if filename.lower().startswith('resultadosmsps_'):
                    results_jsons.append(filepath)
                else:
                    base_jsons.append(filepath)

            self.progreso_actualizado.emit(f"<p style='color:{COLOR_INFO};'>Se encontraron {len(base_jsons)} JSONs base y {len(results_jsons)} JSONs de resultados (recursivo).</p>")

            for base_path in base_jsons:
                if self.esta_cancelado:
                    break

                base_dir = os.path.dirname(base_path)
                base_file = os.path.basename(base_path)
                
                # Parse JSON base
                data = None
                for enc in ['utf-8', 'latin-1', 'cp1252']:
                    try:
                        with open(base_path, 'r', encoding=enc) as f:
                            data = json.load(f)
                            break
                    except Exception:
                        continue

                if data is None:
                    try:
                        with open(base_path, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                    except Exception as e:
                        self.emit_fallo(resultados, base_file, f"Error leyendo/parseando JSON: {e}")
                        continue

                nit = data.get("numDocumentoIdObligado", "800209891")
                num_factura = data.get("numFactura")

                if not num_factura:
                    self.emit_fallo(resultados, base_file, "El JSON no contiene el campo 'numFactura'. Omitiendo.")
                    continue

                # Extraer serie y número de la factura
                match = re.match(r'^([a-zA-Z]+)(\d+)$', num_factura.strip())
                if match:
                    serie = match.group(1).upper()
                    numero = match.group(2)
                else:
                    serie = num_factura.strip().upper()
                    numero = ""

                # Buscar el JSON de resultados correspondiente en el mismo directorio (base_dir)
                res_match_path = None
                prefix_to_match = f"resultadosmsps_{num_factura.lower()}_"
                suffix_to_match = "_a_cuv.json"

                for rp in results_jsons:
                    if os.path.dirname(rp) == base_dir:
                        rf_name = os.path.basename(rp)
                        if rf_name.lower().startswith(prefix_to_match) and rf_name.lower().endswith(suffix_to_match):
                            res_match_path = rp
                            break

                if not res_match_path:
                    self.emit_fallo(resultados, base_file, f"No se encontró el JSON de resultados correspondiente para {num_factura} en la misma carpeta (patrón: {prefix_to_match}...{suffix_to_match})")
                    continue

                # Procesar archivo de resultados
                res_file = os.path.basename(res_match_path)
                res_data = None
                for enc in ['utf-8', 'latin-1', 'cp1252']:
                    try:
                        with open(res_match_path, 'r', encoding=enc) as f:
                            res_data = json.load(f)
                            break
                    except Exception:
                        continue

                if res_data is None:
                    try:
                        with open(res_match_path, 'r', encoding='utf-8') as f:
                            res_data = json.load(f)
                    except Exception as e:
                        self.emit_fallo(resultados, res_file, f"Error leyendo/parseando JSON de resultados: {e}")
                        continue

                # Determinar si ya está organizado (está en una subcarpeta)
                # Si base_dir es exactamente ruta_carpeta_raiz, entonces no está organizado y creamos la carpeta.
                ya_organizado = os.path.normpath(base_dir) != os.path.normpath(self.ruta_carpeta_raiz)

                if ya_organizado:
                    target_dir = base_dir
                    folder_name = os.path.basename(base_dir)
                else:
                    folder_name = f"{nit}_{serie}_{numero}" if numero else f"{nit}_{serie}"
                    target_dir = os.path.join(self.ruta_carpeta_raiz, folder_name)
                    os.makedirs(target_dir, exist_ok=True)

                # Escribir el JSON base formateado (cascada)
                ruta_base_destino = os.path.join(target_dir, base_file)
                # Escribir el JSON de resultados renombrado y formateado
                new_res_name = res_file[:-11] + "_a-cuv.json"
                ruta_res_destino = os.path.join(target_dir, new_res_name)

                try:
                    # Escribir base
                    with open(ruta_base_destino, 'w', encoding='utf-8') as f:
                        json.dump(data, f, indent=4, ensure_ascii=False)

                    # Escribir resultados
                    with open(ruta_res_destino, 'w', encoding='utf-8') as f:
                        json.dump(res_data, f, indent=4, ensure_ascii=False)

                    # Si NO es in-place (es decir, creamos carpeta), eliminamos los archivos origen de la raíz
                    # Si SÍ es in-place, como el nombre del resultados cambia de _a_cuv.json a _a-cuv.json, eliminamos el _a_cuv.json original.
                    if not ya_organizado:
                        os.remove(base_path)
                        os.remove(res_match_path)
                    else:
                        # Si es el mismo archivo base_path (mismo nombre y ruta), al escribirlo en w se sobreescribe, pero por seguridad si es in-place lo manejamos bien.
                        # El archivo de resultados cambia de nombre por lo que hay que borrar el viejo.
                        if os.path.exists(res_match_path) and os.path.normcase(res_match_path) != os.path.normcase(ruta_res_destino):
                            os.remove(res_match_path)

                    mensaje = f"Procesados JSONs en carpeta {folder_name} (Res resultados renombrado a {new_res_name})"
                    resultados['exitosos'].append({"archivo": base_file, "razon": mensaje})
                    self.progreso_actualizado.emit(f"<p style='color:{COLOR_SUCCESS};'>- {mensaje}</p>")

                except Exception as e:
                    self.emit_fallo(resultados, base_file, f"Error al guardar/eliminar archivos: {e}")

            if self.esta_cancelado:
                self.progreso_actualizado.emit(f"<p style='color:{COLOR_WARNING};'>Proceso cancelado por el usuario.</p>")

        except Exception as e:
            self.emit_fallo(resultados, "CRÍTICO", f"Error inesperado en cascada JSON: {e}")

        self.proceso_finalizado.emit(resultados)

    def validar_aeo_en_jsons(self):
        import json
        resultados = {'exitosos': [], 'fallidos': []}
        try:
            if not os.path.isdir(self.ruta_carpeta_raiz):
                self.emit_fallo(resultados, "N/A", "La ruta seleccionada no existe o no es un directorio.")
                self.proceso_finalizado.emit(resultados)
                return

            # Obtener archivos JSON recursivamente
            todos_archivos = []
            for root, dirs, files in os.walk(self.ruta_carpeta_raiz):
                if self.esta_cancelado:
                    break
                for f in files:
                    if f.lower().endswith('.json'):
                        todos_archivos.append(os.path.join(root, f))

            if not todos_archivos:
                self.emit_fallo(resultados, "N/A", "No se encontraron archivos .json en la carpeta ni en sus subcarpetas.", 'warning')
                self.proceso_finalizado.emit(resultados)
                return

            self.progreso_actualizado.emit(f"<p style='color:{COLOR_INFO};'>Validando AEO en {len(todos_archivos)} archivos JSON (recursivo)...</p>")
            
            aeo_files = []
            other_files = []
            
            for base_path in todos_archivos:
                if self.esta_cancelado:
                    break

                base_file = os.path.basename(base_path)
                # Ruta relativa para que el log se vea limpio y descriptivo
                rel_path = os.path.relpath(base_path, self.ruta_carpeta_raiz)
                
                # Parse JSON
                data = None
                for enc in ['utf-8', 'latin-1', 'cp1252']:
                    try:
                        with open(base_path, 'r', encoding=enc) as f:
                            data = json.load(f)
                            break
                    except Exception:
                        continue

                if data is None:
                    try:
                        with open(base_path, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                    except Exception as e:
                        self.emit_fallo(resultados, rel_path, f"Error leyendo/parseando JSON: {e}")
                        continue

                # Check if it is AEO
                is_aeo = False
                
                def buscar_cod_procedimiento(obj):
                    if isinstance(obj, dict):
                        if str(obj.get('codProcedimiento', '')).strip() == '931001':
                            return True
                        for k, v in obj.items():
                            if buscar_cod_procedimiento(v):
                                return True
                    elif isinstance(obj, list):
                        for item in obj:
                            if buscar_cod_procedimiento(item):
                                return True
                    return False

                if buscar_cod_procedimiento(data):
                    is_aeo = True

                if is_aeo:
                    aeo_files.append(rel_path)
                    msg = f"Archivo {rel_path} -> <b>AEO (931001)</b>"
                    self.progreso_actualizado.emit(f"<p style='color:{COLOR_SUCCESS};'>- {msg}</p>")
                else:
                    other_files.append(rel_path)
                    msg = f"Archivo {rel_path} -> Terapia Física / Otro"
                    self.progreso_actualizado.emit(f"<p style='color:{COLOR_DEFAULT};'>- {msg}</p>")

                resultados['exitosos'].append({"archivo": rel_path, "razon": f"Validado (AEO={is_aeo})"})

            # Report Summary
            self.progreso_actualizado.emit("<br><b>--- RESUMEN DE VALIDACIÓN ---</b>")
            self.progreso_actualizado.emit(f"<p style='color:{COLOR_SUCCESS};'><b>Total AEO encontrados: {len(aeo_files)}</b></p>")
            for f in aeo_files:
                self.progreso_actualizado.emit(f"<p style='color:{COLOR_SUCCESS};'>  - {f}</p>")
            self.progreso_actualizado.emit(f"<p style='color:{COLOR_INFO};'>Total Terapia Física / Otros: {len(other_files)}</p>")

        except Exception as e:
            self.emit_fallo(resultados, "CRÍTICO", f"Error inesperado al validar AEO: {e}")

        self.proceso_finalizado.emit(resultados)


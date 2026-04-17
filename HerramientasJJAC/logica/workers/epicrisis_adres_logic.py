import os
from pathlib import Path
from PySide6.QtCore import QObject, Signal

try:
    from pypdf import PdfWriter, PdfReader
    PYPDF_AVAILABLE = True
except ImportError:
    PYPDF_AVAILABLE = False

# --- COLORES ---
COLOR_INFO = "#5DADE2"
COLOR_SUCCESS = "#2ECC71"
COLOR_WARNING = "#F39C12"
COLOR_ERROR = "#E74C3C"
COLOR_DEFAULT = "#ECF0F1"

class EpicrisisAdresWorker(QObject):
    progreso_actualizado = Signal(str)
    proceso_finalizado = Signal(dict)

    def __init__(self, parametros, modo="unir"):
        super().__init__()
        self.parametros = parametros
        self.modo = modo
        self.esta_cancelado = False

    def cancelar(self):
        self.esta_cancelado = True

    def ejecutar(self):
        if not PYPDF_AVAILABLE:
            self.proceso_finalizado.emit({'error': "Error: Instala pypdf ejecutando: pip install pypdf"})
            return

        try:
            if self.modo == "unir":
                self._unificar_solo_epicris()
            elif self.modo == "limpieza_total":
                self._limpieza_total_extrema()
            elif self.modo == "limpieza_automatica":
                self._limpieza_automatica_subcarpetas()
            else:
                self.proceso_finalizado.emit({'error': f"Modo desconocido: {self.modo}"})
        except Exception as e:
            self.proceso_finalizado.emit({'error': str(e)})

    def _unificar_solo_epicris(self):
        lista_ids = self.parametros.get('lista_ids', [])
        ruta_rta = self.parametros.get('ruta_respuestas')
        ruta_sop = self.parametros.get('ruta_soportes')
        
        self.progreso_actualizado.emit(f"<p style='color:{COLOR_INFO};'>Iniciando UNION de RTA a EPICRIS para {len(lista_ids)} IDs...</p>")

        for fid in lista_ids:
            if self.esta_cancelado: return self.proceso_finalizado.emit({'estado': 'cancelado'})
            
            # Búsqueda manual para ignorar mayúsculas/minúsculas en extensión (Windows/Linux safe)
            archivo_rta = None
            for root, dirs, files in os.walk(ruta_rta):
                for f in files:
                    if fid.lower() in f.lower() and f.lower().endswith(".pdf"):
                        archivo_rta = os.path.join(root, f)
                        break
                if archivo_rta: break

            if not archivo_rta:
                self.progreso_actualizado.emit(f"<p style='color:{COLOR_WARNING};'>[!] No existe respuesta para {fid} en {ruta_rta}</p>")
                continue

            soportes = []
            for root, dirs, files in os.walk(ruta_sop):
                for f in files:
                    if f"_{fid}_" in f and "EPICRIS" in f.upper() and f.lower().endswith(".pdf"):
                        soportes.append(os.path.join(root, f))
            
            if not soportes:
                self.progreso_actualizado.emit(f"<p style='color:{COLOR_WARNING};'>[!] No se encontraron soportes EPICRIS válidos para {fid}</p>")

            for s_path in soportes:
                try:
                    s_name = os.path.basename(s_path)
                    if os.path.abspath(s_path) == os.path.abspath(archivo_rta): continue
                    m = PdfWriter()
                    m.append(archivo_rta)
                    m.append(str(s_path))
                    with open(str(s_path) + ".tmp", "wb") as f: m.write(f)
                    m.close()
                    os.replace(str(s_path) + ".tmp", str(s_path))
                    self.progreso_actualizado.emit(f"<p style='color:{COLOR_SUCCESS};'>[OK] Rta pegada en EPICRIS: {s_name}</p>")
                except Exception as e:
                    self.progreso_actualizado.emit(f"<p style='color:{COLOR_ERROR};'>[ERROR] {e} en org. {s_name}</p>")

        self.proceso_finalizado.emit({'estado': 'completado'})

    def _limpieza_total_extrema(self):
        lista_ids = self.parametros.get('lista_ids', [])
        ruta_rta = self.parametros.get('ruta_respuestas')
        ruta_sop = self.parametros.get('ruta_soportes')

        self.progreso_actualizado.emit(f"<p style='color:{COLOR_INFO};'>Iniciando LIMPIEZA TOTAL por ID...</p>")

        for fid in lista_ids:
            if self.esta_cancelado: return self.proceso_finalizado.emit({'estado': 'cancelado'})
            
            archivo_rta = next((str(f) for f in Path(ruta_rta).rglob(f"*{fid}*.pdf")), None)
            if not archivo_rta:
                self.progreso_actualizado.emit(f"<p style='color:{COLOR_WARNING};'>[!] Sin rta original para medir. Saltando {fid}</p>")
                continue
            
            paginas_rta = len(PdfReader(archivo_rta).pages)
            archivos_a_limpiar = list(Path(ruta_sop).rglob(f"*{fid}*.pdf"))

            for path_pdf in archivos_a_limpiar:
                if self.esta_cancelado: return self.proceso_finalizado.emit({'estado': 'cancelado'})
                if os.path.abspath(path_pdf) == os.path.abspath(archivo_rta): continue

                try:
                    reader = PdfReader(str(path_pdf))
                    total = len(reader.pages)

                    if total > paginas_rta:
                        texto_pdf = (reader.pages[0].extract_text() or "")[:500]
                        texto_rta = (PdfReader(archivo_rta).pages[0].extract_text() or "")[:500]
                        
                        if texto_pdf == texto_rta:
                            writer = PdfWriter()
                            for i in range(paginas_rta, total):
                                writer.add_page(reader.pages[i])
                            temp = str(path_pdf) + ".tmp"
                            with open(temp, "wb") as f: writer.write(f)
                            os.replace(temp, str(path_pdf))
                            self.progreso_actualizado.emit(f"<p style='color:{COLOR_SUCCESS};'>[LIMPIO] {path_pdf.name} (coincidencia confirmada)</p>")
                        else:
                            self.progreso_actualizado.emit(f"<p style='color:{COLOR_WARNING};'>[SKIP] {path_pdf.name}: Contenido distinto.</p>")
                except Exception as e:
                    self.progreso_actualizado.emit(f"<p style='color:{COLOR_ERROR};'>[ERROR] En {path_pdf.name}: {e}</p>")

        self.proceso_finalizado.emit({'estado': 'completado'})

    def _limpieza_automatica_subcarpetas(self):
        ruta_raiz = self.parametros.get('ruta_raiz')
        
        self.progreso_actualizado.emit(f"<p style='color:{COLOR_INFO};'>Iniciando LIMPIEZA AUTOMATICA POR CARPETAS...</p>")

        if not os.path.isdir(ruta_raiz):
            return self.proceso_finalizado.emit({'error': f"Error: '{ruta_raiz}' no es un directorio válido."})

        carpetas = [d for d in Path(ruta_raiz).iterdir() if d.is_dir() and d.name.upper() not in ["VALIDACION", "VALIDADORECAT_2026"]]
        
        for carpeta in carpetas:
            if self.esta_cancelado: return self.proceso_finalizado.emit({'estado': 'cancelado'})
            fid = carpeta.name
            
            archivos_pdf = [f for f in carpeta.iterdir() if f.is_file() and f.name.lower().endswith(".pdf")]
            nombres_validos = [f"coex{fid.lower()}.pdf", f"fecr{fid.lower()}.pdf", f"{fid.lower()}.pdf"]
            
            archivo_rta = next((f for f in archivos_pdf if f.name.lower() in nombres_validos), None)
            archivo_epi = next((f for f in archivos_pdf if "epicris" in f.name.lower()), None)

            if archivo_rta and archivo_epi:
                try:
                    reader_rta = PdfReader(str(archivo_rta))
                    paginas_rta = len(reader_rta.pages)
                    
                    reader_epi = PdfReader(str(archivo_epi))
                    total_epi = len(reader_epi.pages)

                    if total_epi > paginas_rta:
                        texto_rta_pag1 = (reader_rta.pages[0].extract_text() or "")[:500]
                        texto_epi_pag1 = (reader_epi.pages[0].extract_text() or "")[:500]

                        if texto_rta_pag1 == texto_epi_pag1:
                            writer = PdfWriter()
                            for i in range(paginas_rta, total_epi):
                                writer.add_page(reader_epi.pages[i])
                            
                            temp = str(archivo_epi) + ".tmp"
                            with open(temp, "wb") as f: writer.write(f)
                            os.replace(temp, str(archivo_epi))
                            self.progreso_actualizado.emit(f"<p style='color:{COLOR_SUCCESS};'>[LIMPIO] {archivo_epi.name} (se quitaron {paginas_rta} págs)</p>")
                        else:
                            self.progreso_actualizado.emit(f"<p style='color:{COLOR_WARNING};'>[SKIP] {archivo_epi.name}: El primer txt no coincide con {archivo_rta.name}</p>")
                    else:
                        self.progreso_actualizado.emit(f"<p style='color:{COLOR_WARNING};'>[INFO] {archivo_epi.name} tiene menos páginas que {archivo_rta.name}. Se omite.</p>")
                except Exception as e:
                    self.progreso_actualizado.emit(f"<p style='color:{COLOR_ERROR};'>[ERROR] {e} en carpeta {fid}</p>")
            else:
                if not archivo_rta: self.progreso_actualizado.emit(f"<p style='color:{COLOR_WARNING};'>[!] Rta falante en la carpeta {fid}</p>")
                if not archivo_epi: self.progreso_actualizado.emit(f"<p style='color:{COLOR_WARNING};'>[!] Epicris faltante en la carpeta {fid}</p>")

        self.proceso_finalizado.emit({'estado': 'completado'})

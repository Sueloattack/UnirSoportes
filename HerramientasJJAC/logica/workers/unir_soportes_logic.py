# logica/logica_unir_soportes.py
import os
import re
from PySide6.QtCore import QObject, Signal

# Importamos los módulos de la nueva estructura
from logica.core import gestor_archivos
from logica.core import identificador_archivos
from logica.core import procesador_pdf

class UnirSoportesWorker(QObject):
    """
    Clase que ejecuta la lógica de negocio en un hilo de trabajo para no bloquear la GUI.
    Emite señales para comunicar el progreso y los resultados.
    """
    progreso_actualizado = Signal(str, float)
    proceso_finalizado = Signal(dict)
    barra_progreso_actualizada = Signal(float)

    def __init__(self, ruta_carpeta_raiz, modo, solo_soportes=False):
        super().__init__()
        self.ruta_carpeta_raiz = ruta_carpeta_raiz
        self.modo = modo
        self.solo_soportes = solo_soportes
        self.esta_cancelado = False
        # Paleta de colores para logs HTML
        self.color_texto = "#ecf0f1"
        self.color_exito = "#2ecc71"
        self.color_error = "#e74c3c"
        self.color_advertencia = "#f39c12"
        self.color_info = "#3498db"

    def ejecutar(self):
        """
        Función principal que orquesta el proceso. Será llamada por el hilo.
        """
        resultados = {'exitosos': [], 'fallidos': []}
        
        subcarpetas = gestor_archivos.listar_subdirectorios(self.ruta_carpeta_raiz)
        subcarpetas.sort(key=lambda path: self._extraer_numero_de_cadena(os.path.basename(path)))

        if not subcarpetas:
            mensaje = "Error: No se encontraron subcarpetas para procesar."
            resultados['fallidos'].append({"carpeta": "N/A", "razon": mensaje})
            self.proceso_finalizado.emit(resultados)
            return

        total_carpetas = len(subcarpetas)
        for i, ruta_carpeta in enumerate(subcarpetas):
            if self.esta_cancelado:
                resultados['fallidos'].append({"carpeta": "N/A", "razon": "Proceso cancelado por el usuario."})
                break
            
            nombre_carpeta = os.path.basename(ruta_carpeta)
            porcentaje = (i + 1) / total_carpetas * 100
            
            self.progreso_actualizado.emit(nombre_carpeta, porcentaje)
            self.barra_progreso_actualizada.emit(porcentaje)
            
            self._procesar_carpeta(ruta_carpeta, nombre_carpeta, resultados)

        self.proceso_finalizado.emit(resultados)

    def _procesar_carpeta(self, ruta_carpeta, nombre_carpeta, resultados):
        """Refactorizado para procesar una carpeta y devolver el resultado como HTML."""
        try:
            if self.modo == "ADRES":
                self._procesar_carpeta_adres(ruta_carpeta, nombre_carpeta, resultados)
            else:  # "Aseguradoras"
                self._procesar_carpeta_aseguradoras(ruta_carpeta, nombre_carpeta, resultados)
        except Exception as e:
            resultados['fallidos'].append({"carpeta": nombre_carpeta, "razon": f"Error inesperado: {e}"})

    def cancelar(self):
        self.esta_cancelado = True

    def _extraer_numero_de_cadena(self, s):
        """Extrae el primer número de una cadena. Usado para ordenar carpetas."""
        match = re.search(r'\d+', s)
        return int(match.group()) if match else 99999999

    def _procesar_carpeta_aseguradoras(self, ruta_carpeta, nombre_carpeta, resultados):
        """Procesa una única carpeta para el modo Aseguradoras."""
        archivos_pdf = gestor_archivos.obtener_archivos_pdf(ruta_carpeta)
        if not archivos_pdf:
            return

        documentos = identificador_archivos.identificar_documentos_aseguradoras(archivos_pdf, ruta_carpeta)
        
        carta_glosa = documentos['carta_glosa']
        respuesta_glosa = documentos['respuesta_glosa']
        soportes = documentos['soportes']

        # MODO SOLO SOPORTES
        if self.solo_soportes:
            if not respuesta_glosa:
                resultados['fallidos'].append({"carpeta": nombre_carpeta, "razon": "No se encontró la Respuesta Glosa (archivo destino)."})
                return
            
            # Verificar qué soportes ya están unidos
            soportes_faltantes = []
            for soporte in soportes:
                try:
                    ya_unido = procesador_pdf.verificar_fusion_por_contenido(
                        ruta_pdf_destino=respuesta_glosa['path'],
                        ruta_pdf_fuente=soporte
                    )
                    if not ya_unido:
                        soportes_faltantes.append(soporte)
                except Exception:
                    soportes_faltantes.append(soporte)  # Si hay error, asumir que falta
            
            if not soportes_faltantes:
                mensaje = f"Todos los {len(soportes)} soportes ya están unidos."
                resultados['exitosos'].append({"carpeta": nombre_carpeta, "razon": mensaje})
                return
            
            # Unir solo los soportes faltantes
            try:
                soportes_faltantes.sort()
                procesador_pdf.fusionar_pdfs_en_destino(
                    ruta_pdf_destino=respuesta_glosa['path'],
                    rutas_pdf_fuentes=soportes_faltantes
                )
                ya_unidos = len(soportes) - len(soportes_faltantes)
                mensaje = f"✅ {ya_unidos} soportes ya unidos, {len(soportes_faltantes)} soportes agregados."
                resultados['exitosos'].append({"carpeta": nombre_carpeta, "razon": mensaje})
            except Exception as e:
                razon = f"Error al unir soportes: {e}"
                resultados['fallidos'].append({"carpeta": nombre_carpeta, "razon": razon})
            return

        # MODO NORMAL (con Carta Glosa)
        if not carta_glosa:
            resultados['fallidos'].append({"carpeta": nombre_carpeta, "razon": "No se encontró la Carta Glosa."})
            return

        if not respuesta_glosa:
            resultados['fallidos'].append({"carpeta": nombre_carpeta, "razon": "No se encontró la Respuesta Glosa."})
            return
            
        if respuesta_glosa['type'] == 'VERIFICABLE':
            if (carta_glosa['serie'] != respuesta_glosa['serie'] or
                carta_glosa['numero'] != respuesta_glosa['numero']):
                razon = f"Discrepancia Serie/Número. Carta: {carta_glosa['serie']}-{carta_glosa['numero']}, Respuesta: {respuesta_glosa['serie']}-{respuesta_glosa['numero']}"
                resultados['fallidos'].append({"carpeta": nombre_carpeta, "razon": razon})
                return
                
        try:
            ya_procesado = procesador_pdf.verificar_fusion_por_contenido(
                ruta_pdf_destino=respuesta_glosa['path'],
                ruta_pdf_fuente=carta_glosa['path']
            )
            if ya_procesado:
                mensaje = "Validación de contenido correcta. La Carta Glosa ya está unida."
                resultados['exitosos'].append({"carpeta": nombre_carpeta, "razon": mensaje})
                return
        except Exception as e:
            razon = f"Error al verificar el contenido del archivo: {e}"
            resultados['fallidos'].append({"carpeta": nombre_carpeta, "razon": razon})
            return
            
        archivos_a_fusionar = [carta_glosa['path']] + soportes
        archivos_a_fusionar.sort()

        try:
            procesador_pdf.fusionar_pdfs_en_destino(
                ruta_pdf_destino=respuesta_glosa['path'],
                rutas_pdf_fuentes=archivos_a_fusionar
            )
            mensaje = f"¡Unión exitosa! Se anexó la Carta Glosa y {len(soportes)} soporte(s)."
            resultados['exitosos'].append({"carpeta": nombre_carpeta, "razon": mensaje})
        except Exception as e:
            razon = f"Error crítico al intentar unir los PDFs: {e}"
            resultados['fallidos'].append({"carpeta": nombre_carpeta, "razon": razon})

    def _procesar_carpeta_adres(self, ruta_carpeta, nombre_carpeta, resultados):
        """Procesa una única carpeta según las reglas de ADRES."""
        archivos_pdf = gestor_archivos.obtener_archivos_pdf(ruta_carpeta)
        if not archivos_pdf:
            return

        documentos = identificador_archivos.identificar_documentos_adres(archivos_pdf, ruta_carpeta)
        
        epicrisis = documentos['epicrisis']
        respuesta_glosa = documentos['respuesta_glosa']
        soportes = documentos['soportes']

        # MODO SOLO SOPORTES
        if self.solo_soportes:
            if not epicrisis:
                resultados['fallidos'].append({"carpeta": nombre_carpeta, "razon": "Modo ADRES: No se encontró el archivo de Epicrisis (archivo destino)."})
                return
            
            # Verificar qué soportes ya están unidos
            soportes_faltantes = []
            for soporte in soportes:
                try:
                    ya_unido = procesador_pdf.verificar_fusion_por_contenido(
                        ruta_pdf_destino=epicrisis['path'],
                        ruta_pdf_fuente=soporte
                    )
                    if not ya_unido:
                        soportes_faltantes.append(soporte)
                except Exception:
                    soportes_faltantes.append(soporte)  # Si hay error, asumir que falta
            
            if not soportes_faltantes:
                mensaje = f"Todos los {len(soportes)} soportes ya están unidos a la Epicrisis."
                resultados['exitosos'].append({"carpeta": nombre_carpeta, "razon": mensaje})
                return
            
            # Unir solo los soportes faltantes
            try:
                soportes_faltantes.sort()
                procesador_pdf.fusionar_pdfs_en_destino(
                    ruta_pdf_destino=epicrisis['path'],
                    rutas_pdf_fuentes=soportes_faltantes
                )
                ya_unidos = len(soportes) - len(soportes_faltantes)
                mensaje = f"✅ {ya_unidos} soportes ya unidos, {len(soportes_faltantes)} soportes agregados a Epicrisis."
                resultados['exitosos'].append({"carpeta": nombre_carpeta, "razon": mensaje})
            except Exception as e:
                razon = f"Error al unir soportes a Epicrisis: {e}"
                resultados['fallidos'].append({"carpeta": nombre_carpeta, "razon": razon})
            return

        # MODO NORMAL (con Respuesta Glosa)
        if not epicrisis:
            resultados['fallidos'].append({"carpeta": nombre_carpeta, "razon": "Modo ADRES: No se encontró el archivo de Epicrisis."})
            return

        if not respuesta_glosa:
            resultados['fallidos'].append({"carpeta": nombre_carpeta, "razon": "Modo ADRES: No se encontró el archivo de Respuesta Glosa."})
            return
            
        if procesador_pdf.verificar_fusion_por_contenido(
            ruta_pdf_destino=epicrisis['path'], 
            ruta_pdf_fuente=respuesta_glosa['path']
        ):
            mensaje = "Validación correcta. La Respuesta Glosa ya parece estar unida a la Epicrisis."
            resultados['exitosos'].append({"carpeta": nombre_carpeta, "razon": mensaje})
            return
            
        try:
            escritor = procesador_pdf.pypdf.PdfWriter()

            lector_respuesta = procesador_pdf.pypdf.PdfReader(respuesta_glosa['path'])
            for pagina in lector_respuesta.pages:
                escritor.add_page(pagina)

            lector_epicrisis = procesador_pdf.pypdf.PdfReader(epicrisis['path'])
            for pagina in lector_epicrisis.pages:
                escritor.add_page(pagina)
            
            soportes.sort()
            for ruta_soporte in soportes:
                lector_soporte = procesador_pdf.pypdf.PdfReader(ruta_soporte)
                for pagina in lector_soporte.pages:
                    escritor.add_page(pagina)

            ruta_salida = procesador_pdf.normalizar_ruta_pdf(epicrisis['path'])
            with open(ruta_salida, 'wb') as archivo_salida:
                escritor.write(archivo_salida)
            
            # Si el nombre cambió (por la extensión), el original ya no es "epicrisis['path']" 
            # pero en este flujo ADRES estamos sobrescribiendo la epicrisis original.
            # Si la extensión cambió, eliminamos el .PDF antiguo.
            if ruta_salida != epicrisis['path'] and os.path.exists(epicrisis['path']):
                try:
                    os.remove(epicrisis['path'])
                except Exception:
                    pass

            mensaje = f"¡Unión ADRES exitosa! Se unió Respuesta + Epicrisis + {len(soportes)} soporte(s) en '{os.path.basename(ruta_salida)}'."
            resultados['exitosos'].append({"carpeta": nombre_carpeta, "razon": mensaje})

        except Exception as e:
            razon = f"Error crítico al intentar unir los PDFs en modo ADRES: {e}"
            resultados['fallidos'].append({"carpeta": nombre_carpeta, "razon": razon})

# logica/workers/renombrador_logic.py
import os
from PySide6.QtCore import QObject, Signal

from logica.core import gestor_archivos, identificador_archivos

class RenombradorWorker(QObject):
    """
    Lógica de negocio para el renombrado de archivos en un hilo de trabajo.
    """
    progreso_actualizado = Signal(str, float)
    proceso_finalizado = Signal(dict)
    barra_progreso_actualizada = Signal(float)

    def __init__(self, ruta_carpeta_raiz, modo):
        super().__init__()
        self.ruta_carpeta_raiz = ruta_carpeta_raiz
        self.modo = modo # 'escolar', 'devolucion', 'glosa'
        self.esta_cancelado = False

    def ejecutar(self):
        """
        Orquesta el proceso de renombrado según el modo seleccionado.
        """
        if self.modo == 'escolar':
            self.renombrar_escolares()
        elif self.modo == 'glosa':
            self.renombrar_glosa()
        elif self.modo == 'devolucion':
            self.renombrar_devolucion()
        elif self.modo == 'revertir_escolar':
            self.revertir_renombrado_escolares()
        else:
            resultados = {'exitosos': [], 'fallidos': [{'carpeta': 'N/A', 'razon': f"Modo '{self.modo}' no implementado."}]}
            self.proceso_finalizado.emit(resultados)

    def renombrar_glosa(self):
        """
        Lógica específica para el renombrado de 'respuestas glosa' en modo glosa.
        """
        resultados = {'exitosos': [], 'fallidos': []}
        subcarpetas = gestor_archivos.listar_subdirectorios(self.ruta_carpeta_raiz)

        if not subcarpetas:
            resultados['fallidos'].append({"carpeta": "N/A", "razon": "No se encontraron subcarpetas."})
            self.proceso_finalizado.emit(resultados)
            return

        total_carpetas = len(subcarpetas)
        for i, ruta_carpeta in enumerate(subcarpetas):
            if self.esta_cancelado:
                resultados['fallidos'].append({"carpeta": "N/A", "razon": "Proceso cancelado."})
                break
            
            nombre_carpeta = os.path.basename(ruta_carpeta)
            porcentaje = (i + 1) / total_carpetas * 100
            self.progreso_actualizado.emit(nombre_carpeta, porcentaje)
            self.barra_progreso_actualizada.emit(porcentaje)

            try:
                archivos_pdf = gestor_archivos.obtener_archivos_pdf(ruta_carpeta)
                if not archivos_pdf:
                    continue

                documentos = identificador_archivos.identificar_documentos_aseguradoras(archivos_pdf, ruta_carpeta)
                
                carta_glosa = documentos.get('carta_glosa')
                respuesta_glosa = documentos.get('respuesta_glosa')

                if carta_glosa and respuesta_glosa:
                    ruta_a_renombrar = respuesta_glosa['path']
                    nombre_respuesta_original = os.path.basename(ruta_a_renombrar)

                    if nombre_respuesta_original.startswith('R-8002098917-'):
                        resultados['fallidos'].append({"carpeta": nombre_carpeta, "razon": f"El archivo ya parece estar renombrado: {nombre_respuesta_original}"})
                        continue

                    nuevo_nombre = f"R-8002098917-{nombre_respuesta_original}"
                    nueva_ruta = os.path.join(os.path.dirname(ruta_a_renombrar), nuevo_nombre)
                    
                    os.rename(ruta_a_renombrar, nueva_ruta)
                    
                    mensaje = f"Renombrado: {nombre_respuesta_original} -> {nuevo_nombre}"
                    resultados['exitosos'].append({"carpeta": nombre_carpeta, "razon": mensaje})

            except Exception as e:
                resultados['fallidos'].append({"carpeta": nombre_carpeta, "razon": f"Error inesperado: {e}"})

        self.proceso_finalizado.emit(resultados)
    def renombrar_devolucion(self):
        """
        Lógica específica para el renombrado de 'cartas glosa' en modo devolución.
        """
        resultados = {'exitosos': [], 'fallidos': []}
        subcarpetas = gestor_archivos.listar_subdirectorios(self.ruta_carpeta_raiz)

        if not subcarpetas:
            resultados['fallidos'].append({"carpeta": "N/A", "razon": "No se encontraron subcarpetas."})
            self.proceso_finalizado.emit(resultados)
            return

        total_carpetas = len(subcarpetas)
        for i, ruta_carpeta in enumerate(subcarpetas):
            if self.esta_cancelado:
                resultados['fallidos'].append({"carpeta": "N/A", "razon": "Proceso cancelado."})
                break
            
            nombre_carpeta = os.path.basename(ruta_carpeta)
            porcentaje = (i + 1) / total_carpetas * 100
            self.progreso_actualizado.emit(nombre_carpeta, porcentaje)
            self.barra_progreso_actualizada.emit(porcentaje)

            try:
                archivos_pdf = gestor_archivos.obtener_archivos_pdf(ruta_carpeta)
                if not archivos_pdf:
                    continue

                documentos = identificador_archivos.identificar_documentos_aseguradoras(archivos_pdf, ruta_carpeta)
                
                carta_glosa = documentos.get('carta_glosa')
                respuesta_glosa = documentos.get('respuesta_glosa')

                if carta_glosa and respuesta_glosa:
                    ruta_a_renombrar = respuesta_glosa['path']
                    nombre_respuesta_original = os.path.basename(ruta_a_renombrar)

                    # Evitar renombrar múltiples veces
                    if nombre_respuesta_original.startswith('8002098917-'):
                        resultados['fallidos'].append({"carpeta": nombre_carpeta, "razon": f"El archivo ya parece estar renombrado: {nombre_respuesta_original}"})
                        continue

                    nuevo_nombre = f"8002098917-{nombre_respuesta_original}"
                    nueva_ruta = os.path.join(os.path.dirname(ruta_a_renombrar), nuevo_nombre)
                    
                    os.rename(ruta_a_renombrar, nueva_ruta)
                    
                    mensaje = f"Renombrado: {nombre_respuesta_original} -> {nuevo_nombre}"
                    resultados['exitosos'].append({"carpeta": nombre_carpeta, "razon": mensaje})

            except Exception as e:
                resultados['fallidos'].append({"carpeta": nombre_carpeta, "razon": f"Error inesperado: {e}"})

        self.proceso_finalizado.emit(resultados)

    def revertir_renombrado_escolares(self):
        """
        Lógica para revertir nombres de archivo que terminan en _PRG_1.
        """
        resultados = {'exitosos': [], 'fallidos': []}
        subcarpetas = gestor_archivos.listar_subdirectorios(self.ruta_carpeta_raiz)

        if not subcarpetas:
            resultados['fallidos'].append({"carpeta": "N/A", "razon": "No se encontraron subcarpetas."})
            self.proceso_finalizado.emit(resultados)
            return

        total_carpetas = len(subcarpetas)
        for i, ruta_carpeta in enumerate(subcarpetas):
            if self.esta_cancelado:
                resultados['fallidos'].append({"carpeta": "N/A", "razon": "Proceso cancelado."})
                break
            
            nombre_carpeta = os.path.basename(ruta_carpeta)
            porcentaje = (i + 1) / total_carpetas * 100
            self.progreso_actualizado.emit(nombre_carpeta, porcentaje)
            self.barra_progreso_actualizada.emit(porcentaje)

            try:
                archivos = os.listdir(ruta_carpeta)
                for nombre_archivo in archivos:
                    if '_PRG_1' in nombre_archivo:
                        ruta_original = os.path.join(ruta_carpeta, nombre_archivo)
                        nuevo_nombre = nombre_archivo.replace('_PRG_1', '')
                        nueva_ruta = os.path.join(ruta_carpeta, nuevo_nombre)
                        
                        os.rename(ruta_original, nueva_ruta)
                        
                        mensaje = f"Revertido: {nombre_archivo} -> {nuevo_nombre}"
                        resultados['exitosos'].append({"carpeta": nombre_carpeta, "razon": mensaje})

            except Exception as e:
                resultados['fallidos'].append({"carpeta": nombre_carpeta, "razon": f"Error inesperado al revertir: {e}"})

        self.proceso_finalizado.emit(resultados)

    def renombrar_escolares(self):
        """
        Lógica específica para el renombrado de 'cartas glosa' en modo escolar.
        """
        resultados = {'exitosos': [], 'fallidos': []}
        subcarpetas = gestor_archivos.listar_subdirectorios(self.ruta_carpeta_raiz)

        if not subcarpetas:
            resultados['fallidos'].append({"carpeta": "N/A", "razon": "No se encontraron subcarpetas."})
            self.proceso_finalizado.emit(resultados)
            return

        total_carpetas = len(subcarpetas)
        for i, ruta_carpeta in enumerate(subcarpetas):
            if self.esta_cancelado:
                resultados['fallidos'].append({"carpeta": "N/A", "razon": "Proceso cancelado."})
                break
            
            nombre_carpeta = os.path.basename(ruta_carpeta)
            porcentaje = (i + 1) / total_carpetas * 100
            self.progreso_actualizado.emit(nombre_carpeta, porcentaje)
            self.barra_progreso_actualizada.emit(porcentaje)

            try:
                archivos_pdf = gestor_archivos.obtener_archivos_pdf(ruta_carpeta)
                if not archivos_pdf:
                    continue

                documentos = identificador_archivos.identificar_documentos_aseguradoras(archivos_pdf, ruta_carpeta)
                
                carta_glosa = documentos.get('carta_glosa')
                respuesta_glosa = documentos.get('respuesta_glosa')

                if carta_glosa and respuesta_glosa:
                    ruta_original = respuesta_glosa['path']
                    nombre_base, extension = os.path.splitext(ruta_original)
                    
                    # Evitar renombrar múltiples veces
                    if nombre_base.endswith('_PRG_1'):
                        resultados['fallidos'].append({"carpeta": nombre_carpeta, "razon": f"El archivo ya está renombrado: {os.path.basename(ruta_original)}"})
                        continue

                    nueva_ruta = f"{nombre_base}_PRG_1{extension}"
                    
                    os.rename(ruta_original, nueva_ruta)
                    
                    mensaje = f"Renombrado: {os.path.basename(ruta_original)} -> {os.path.basename(nueva_ruta)}"
                    resultados['exitosos'].append({"carpeta": nombre_carpeta, "razon": mensaje})

            except Exception as e:
                resultados['fallidos'].append({"carpeta": nombre_carpeta, "razon": f"Error inesperado: {e}"})

        self.proceso_finalizado.emit(resultados)

    def cancelar(self):
        self.esta_cancelado = True

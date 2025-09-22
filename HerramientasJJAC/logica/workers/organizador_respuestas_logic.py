# logica/logica_organizar_pdfs.py
import os
import shutil
import re
from PySide6.QtCore import QObject, Signal

class OrganizadorRespuestasWorker(QObject):
    """
    Clase que ejecuta la lógica de negocio para organizar PDFs en un hilo de trabajo.
    """
    progreso_actualizado = Signal(str, float)
    proceso_finalizado = Signal(dict)

    def __init__(self, carpeta_raiz, carpeta_respuestas, mover_archivos=True):
        super().__init__()
        self.carpeta_raiz = carpeta_raiz
        self.carpeta_respuestas = carpeta_respuestas
        self.mover_archivos = mover_archivos
        self.esta_cancelado = False

    def ejecutar(self):
        """
        Función principal que orquesta el proceso.
        """
        resultados = {'exitosos': [], 'fallidos': [], 'sobrantes': []}
        
        accion_verbo = "Moviendo" if self.mover_archivos else "Copiando"

        try:
            respuestas_disponibles = []
            for filename in os.listdir(self.carpeta_respuestas):
                filepath = os.path.join(self.carpeta_respuestas, filename)
                if os.path.isfile(filepath):
                    info = self._extraer_info_respuesta(filename)
                    if info:
                        respuestas_disponibles.append({'nombre': filename, **info})
            
            total_respuestas = len(respuestas_disponibles)
            for i, respuesta_info in enumerate(list(respuestas_disponibles)):
                if self.esta_cancelado:
                    break

                numero_respuesta = respuesta_info['numero']
                nombre_respuesta = respuesta_info['nombre']
                
                ruta_carpeta_destino = os.path.join(self.carpeta_raiz, numero_respuesta)

                porcentaje = (i + 1) / total_respuestas * 100
                self.progreso_actualizado.emit(f"Procesando {nombre_respuesta}...", porcentaje)

                if os.path.isdir(ruta_carpeta_destino):
                    origen_path = os.path.join(self.carpeta_respuestas, nombre_respuesta)
                    destino_path = os.path.join(ruta_carpeta_destino, nombre_respuesta)
                    
                    try:
                        if self.mover_archivos:
                            shutil.move(origen_path, destino_path)
                        else:
                            shutil.copy2(origen_path, destino_path)
                        
                        resultados['exitosos'].append({'respuesta': nombre_respuesta, 'carpeta_destino': numero_respuesta})
                        respuestas_disponibles.remove(respuesta_info)

                    except Exception as e:
                        resultados['fallidos'].append({'respuesta': nombre_respuesta, 'razon': str(e)})
                else:
                    # Esta respuesta no tiene carpeta de destino, se considera "sobrante"
                    pass
            
            resultados['sobrantes'] = respuestas_disponibles

        except Exception as e:
            resultados['fallidos'].append({'respuesta': 'General', 'razon': f'Error crítico durante la ejecución: {e}'})

        self.proceso_finalizado.emit(resultados)

    def cancelar(self):
        self.esta_cancelado = True

    def _extraer_info_respuesta(self, nombre_archivo):
        """
        Extrae la información únicamente de un archivo de respuesta simple.
        Ej: 'FERD158.PDF' -> {'serie': 'FERD', 'numero': '158'}
        """
        base_nombre, _ = os.path.splitext(nombre_archivo)
        match = re.match(r'^(COEX|FECR|FERD|FERR)([0-9]+)$', base_nombre, re.IGNORECASE)
        if match:
            serie = match.group(1).upper()
            numero = match.group(2)
            return {"serie": serie, "numero": numero}
        return None

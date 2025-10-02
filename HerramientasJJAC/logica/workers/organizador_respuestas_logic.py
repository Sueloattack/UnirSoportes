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
        Función principal que orquesta el proceso, con lógica mejorada para encontrar carpetas de destino.
        """
        resultados = {'exitosos': [], 'fallidos': [], 'sobrantes': []}
        
        try:
            # 1. Obtener todas las respuestas disponibles
            respuestas_disponibles = []
            for filename in os.listdir(self.carpeta_respuestas):
                filepath = os.path.join(self.carpeta_respuestas, filename)
                if os.path.isfile(filepath):
                    info = self._extraer_info_respuesta(filename)
                    if info:
                        respuestas_disponibles.append({'nombre': filename, **info})

            # 2. Obtener todas las subcarpetas de la carpeta raíz
            subcarpetas_raiz = [d for d in os.listdir(self.carpeta_raiz) if os.path.isdir(os.path.join(self.carpeta_raiz, d))]

            # 3. Procesar cada respuesta
            total_respuestas = len(respuestas_disponibles)
            respuestas_procesadas = set()

            for i, respuesta_info in enumerate(respuestas_disponibles):
                if self.esta_cancelado:
                    break

                numero_respuesta = respuesta_info['numero']
                nombre_respuesta = respuesta_info['nombre']
                
                porcentaje = (i + 1) / total_respuestas * 100
                self.progreso_actualizado.emit(f"Buscando destino para {nombre_respuesta}...", porcentaje)

                # 4. Búsqueda flexible de la carpeta de destino
                posibles_carpetas = []
                for nombre_subcarpeta in subcarpetas_raiz:
                    if nombre_subcarpeta == numero_respuesta:
                        posibles_carpetas.append(nombre_subcarpeta)
                    elif nombre_subcarpeta.startswith(numero_respuesta):
                        # Validar que no sea un número más largo (ej. '123' vs '1234')
                        if len(nombre_subcarpeta) > len(numero_respuesta):
                            siguiente_char = nombre_subcarpeta[len(numero_respuesta)]
                            if not siguiente_char.isdigit():
                                posibles_carpetas.append(nombre_subcarpeta)
                
                # 5. Evaluar resultados de la búsqueda
                if len(posibles_carpetas) == 1:
                    nombre_carpeta_destino = posibles_carpetas[0]
                    ruta_carpeta_destino = os.path.join(self.carpeta_raiz, nombre_carpeta_destino)
                    
                    origen_path = os.path.join(self.carpeta_respuestas, nombre_respuesta)
                    destino_path = os.path.join(ruta_carpeta_destino, nombre_respuesta)
                    
                    try:
                        if self.mover_archivos:
                            shutil.move(origen_path, destino_path)
                        else:
                            shutil.copy2(origen_path, destino_path)
                        
                        resultados['exitosos'].append({'respuesta': nombre_respuesta, 'carpeta_destino': nombre_carpeta_destino})
                        respuestas_procesadas.add(nombre_respuesta)

                    except Exception as e:
                        resultados['fallidos'].append({'respuesta': nombre_respuesta, 'razon': f"Error al mover/copiar: {e}"})
                        respuestas_procesadas.add(nombre_respuesta)
                
                elif len(posibles_carpetas) > 1:
                    razon = f"Ambigüedad: Se encontraron múltiples carpetas de destino: {', '.join(posibles_carpetas)}"
                    resultados['fallidos'].append({'respuesta': nombre_respuesta, 'razon': razon})
                    respuestas_procesadas.add(nombre_respuesta)
                
                # Si len(posibles_carpetas) == 0, no se hace nada y quedará como sobrante.

            # 6. Determinar las respuestas sobrantes
            nombres_respuestas_disponibles = {r['nombre'] for r in respuestas_disponibles}
            sobrantes_nombres = nombres_respuestas_disponibles - respuestas_procesadas
            resultados['sobrantes'] = [r for r in respuestas_disponibles if r['nombre'] in sobrantes_nombres]

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

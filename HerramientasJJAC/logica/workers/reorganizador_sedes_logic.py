# logica/logica_envios.py
import os
import shutil
import re
from PySide6.QtCore import QObject, Signal

class ReorganizadorSedesWorker(QObject):
    progreso_actualizado = Signal(str, float)
    proceso_finalizado = Signal(dict)

    def __init__(self, carpeta_raiz):
        super().__init__()
        self.carpeta_raiz = carpeta_raiz
        self.esta_cancelado = False

    def ejecutar(self):
        resultados = {
            'movimientos': [],
            'errores': []
        }

        try:
            ruta_sede1 = os.path.join(self.carpeta_raiz, "sede 1")
            ruta_sede2 = os.path.join(self.carpeta_raiz, "sede 2")

            if not os.path.isdir(ruta_sede1) or not os.path.isdir(ruta_sede2):
                raise ValueError("No se encontraron las carpetas 'sede 1' y 'sede 2' dentro de la ruta raíz.")

            todas_las_subcarpetas = []
            for sede_nombre, sede_path in [("sede 1", ruta_sede1), ("sede 2", ruta_sede2)]:
                if not os.path.isdir(sede_path): continue
                for sub_nombre in os.listdir(sede_path):
                    sub_path = os.path.join(sede_path, sub_nombre)
                    if os.path.isdir(sub_path):
                        todas_las_subcarpetas.append({'nombre': sub_nombre, 'path': sub_path, 'sede_actual': sede_nombre})
            
            total_carpetas = len(todas_las_subcarpetas)
            for i, subcarpeta_info in enumerate(todas_las_subcarpetas):
                if self.esta_cancelado: break

                nombre_sub = subcarpeta_info['nombre']
                path_sub = subcarpeta_info['path']
                sede_actual = subcarpeta_info['sede_actual']
                
                porcentaje = (i + 1) / total_carpetas * 100
                self.progreso_actualizado.emit(f"Analizando '{nombre_sub}'...", porcentaje)

                serie = self._extraer_serie_de_referencia(path_sub)

                if not serie:
                    resultados['errores'].append({'carpeta': nombre_sub, 'razon': 'No se encontró archivo de referencia válido.'})
                    continue

                sede_correcta = "sede 2" if serie == "COEX" else "sede 1"

                if sede_actual != sede_correcta:
                    ruta_destino_final = os.path.join(self.carpeta_raiz, sede_correcta, nombre_sub)
                    if os.path.exists(ruta_destino_final):
                        resultados['errores'].append({'carpeta': nombre_sub, 'razon': f'Conflicto de nombre en la sede de destino ({sede_correcta}).'})
                        continue
                    
                    try:
                        shutil.move(path_sub, ruta_destino_final)
                        resultados['movimientos'].append({'carpeta': nombre_sub, 'origen': sede_actual, 'destino': sede_correcta, 'serie': serie})
                    except Exception as e:
                        resultados['errores'].append({'carpeta': nombre_sub, 'razon': f'Error del sistema al mover: {e}'})
            
            if self.esta_cancelado: return

            self.progreso_actualizado.emit("Reorganización completada.", 100)

        except Exception as e:
            resultados['errores'].append({'carpeta': 'General', 'razon': str(e)})
        
        self.proceso_finalizado.emit(resultados)

    def cancelar(self):
        self.esta_cancelado = True

    def _extraer_serie_de_referencia(self, ruta_subcarpeta):
        patron_nuevo = re.compile(r"^\d{4,}_([A-Z]+)\d+_(?:FACTURA|EPICRIS)", re.IGNORECASE)
        patron_carta_antiguo = re.compile(r"^\d{4,}_([A-Z]+)_\d+", re.IGNORECASE)

        for nombre_archivo in os.listdir(ruta_subcarpeta):
            if not nombre_archivo.lower().endswith('.pdf'):
                continue

            match_nuevo = patron_nuevo.match(nombre_archivo)
            if match_nuevo:
                return match_nuevo.group(1).upper()

            match_antiguo = patron_carta_antiguo.match(nombre_archivo)
            if match_antiguo:
                return match_antiguo.group(1).upper()
                
        return None

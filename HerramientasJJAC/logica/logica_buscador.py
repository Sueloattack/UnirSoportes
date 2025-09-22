# logica/logica_buscador.py
import os
import shutil
import re
from PySide6.QtCore import QObject, Signal

class WorkerBuscador(QObject):
    progreso_actualizado = Signal(str, float)
    proceso_finalizado = Signal(dict)

    def __init__(self, codigos, carpeta_busqueda, carpeta_destino):
        super().__init__()
        self.codigos = codigos
        self.carpeta_busqueda = carpeta_busqueda
        self.carpeta_destino = carpeta_destino
        self.esta_cancelado = False

    def ejecutar(self):
        resultados = {
            'encontrados': {},
            'copiados': set(),
            'no_encontrados': set(),
            'duplicados': {}
        }

        try:
            self.progreso_actualizado.emit("Iniciando búsqueda...", 0)

            for dirpath, dirnames, _ in os.walk(self.carpeta_busqueda):
                if self.esta_cancelado: break
                for dirname in list(dirnames):
                    for codigo in self.codigos:
                        if dirname.startswith(codigo):
                            ruta_completa = os.path.join(dirpath, dirname)
                            if codigo not in resultados['encontrados']:
                                resultados['encontrados'][codigo] = []
                            resultados['encontrados'][codigo].append(ruta_completa)
            
            if self.esta_cancelado: return

            self.progreso_actualizado.emit("Copiando carpetas...", 50)
            if not os.path.exists(self.carpeta_destino):
                os.makedirs(self.carpeta_destino)
            
            total_encontrados = len(resultados['encontrados'])
            for i, (codigo, rutas) in enumerate(resultados['encontrados'].items()):
                if self.esta_cancelado: break
                
                porcentaje = 50 + (i + 1) / total_encontrados * 50
                self.progreso_actualizado.emit(f"Copiando carpeta para código {codigo}...", porcentaje)

                ruta_origen = rutas[0]
                nombre_carpeta_origen = os.path.basename(ruta_origen)
                ruta_final_destino = os.path.join(self.carpeta_destino, nombre_carpeta_origen)
                
                if os.path.exists(ruta_final_destino):
                    resultados['copiados'].add(codigo)
                    continue
                
                try:
                    shutil.copytree(ruta_origen, ruta_final_destino)
                    resultados['copiados'].add(codigo)
                except Exception as e:
                    # Manejar error de copia
                    pass

            if self.esta_cancelado: return

            resultados['no_encontrados'] = self.codigos - set(resultados['encontrados'].keys())
            resultados['duplicados'] = {codigo: rutas for codigo, rutas in resultados['encontrados'].items() if len(rutas) > 1}

            self.progreso_actualizado.emit("Búsqueda completada.", 100)

        except Exception as e:
            # Manejar error general
            pass
        
        self.proceso_finalizado.emit(resultados)

    def cancelar(self):
        self.esta_cancelado = True

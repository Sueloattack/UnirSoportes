# logica/logica_traer_soportes.py
import os
import shutil
import re
from PySide6.QtCore import QObject, Signal

class WorkerTraerSoportes(QObject):
    """
    Clase que ejecuta la lógica de negocio para traer soportes en un hilo de trabajo.
    """
    progreso_actualizado = Signal(str, float)
    proceso_finalizado = Signal(dict)

    def __init__(self, carpeta_raiz, carpeta_soportes_origen, mover_archivos=True):
        super().__init__()
        self.carpeta_raiz = carpeta_raiz
        self.carpeta_soportes_origen = carpeta_soportes_origen
        self.mover_archivos = mover_archivos
        self.esta_cancelado = False

    def ejecutar(self):
        resultados = {
            'exitosos': [],
            'fallidos': [],
            'sin_soportes_encontrados': [],
            'sobrantes': []
        }

        try:
            subcarpetas = sorted([d for d in os.listdir(self.carpeta_raiz) if os.path.isdir(os.path.join(self.carpeta_raiz, d))])

            soportes_disponibles = {}
            for nombre_soporte in os.listdir(self.carpeta_soportes_origen):
                if os.path.isfile(os.path.join(self.carpeta_soportes_origen, nombre_soporte)):
                    info_soporte = self._extraer_info_archivo(nombre_soporte)
                    if info_soporte and info_soporte['tipo'] == 'SOPORTE':
                        codigo = info_soporte['codigo']
                        if codigo not in soportes_disponibles:
                            soportes_disponibles[codigo] = []
                        soportes_disponibles[codigo].append(nombre_soporte)
            
            total_carpetas = len(subcarpetas)
            for i, nombre_subcarpeta in enumerate(subcarpetas):
                if self.esta_cancelado:
                    break

                ruta_subcarpeta = os.path.join(self.carpeta_raiz, nombre_subcarpeta)
                porcentaje = (i + 1) / total_carpetas * 100
                self.progreso_actualizado.emit(f"Procesando carpeta {nombre_subcarpeta}...", porcentaje)

                codigo_factura_ancla = None
                for item in os.listdir(ruta_subcarpeta):
                    if item.lower().endswith('.pdf'):
                        info_factura = self._extraer_info_archivo(item)
                        if info_factura and info_factura['tipo'] == 'FACTURA':
                            codigo_factura_ancla = info_factura['codigo']
                            break
                
                if not codigo_factura_ancla:
                    resultados['fallidos'].append({'carpeta': nombre_subcarpeta, 'razon': 'No se encontró archivo de Factura con formato válido.'})
                    continue

                soportes_movidos_esta_carpeta = []
                
                if codigo_factura_ancla in soportes_disponibles:
                    for nombre_soporte in soportes_disponibles[codigo_factura_ancla]:
                        origen_path = os.path.join(self.carpeta_soportes_origen, nombre_soporte)
                        destino_path = os.path.join(ruta_subcarpeta, nombre_soporte)
                        
                        try:
                            if self.mover_archivos:
                                shutil.move(origen_path, destino_path)
                            else:
                                shutil.copy2(origen_path, destino_path)
                            
                            soportes_movidos_esta_carpeta.append(nombre_soporte)

                        except Exception as e:
                            resultados['fallidos'].append({'carpeta': nombre_subcarpeta, 'razon': f"Error al {'mover' if self.mover_archivos else 'copiar'} '{nombre_soporte}': {e}"})
                    
                    del soportes_disponibles[codigo_factura_ancla]
                
                if soportes_movidos_esta_carpeta:
                    resultados['exitosos'].append({'carpeta': nombre_subcarpeta, 'archivos': soportes_movidos_esta_carpeta})
                else:
                    resultados['sin_soportes_encontrados'].append({'carpeta': nombre_subcarpeta})
            
            resultados['sobrantes'] = soportes_disponibles

        except Exception as e:
            resultados['fallidos'].append({'carpeta': 'General', 'razon': f'Error crítico durante la ejecución: {e}'})

        self.proceso_finalizado.emit(resultados)

    def cancelar(self):
        self.esta_cancelado = True

    def _extraer_info_archivo(self, nombre_archivo):
        match_factura = re.match(r'^\d{4,}_([A-Z]+)(\d+)_FACTURA', nombre_archivo, re.IGNORECASE)
        if match_factura:
            serie = match_factura.group(1).upper()
            numero = match_factura.group(2)
            return {"tipo": "FACTURA", "serie": serie, "numero": numero, "codigo": f"{serie}_{numero}"}

        base_nombre, _ = os.path.splitext(nombre_archivo)
        match_soporte = re.match(r'^(COEX|FECR|FERD|FERR)([0-9]+)', base_nombre, re.IGNORECASE)
        if match_soporte:
            serie = match_soporte.group(1).upper()
            numero = match_soporte.group(2)
            return {"tipo": "SOPORTE", "serie": serie, "numero": numero, "codigo": f"{serie}_{numero}"}

        return None

# logica/logica_adres.py
import os
import shutil
import re
from PySide6.QtCore import QObject, Signal

class WorkerAdres(QObject):
    """
    Clase que ejecuta la lógica de negocio para el procesamiento de ADRES en un hilo de trabajo.
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
        resultados = {
            'exitosos': [],
            'ya_tenian_respuesta': [],
            'fallidos': [],
            'sin_respuesta_encontrada': [],
            'sobrantes': []
        }

        try:
            subcarpetas = sorted([d for d in os.listdir(self.carpeta_raiz) if os.path.isdir(os.path.join(self.carpeta_raiz, d))])

            respuestas_disponibles = {}
            for nombre_respuesta in os.listdir(self.carpeta_respuestas):
                if os.path.isfile(os.path.join(self.carpeta_respuestas, nombre_respuesta)):
                    info_respuesta = self._extraer_info_archivo(nombre_respuesta)
                    if info_respuesta and info_respuesta['tipo'] == 'RESPUESTA':
                        respuestas_disponibles[info_respuesta['codigo']] = nombre_respuesta
            
            total_carpetas = len(subcarpetas)
            for i, nombre_subcarpeta in enumerate(subcarpetas):
                if self.esta_cancelado:
                    break

                ruta_subcarpeta = os.path.join(self.carpeta_raiz, nombre_subcarpeta)
                porcentaje = (i + 1) / total_carpetas * 100
                self.progreso_actualizado.emit(f"Procesando carpeta {nombre_subcarpeta}...", porcentaje)

                factura_info = None
                respuesta_existente = False
                for item in os.listdir(ruta_subcarpeta):
                    info_item = self._extraer_info_archivo(item)
                    if info_item:
                        if info_item['tipo'] == 'FACTURA':
                            factura_info = info_item
                        elif info_item['tipo'] == 'RESPUESTA':
                            respuesta_existente = True
                
                if not factura_info:
                    resultados['fallidos'].append({'carpeta': nombre_subcarpeta, 'razon': 'No se encontró archivo de Factura con formato válido.'})
                    continue

                if respuesta_existente:
                    resultados['ya_tenian_respuesta'].append({'carpeta': nombre_subcarpeta})
                    continue
                
                codigo_factura = factura_info['codigo']
                if codigo_factura in respuestas_disponibles:
                    nombre_respuesta_encontrada = respuestas_disponibles[codigo_factura]
                    origen_path = os.path.join(self.carpeta_respuestas, nombre_respuesta_encontrada)
                    
                    nombre_destino = self._limpiar_nombre_respuesta(nombre_respuesta_encontrada)
                    destino_path = os.path.join(ruta_subcarpeta, nombre_destino)

                    try:
                        if self.mover_archivos:
                            shutil.move(origen_path, destino_path)
                        else:
                            shutil.copy2(origen_path, destino_path)

                        resultados['exitosos'].append({'carpeta': nombre_subcarpeta, 'respuesta_procesada': nombre_respuesta_encontrada})
                        del respuestas_disponibles[codigo_factura]
                    except Exception as e:
                        resultados['fallidos'].append({'carpeta': nombre_subcarpeta, 'razon': f"Error al {'mover' if self.mover_archivos else 'copiar'} '{nombre_respuesta_encontrada}': {e}"})
                else:
                    resultados['sin_respuesta_encontrada'].append({'carpeta': nombre_subcarpeta})

            resultados['sobrantes'] = respuestas_disponibles

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
        match_respuesta = re.match(r'^(COEX|FECR|FERD|FERR)([0-9]+)', base_nombre, re.IGNORECASE)
        if match_respuesta:
            serie = match_respuesta.group(1).upper()
            numero = match_respuesta.group(2)
            return {"tipo": "RESPUESTA", "serie": serie, "numero": numero, "codigo": f"{serie}_{numero}"}

        return None

    def _limpiar_nombre_respuesta(self, nombre):
        info = self._extraer_info_archivo(nombre)
        if info and info['tipo'] == 'RESPUESTA':
            return f"{info['serie']}{info['numero']}.pdf"
        
        nuevo_nombre = nombre.replace(" ", "")
        nuevo_nombre = re.sub(r'\.{2,}', '.', nuevo_nombre)
        return nuevo_nombre

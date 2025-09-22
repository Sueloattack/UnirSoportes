# logica/logica_organizar_xmls.py
import os
import shutil
import re
from PySide6.QtCore import QObject, Signal

class OrganizadorXMLWorker(QObject):
    """
    Clase que ejecuta la lógica de negocio para organizar XMLs en un hilo de trabajo.
    """
    progreso_actualizado = Signal(str, float)
    proceso_finalizado = Signal(dict)

    def __init__(self, carpeta_raiz, carpeta_xmls, mover_archivos=True):
        super().__init__()
        self.carpeta_raiz = carpeta_raiz
        self.carpeta_xmls = carpeta_xmls
        self.mover_archivos = mover_archivos
        self.esta_cancelado = False

    def ejecutar(self):
        resultados = {
            'exitosos': [],
            'ya_tenian_xml': [],
            'fallidos': [],
            'sin_xml_encontrado': [],
            'sobrantes': []
        }

        try:
            subcarpetas = sorted([d for d in os.listdir(self.carpeta_raiz) if os.path.isdir(os.path.join(self.carpeta_raiz, d))])

            xmls_disponibles = {}
            for nombre_xml in os.listdir(self.carpeta_xmls):
                if nombre_xml.lower().endswith('.xml'):
                    info_xml = self._extraer_info_archivo(nombre_xml)
                    if info_xml and info_xml['tipo'] == 'XML':
                        xmls_disponibles[info_xml['codigo']] = info_xml
            
            total_carpetas = len(subcarpetas)
            for i, nombre_subcarpeta in enumerate(subcarpetas):
                if self.esta_cancelado:
                    break

                ruta_subcarpeta = os.path.join(self.carpeta_raiz, nombre_subcarpeta)
                porcentaje = (i + 1) / total_carpetas * 100
                self.progreso_actualizado.emit(f"Procesando carpeta {nombre_subcarpeta}...", porcentaje)

                factura_info = None
                xml_existente = False
                for item in os.listdir(ruta_subcarpeta):
                    if os.path.isfile(os.path.join(ruta_subcarpeta, item)):
                        if item.lower().endswith('.xml'):
                            xml_existente = True
                        elif item.lower().endswith('.pdf'):
                            info_item = self._extraer_info_archivo(item)
                            if info_item and info_item['tipo'] == 'FACTURA':
                                factura_info = info_item
                
                if not factura_info:
                    resultados['fallidos'].append({'carpeta': nombre_subcarpeta, 'razon': 'No se encontró archivo de Factura con formato válido.'})
                    continue

                if xml_existente:
                    resultados['ya_tenian_xml'].append({'carpeta': nombre_subcarpeta})
                    continue
                
                codigo_factura = factura_info['codigo']
                if codigo_factura in xmls_disponibles:
                    xml_encontrado = xmls_disponibles[codigo_factura]
                    origen_path = os.path.join(self.carpeta_xmls, xml_encontrado['nombre_completo'])
                    
                    nombre_base_factura, _ = os.path.splitext(factura_info['nombre_completo'])
                    nombre_destino = f"{nombre_base_factura}.xml"
                    destino_path = os.path.join(ruta_subcarpeta, nombre_destino)

                    try:
                        if self.mover_archivos:
                            shutil.move(origen_path, destino_path)
                        else:
                            shutil.copy2(origen_path, destino_path)

                        resultados['exitosos'].append({'carpeta': nombre_subcarpeta, 'xml_procesado': xml_encontrado['nombre_completo']})
                        del xmls_disponibles[codigo_factura]

                    except Exception as e:
                        resultados['fallidos'].append({'carpeta': nombre_subcarpeta, 'razon': f"Error al {'mover' if self.mover_archivos else 'copiar'} '{xml_encontrado['nombre_completo']}': {e}"})
                else:
                    resultados['sin_xml_encontrado'].append({'carpeta': nombre_subcarpeta})

            resultados['sobrantes'] = list(xmls_disponibles.values())

        except Exception as e:
            resultados['fallidos'].append({'carpeta': 'General', 'razon': f'Error crítico durante la ejecución: {e}'})

        self.proceso_finalizado.emit(resultados)

    def cancelar(self):
        self.esta_cancelado = True

    def _extraer_info_archivo(self, nombre_archivo):
        base_nombre, extension = os.path.splitext(nombre_archivo)
        extension = extension.lower()
        
        if extension == '.pdf':
            match_factura = re.match(r'^\d{4,}_([A-Z]+)(\d+)_FACTURA', base_nombre, re.IGNORECASE)
            if match_factura:
                serie = match_factura.group(1).upper()
                numero = match_factura.group(2)
                return {"tipo": "FACTURA", "serie": serie, "numero": numero, "codigo": f"{serie}_{numero}", "nombre_completo": nombre_archivo}

        elif extension == '.xml':
            match_xml = re.search(r'(COEX|FECR|FERD|FERR)([0-9]+)', base_nombre, re.IGNORECASE)
            if match_xml:
                serie = match_xml.group(1).upper()
                numero = match_xml.group(2)
                return {"tipo": "XML", "serie": serie, "numero": numero, "codigo": f"{serie}_{numero}", "nombre_completo": nombre_archivo}

        return None

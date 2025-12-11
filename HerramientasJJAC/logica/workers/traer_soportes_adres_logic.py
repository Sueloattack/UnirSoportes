# logica/workers/traer_soportes_adres_logic.py
import os
import re
import shutil
from PySide6.QtCore import QObject, Signal
from logica.core.gestor_archivos import buscar_carpetas_por_nombre, copiar_contenido_carpeta

class TraerSoportesAdresWorker(QObject):
    """
    Worker para buscar facturas en carpetas 'envios' y copiar los soportes
    correspondientes de forma selectiva, agrupando los FURIPS en una carpeta central.
    """
    log_generado = Signal(str)
    proceso_finalizado = Signal()

    def __init__(self, facturas_con_serie, dir_busqueda, dir_destino):
        super().__init__()
        self.facturas_raw = facturas_con_serie
        self.dir_busqueda = dir_busqueda
        self.dir_destino = dir_destino
        self.esta_cancelado = False

    def ejecutar(self):
        try:
            # 1. Preparar facturas y rutas de destino
            facturas_a_buscar = set(self.facturas_raw)
            facturas_encontradas = set()
            
            ruta_destino_furips = os.path.join(self.dir_destino, "FURIPS")

            def extraer_numero(factura_str):
                match = re.search(r'\d+$', factura_str)
                return match.group(0) if match else factura_str

            self.log_generado.emit(f"Se buscarán {len(facturas_a_buscar)} facturas.")
            self.log_generado.emit(f"Los FURIPS se guardarán en: {ruta_destino_furips}")

            # 2. Buscar todas las carpetas 'envios' y 'furips'
            self.log_generado.emit(f"Buscando carpetas 'envios' y 'furips' en: {self.dir_busqueda}...")
            carpetas_agrupadas = buscar_carpetas_por_nombre(self.dir_busqueda, ['envios', 'envio', 'furips'])
            self.log_generado.emit(f"Se encontraron {len(carpetas_agrupadas)} cuentas de cobro con carpetas relevantes.")

            if not carpetas_agrupadas:
                self.log_generado.emit("<font color='red'>No se encontraron carpetas 'envios' o 'furips' en la ruta especificada.</font>")
                self.proceso_finalizado.emit()
                return

            # 3. Iterar sobre cada cuenta de cobro
            for i, (ruta_padre, subcarpetas) in enumerate(carpetas_agrupadas.items()):
                if self.esta_cancelado or not facturas_a_buscar:
                    break
                
                self.log_generado.emit(f"<b>Procesando cuenta:</b> {os.path.basename(ruta_padre)} ({i+1}/{len(carpetas_agrupadas)})")

                ruta_envios = subcarpetas.get('envios') or subcarpetas.get('envio')
                if not ruta_envios:
                    self.log_generado.emit(f"<font color='orange'>- Advertencia: No se encontró la carpeta 'envios' en {ruta_padre}.</font>")
                    continue

                # 4. Buscar qué facturas de nuestra lista están en esta carpeta 'envios'
                facturas_halladas_en_esta_cuenta = set()
                try:
                    archivos_envio = os.listdir(ruta_envios)
                    for factura_buscada in list(facturas_a_buscar):
                        for archivo in archivos_envio:
                            if factura_buscada.lower() in archivo.lower():
                                facturas_halladas_en_esta_cuenta.add(factura_buscada)
                                break
                except FileNotFoundError:
                    self.log_generado.emit(f"<font color='red'>- Error: La carpeta 'envios' en {ruta_padre} no es accesible.</font>")
                    continue

                # 5. Si se encontraron facturas, realizar las copias selectivas
                if facturas_halladas_en_esta_cuenta:
                    # Copiar y renombrar FURIPS a la carpeta centralizada (si existen)
                    ruta_furips = subcarpetas.get('furips')
                    if ruta_furips:
                        self.log_generado.emit("- Copiando y renombrando archivos FURIPS (.txt)...")
                        nombre_cuenta_cobro = os.path.basename(ruta_padre)
                        os.makedirs(ruta_destino_furips, exist_ok=True)

                        for item in os.listdir(ruta_furips):
                            if item.lower().endswith('.txt'):
                                origen_path = os.path.join(ruta_furips, item)
                                
                                # Crear el nuevo nombre único
                                nombre_base, extension = os.path.splitext(item)
                                nuevo_nombre = f"{nombre_base}_cuenta_{nombre_cuenta_cobro}{extension}"
                                destino_path = os.path.join(ruta_destino_furips, nuevo_nombre)
                                
                                # Asegurar que no haya colisiones incluso con el nuevo nombre
                                contador = 1
                                while os.path.exists(destino_path):
                                    nuevo_nombre = f"{nombre_base}_cuenta_{nombre_cuenta_cobro} ({contador}){extension}"
                                    destino_path = os.path.join(ruta_destino_furips, nuevo_nombre)
                                    contador += 1
                                
                                shutil.copy2(origen_path, destino_path)
                    
                    # Para cada factura encontrada, copiar sus archivos específicos de 'envios'
                    for factura_encontrada in facturas_halladas_en_esta_cuenta:
                        numero_factura = extraer_numero(factura_encontrada)
                        ruta_destino_factura = os.path.join(self.dir_destino, numero_factura)

                        self.log_generado.emit(f"<font color='green'>✔ Factura {factura_encontrada} encontrada. Copiando sus archivos específicos (no JSON)...</font>")
                        
                        copiar_contenido_carpeta(
                            origen=ruta_envios,
                            destino=ruta_destino_factura,
                            patron_nombre=factura_encontrada,
                            extensiones_excluidas=['.json']
                        )
                        
                        facturas_a_buscar.remove(factura_encontrada)
                        facturas_encontradas.add(factura_encontrada)

            # 6. Reporte final
            self.log_generado.emit("<hr><b>Reporte Final:</b>")
            self.log_generado.emit(f"Facturas encontradas y procesadas: {len(facturas_encontradas)}")
            
            if facturas_a_buscar:
                self.log_generado.emit(f"<font color='red'>Facturas no encontradas ({len(facturas_a_buscar)}):</font>")
                for factura_no_encontrada in sorted(list(facturas_a_buscar)):
                    self.log_generado.emit(f"- {factura_no_encontrada}")

        except Exception as e:
            self.log_generado.emit(f"<font color='red'><b>Error crítico:</b> {e}</font>")
        finally:
            self.proceso_finalizado.emit()

    def cancelar(self):
        self.esta_cancelado = True

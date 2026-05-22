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
                    # Evitar advertencia si solo encontró una carpeta furips anidada
                    if not (len(subcarpetas) == 1 and 'furips' in subcarpetas):
                        self.log_generado.emit(f"<font color='orange'>- Advertencia: No se encontró la carpeta 'envios' en {ruta_padre}.</font>")
                    continue

                # Detectar subcarpeta '1_Renombrados' dentro de envios (nueva estructura)
                ruta_renombrados = os.path.join(ruta_envios, "1_Renombrados")
                if os.path.isdir(ruta_renombrados):
                    self.log_generado.emit(f"- Subcarpeta '1_Renombrados' detectada, se usará como fuente de archivos.")
                    ruta_fuente_archivos = ruta_renombrados
                else:
                    ruta_fuente_archivos = ruta_envios

                # 4. Buscar qué facturas de nuestra lista están en la carpeta fuente
                facturas_halladas_en_esta_cuenta = set()
                try:
                    archivos_envio = os.listdir(ruta_fuente_archivos)
                    for factura_buscada in list(facturas_a_buscar):
                        for archivo in archivos_envio:
                            if factura_buscada.lower() in archivo.lower():
                                facturas_halladas_en_esta_cuenta.add(factura_buscada)
                                break
                except FileNotFoundError:
                    self.log_generado.emit(f"<font color='red'>- Error: La carpeta fuente en {ruta_padre} no es accesible.</font>")
                    continue

                # 5. Si se encontraron facturas, realizar las copias selectivas
                if facturas_halladas_en_esta_cuenta:
                    # Copiar y renombrar FURIPS a la carpeta centralizada (si existen)
                    ruta_furips = subcarpetas.get('furips')
                    
                    # Buscar también si la carpeta furips está dentro de la fuente de archivos o envios
                    if not ruta_furips:
                        posible_furips = os.path.join(ruta_fuente_archivos, "furips")
                        if os.path.isdir(posible_furips):
                            ruta_furips = posible_furips
                        else:
                            posible_furips = os.path.join(ruta_envios, "furips")
                            if os.path.isdir(posible_furips):
                                ruta_furips = posible_furips

                    # Recolectar todos los archivos .txt (FURIPS)
                    archivos_furips = []
                    
                    if ruta_furips and os.path.isdir(ruta_furips):
                        for item in os.listdir(ruta_furips):
                            if item.lower().endswith('.txt'):
                                archivos_furips.append(os.path.join(ruta_furips, item))
                                
                    # Buscar .txt directamente en la carpeta fuente por si no hay subcarpeta 'furips'
                    try:
                        for item in os.listdir(ruta_fuente_archivos):
                            if item.lower().endswith('.txt'):
                                ruta_txt = os.path.join(ruta_fuente_archivos, item)
                                if ruta_txt not in archivos_furips:
                                    archivos_furips.append(ruta_txt)
                    except Exception:
                        pass

                    if archivos_furips:
                        self.log_generado.emit("- Copiando y renombrando archivos FURIPS (.txt)...")
                        nombre_cuenta_cobro = os.path.basename(ruta_padre)
                        os.makedirs(ruta_destino_furips, exist_ok=True)

                        for origen_path in archivos_furips:
                            item = os.path.basename(origen_path)
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
                            origen=ruta_fuente_archivos,
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

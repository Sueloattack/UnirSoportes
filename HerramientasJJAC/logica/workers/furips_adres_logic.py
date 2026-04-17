import os
import glob
import pandas as pd
import re
from PySide6.QtCore import QObject, Signal

# --- COLORES ---
COLOR_INFO = "#5DADE2"
COLOR_SUCCESS = "#2ECC71"
COLOR_WARNING = "#F39C12"
COLOR_ERROR = "#E74C3C"
COLOR_DEFAULT = "#ECF0F1"

class FuripsAdresWorker(QObject):
    progreso_actualizado = Signal(str)
    proceso_finalizado = Signal(dict)

    def __init__(self, parametros, modo="unir"):
        super().__init__()
        self.parametros = parametros
        self.modo = modo
        self.esta_cancelado = False

    def cancelar(self):
        self.esta_cancelado = True

    def ejecutar(self):
        try:
            if self.modo == "unir":
                self._unir_furips()
            elif self.modo == "filtrar":
                self._filtrar_dual()
            else:
                self.proceso_finalizado.emit({'error': f"Modo desconocido: {self.modo}"})
        except Exception as e:
            self.proceso_finalizado.emit({'error': str(e)})

    def _parsear_archivo_irregular(self, ruta_archivo, num_campos_esperados, tiene_comas_iniciales):
        try:
            with open(ruta_archivo, 'r', encoding='utf-8-sig') as f:
                texto_original = f.read()
        except UnicodeDecodeError:
            with open(ruta_archivo, 'r', encoding='latin-1') as f:
                texto_original = f.read()

        delimitador_registro = r'(,,COEX|,,FECR)' if tiene_comas_iniciales else r'(COEX|FECR)'
        texto_normalizado = re.sub(delimitador_registro, r'\n\1', texto_original).strip()

        lineas = texto_normalizado.split('\n')
        if not lineas: return None

        datos_parseados = []
        num_delimitadores = num_campos_esperados - 1

        for linea in lineas:
            if not linea.strip(): continue
            campos = linea.split(',', maxsplit=num_delimitadores)
            while len(campos) < num_campos_esperados:
                campos.append('')
            datos_parseados.append(campos)
        
        if not datos_parseados: return None
        return pd.DataFrame(datos_parseados)

    def _unir_furips(self):
        carpeta_entrada = self.parametros.get('carpeta_entrada')
        carpeta_salida = self.parametros.get('carpeta_salida')
        numero_cuenta = self.parametros.get('numero_cuenta')

        self.progreso_actualizado.emit(f"<p style='color:{COLOR_INFO};'>Iniciando UNIÓN DE FURIPS para cuenta: {numero_cuenta}</p>")

        # F1
        archivos_f1 = glob.glob(os.path.join(carpeta_entrada, "FURIPS1*.txt"))
        df_f1_list = []
        for f in archivos_f1:
            if self.esta_cancelado: return self.proceso_finalizado.emit({'estado': 'cancelado'})
            df = self._parsear_archivo_irregular(f, 102, tiene_comas_iniciales=True)
            if df is not None: df_f1_list.append(df)
            
        if df_f1_list:
            df_f1_unido = pd.concat(df_f1_list, ignore_index=True)
            nombre_salida = f"FURIPS1_{numero_cuenta}.txt"
            df_f1_unido.to_csv(os.path.join(carpeta_salida, nombre_salida), sep=',', header=False, index=False, encoding='utf-8')
            self.progreso_actualizado.emit(f"<p style='color:{COLOR_SUCCESS};'>- Archivo '{nombre_salida}' creado con {len(df_f1_unido)} registros.</p>")

        # F2
        archivos_f2 = glob.glob(os.path.join(carpeta_entrada, "FURIPS2*.txt"))
        df_f2_list = []
        for f in archivos_f2:
            if self.esta_cancelado: return self.proceso_finalizado.emit({'estado': 'cancelado'})
            df = self._parsear_archivo_irregular(f, 9, tiene_comas_iniciales=False)
            if df is not None: df_f2_list.append(df)

        if df_f2_list:
            df_f2_unido = pd.concat(df_f2_list, ignore_index=True)
            nombre_salida = f"FURIPS2_{numero_cuenta}.txt"
            df_f2_unido.to_csv(os.path.join(carpeta_salida, nombre_salida), sep=',', header=False, index=False, encoding='utf-8')
            self.progreso_actualizado.emit(f"<p style='color:{COLOR_SUCCESS};'>- Archivo '{nombre_salida}' creado con {len(df_f2_unido)} registros.</p>")

        self.proceso_finalizado.emit({'estado': 'completado'})

    def _filtrar_dual(self):
        archivo_f1 = self.parametros.get('archivo_f1')
        archivo_f2 = self.parametros.get('archivo_f2')
        carpeta_salida = self.parametros.get('carpeta_salida')
        glosas = self.parametros.get('glosas', [])

        self.progreso_actualizado.emit(f"<p style='color:{COLOR_INFO};'>Iniciando FILTRADO DUAL para {len(glosas)} facturas...</p>")

        df_f1 = self._parsear_archivo_irregular(archivo_f1, 102, tiene_comas_iniciales=True)
        df_f2 = self._parsear_archivo_irregular(archivo_f2, 9, tiene_comas_iniciales=False)

        if df_f1 is None or df_f2 is None:
            self.proceso_finalizado.emit({'error': "No se pudieron cargar los archivos originales F1/F2."})
            return

        archivos_creados = 0
        
        # Filtramos todo el dataframe de una sola vez
        df_f1_filtrado = df_f1[df_f1.iloc[:, 2].isin(glosas)]
        df_f2_filtrado = df_f2[df_f2.iloc[:, 0].isin(glosas)]

        creado_algo = False
        if not df_f1_filtrado.empty:
            nombre = "FURIPS1_filtrado.txt"
            df_f1_filtrado.to_csv(os.path.join(carpeta_salida, nombre), sep=',', header=False, index=False, encoding='utf-8')
            archivos_creados += 1
            creado_algo = True
            self.progreso_actualizado.emit(f"<p style='color:{COLOR_SUCCESS};'>- Creado archivo agrupado FURIPS1_filtrado.txt con {len(df_f1_filtrado)} registros.</p>")
            
        if not df_f2_filtrado.empty:
            nombre = "FURIPS2_filtrado.txt"
            df_f2_filtrado.to_csv(os.path.join(carpeta_salida, nombre), sep=',', header=False, index=False, encoding='utf-8')
            archivos_creados += 1
            creado_algo = True
            self.progreso_actualizado.emit(f"<p style='color:{COLOR_SUCCESS};'>- Creado archivo agrupado FURIPS2_filtrado.txt con {len(df_f2_filtrado)} registros.</p>")
            
        if not creado_algo:
            self.progreso_actualizado.emit(f"<p style='color:{COLOR_WARNING};'>- No se encontraron coincidencias para ninguna factura.</p>")

        self.proceso_finalizado.emit({'estado': 'completado', 'archivos': archivos_creados})

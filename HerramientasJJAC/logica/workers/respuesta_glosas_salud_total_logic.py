# logica/workers/respuesta_glosas_salud_total_logic.py
import os
import csv
import json
import re
from datetime import date

from PySide6.QtCore import QObject, Signal

# ---------------------------------------------------------------------------
# Columnas que se conservan del TXT original (con sus nombres exactos)
# y columnas nuevas que se agregan vacías para que el usuario las diligencie.
# ---------------------------------------------------------------------------
COLUMNAS_ORIGINALES = [
    "NumeroRad_",
    "PrefijoFac_",
    "NumeroFac_",
    "Numreg",
    "NombreServicio",
    "ValorGlosaTotalxServ",
    "CodMotvGlosaGeneral",
    "CodMotvGlosaEspc",
]

COLUMNAS_NUEVAS = [
    "ValorAceptadoIPS",
    "Codigo Respuesta a glosas",
    "ConceptoRespuesta",
    "Observacion IPS",
]

COLUMNAS_REQUERIDAS = COLUMNAS_ORIGINALES + COLUMNAS_NUEVAS

CONTADOR_FILENAME = "contador_rtaglosa.json"

COLOR_INFO = "#5DADE2"
COLOR_SUCCESS = "#2ECC71"
COLOR_WARNING = "#F39C12"
COLOR_ERROR = "#E74C3C"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _buscar_columna(nombre: str, headers: list[str]) -> str | None:
    """Busca 'nombre' en headers: exacta primero, luego normalizada."""
    if nombre in headers:
        return nombre
    norm_buscado = nombre.lower().replace('_', '').replace(' ', '')
    for h in headers:
        if h.lower().replace('_', '').replace(' ', '') == norm_buscado:
            return h
    return None


def leer_txt_pipe(ruta_archivo: str) -> tuple[list[str], list[dict]]:
    """Lee un TXT delimitado por | y devuelve (headers, filas_como_dicts)."""
    with open(ruta_archivo, 'r', encoding='utf-8-sig') as f:
        lines = [line.rstrip('\r\n') for line in f.readlines()]

    lines = [l for l in lines if l.strip()]
    if not lines:
        return [], []

    # Eliminar pipe final si existe
    headers = [h.strip() for h in lines[0].rstrip('|').split('|')]
    rows = []
    for line in lines[1:]:
        if not line.strip():
            continue
        values = [v.strip() for v in line.rstrip('|').split('|')]
        while len(values) < len(headers):
            values.append('')
        rows.append(dict(zip(headers, values)))

    return headers, rows


def obtener_siguiente_consecutivo(carpeta_salida: str) -> int:
    """
    Retorna el siguiente número consecutivo para el día de hoy.
    El contador se guarda en {carpeta_salida}/contador_rtaglosa.json.
    Se reinicia automáticamente cada día.
    """
    hoy = date.today().isoformat()
    ruta = os.path.join(carpeta_salida, CONTADOR_FILENAME)
    datos = {}
    if os.path.exists(ruta):
        try:
            with open(ruta, 'r', encoding='utf-8') as f:
                datos = json.load(f)
        except (json.JSONDecodeError, IOError):
            datos = {}

    if datos.get("fecha") != hoy:
        datos = {"fecha": hoy, "consecutivo": 0}

    datos["consecutivo"] += 1
    with open(ruta, 'w', encoding='utf-8') as f:
        json.dump(datos, f, ensure_ascii=False)

    return datos["consecutivo"]


# ---------------------------------------------------------------------------
# Worker 1: Ajustar TXT (quitar campos sobrantes, agregar campos faltantes)
# ---------------------------------------------------------------------------

class AjustarTXTWorker(QObject):
    progreso_actualizado = Signal(str)
    proceso_finalizado = Signal(dict)

    def __init__(self, ruta_txt: str, carpeta_salida: str):
        super().__init__()
        self.ruta_txt = ruta_txt
        self.carpeta_salida = carpeta_salida

    def ejecutar(self):
        resultados = {'exitosos': [], 'fallidos': []}
        nombre_archivo = os.path.basename(self.ruta_txt)
        try:
            self.progreso_actualizado.emit(
                f"<font color='{COLOR_INFO}'>Leyendo archivo: <b>{nombre_archivo}</b></font>"
            )
            headers, rows = leer_txt_pipe(self.ruta_txt)

            if not headers:
                resultados['fallidos'].append({
                    'archivo': nombre_archivo,
                    'razon': 'El archivo está vacío o no tiene encabezados.'
                })
                self.proceso_finalizado.emit(resultados)
                return

            self.progreso_actualizado.emit(
                f"<font color='{COLOR_INFO}'>{len(rows)} registros encontrados. "
                f"Columnas originales: {len(headers)}</font>"
            )

            # Construir mapa: col_requerida → col_en_archivo (sólo para originales)
            mapa = {}
            for col in COLUMNAS_ORIGINALES:
                encontrada = _buscar_columna(col, headers)
                if encontrada:
                    mapa[col] = encontrada

            faltantes_orig = [c for c in COLUMNAS_ORIGINALES if c not in mapa]
            if faltantes_orig:
                self.progreso_actualizado.emit(
                    f"<font color='{COLOR_WARNING}'>Columnas del TXT original no encontradas "
                    f"(quedarán vacías): {', '.join(faltantes_orig)}</font>"
                )

            self.progreso_actualizado.emit(
                f"<font color='{COLOR_INFO}'>Columnas nuevas que se agregarán vacías "
                f"para diligenciar: {', '.join(COLUMNAS_NUEVAS)}</font>"
            )

            # Construir filas de salida
            output_rows = []
            for row in rows:
                new_row = {}
                for col in COLUMNAS_ORIGINALES:
                    col_origen = mapa.get(col)
                    new_row[col] = row.get(col_origen, '') if col_origen else ''
                for col in COLUMNAS_NUEVAS:
                    new_row[col] = ''
                output_rows.append(new_row)

            # Escribir archivo ajustado
            os.makedirs(self.carpeta_salida, exist_ok=True)
            nombre_base = os.path.splitext(nombre_archivo)[0]
            nombre_salida = f"{nombre_base}_ajustado.txt"
            ruta_salida = os.path.join(self.carpeta_salida, nombre_salida)

            with open(ruta_salida, 'w', encoding='utf-8', newline='') as f:
                f.write('|'.join(COLUMNAS_REQUERIDAS) + '|\n')
                for row in output_rows:
                    valores = [row.get(c, '') for c in COLUMNAS_REQUERIDAS]
                    f.write('|'.join(valores) + '|\n')

            self.progreso_actualizado.emit(
                f"<font color='{COLOR_SUCCESS}'>✔ Archivo ajustado guardado: "
                f"<b>{nombre_salida}</b> ({len(output_rows)} registros)</font>"
            )
            resultados['exitosos'].append({
                'archivo': nombre_salida,
                'registros': len(output_rows),
                'ruta': ruta_salida
            })

        except Exception as e:
            resultados['fallidos'].append({'archivo': nombre_archivo, 'razon': str(e)})
            self.progreso_actualizado.emit(
                f"<font color='{COLOR_ERROR}'>✖ Error: {e}</font>"
            )

        self.proceso_finalizado.emit(resultados)


# ---------------------------------------------------------------------------
# Worker 2: Convertir CSV → TXTs con pipe (uno por factura)
# ---------------------------------------------------------------------------

def _parsear_factura(texto: str) -> tuple[str, str] | None:
    """
    Dado un string como 'FECR363035' o 'COEX 38678' separa el prefijo
    alfabético del número. Devuelve (prefijo, numero) o None si no aplica.
    """
    import re
    texto = texto.strip()
    m = re.match(r'^([A-Za-z]+)\s*(\d+)$', texto)
    if m:
        return m.group(1).upper(), m.group(2)
    return None


class ConvertirCSVWorker(QObject):
    progreso_actualizado = Signal(str)
    proceso_finalizado = Signal(dict)

    def __init__(self, ruta_csv: str, nit: str, facturas: list[str], carpeta_salida: str):
        super().__init__()
        self.ruta_csv = ruta_csv
        self.nit = "800209891"  # NIT siempre fijo
        self.facturas = [f.strip() for f in facturas if f.strip()]
        self.carpeta_salida = carpeta_salida

    def _buscar_carpeta_por_factura(self, serie: str, numero: str) -> str | None:
        """
        Busca una subcarpeta dentro de carpeta_salida que contenga carta glosa coincidente.
        Patrón de carta glosa: serie-numero- o serie_numero_
        Retorna la ruta de la subcarpeta si la encuentra, None si no.
        """
        if not os.path.isdir(self.carpeta_salida):
            return None
        
        try:
            # Buscar en subcarpetas directas (un nivel)
            for item in os.listdir(self.carpeta_salida):
                ruta_item = os.path.join(self.carpeta_salida, item)
                if not os.path.isdir(ruta_item):
                    continue
                # Buscar cartas glosas en esta subcarpeta
                for filename in os.listdir(ruta_item):
                    if filename.lower().endswith('.pdf'):
                        match = re.search(rf'{re.escape(serie)}[_-]{re.escape(numero)}[_-]', filename, re.IGNORECASE)
                        if match:
                            return ruta_item
        except Exception:
            pass
        return None

    def ejecutar(self):
        resultados = {'exitosos': [], 'fallidos': []}
        nombre_csv = os.path.basename(self.ruta_csv)
        try:
            self.progreso_actualizado.emit(
                f"<font color='{COLOR_INFO}'>Leyendo CSV: <b>{nombre_csv}</b></font>"
            )

            with open(self.ruta_csv, 'r', encoding='utf-8-sig', newline='') as f:
                muestra = f.read(4096)
                f.seek(0)
                delimitador = ','
                if muestra.count(';') > muestra.count(','):
                    delimitador = ';'
                reader = csv.DictReader(f, delimiter=delimitador)
                fieldnames = reader.fieldnames or []
                all_rows = list(reader)

            if not all_rows:
                resultados['fallidos'].append({
                    'archivo': nombre_csv,
                    'razon': 'El CSV está vacío o no tiene filas de datos.'
                })
                self.proceso_finalizado.emit(resultados)
                return

            self.progreso_actualizado.emit(
                f"<font color='{COLOR_INFO}'>{len(all_rows)} registros totales encontrados.</font>"
            )

            # Detectar columnas PrefijoFac_ y NumeroFac_ en el CSV
            col_prefijo = _buscar_columna('PrefijoFac_', fieldnames)
            col_numero = _buscar_columna('NumeroFac_', fieldnames)

            if not col_prefijo or not col_numero:
                resultados['fallidos'].append({
                    'archivo': nombre_csv,
                    'razon': (
                        f"No se encontraron las columnas 'PrefijoFac_' y/o 'NumeroFac_' en el CSV. "
                        f"Columnas detectadas: {', '.join(fieldnames)}"
                    )
                })
                self.proceso_finalizado.emit(resultados)
                return

            self.progreso_actualizado.emit(
                f"<font color='{COLOR_INFO}'>Columnas de factura detectadas: "
                f"<b>{col_prefijo}</b> + <b>{col_numero}</b></font>"
            )

            fecha_hoy = date.today().strftime("%d%m%Y")
            os.makedirs(self.carpeta_salida, exist_ok=True)
            cols = list(all_rows[0].keys())

            for factura_raw in self.facturas:
                parsed = _parsear_factura(factura_raw)
                if not parsed:
                    resultados['fallidos'].append({
                        'archivo': factura_raw,
                        'razon': f"Formato de factura no reconocido: '{factura_raw}'. Use PREFIJOnumero, ej: FECR363035"
                    })
                    self.progreso_actualizado.emit(
                        f"<font color='{COLOR_WARNING}'>⚠ Formato inválido: {factura_raw}</font>"
                    )
                    continue

                prefijo, numero = parsed
                
                # Buscar la carpeta correcta dentro de carpeta_salida basándose en la carta glosa
                carpeta_destino = self.carpeta_salida
                ubicacion_info = ""
                carpeta_encontrada = self._buscar_carpeta_por_factura(prefijo, numero)
                if carpeta_encontrada:
                    carpeta_destino = carpeta_encontrada
                    ubicacion_info = f" (en {os.path.basename(carpeta_encontrada)})"
                
                # Buscar registros en el CSV (con búsqueda flexible)
                filas_fac = [
                    r for r in all_rows
                    if r.get(col_prefijo, '').strip().upper() == prefijo
                    and r.get(col_numero, '').strip() == numero
                ]

                if not filas_fac:
                    razon_falta = "sin datos en CSV"
                    if ubicacion_info:
                        razon_falta += f", pero la carpeta existe {ubicacion_info}"
                    resultados['fallidos'].append({
                        'archivo': factura_raw,
                        'razon': f"No se encontraron registros para {prefijo}{numero} ({razon_falta})."
                    })
                    self.progreso_actualizado.emit(
                        f"<font color='{COLOR_WARNING}'>⚠ {prefijo}{numero}: {razon_falta}{ubicacion_info}</font>"
                    )
                    continue

                os.makedirs(carpeta_destino, exist_ok=True)
                consecutivo = obtener_siguiente_consecutivo(carpeta_destino)
                nombre_salida = f"RTAGLOSA_{self.nit}_{fecha_hoy}_{consecutivo}.txt"
                ruta_salida = os.path.join(carpeta_destino, nombre_salida)

                with open(ruta_salida, 'w', encoding='utf-8', newline='') as f:
                    f.write('|'.join(cols) + '|\n')
                    for row in filas_fac:
                        valores = [str(row.get(c, '')) for c in cols]
                        f.write('|'.join(valores) + '|\n')

                self.progreso_actualizado.emit(
                    f"<font color='{COLOR_SUCCESS}'>✔ Factura <b>{prefijo}{numero}</b> → "
                    f"<b>{nombre_salida}</b> ({len(filas_fac)} registros){ubicacion_info}</font>"
                )
                resultados['exitosos'].append({
                    'factura': f"{prefijo}{numero}",
                    'archivo': nombre_salida,
                    'registros': len(filas_fac),
                    'ruta': ruta_salida
                })

        except Exception as e:
            resultados['fallidos'].append({'archivo': nombre_csv, 'razon': str(e)})
            self.progreso_actualizado.emit(
                f"<font color='{COLOR_ERROR}'>✖ Error crítico: {e}</font>"
            )

        self.proceso_finalizado.emit(resultados)

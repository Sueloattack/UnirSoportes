import os
import shutil
import zipfile
import re
from typing import Callable, Iterable


NIT_FIJO = "800209891"
UMBRAL_TAMANO_BYTES = 20 * 1024 * 1024
UMBRAL_COMPRESION_BYTES = 50 * 1024 * 1024  # 50MB
MAX_BATCH_SIZE_BYTES = 500 * 1024 * 1024


def _cli_logger(mensaje: str, nivel: str = "info"):
    print(mensaje)


def _debe_cancelarse(cancel_check: Callable[[], bool] | None) -> bool:
    return bool(cancel_check and cancel_check())


def _normalizar_facturas(facturas_input: Iterable[str]) -> list[str]:
    facturas = []
    vistos = set()
    for factura in facturas_input:
        factura_limpia = str(factura).strip()
        if factura_limpia and factura_limpia not in vistos:
            facturas.append(factura_limpia)
            vistos.add(factura_limpia)
    return facturas


def _resolver_tipos_requeridos(modo: str) -> list[str]:
    if modo == '3':
        return ['FURIPS']
    tipos_requeridos = ['EPI', 'PDX', 'CRC']
    if modo == '2':
        tipos_requeridos.append('FURIPS')
    return tipos_requeridos


def _resolver_configuracion_busqueda(modo: str) -> tuple[str, bool, bool]:
    if modo == '1':
        return "Estándar (HC+CRC)", True, False
    if modo == '2':
        return "Completa (HC+CRC+FURIPS)", True, True
    if modo == '4':
        return "Solo HC y FURIPS", False, True
    if modo == '6':
        return "Aceptadas (Rta Glosa + Nota Crédito)", False, False
    raise ValueError(f"Modo de búsqueda no válido: {modo}")


def _copiar_o_comprimir_soporte(
    ruta_origen_soporte: str,
    ruta_destino_pdf: str,
    logger: Callable[[str, str], None] = _cli_logger,
) -> str:
    """
    Copia el soporte a la ruta destino en PDF. Si el archivo pesa más de 50MB (50*1024*1024 bytes),
    también genera una versión comprimida .zip en la misma carpeta destino.
    """
    shutil.copy2(ruta_origen_soporte, ruta_destino_pdf)
    size_bytes = os.path.getsize(ruta_origen_soporte)
    if size_bytes > UMBRAL_COMPRESION_BYTES:
        size_mb = size_bytes / (1024 * 1024)
        base_path, _ = os.path.splitext(ruta_destino_pdf)
        ruta_zip = f"{base_path}.zip"
        nombre_pdf_zip = os.path.basename(ruta_destino_pdf)
        with zipfile.ZipFile(ruta_zip, 'w', zipfile.ZIP_DEFLATED) as zipf:
            zipf.write(ruta_destino_pdf, nombre_pdf_zip)
        logger(
            f"  [!] ADVERTENCIA / COMPRESIÓN: El soporte excede 50MB ({size_mb:.2f}MB). Se comprimió automáticamente en '{os.path.basename(ruta_zip)}'",
            "warning",
        )
    elif size_bytes > UMBRAL_TAMANO_BYTES:
        size_mb = size_bytes / (1024 * 1024)
        logger(f"  [!] ADVERTENCIA: El soporte excede 20MB ({size_mb:.2f}MB)", "warning")

    return ruta_destino_pdf


def ejecutar_compresion_en_lotes(
    modo_compresion: str,
    dir_origen: str | list[str] | tuple[str, ...],
    dir_destino: str | list[str] | tuple[str, ...],
    logger: Callable[[str, str], None] = _cli_logger,
    cancel_check: Callable[[], bool] | None = None,
) -> dict:
    if modo_compresion not in ['1', '2', '3', '4']:
        raise ValueError("La modalidad de compresión debe ser 1, 2, 3 o 4.")

    # Normalizar carpetas origen y destino
    if isinstance(dir_origen, str):
        # Si viniere como string único separado por comas o saltos de línea
        rutas_origen_raw = [r.strip() for r in dir_origen.replace('\n', ',').split(',') if r.strip()]
    else:
        rutas_origen_raw = [str(d).strip() for d in dir_origen]

    if isinstance(dir_destino, str):
        rutas_destino_raw = [r.strip() for r in dir_destino.replace('\n', ',').split(',') if r.strip()]
    else:
        rutas_destino_raw = [str(d).strip() for d in dir_destino]

    rutas_origen = [os.path.normpath(d) for d in rutas_origen_raw]
    rutas_destino = [os.path.normpath(d) for d in rutas_destino_raw]

    for d_orig in rutas_origen:
        if not os.path.isdir(d_orig):
            raise ValueError(f"La ruta de origen '{d_orig}' no es un directorio válido.")

    for d_dest in rutas_destino:
        os.makedirs(d_dest, exist_ok=True)

    if modo_compresion == '4':
        if len(rutas_origen) < 2:
            raise ValueError("La modalidad simultánea (Soportes + FURIPS) requiere 2 carpetas de origen (Soportes y FURIPS).")
        origen_sop, origen_furips = rutas_origen[0], rutas_origen[1]
        destino_sop = rutas_destino[0] if len(rutas_destino) >= 1 and rutas_destino[0] else origen_sop
        destino_furips = rutas_destino[1] if len(rutas_destino) >= 2 and rutas_destino[1] else origen_furips

        logger("\n[1/2] Analizando y cruzando facturas entre Soportes (EPI, PDX, CRC) y FURIPS...", "info")

        tipos_sop = {'EPI', 'PDX', 'CRC'}
        grupos_sop = {}
        for filename in os.listdir(origen_sop):
            if _debe_cancelarse(cancel_check):
                return {'estado': 'cancelado', 'zips': 0, 'facturas': 0}
            if not filename.lower().endswith('.pdf'): continue
            partes = os.path.splitext(filename)[0].split('_')
            if len(partes) < 3: continue
            tipo, f_id = partes[0].upper(), partes[-1]
            if tipo in tipos_sop:
                grupos_sop.setdefault(f_id, {})
                if f_id not in grupos_sop or tipo not in grupos_sop[f_id] or os.path.getmtime(os.path.join(origen_sop, filename)) >= os.path.getmtime(grupos_sop[f_id][tipo]):
                    grupos_sop[f_id][tipo] = os.path.join(origen_sop, filename)

        grupos_furips = {}
        for filename in os.listdir(origen_furips):
            if _debe_cancelarse(cancel_check):
                return {'estado': 'cancelado', 'zips': 0, 'facturas': 0}

            ext = os.path.splitext(filename)[1].lower()
            if ext not in ('.pdf', '.txt'):
                continue

            nombre_sin_ext = os.path.splitext(filename)[0]
            # Patrones comunes: COEX33981_FURIPS1.txt, FURIPS_800209891_COEX33981.pdf, etc.
            partes = nombre_sin_ext.split('_')
            factura_id = None
            if len(partes) >= 2:
                if partes[0].upper().startswith("FURIPS"):
                    factura_id = partes[-1]
                else:
                    factura_id = partes[0]

            if factura_id:
                f_id_upper = factura_id.upper()
                grupos_furips.setdefault(f_id_upper, []).append(os.path.join(origen_furips, filename))

        facturas_completas = []
        facturas_incompletas = []

        todas_facturas = sorted(set(grupos_sop.keys()).union(grupos_furips.keys()))
        for f_id in todas_facturas:
            arch_sop_dict = grupos_sop.get(f_id, {})
            arch_furips_list = grupos_furips.get(f_id, [])

            faltantes_sop = tipos_sop.difference(arch_sop_dict.keys())
            if not faltantes_sop and arch_furips_list:
                arch_sop = [arch_sop_dict[t] for t in sorted(tipos_sop)]
                size_sop = sum(os.path.getsize(f) for f in arch_sop)
                size_furips = sum(os.path.getsize(f) for f in arch_furips_list)
                facturas_completas.append({
                    'id': f_id,
                    'archivos_sop': arch_sop,
                    'size_sop': size_sop,
                    'archivos_furips': arch_furips_list,
                    'size_furips': size_furips,
                })
            else:
                facturas_incompletas.append(f_id)

        if not facturas_completas:
            logger("No se encontraron facturas completas que tengan los 3 soportes Y su FURIPS correspondiente.", "warning")
            if facturas_incompletas:
                logger(f"Facturas omitidas por estar incompletas en alguna carpeta: {len(facturas_incompletas)}", "warning")
            return {'estado': 'sin_facturas', 'zips': 0, 'facturas': 0, 'omitidas': len(facturas_incompletas)}

        logger(f"Total de facturas completas en ambas carpetas: {len(facturas_completas)}", "success")
        if facturas_incompletas:
            logger(f"Aviso: Se omitirán {len(facturas_incompletas)} facturas por estar incompletas.", "warning")

        logger("\n[2/2] Creando lotes ZIP simultáneos en ambas carpetas destino...", "info")

        lote_actual = []
        size_lote_sop = 0
        size_lote_furips = 0
        numero_lote = 1
        total_zips = 0

        def crear_zips_dobles(lote: list[dict], numero: int):
            nombre_zip = f"SUBIDA {numero}.zip"
            ruta_zip_sop = os.path.join(destino_sop, nombre_zip)
            ruta_zip_furips = os.path.join(destino_furips, nombre_zip)

            logger(f"  > Generando {nombre_zip} en Soportes y FURIPS (Facturas: {len(lote)})", "info")

            with zipfile.ZipFile(ruta_zip_sop, 'w', zipfile.ZIP_DEFLATED) as zipf_s:
                for item in lote:
                    for f_path in item['archivos_sop']:
                        zipf_s.write(f_path, os.path.basename(f_path))

            with zipfile.ZipFile(ruta_zip_furips, 'w', zipfile.ZIP_DEFLATED) as zipf_f:
                for item in lote:
                    for f_path in item['archivos_furips']:
                        zipf_f.write(f_path, os.path.basename(f_path))

            return 1

        for f_item in facturas_completas:
            if _debe_cancelarse(cancel_check):
                logger("Compresión cancelada por el usuario.", "warning")
                return {'estado': 'cancelado', 'zips': total_zips, 'facturas': total_zips, 'omitidas': len(facturas_incompletas)}

            if (size_lote_sop + f_item['size_sop'] > MAX_BATCH_SIZE_BYTES or size_lote_furips + f_item['size_furips'] > MAX_BATCH_SIZE_BYTES) and lote_actual:
                total_zips += crear_zips_dobles(lote_actual, numero_lote)
                numero_lote += 1
                lote_actual = []
                size_lote_sop = 0
                size_lote_furips = 0

            lote_actual.append(f_item)
            size_lote_sop += f_item['size_sop']
            size_lote_furips += f_item['size_furips']

        if lote_actual:
            total_zips += crear_zips_dobles(lote_actual, numero_lote)

        logger("\n" + "=" * 40, "info")
        logger("PROCESO DE COMPRESIÓN SIMULTÁNEA FINALIZADO", "success")
        logger(f"Total de parejas de .ZIP creadas: {total_zips}", "success")
        logger(f"Total de facturas comprimidas: {len(facturas_completas)}", "success")
        logger("=" * 40, "info")

        return {
            'estado': 'completado',
            'zips': total_zips,
            'facturas': len(facturas_completas),
            'omitidas': len(facturas_incompletas),
        }

    # Lógica estándar de 1 sola carpeta origen y 1 sola carpeta destino (modos 1, 2 y 3)
    dir_orig = rutas_origen[0]
    dir_dest = rutas_destino[0]
    tipos_requeridos = set(_resolver_tipos_requeridos(modo_compresion))

    logger("\n[1/2] Analizando archivos y agrupando por factura...", "info")

    grupos = {}
    for filename in os.listdir(dir_orig):
        if _debe_cancelarse(cancel_check):
            logger("Compresión cancelada por el usuario.", "warning")
            return {'estado': 'cancelado', 'zips': 0, 'facturas': 0}

        if not filename.lower().endswith('.pdf'):
            continue

        nombre_sin_ext = os.path.splitext(filename)[0]
        partes = nombre_sin_ext.split('_')
        if len(partes) < 3:
            continue

        tipo_archivo = partes[0].upper()
        factura_id = partes[-1]
        if tipo_archivo not in tipos_requeridos:
            continue

        ruta_archivo = os.path.join(dir_orig, filename)
        if factura_id not in grupos:
            grupos[factura_id] = {}

        ruta_existente = grupos[factura_id].get(tipo_archivo)
        if ruta_existente is None or os.path.getmtime(ruta_archivo) >= os.path.getmtime(ruta_existente):
            grupos[factura_id][tipo_archivo] = ruta_archivo

    facturas_completas = []
    facturas_incompletas = []

    for factura_id, archivos_por_tipo in sorted(grupos.items()):
        faltantes = tipos_requeridos.difference(archivos_por_tipo.keys())
        if not faltantes:
            archivos_factura = [archivos_por_tipo[tipo] for tipo in sorted(tipos_requeridos)]
            size_total = sum(os.path.getsize(ruta) for ruta in archivos_factura)
            facturas_completas.append({'id': factura_id, 'archivos': archivos_factura, 'size': size_total})
        else:
            facturas_incompletas.append(factura_id)

    if not facturas_completas:
        logger(
            f"No se encontraron facturas completas (con {len(tipos_requeridos)} archivos requeridos cada una).",
            "warning",
        )
        if facturas_incompletas:
            logger(f"Facturas incompletas detectadas: {len(facturas_incompletas)}", "warning")
        return {'estado': 'sin_facturas', 'zips': 0, 'facturas': 0, 'omitidas': len(facturas_incompletas)}

    logger(f"Total de facturas completas encontradas: {len(facturas_completas)}", "success")
    if facturas_incompletas:
        logger(f"Aviso: Se omitirán {len(facturas_incompletas)} facturas por estar incompletas.", "warning")

    logger("\n[2/2] Creando lotes ZIP...", "info")

    lote_actual = []
    size_lote_actual = 0
    numero_lote = 1
    total_zips = 0
    total_facturas_en_zip = 0

    def crear_zip(lote: list[dict], numero: int):
        nombre_zip = f"SUBIDA {numero}.zip"
        ruta_zip = os.path.join(dir_dest, nombre_zip)
        logger(f"  > Generando {nombre_zip} (Facturas: {len(lote)})", "info")
        with zipfile.ZipFile(ruta_zip, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for factura_data in lote:
                for archivo_path in factura_data['archivos']:
                    zipf.write(archivo_path, os.path.basename(archivo_path))
        return 1

    for factura_data in facturas_completas:
        if _debe_cancelarse(cancel_check):
            logger("Compresión cancelada por el usuario.", "warning")
            return {
                'estado': 'cancelado',
                'zips': total_zips,
                'facturas': total_facturas_en_zip,
                'omitidas': len(facturas_incompletas),
            }

        if size_lote_actual + factura_data['size'] > MAX_BATCH_SIZE_BYTES and lote_actual:
            total_zips += crear_zip(lote_actual, numero_lote)
            total_facturas_en_zip += len(lote_actual)
            numero_lote += 1
            lote_actual = []
            size_lote_actual = 0

        lote_actual.append(factura_data)
        size_lote_actual += factura_data['size']

    if lote_actual:
        total_zips += crear_zip(lote_actual, numero_lote)
        total_facturas_en_zip += len(lote_actual)

    logger("\n" + "=" * 40, "info")
    logger("PROCESO DE COMPRESIÓN FINALIZADO", "success")
    logger(f"Total de archivos .ZIP creados: {total_zips}", "success")
    logger(f"Total de facturas comprimidas: {len(facturas_completas)}", "success")
    logger("=" * 40, "info")

    return {
        'estado': 'completado',
        'zips': total_zips,
        'facturas': len(facturas_completas),
        'omitidas': len(facturas_incompletas),
    }


def ejecutar_validacion_soportes(
    dir_val: str,
    facturas_check: Iterable[str],
    modo_val: str,
    logger: Callable[[str, str], None] = _cli_logger,
    cancel_check: Callable[[], bool] | None = None,
) -> dict:
    if modo_val not in ['1', '2']:
        raise ValueError("La modalidad de validación debe ser 1 o 2.")
    if not os.path.isdir(dir_val):
        raise ValueError(f"La ruta '{dir_val}' no es un directorio válido.")

    facturas = _normalizar_facturas(facturas_check)
    if not facturas:
        raise ValueError("No se ingresaron facturas para validar.")

    tipos_requeridos = _resolver_tipos_requeridos(modo_val)
    logger(f"\n[1/1] Validando {len(facturas)} facturas...", "info")

    completas = 0
    incompletas = 0
    reporte_validacion = []

    for factura in facturas:
        if _debe_cancelarse(cancel_check):
            logger("Validación cancelada por el usuario.", "warning")
            return {
                'estado': 'cancelado',
                'completas': completas,
                'incompletas': incompletas,
                'reporte': reporte_validacion,
            }

        faltantes = []
        for tipo in tipos_requeridos:
            nombre_archivo = f"{tipo}_{NIT_FIJO}_{factura}.pdf"
            ruta_archivo = os.path.join(dir_val, nombre_archivo)
            if not os.path.exists(ruta_archivo):
                faltantes.append(tipo)

        if not faltantes:
            logger(f"  [OK] Factura {factura}: Completa", "success")
            completas += 1
        else:
            msg_error = f"  [X] Factura {factura}: Faltan {', '.join(faltantes)}"
            logger(msg_error, "warning")
            incompletas += 1
            reporte_validacion.append(msg_error)

    logger("\n" + "=" * 40, "info")
    logger("RESULTADO DE VALIDACIÓN:", "info")
    logger(f"Total revisadas: {len(facturas)}", "info")
    logger(f"Completas: {completas}", "success")
    logger(f"Incompletas: {incompletas}", "warning")
    logger("=" * 40, "info")

    return {
        'estado': 'completado',
        'total': len(facturas),
        'completas': completas,
        'incompletas': incompletas,
        'reporte': reporte_validacion,
    }


def ejecutar_busqueda_soportes_nu(
    modo: str,
    facturas_input: Iterable[str],
    dir_origen: str,
    dir_destino: str,
    logger: Callable[[str, str], None] = _cli_logger,
    cancel_check: Callable[[], bool] | None = None,
) -> dict:
    tag, requiere_crc, requiere_furips = _resolver_configuracion_busqueda(modo)

    if not os.path.isdir(dir_origen):
        raise ValueError(f"La ruta '{dir_origen}' no es un directorio válido.")

    facturas = _normalizar_facturas(facturas_input)
    if not facturas:
        raise ValueError("No se ingresaron facturas. Saliendo.")

    os.makedirs(dir_destino, exist_ok=True)

    logger("\n[1/2] Indexando archivos... (esto puede tardar si hay miles de carpetas)", "info")

    indice = {}
    total_indexados = 0

    try:
        for root, _dirs, files in os.walk(dir_origen):
            if _debe_cancelarse(cancel_check):
                logger("Búsqueda cancelada durante la indexación.", "warning")
                return {'estado': 'cancelado', 'exitos': 0, 'errores': 0, 'archivos': 0}

            for filename in files:
                nombre_sin_ext = os.path.splitext(filename)[0].upper()
                if nombre_sin_ext not in indice:
                    indice[nombre_sin_ext] = []
                indice[nombre_sin_ext].append(os.path.join(root, filename))
                total_indexados += 1
    except Exception as e:
        raise RuntimeError(f"Error crítico indexando archivos: {e}") from e

    logger(f"Indexación completada. {total_indexados} archivos encontrados en total.", "success")
    logger("\n[2/2] Procesando facturas...", "info")

    exitos = 0
    errores = 0
    total_archivos_creados = 0
    fallas = []

    for factura in facturas:
        if _debe_cancelarse(cancel_check):
            logger("Búsqueda cancelada por el usuario.", "warning")
            break

        logger(f"\nFactura: {factura}", "info")
        motivos_falla = []

        if modo == '6':
            # Modo Aceptadas: Busca Respuesta Glosa (CRC) y Nota Crédito (HEV)
            encontrado_rta = False
            encontrado_nc = False

            nombre_nc_buscado = f"NC{factura}".upper()
            nombre_coex_buscado = f"COEX{factura}".upper()
            nombre_factura_buscado = factura.upper()
            nombre_crc_nit_buscado = f"CRC_{NIT_FIJO}_{factura}".upper()

            # 1. Buscar Respuesta Glosa (CRC)
            ruta_rta = None
            factura_completa = factura.upper()

            if nombre_crc_nit_buscado in indice:
                ruta_rta = max(indice[nombre_crc_nit_buscado], key=os.path.getmtime)
            elif nombre_coex_buscado in indice:
                ruta_rta = max(indice[nombre_coex_buscado], key=os.path.getmtime)
            elif nombre_factura_buscado in indice:
                ruta_rta = max(indice[nombre_factura_buscado], key=os.path.getmtime)
            else:
                # Búsqueda por coincidencia de fragmento de factura en la Respuesta Glosa
                for clave in indice:
                    if factura.upper() in clave and not clave.startswith("NC"):
                        ruta_rta = max(indice[clave], key=os.path.getmtime)
                        break

            if ruta_rta:
                encontrado_rta = True
                nombre_archivo_rta = os.path.basename(ruta_rta)
                nombre_sin_ext_rta = os.path.splitext(nombre_archivo_rta)[0].strip()

                # Si el archivo encontrado es de la forma COEX43324.pdf o CRC_800209891_COEX43324.pdf
                # extraemos la identificación completa de la factura (ej: COEX43324)
                if "_" in nombre_sin_ext_rta:
                    partes_rta = nombre_sin_ext_rta.split("_")
                    factura_completa = partes_rta[-1].upper()
                else:
                    factura_completa = nombre_sin_ext_rta.upper()

                _, ext = os.path.splitext(ruta_rta)
                extension = ext if ext else '.pdf'
                try:
                    nombre_crc = f"CRC_{NIT_FIJO}_{factura_completa}{extension}"
                    _copiar_o_comprimir_soporte(ruta_rta, os.path.join(dir_destino, nombre_crc), logger=logger)
                    logger(f"  [OK] Rta Glosa -> {nombre_crc}", "success")
                    total_archivos_creados += 1
                except Exception as e:
                    motivos_falla.append(f"Error al copiar Rta Glosa (CRC): {e}")
            else:
                motivos_falla.append(f"No se encontró Rta Glosa ({nombre_coex_buscado} ni CRC_{NIT_FIJO}_{factura})")

            # 2. Buscar Nota Crédito (HEV)
            ruta_nc = None
            digitos_factura = re.sub(r'\D', '', factura_completa) or re.sub(r'\D', '', factura)

            posibles_nombres_nc = [
                f"NC{factura}".upper(),
                f"NC_{factura}".upper(),
                f"{factura}-NC".upper(),
                f"{factura}_NC".upper(),
                f"NC{factura_completa}".upper(),
                f"NC_{factura_completa}".upper(),
                f"{factura_completa}-NC".upper(),
                f"{factura_completa}_NC".upper(),
            ]
            if digitos_factura:
                posibles_nombres_nc.extend([
                    f"NC{digitos_factura}".upper(),
                    f"NC_{digitos_factura}".upper(),
                    f"N{digitos_factura}".upper(),
                    f"N_{digitos_factura}".upper(),
                    f"{digitos_factura}-NC".upper(),
                    f"{digitos_factura}_NC".upper(),
                    f"{digitos_factura}NC".upper(),
                ])

            for nombre_nc_cand in posibles_nombres_nc:
                if nombre_nc_cand in indice:
                    ruta_nc = max(indice[nombre_nc_cand], key=os.path.getmtime)
                    break

            if not ruta_nc:
                # Búsqueda por escaneo del índice con patrones flexibles (prefijos/sufijos/palabras clave)
                for clave, rutas_cand in indice.items():
                    clave_up = clave.upper()
                    # Caso 1: Empieza o termina con NC o N y coincide con la factura o dígitos
                    es_nc_tipo = clave_up.startswith(("NC", "N_", "NOTA")) or clave_up.endswith(("-NC", "_NC", "NC", "CREDITO")) or ("NOTA" in clave_up and "CREDITO" in clave_up)
                    coincide_factura = (factura.upper() in clave_up) or (factura_completa and factura_completa in clave_up) or (digitos_factura and digitos_factura in clave_up)

                    if es_nc_tipo and coincide_factura:
                        ruta_nc = max(rutas_cand, key=os.path.getmtime)
                        break

            if not ruta_nc and ruta_rta:
                # Búsqueda dentro de la misma carpeta contenedora de la Respuesta Glosa
                dir_padre_factura = os.path.dirname(ruta_rta)
                if os.path.isdir(dir_padre_factura):
                    for fn in os.listdir(dir_padre_factura):
                        fn_up = fn.upper()
                        if fn_up.endswith(".PDF"):
                            # Coincide si el nombre contiene NC, NOTA, CREDITO o empieza por N + números
                            if ("NC" in fn_up or "NOTA" in fn_up or "CREDITO" in fn_up or re.match(r'^N\d+', fn_up)):
                                ruta_nc = os.path.join(dir_padre_factura, fn)
                                break

            if ruta_nc:
                encontrado_nc = True
                _, ext = os.path.splitext(ruta_nc)
                extension = ext if ext else '.pdf'
                try:
                    nombre_hev = f"HEV_{NIT_FIJO}_{factura_completa}{extension}"
                    _copiar_o_comprimir_soporte(ruta_nc, os.path.join(dir_destino, nombre_hev), logger=logger)
                    logger(f"  [OK] Nota Crédito -> {nombre_hev}", "success")
                    total_archivos_creados += 1
                except Exception as e:
                    motivos_falla.append(f"Error al copiar Nota Crédito (HEV): {e}")
            else:
                motivos_falla.append(f"No se encontró Nota Crédito (para {factura_completa})")

            if encontrado_rta and encontrado_nc and not motivos_falla:
                exitos += 1
            else:
                errores += 1
                mensaje_falla = f"Factura: {factura} | Fallos: {', '.join(motivos_falla)}"
                logger(f"  [!] Factura {factura} INCOMPLETA: {', '.join(motivos_falla)}", "warning")
                fallas.append(mensaje_falla)

            continue

        encontrado_hc = False
        encontrado_factura = not requiere_crc
        encontrado_furips = not requiere_furips

        nombre_hc_buscado = f"HC_{factura}".upper()
        nombre_factura_buscado = factura.upper()
        nombre_epi_nit_buscado = f"EPI_{NIT_FIJO}_{factura}".upper()
        nombre_pdx_nit_buscado = f"PDX_{NIT_FIJO}_{factura}".upper()
        nombre_furips_nit_buscado = f"FURIPS_{NIT_FIJO}_{factura}".upper()
        nombre_furips_buscado = f"FURIPS_{factura}".upper()
        nombre_soporte_unido = f"{factura}-SOPORTE".upper()

        ruta_epi = max(indice[nombre_epi_nit_buscado], key=os.path.getmtime) if nombre_epi_nit_buscado in indice else None
        ruta_pdx = max(indice[nombre_pdx_nit_buscado], key=os.path.getmtime) if nombre_pdx_nit_buscado in indice else None

        ruta_hc = None
        if not ruta_epi or not ruta_pdx:
            if nombre_hc_buscado in indice:
                ruta_hc = max(indice[nombre_hc_buscado], key=os.path.getmtime)
            elif nombre_soporte_unido in indice:
                ruta_hc = max(indice[nombre_soporte_unido], key=os.path.getmtime)
                logger(f"  [!] Usando archivo UNIDO para HC: {os.path.basename(ruta_hc)}", "warning")

        if ruta_hc and not ruta_epi:
            ruta_epi = ruta_hc
        if ruta_hc and not ruta_pdx:
            ruta_pdx = ruta_hc

        if ruta_epi and ruta_pdx:
            encontrado_hc = True
            try:
                _, ext_epi = os.path.splitext(ruta_epi)
                extension_epi = ext_epi if ext_epi else '.pdf'
                nombre_epi = f"EPI_{NIT_FIJO}_{factura}{extension_epi}"
                _copiar_o_comprimir_soporte(ruta_epi, os.path.join(dir_destino, nombre_epi), logger=logger)

                _, ext_pdx = os.path.splitext(ruta_pdx)
                extension_pdx = ext_pdx if ext_pdx else '.pdf'
                nombre_pdx = f"PDX_{NIT_FIJO}_{factura}{extension_pdx}"
                _copiar_o_comprimir_soporte(ruta_pdx, os.path.join(dir_destino, nombre_pdx), logger=logger)

                if ruta_epi == ruta_pdx:
                    logger(f"  [OK] HC -> {nombre_epi} y {nombre_pdx}", "success")
                else:
                    logger(f"  [OK] EPI/PDX homologados -> {nombre_epi} y {nombre_pdx}", "success")
                total_archivos_creados += 2
            except Exception as e:
                motivos_falla.append(f"Error al copiar EPI/PDX: {e}")
        else:
            if not ruta_epi:
                motivos_falla.append(f"No se encontró EPI_{NIT_FIJO}_{factura} ni HC_{factura} ni {factura}-SOPORTE")
            if not ruta_pdx:
                motivos_falla.append(f"No se encontró PDX_{NIT_FIJO}_{factura} ni HC_{factura} ni {factura}-SOPORTE")

        if requiere_crc:
            if nombre_factura_buscado in indice:
                encontrado_factura = True
                rutas = indice[nombre_factura_buscado]
                ruta_src = max(rutas, key=os.path.getmtime)

                _, ext = os.path.splitext(ruta_src)
                extension = ext if ext else '.pdf'

                try:
                    nombre_crc = f"CRC_{NIT_FIJO}_{factura}{extension}"
                    _copiar_o_comprimir_soporte(ruta_src, os.path.join(dir_destino, nombre_crc), logger=logger)
                    logger(f"  [OK] Factura -> {nombre_crc}", "success")
                    total_archivos_creados += 1
                except Exception as e:
                    motivos_falla.append(f"Error al copiar Factura (CRC): {e}")
            else:
                motivos_falla.append(f"No se encontró archivo de factura {factura}")

        if requiere_furips:
            ruta_furips = None
            if nombre_furips_nit_buscado in indice:
                ruta_furips = max(indice[nombre_furips_nit_buscado], key=os.path.getmtime)
            elif nombre_furips_buscado in indice:
                ruta_furips = max(indice[nombre_furips_buscado], key=os.path.getmtime)
            elif nombre_soporte_unido in indice:
                ruta_furips = max(indice[nombre_soporte_unido], key=os.path.getmtime)
                logger(f"  [!] Usando archivo UNIDO para FURIPS: {os.path.basename(ruta_furips)}", "warning")

            if ruta_furips:
                encontrado_furips = True
                _, ext = os.path.splitext(ruta_furips)
                extension = ext if ext else '.pdf'

                try:
                    nombre_furips_dst = f"FURIPS_{NIT_FIJO}_{factura}{extension}"
                    _copiar_o_comprimir_soporte(ruta_furips, os.path.join(dir_destino, nombre_furips_dst), logger=logger)
                    logger(f"  [OK] FURIPS -> {nombre_furips_dst}", "success")
                    total_archivos_creados += 1
                except Exception as e:
                    motivos_falla.append(f"Error al copiar FURIPS: {e}")
            else:
                motivos_falla.append(f"No se encontró FURIPS_{NIT_FIJO}_{factura} ni FURIPS_{factura} ni {factura}-SOPORTE")

        if encontrado_hc and encontrado_factura and encontrado_furips and not motivos_falla:
            exitos += 1
        else:
            errores += 1
            mensaje_falla = f"Factura: {factura} | Fallos: {', '.join(motivos_falla)}"
            logger(f"  [!] Factura {factura} INCOMPLETA: {', '.join(motivos_falla)}", "warning")
            fallas.append(mensaje_falla)

    ruta_reporte = None
    if fallas:
        ruta_reporte = os.path.join(dir_destino, "facturas_fallidas.txt")
        try:
            with open(ruta_reporte, "w", encoding="utf-8") as reporte:
                reporte.write("REPORTE DE FACTURAS FALLIDAS O INCOMPLETAS\n")
                reporte.write("=" * 50 + "\n")
                reporte.write(f"Modalidad: {tag}\n\n")
                for falla in fallas:
                    reporte.write(f"- {falla}\n")
            logger(f"\n[!] Se ha generado el reporte de fallas en: {ruta_reporte}", "warning")
        except Exception as e:
            logger(f"Error al crear el reporte de fallas: {e}", "error")

    estado = 'cancelado' if _debe_cancelarse(cancel_check) else 'completado'
    logger("\n" + "=" * 40, "info")
    logger(f"RESUMEN FINAL ({tag}):", "info")
    logger(f"Facturas completas: {exitos}", "success")
    logger(f"Facturas incompletas/fallidas: {errores}", "warning")
    logger(f"Total de archivos generados: {total_archivos_creados}", "success")
    logger("=" * 40, "info")

    return {
        'estado': estado,
        'modo': modo,
        'tag': tag,
        'exitos': exitos,
        'errores': errores,
        'archivos': total_archivos_creados,
        'reporte': ruta_reporte,
        'fallas': fallas,
    }


def comprimir_en_lotes():
    print("\n--- COMPRESIÓN DE ARCHIVOS EN LOTES (ZIP < 500MB) ---")

    print("\n¿Qué modalidad desea comprimir?")
    print("1. Estándar (3 archivos: EPI, PDX, CRC)")
    print("2. Completa (4 archivos: EPI, PDX, CRC, FURIPS)")
    print("3. Solo FURIPS (1 archivo: FURIPS)")
    print("4. Simultánea Soportes + FURIPS (En 2 carpetas destino con los mismos lotes)")
    while True:
        modo_compresion = input("Seleccione (1, 2, 3 o 4): ").strip()
        if modo_compresion in ['1', '2', '3', '4']:
            break
        print("Opción no válida.")

    if modo_compresion == '4':
        while True:
            dir_origen_sop = input("\nIngrese la ruta de la carpeta con los SOPORTES (EPI, PDX, CRC): ").strip()
            if os.path.isdir(dir_origen_sop): break
            print("Error: Ruta no válida.")
        while True:
            dir_origen_fur = input("Ingrese la ruta de la carpeta con los FURIPS: ").strip()
            if os.path.isdir(dir_origen_fur): break
            print("Error: Ruta no válida.")
        while True:
            dir_dest_sop = input("\nIngrese la carpeta DESTINO para los ZIPs de SOPORTES: ").strip()
            if dir_dest_sop: os.makedirs(dir_dest_sop, exist_ok=True); break
        while True:
            dir_dest_fur = input("Ingrese la carpeta DESTINO para los ZIPs de FURIPS: ").strip()
            if dir_dest_fur: os.makedirs(dir_dest_fur, exist_ok=True); break

        ejecutar_compresion_en_lotes('4', [dir_origen_sop, dir_origen_fur], [dir_dest_sop, dir_dest_fur], logger=_cli_logger)
        return

    while True:
        dir_origen = input("\nIngrese la ruta de la carpeta con los PDFs a comprimir: ").strip()
        if os.path.isdir(dir_origen):
            break
        print(f"Error: La ruta '{dir_origen}' no es un directorio válido.")

    while True:
        dir_destino = input("Ingrese la ruta donde se guardarán los archivos .ZIP: ").strip()
        if not os.path.exists(dir_destino):
            try:
                os.makedirs(dir_destino)
                break
            except Exception as e:
                print(f"Error al crear el directorio: {e}")
        elif os.path.isdir(dir_destino):
            break
        else:
            print("La ruta de destino no es válida.")

    ejecutar_compresion_en_lotes(modo_compresion, dir_origen, dir_destino, logger=_cli_logger)


def validar_soportes_existentes():
    print("\n--- VALIDADORA DE SOPORTES ---")

    while True:
        dir_val = input("\nIngrese la ruta de la carpeta que desea validar: ").strip()
        if os.path.isdir(dir_val):
            break
        print(f"Error: La ruta '{dir_val}' no es un directorio válido.")

    print("\nIngrese el listado de facturas a validar (una por línea, deje en blanco para terminar):")
    facturas_check = []
    while True:
        entrada = input("> ").strip()
        if not entrada:
            break
        facturas_check.append(entrada)

    if not facturas_check:
        print("No se ingresaron facturas.")
        return

    print("\n¿Qué modalidad desea validar?")
    print("1. Estándar (3 archivos: EPI, PDX, CRC)")
    print("2. Completa (4 archivos: EPI, PDX, CRC, FURIPS)")
    while True:
        modo_val = input("Seleccione (1 o 2): ").strip()
        if modo_val in ['1', '2']:
            break
        print("Opción no válida.")

    ejecutar_validacion_soportes(dir_val, facturas_check, modo_val, logger=_cli_logger)


def buscar_y_procesar_soportes_nu():
    print("=== BUSCADOR DE SOPORTES NU (SOPORTES + COMPRESIÓN + VALIDACIÓN) ===")

    print("\nSeleccione la operación a realizar:")
    print("1. Buscar y Organizar Soportes - Modalidad Estándar (3 archivos: HC, CRC)")
    print("2. Buscar y Organizar Soportes - Modalidad Completa (4 archivos: HC, CRC, FURIPS)")
    print("3. Comprimir Archivos en Lotes (ZIP < 500MB)")
    print("4. Buscar y Organizar Soportes - Solo HC y FURIPS (3 archivos: HC, FURIPS)")
    print("5. Validar Soportes Existentes en Carpeta")
    print("6. Buscar y Organizar Aceptadas (2 archivos: Rta Glosa CRC + Nota Crédito HEV)")

    while True:
        choice = input("Seleccione una opción (1, 2, 3, 4, 5 o 6): ").strip()
        if choice in ['1', '2', '3', '4', '5', '6']:
            break
        print("Opción no válida.")

    if choice == '3':
        comprimir_en_lotes()
        return
    if choice == '5':
        validar_soportes_existentes()
        return

    print("\nIngrese el listado de facturas (una por línea, deje en blanco y presione Enter para terminar):")
    facturas_input = []
    while True:
        entrada = input("> ").strip()
        if not entrada:
            break
        facturas_input.append(entrada)

    if not facturas_input:
        print("No se ingresaron facturas. Saliendo.")
        return

    while True:
        dir_origen = input("\nIngrese la ruta de la carpeta de ORIGEN (donde buscará): ").strip()
        if os.path.isdir(dir_origen):
            break
        print(f"Error: La ruta '{dir_origen}' no es un directorio válido.")

    while True:
        dir_destino = input("Ingrese la ruta de la carpeta de DESTINO: ").strip()
        if not os.path.exists(dir_destino):
            try:
                os.makedirs(dir_destino)
                break
            except Exception as e:
                print(f"Error al crear el directorio de destino: {e}")
        elif os.path.isdir(dir_destino):
            break
        else:
            print("La ruta de destino no es válida.")

    ejecutar_busqueda_soportes_nu(choice, facturas_input, dir_origen, dir_destino, logger=_cli_logger)


if __name__ == "__main__":
    buscar_y_procesar_soportes_nu()
    input("\nPresione Enter para salir...")

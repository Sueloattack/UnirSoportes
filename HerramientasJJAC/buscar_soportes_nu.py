import os
import shutil
import zipfile
import re
from typing import Callable, Iterable


NIT_FIJO = "800209891"
UMBRAL_TAMANO_BYTES = 20 * 1024 * 1024
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
    raise ValueError(f"Modo de búsqueda no válido: {modo}")


def ejecutar_compresion_en_lotes(
    modo_compresion: str,
    dir_origen: str,
    dir_destino: str,
    logger: Callable[[str, str], None] = _cli_logger,
    cancel_check: Callable[[], bool] | None = None,
) -> dict:
    if modo_compresion not in ['1', '2']:
        raise ValueError("La modalidad de compresión debe ser 1 o 2.")
    if not os.path.isdir(dir_origen):
        raise ValueError(f"La ruta '{dir_origen}' no es un directorio válido.")

    os.makedirs(dir_destino, exist_ok=True)
    tipos_requeridos = set(_resolver_tipos_requeridos(modo_compresion))

    logger("\n[1/2] Analizando archivos y agrupando por factura...", "info")

    grupos = {}
    for filename in os.listdir(dir_origen):
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

        ruta_archivo = os.path.join(dir_origen, filename)
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
        ruta_zip = os.path.join(dir_destino, nombre_zip)
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
                if os.path.getsize(ruta_epi) > UMBRAL_TAMANO_BYTES:
                    logger("  [!] ADVERTENCIA: Soporte EPI excede 20MB", "warning")

                _, ext_pdx = os.path.splitext(ruta_pdx)
                extension_pdx = ext_pdx if ext_pdx else '.pdf'
                if os.path.getsize(ruta_pdx) > UMBRAL_TAMANO_BYTES:
                    logger("  [!] ADVERTENCIA: Soporte PDX excede 20MB", "warning")

                nombre_epi = f"EPI_{NIT_FIJO}_{factura}{extension_epi}"
                shutil.copy2(ruta_epi, os.path.join(dir_destino, nombre_epi))

                nombre_pdx = f"PDX_{NIT_FIJO}_{factura}{extension_pdx}"
                shutil.copy2(ruta_pdx, os.path.join(dir_destino, nombre_pdx))

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

                if os.path.getsize(ruta_src) > UMBRAL_TAMANO_BYTES:
                    logger("  [!] ADVERTENCIA: Factura original excede 20MB", "warning")

                try:
                    nombre_crc = f"CRC_{NIT_FIJO}_{factura}{extension}"
                    shutil.copy2(ruta_src, os.path.join(dir_destino, nombre_crc))
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

                if os.path.getsize(ruta_furips) > UMBRAL_TAMANO_BYTES:
                    logger("  [!] ADVERTENCIA: Soporte FURIPS excede 20MB", "warning")

                try:
                    nombre_furips_dst = f"FURIPS_{NIT_FIJO}_{factura}{extension}"
                    shutil.copy2(ruta_furips, os.path.join(dir_destino, nombre_furips_dst))
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
    while True:
        modo_compresion = input("Seleccione (1 o 2): ").strip()
        if modo_compresion in ['1', '2']:
            break
        print("Opción no válida.")

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

    while True:
        choice = input("Seleccione una opción (1, 2, 3, 4 o 5): ").strip()
        if choice in ['1', '2', '3', '4', '5']:
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

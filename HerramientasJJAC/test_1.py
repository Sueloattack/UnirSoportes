import os
from pathlib import Path
try:
    from pypdf import PdfWriter, PdfReader
except ImportError:
    print("Error: Instala pypdf ejecutando: pip install pypdf")
    exit()

def obtener_lista():
    print("\n1. Pega el listado de facturas (COEX..., FECR...).")
    print("   Presiona ENTER DOS VECES para procesar:")
    lista = []
    while True:
        linea = input().strip()
        if not linea: break
        lista.append(linea)
    return lista

def unificar_solo_epicris():
    """UNE LA RESPUESTA ÚNICAMENTE AL ARCHIVO QUE ES EPICRIS"""
    lista_ids = obtener_lista()
    if not lista_ids: return
    ruta_rta = input("2. Ruta de carpeta de RESPUESTAS: ").strip().replace('"', '')
    ruta_sop = input("3. Ruta de carpeta de SOPORTES: ").strip().replace('"', '')

    for fid in lista_ids:
        print(f"\n>>> PROCESANDO: {fid}")
        # Buscar Rta recursivamente en la carpeta de respuestas
        archivo_rta = next((str(f) for f in Path(ruta_rta).rglob(f"*{fid}*.pdf")), None)
        if not archivo_rta:
            print(f"  [!] No existe respuesta para {fid}")
            continue

        # Buscar SOLO el archivo que termina en _EPICRIS.pdf
        soportes = list(Path(ruta_sop).rglob(f"*_{fid}_EPICRIS.pdf"))
        for s in soportes:
            try:
                if os.path.abspath(s) == os.path.abspath(archivo_rta): continue
                m = PdfWriter()
                m.append(archivo_rta)
                m.append(str(s))
                with open(str(s) + ".tmp", "wb") as f: m.write(f)
                m.close()
                os.replace(str(s) + ".tmp", str(s))
                print(f"  [OK] Rta pegada en EPICRIS: {s.name}")
            except Exception as e: print(f"  [ERROR] {e}")

def limpieza_total_extrema():
    """QUITA LA RESPUESTA DE ABSOLUTAMENTE CUALQUIER PDF QUE TENGA EL ID"""
    print("\n--- MODO LIMPIEZA TOTAL (RESTAURAR TODOS LOS SOPORTES) ---")
    lista_ids = obtener_lista()
    if not lista_ids: return
    ruta_rta = input("2. Ruta de carpeta de RESPUESTAS: ").strip().replace('"', '')
    ruta_sop = input("3. Ruta de carpeta de SOPORTES: ").strip().replace('"', '')

    for fid in lista_ids:
        print(f"\n>>> LIMPANDO TODO LO RELACIONADO A: {fid}")
        # 1. Medir rta (Búsqueda recursiva)
        archivo_rta = next((str(f) for f in Path(ruta_rta).rglob(f"*{fid}*.pdf")), None)
        if not archivo_rta:
            print(f"  [!] Sin rta original para medir. Saltando {fid}")
            continue
        
        paginas_rta = len(PdfReader(archivo_rta).pages)
        
        # 2. Buscar CUALQUIER PDF que contenga el ID (Filtro amplio)
        # Esto atrapará FACTURA, INFOPOL, FACOSTE, etc.
        archivos_a_limpiar = list(Path(ruta_sop).rglob(f"*{fid}*.pdf"))

        for path_pdf in archivos_a_limpiar:
            # No limpiar el archivo de la carpeta de respuestas
            if os.path.abspath(path_pdf) == os.path.abspath(archivo_rta): continue

            try:
                reader = PdfReader(str(path_pdf))
                total = len(reader.pages)

                if total > paginas_rta:
                    # SEGURIDAD: Comparar contenido de la primera página
                    texto_pdf = (reader.pages[0].extract_text() or "")[:500]
                    texto_rta = (PdfReader(archivo_rta).pages[0].extract_text() or "")[:500]
                    
                    if texto_pdf == texto_rta:
                        writer = PdfWriter()
                        # Quitamos las primeras N páginas
                        for i in range(paginas_rta, total):
                            writer.add_page(reader.pages[i])
                        
                        temp = str(path_pdf) + ".tmp"
                        with open(temp, "wb") as f: writer.write(f)
                        os.replace(temp, str(path_pdf))
                        print(f"  [LIMPIO] {path_pdf.name} (coincidencia confirmada)")
                    else:
                        print(f"  [SKIP] {path_pdf.name}: El contenido inicial no coincide con la respuesta.")
                else:
                    print(f"  [INFO] {path_pdf.name} no parece tener la rta pegada (muy corto).")
            except Exception as e:
                print(f"  [ERROR] En {path_pdf.name}: {e}")

def limpieza_automatica_subcarpetas():
    """SCANEA CARPETAS Y LIMPIA EPICRIS AUTOMÁTICAMENTE"""
    print("\n--- MODO LIMPIEZA AUTOMÁTICA POR CARPETAS ---")
    ruta_raiz = input("Ingrese la ruta de la carpeta raíz (donde están las carpetas 4318, 4389, etc.): ").strip().replace('"', '')
    
    if not os.path.isdir(ruta_raiz):
        print(f"Error: '{ruta_raiz}' no es un directorio válido.")
        return

    # Listar carpetas que no sean las de validación
    carpetas = [d for d in Path(ruta_raiz).iterdir() if d.is_dir() and d.name.upper() not in ["VALIDACION", "VALIDADORECAT_2026"]]
    
    if not carpetas:
        print("No se encontraron subcarpetas procesables.")
        return

    print(f"\nProcesando {len(carpetas)} carpetas...")

    for carpeta in carpetas:
        fid = carpeta.name
        print(f"\n>>> Carpeta: {fid}")
        
        # 1. Buscar Rta (debe llamarse exactamente COEX{fid}.pdf o {fid}.pdf)
        archivo_rta = next((f for f in carpeta.glob("*.pdf") if f.name.lower() in [f"coex{fid.lower()}.pdf", f"{fid.lower()}.pdf"]), None)
        
        # 2. Buscar Epicris
        archivo_epi = next((f for f in carpeta.glob("*.pdf") if "EPICRIS" in f.name.upper()), None)

        if archivo_rta and archivo_epi:
            try:
                reader_rta = PdfReader(str(archivo_rta))
                paginas_rta = len(reader_rta.pages)
                
                reader_epi = PdfReader(str(archivo_epi))
                total_epi = len(reader_epi.pages)

                if total_epi > paginas_rta:
                    # SEGURIDAD: Comparar texto de la primera página
                    texto_rta_pag1 = (reader_rta.pages[0].extract_text() or "")[:500]
                    texto_epi_pag1 = (reader_epi.pages[0].extract_text() or "")[:500]

                    if texto_rta_pag1 == texto_epi_pag1:
                        writer = PdfWriter()
                        for i in range(paginas_rta, total_epi):
                            writer.add_page(reader_epi.pages[i])
                        
                        temp = str(archivo_epi) + ".tmp"
                        with open(temp, "wb") as f: writer.write(f)
                        os.replace(temp, str(archivo_epi))
                        print(f"  [LIMPIO] {archivo_epi.name} (se quitaron {paginas_rta} págs de {archivo_rta.name})")
                    else:
                        print(f"  [SKIP] {archivo_epi.name}: El contenido inicial no coincide con {archivo_rta.name}.")
                else:
                    print(f"  [INFO] {archivo_epi.name} ya no tiene páginas de respuesta (o es muy corto).")
            except Exception as e:
                print(f"  [ERROR] {e}")
        else:
            if not archivo_rta: print(f"  [!] No se encontró arquivo de rta para {fid}")
            if not archivo_epi: print(f"  [!] No se encontró arquivo EPICRIS para {fid}")

def menu():
    while True:
        print("\n" + "="*50)
        print("   GESTOR DE ARCHIVOS (FILTRO ESTRICTO EPICRIS)")
        print("="*50)
        print("1. UNIR Respuesta (SOLO al archivo EPICRIS)")
        print("2. LIMPIAR TODO (Filtro por ID y Rta externas)")
        print("3. Limpieza AUTOMÁTICA (Scan de carpetas internas)")
        print("4. Salir")
        op = input("\nSeleccione: ")
        if op == "1": unificar_solo_epicris()
        elif op == "2": limpieza_total_extrema()
        elif op == "3": limpieza_automatica_subcarpetas()
        elif op == "4": break

if __name__ == "__main__":
    menu()

if __name__ == "__main__":
    menu()
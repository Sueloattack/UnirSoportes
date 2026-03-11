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
        # Buscar Rta
        archivo_rta = next((os.path.join(ruta_rta, f) for f in os.listdir(ruta_rta) if f"_{fid}_" in f), None)
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
        # 1. Medir rta
        archivo_rta = next((os.path.join(ruta_rta, f) for f in os.listdir(ruta_rta) if f"_{fid}_" in f), None)
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
                    writer = PdfWriter()
                    # Quitamos las primeras N páginas
                    for i in range(paginas_rta, total):
                        writer.add_page(reader.pages[i])
                    
                    temp = str(path_pdf) + ".tmp"
                    with open(temp, "wb") as f: writer.write(f)
                    os.replace(temp, str(path_pdf))
                    print(f"  [LIMPIO] {path_pdf.name}")
                else:
                    print(f"  [INFO] {path_pdf.name} no parece tener la rta pegada (muy corto).")
            except Exception as e:
                print(f"  [ERROR] En {path_pdf.name}: {e}")

def menu():
    while True:
        print("\n" + "="*50)
        print("   GESTOR DE ARCHIVOS (FILTRO ESTRICTO EPICRIS)")
        print("="*50)
        print("1. UNIR Respuesta (SOLO al archivo EPICRIS)")
        print("2. LIMPIAR TODO (Quitar rta de FACTURA, INFOPOL, etc.)")
        print("3. Salir")
        op = input("\nSeleccione: ")
        if op == "1": unificar_solo_epicris()
        elif op == "2": limpieza_total_extrema()
        elif op == "3": break

if __name__ == "__main__":
    menu()
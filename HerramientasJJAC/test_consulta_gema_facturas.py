from datetime import date

from api_gema import query_api_gema


FACTURAS = [
    "FECR351240",
    "FECR356353",
    "FECR358537",
    "FECR360336",
    "FECR360738",
    "FECR364187",
    "FECR364236",
    "FECR364554",
    "FECR364563",
    "FECR364964",
    "FECR363886",
    "FECR229697",
]


def parse_factura(factura: str):
    serie = ''.join(ch for ch in factura if ch.isalpha()).upper()
    numero = ''.join(ch for ch in factura if ch.isdigit())
    return serie, numero


def buscar_factura(factura: str):
    serie, numero_factura = parse_factura(factura)
    errores = []

    anio_actual = date.today().year % 100
    for anio in range(anio_actual, max(anio_actual - 8, -1), -1):
        tabla = f"GEMA10.D/VENTAS/DATOS/VTFACC{anio:02d}"
        consulta = f"radicacion, fech_rad, serie, docn FROM [{tabla}] WHERE serie = '{serie}' AND docn = {numero_factura}"
        try:
            filas = query_api_gema(consulta)
        except Exception as error:
            errores.append({"consulta": consulta, "error": str(error)})
            continue
        if filas:
            fila = filas[0]
            return {
                "factura": factura,
                "tabla": tabla,
                "consulta": consulta,
                "fila": fila,
                "errores": errores,
            }

    return {"factura": factura, "sin_coincidencia": True, "errores": errores}



def main():
    print("Prueba rapida de consultas GEMA por factura")
    print("=" * 70)

    for factura in FACTURAS:
        resultado = buscar_factura(factura)

        if resultado.get("sin_coincidencia"):
            print(f"{factura}: SIN COINCIDENCIA")
            if resultado.get("errores"):
                ultimo_error = resultado["errores"][-1]
                print(f"  ultimo error: {ultimo_error['error']}")
            continue

        fila = resultado["fila"]
        print(f"{factura}: OK | tabla={resultado['tabla']}")
        print(f"  radicacion={fila.get('radicacion')} | fech_rad={fila.get('fech_rad')}")


if __name__ == "__main__":
    main()
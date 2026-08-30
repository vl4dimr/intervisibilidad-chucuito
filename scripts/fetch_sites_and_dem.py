# -*- coding: utf-8 -*-
"""
Recolector base: sitios arqueologicos de Puno y modelo digital de elevacion.

Dos fuentes, ninguna requiere clave:

1. Capa de sitios arqueologicos del INC (hoy Ministerio de Cultura), 7 907
   puntos en todo el Peru, distribuida por Geo GPS Peru. Se filtra Puno.

   Advertencia de procedencia: el fichero se sirve desde Google Drive sin
   licencia declarada ni version. El dato es del INC y por tanto de origen
   publico, pero el redistribuidor no documenta ni la fecha de corte ni el
   criterio de inclusion. Cualquier resultado hereda esa opacidad y hay que
   declararlo en el articulo, no darlo por bueno.

2. Copernicus DEM GLO-30, 30 m de resolucion, desde el bucket publico de AWS.
   No necesita registro, a diferencia de OpenTopography. Las teselas se nombran
   por su esquina suroeste, de modo que la latitud -16.4 cae en la tesela S17.

Salidas (data/):
  sitios_puno.csv        puntos con coordenadas y division politica
  dem/*.tif              teselas del modelo de elevacion
  fetch_log.json
"""
import csv
import json
import math
import os
import urllib.request

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(BASE, "data")
DEMDIR = os.path.join(DATA, "dem")
UA = {"User-Agent": "andean-viewshed-research/1.0 (academic)"}

SITES_ZIP = "https://drive.google.com/uc?export=download&id=0B2LXWd-oFIpfRzE4WEQtdHdRbVE"
DEM_BASE = "https://copernicus-dem-30m.s3.amazonaws.com"

# Terminos que identifican estructuras funerarias altiplanicas en el toponimo.
# «amaya» es difunto en aymara y «gentil» designa en el habla local a los
# antiguos; ambos acompanan con frecuencia a las torres funerarias.
FUNERARY = ["chullpa", "chulpa", "amaya", "gentil", "torre"]


def download(url, path, label):
    if os.path.exists(path) and os.path.getsize(path) > 0:
        print("  %s ya presente (%.1f MB)" % (label, os.path.getsize(path) / 1e6), flush=True)
        return True
    try:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=300) as r, open(path, "wb") as f:
            total = 0
            while True:
                b = r.read(1 << 20)
                if not b:
                    break
                f.write(b)
                total += len(b)
        print("  %s -> %.1f MB" % (label, total / 1e6), flush=True)
        return True
    except Exception as e:
        print("  %s FALLO: %s" % (label, e), flush=True)
        return False


def tiles_for(lat_min, lat_max, lon_min, lon_max):
    """Teselas Copernicus que cubren el rectangulo dado.

    El nombre de la tesela indica su esquina suroeste, asi que hay que tomar el
    suelo de la latitud y de la longitud, no el redondeo.
    """
    out = []
    for lat in range(math.floor(lat_min), math.floor(lat_max) + 1):
        for lon in range(math.floor(lon_min), math.floor(lon_max) + 1):
            ns = "N%02d" % lat if lat >= 0 else "S%02d" % abs(lat)
            ew = "E%03d" % lon if lon >= 0 else "W%03d" % abs(lon)
            out.append("Copernicus_DSM_COG_10_%s_00_%s_00_DEM" % (ns, ew))
    return out


def main():
    os.makedirs(DATA, exist_ok=True)
    os.makedirs(DEMDIR, exist_ok=True)

    # ---------------------------------------------------------------- sitios
    print("[1/3] Capa de sitios arqueologicos (INC via Geo GPS Peru)", flush=True)
    zpath = os.path.join(DATA, "sitios_peru.zip")
    if not download(SITES_ZIP, zpath, "shapefile"):
        raise SystemExit("no se pudo descargar la capa de sitios")

    import zipfile
    shpdir = os.path.join(DATA, "sitios_shp")
    os.makedirs(shpdir, exist_ok=True)
    with zipfile.ZipFile(zpath) as z:
        z.extractall(shpdir)

    import shapefile
    base = os.path.join(shpdir, "Sitio Arqueologico")
    r = shapefile.Reader(base, encoding="latin-1")
    fields = [f[0] for f in r.fields[1:]]
    rows = []
    for rec, shp in zip(r.records(), r.shapes()):
        d = dict(zip(fields, list(rec)))
        if str(d.get("Dpto", "")).strip().lower() != "puno":
            continue
        try:
            lat, lon = float(d["Latitud"]), float(d["Longitud"])
        except (TypeError, ValueError):
            continue
        nombre = str(d.get("Nombre", "")).strip()
        rows.append({
            "nombre": nombre,
            "provincia": str(d.get("Prov", "")).strip(),
            "distrito": str(d.get("Dist", "")).strip(),
            "lat": lat, "lon": lon,
            "fuente": str(d.get("Fuente", "")).strip(),
            "funerario": any(k in nombre.lower() for k in FUNERARY),
        })

    out_csv = os.path.join(DATA, "sitios_puno.csv")
    with open(out_csv, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    fun = sum(1 for x in rows if x["funerario"])
    print("  Puno: %d sitios, %d con toponimo funerario" % (len(rows), fun), flush=True)

    # ------------------------------------------------------------------- dem
    lat_min = min(x["lat"] for x in rows)
    lat_max = max(x["lat"] for x in rows)
    lon_min = min(x["lon"] for x in rows)
    lon_max = max(x["lon"] for x in rows)
    print("\n[2/3] Extension: lat %.3f a %.3f | lon %.3f a %.3f"
          % (lat_min, lat_max, lon_min, lon_max), flush=True)

    names = tiles_for(lat_min, lat_max, lon_min, lon_max)
    print("[3/3] Copernicus DEM GLO-30: %d teselas" % len(names), flush=True)
    ok = 0
    for n in names:
        url = "%s/%s/%s.tif" % (DEM_BASE, n, n)
        if download(url, os.path.join(DEMDIR, n + ".tif"), n[-16:]):
            ok += 1

    log = {
        "sitios_fuente": "INC / Ministerio de Cultura, redistribuido por Geo GPS Peru",
        "sitios_licencia": "no declarada por el redistribuidor; verificar antes de publicar",
        "sitios_puno": len(rows),
        "sitios_funerarios": fun,
        "dem_fuente": "Copernicus DEM GLO-30 (ESA), bucket publico de AWS",
        "dem_licencia": "Copernicus, uso libre con atribucion",
        "dem_teselas_pedidas": len(names),
        "dem_teselas_obtenidas": ok,
        "extension": {"lat_min": lat_min, "lat_max": lat_max,
                      "lon_min": lon_min, "lon_max": lon_max},
    }
    with open(os.path.join(DATA, "fetch_log.json"), "w", encoding="utf-8") as f:
        json.dump(log, f, ensure_ascii=False, indent=2)

    print("\nRESUMEN")
    for k, v in log.items():
        if k != "extension":
            print("  %-24s %s" % (k, v))
    print("\n  ->", out_csv)


if __name__ == "__main__":
    main()

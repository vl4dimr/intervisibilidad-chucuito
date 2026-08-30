# -*- coding: utf-8 -*-
"""
Recorte del terreno de estudio y preparacion de los sitios de Chucuito.

Se recorta el Copernicus DEM GLO-30 al rectangulo que envuelve los sitios mas un
margen. El margen no es decorativo: una linea de vision entre dos sitios del
borde puede pasar por terreno situado fuera del rectangulo minimo, y truncarlo
haria que ese relieve dejara de bloquear la vista. Se toman 5 km, muy por encima
de la desviacion maxima posible entre dos puntos interiores.

El DEM viene en coordenadas geograficas, donde un grado de longitud mide menos
que uno de latitud y la diferencia crece con la latitud. A 16 grados sur, un
grado de longitud son unos 107 km frente a 111 de latitud. Trabajar en grados
sin corregir deformaria las distancias un 4 %, asi que las medidas se hacen en
metros mediante una proyeccion local.

Salidas (data/):
  terreno_chucuito.tif   recorte del DEM
  sitios_chucuito.csv    sitios con coordenadas proyectadas y altitud
  terreno_log.json
"""
import csv
import json
import math
import os

import numpy as np
import rasterio
from rasterio.windows import from_bounds

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(BASE, "data")
DEMDIR = os.path.join(DATA, "dem")

# El margen no es solo para que las lineas de vision no se salgan del recorte.
# El modelo nulo rigido rota la nube de sitios entera, y esa nube mide 26 km en
# su eje mayor: con 5 km de margen solo cabian 244 de 360 orientaciones, de modo
# que el nulo excluia sistematicamente las perpendiculares a la disposicion
# observada. Con 20 km caben todas y el contraste deja de estar sesgado por la
# forma del recorte. La ventana resultante sigue dentro de una sola tesela.
MARGIN_KM = 18.0
PROVINCE = "chucuito"

# Radio terrestre medio, para convertir grados a metros en la proyeccion local.
R_EARTH = 6371000.0


def load_sites():
    path = os.path.join(DATA, "sitios_puno.csv")
    with open(path, encoding="utf-8-sig", newline="") as f:
        rows = [r for r in csv.DictReader(f)
                if r["provincia"].strip().lower() == PROVINCE]
    for r in rows:
        r["lat"] = float(r["lat"])
        r["lon"] = float(r["lon"])
        r["funerario"] = r["funerario"] == "True"
    return rows


def tile_for(lat, lon):
    ns = "N%02d" % math.floor(lat) if lat >= 0 else "S%02d" % abs(math.floor(lat))
    ew = "E%03d" % math.floor(lon) if lon >= 0 else "W%03d" % abs(math.floor(lon))
    return "Copernicus_DSM_COG_10_%s_00_%s_00_DEM.tif" % (ns, ew)


def main():
    sites = load_sites()
    lat = np.array([s["lat"] for s in sites])
    lon = np.array([s["lon"] for s in sites])
    print("Sitios en %s: %d" % (PROVINCE, len(sites)), flush=True)

    # Margen en grados, distinto por eje porque el grado de longitud se acorta
    lat0 = float(lat.mean())
    dlat = MARGIN_KM * 1000 / (R_EARTH * math.pi / 180)
    dlon = dlat / math.cos(math.radians(lat0))
    bounds = (lon.min() - dlon, lat.min() - dlat, lon.max() + dlon, lat.max() + dlat)
    print("Ventana: lon %.4f a %.4f | lat %.4f a %.4f"
          % (bounds[0], bounds[2], bounds[1], bounds[3]), flush=True)

    # Las teselas que tocan la ventana
    needed = sorted({tile_for(la, lo)
                     for la in (bounds[1], bounds[3])
                     for lo in (bounds[0], bounds[2])})
    print("Teselas implicadas: %s" % ", ".join(t[-20:] for t in needed), flush=True)

    arrays, transforms = [], []
    for t in needed:
        p = os.path.join(DEMDIR, t)
        if not os.path.exists(p):
            print("  falta %s" % t, flush=True)
            continue
        with rasterio.open(p) as src:
            b = src.bounds
            # interseccion de la ventana con la tesela
            ix = (max(bounds[0], b.left), max(bounds[1], b.bottom),
                  min(bounds[2], b.right), min(bounds[3], b.top))
            if ix[0] >= ix[2] or ix[1] >= ix[3]:
                continue
            win = from_bounds(*ix, transform=src.transform)
            a = src.read(1, window=win)
            arrays.append(a)
            transforms.append(src.window_transform(win))
            print("  %s -> %s px" % (t[-20:], a.shape), flush=True)

    if len(arrays) == 1:
        dem, transform = arrays[0], transforms[0]
    else:
        raise SystemExit("La ventana cruza varias teselas; falta implementar el mosaico.")

    out_tif = os.path.join(DATA, "terreno_chucuito.tif")
    with rasterio.open(os.path.join(DEMDIR, needed[0])) as src:
        profile = src.profile.copy()
    profile.update(height=dem.shape[0], width=dem.shape[1], transform=transform,
                   compress="deflate")
    with rasterio.open(out_tif, "w", **profile) as dst:
        dst.write(dem, 1)

    # ------------------------------------------------- coordenadas en metros
    # Proyeccion local equirectangular centrada en el area: para 26 km el error
    # es milimetrico y evita depender de librerias de proyeccion.
    lon0 = float(lon.mean())
    mx = (np.radians(lon - lon0) * R_EARTH * math.cos(math.radians(lat0)))
    my = (np.radians(lat - lat0) * R_EARTH)

    # altitud de cada sitio, tomada del DEM
    inv = ~transform
    cols, rows_ = inv * (lon, lat)
    cols = np.round(cols).astype(int)
    rows_ = np.round(rows_).astype(int)
    alt = dem[np.clip(rows_, 0, dem.shape[0] - 1), np.clip(cols, 0, dem.shape[1] - 1)]

    out_csv = os.path.join(DATA, "sitios_chucuito.csv")
    with open(out_csv, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "nombre", "distrito", "lat", "lon", "x_m", "y_m",
                    "altitud_m", "col", "fila", "funerario"])
        for i, s in enumerate(sites):
            w.writerow([i, s["nombre"], s["distrito"], s["lat"], s["lon"],
                        round(float(mx[i]), 1), round(float(my[i]), 1),
                        round(float(alt[i]), 1), int(cols[i]), int(rows_[i]),
                        s["funerario"]])

    log = {
        "provincia": PROVINCE,
        "sitios": len(sites),
        "funerarios_por_toponimo": int(sum(1 for s in sites if s["funerario"])),
        "margen_km": MARGIN_KM,
        "dem_shape": list(dem.shape),
        "dem_resolucion_grados": [abs(transform.a), abs(transform.e)],
        "dem_resolucion_m_aprox": [abs(transform.a) * R_EARTH * math.pi / 180 * math.cos(math.radians(lat0)),
                                   abs(transform.e) * R_EARTH * math.pi / 180],
        "altitud_min": float(np.nanmin(alt)), "altitud_max": float(np.nanmax(alt)),
        "altitud_media_sitios": float(np.nanmean(alt)),
        "altitud_media_terreno": float(np.nanmean(dem)),
        "centro": {"lat": lat0, "lon": lon0},
        "extension_m": {"x": float(mx.max() - mx.min()), "y": float(my.max() - my.min())},
    }
    with open(os.path.join(DATA, "terreno_log.json"), "w", encoding="utf-8") as f:
        json.dump(log, f, ensure_ascii=False, indent=2)

    print("\nRESUMEN")
    print("  DEM recortado      %s px, resolucion ~%.0f x %.0f m"
          % (dem.shape, log["dem_resolucion_m_aprox"][0], log["dem_resolucion_m_aprox"][1]))
    print("  altitud sitios     %.0f a %.0f m (media %.0f)"
          % (log["altitud_min"], log["altitud_max"], log["altitud_media_sitios"]))
    print("  altitud terreno    media %.0f m" % log["altitud_media_terreno"])
    print("  extension          %.1f x %.1f km"
          % (log["extension_m"]["x"] / 1000, log["extension_m"]["y"] / 1000))
    print("\n  ->", out_csv)


if __name__ == "__main__":
    main()

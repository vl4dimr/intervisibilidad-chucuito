# -*- coding: utf-8 -*-
"""
Ortoimagen Sentinel-2 L2A en color natural sobre la malla del terreno.

Busca en el catalogo STAC publico de Element 84 (Earth Search, coleccion
sentinel-2-l2a) las pasadas de estacion seca (mayo-agosto) que cubren el area
del DEM con nubosidad < 5 % en todas sus granulas, y elige la mas despejada de
la temporada mas reciente. Una pasada abarca dos granulas MGRS (19LDC y 19KDB)
tomadas en el mismo minuto, de modo que el mosaico no tiene costuras de fecha.

Las bandas B04/B03/B02 (10 m) se leen por ventana directamente de los COG
remotos, se pasan a reflectancia con la escala y el desplazamiento que declara
el propio STAC, y se remuestrean (bilineal) a una malla de 10 m alineada con
data/terreno_utm.tif: misma esquina, celda tres veces mas fina. Ajuste de color
natural: recorte por percentiles comun a las tres bandas (conserva el balance
de color), gamma y una ligera ganancia de saturacion.

Salidas:
  data/ortofoto_s2.tif       RGB 8 bits, EPSG:32719, 10 m, JPEG-en-GeoTIFF
  results/ortofoto_s2.json   escenas, fecha, nubosidad, sol y atribucion

Atribucion obligatoria: «Contains modified Copernicus Sentinel data [año]».
Si la red falla, el guion se detiene: no hay textura de sustitucion.
"""
import json
import os
import sys

import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.transform import Affine
from rasterio.warp import reproject, transform_bounds
from rasterio.windows import from_bounds
from pystac_client import Client

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA, RES = os.path.join(BASE, "data"), os.path.join(BASE, "results")
STAC = "https://earth-search.aws.element84.com/v1"
RES_M = 10.0
NUBES_MAX = 5.0
PERIODO = "2023-05-01/2025-08-31"

os.environ.setdefault("GDAL_DISABLE_READDIR_ON_OPEN", "EMPTY_DIR")
os.environ.setdefault("GDAL_HTTP_MULTIRANGE", "YES")
os.environ.setdefault("GDAL_HTTP_MERGE_CONSECUTIVE_RANGES", "YES")
os.environ.setdefault("CPL_VSIL_CURL_ALLOWED_EXTENSIONS", ".tif")
os.environ.setdefault("GDAL_HTTP_TIMEOUT", "60")
os.environ.setdefault("GDAL_HTTP_MAX_RETRY", "5")
os.environ.setdefault("GDAL_HTTP_RETRY_DELAY", "3")
os.environ.setdefault("VSI_CACHE", "TRUE")

# Solo hace falta el entorno de la torre: las tres vistas 3D abarcan como mucho
# 10.5 km a cada lado. Pedir el recorte entero del DEM (62 x 51 km a 10 m) por
# red hacia que la descarga no terminara.
SEMILADO_M = 12000.0


def elegir_pasada(bbox):
    cat = Client.open(STAC)
    items = list(cat.search(collections=["sentinel-2-l2a"], bbox=bbox,
                            datetime=PERIODO,
                            query={"eo:cloud_cover": {"lt": NUBES_MAX}},
                            max_items=500).items())
    pasadas = {}
    for it in items:
        if not 5 <= it.datetime.month <= 8:
            continue
        if it.properties.get("s2:nodata_pixel_percentage", 0) > 1:
            continue
        clave = (it.datetime.date().isoformat(), it.id.split("_")[0])
        pasadas.setdefault(clave, []).append(it)
    granulas = {it.properties["grid:code"] for it in items}
    completas = [(k, v) for k, v in pasadas.items()
                 if {i.properties["grid:code"] for i in v} == granulas]
    if not completas:
        sys.exit("ninguna pasada de estacion seca cubre el area con < %.0f %% de nubes"
                 % NUBES_MAX)
    # la temporada seca mas reciente; dentro de ella, la pasada mas despejada
    anio = max(k[0][:4] for k, _ in completas)
    cand = [(max(i.properties["eo:cloud_cover"] for i in v), k, v)
            for k, v in completas if k[0][:4] == anio]
    cand.sort(key=lambda t: (t[0], t[1]))
    return cand[0][2], granulas


def main():
    with rasterio.open(os.path.join(DATA, "terreno_utm.tif")) as s:
        crs, tr30 = s.crs, s.transform
    obs = json.load(open(os.path.join(RES, "observador_3d.json"), encoding="utf-8"))
    from rasterio.warp import transform as tcoords
    ox, oy = tcoords("EPSG:4326", crs, [obs["x_raster"]], [obs["y_raster"]])
    # ventana alineada con las celdas de 30 m del DEM, centrada en la torre
    c0 = int((ox[0] - SEMILADO_M - tr30.c) // tr30.a)
    f0 = int((tr30.f - (oy[0] + SEMILADO_M)) // -tr30.e)
    n30 = int(2 * SEMILADO_M / tr30.a)
    x0, y0 = tr30.c + c0 * tr30.a, tr30.f + f0 * tr30.e
    f = int(round(30.0 / RES_M))
    dst_tr = Affine(tr30.a / f, 0, x0, 0, tr30.e / f, y0)
    h = w = n30 * f
    bounds = (x0, y0 + n30 * tr30.e, x0 + n30 * tr30.a, y0)
    bbox = list(transform_bounds(crs, "EPSG:4326", *bounds))

    pasada, granulas = elegir_pasada(bbox)
    pasada.sort(key=lambda i: i.id)
    print("pasada:", [i.id for i in pasada])

    refl = np.zeros((3, h, w), np.float32)
    lleno = np.zeros((h, w), bool)
    for it in pasada:
        for b, nombre in enumerate(("red", "green", "blue")):
            a = it.assets[nombre]
            rb = a.extra_fields["raster:bands"][0]
            with rasterio.open(a.href) as src:
                if src.crs != crs:
                    raise RuntimeError("CRS inesperado en %s" % a.href)
                win = from_bounds(*bounds, transform=src.transform).round_offsets().round_lengths()
                dn = src.read(1, window=win, boundless=True, fill_value=0).astype(np.float32)
                wtr = src.window_transform(win)
            dst = np.zeros((h, w), np.float32)
            reproject(dn, dst, src_transform=wtr, src_crs=crs, src_nodata=0,
                      dst_transform=dst_tr, dst_crs=crs, dst_nodata=0,
                      resampling=Resampling.bilinear)
            ok = dst > 0
            if b == 0:
                nuevo = ok & ~lleno
            r = dst * rb["scale"] + rb["offset"]
            refl[b][nuevo] = r[nuevo]
            print("  %s %s: %.0f %% de la malla" % (it.id, nombre, 100 * ok.mean()))
        lleno |= nuevo
    if lleno.mean() < 0.999:
        raise RuntimeError("cobertura incompleta: %.2f %%" % (100 * lleno.mean()))

    # --- color natural -----------------------------------------------------
    lum = refl.mean(0)
    lo = float(np.percentile(refl, 0.3))
    hi = float(np.percentile(lum, 99.7)) * 1.08
    x = np.clip((refl - lo) / (hi - lo), 0, 1)
    x = x ** (1 / 1.9)                                  # gamma
    gris = x.mean(0, keepdims=True)
    x = np.clip(gris + 1.18 * (x - gris), 0, 1)         # saturacion ligera
    rgb = (x * 255 + 0.5).astype(np.uint8)

    out = os.path.join(DATA, "ortofoto_s2.tif")
    perfil = dict(driver="GTiff", width=w, height=h, count=3, dtype="uint8",
                  crs=crs, transform=dst_tr, compress="JPEG", jpeg_quality=88,
                  photometric="YCBCR", tiled=True, blockxsize=512, blockysize=512,
                  interleave="pixel")
    with rasterio.open(out, "w", **perfil) as d:
        d.write(rgb)
        d.build_overviews([2, 4, 8, 16], Resampling.average)
        d.update_tags(ATRIBUCION="Contains modified Copernicus Sentinel data %s"
                      % pasada[0].datetime.year)

    anio = pasada[0].datetime.year
    meta = {
        "fuente": "Copernicus Sentinel-2 L2A (ESA), via Earth Search STAC (Element 84)",
        "stac": STAC,
        "criterio": "pasada de estacion seca (mayo-agosto) mas despejada de la temporada mas "
                    "reciente, nubosidad < %.0f %% en todas las granulas" % NUBES_MAX,
        "escenas": [{"id": i.id, "granula": i.properties["grid:code"],
                     "fecha_hora_utc": i.datetime.isoformat(),
                     "nubosidad_pct": round(i.properties["eo:cloud_cover"], 4),
                     "sol_azimut": round(i.properties["view:sun_azimuth"], 2),
                     "sol_elevacion": round(i.properties["view:sun_elevation"], 2),
                     "linea_base": i.properties.get("s2:processing_baseline")}
                    for i in pasada],
        "fecha": pasada[0].datetime.date().isoformat(),
        "anio": anio,
        "nubosidad_max_pct": round(max(i.properties["eo:cloud_cover"] for i in pasada), 4),
        "sol_azimut": round(float(np.mean([i.properties["view:sun_azimuth"] for i in pasada])), 2),
        "sol_elevacion": round(float(np.mean([i.properties["view:sun_elevation"] for i in pasada])), 2),
        "bandas": "B04, B03, B02 (10 m), reflectancia de superficie",
        "malla": "EPSG:32719, %.0f m, alineada con data/terreno_utm.tif (%d x %d), %.0f km alrededor de la torre" % (RES_M, w, h, 2 * SEMILADO_M / 1000),
        "ajuste_color": {"recorte_bajo": round(lo, 4), "recorte_alto": round(hi, 4),
                         "gamma": 1.9, "saturacion": 1.18},
        "atribucion": "Contains modified Copernicus Sentinel data %d" % anio,
        "atribucion_es": "Contiene datos modificados de Copernicus Sentinel %d" % anio,
    }
    json.dump(meta, open(os.path.join(RES, "ortofoto_s2.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    print("-> %s (%.1f MB) | %s" % (out, os.path.getsize(out) / 1e6, meta["fecha"]))


if __name__ == "__main__":
    main()

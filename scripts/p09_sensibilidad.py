# -*- coding: utf-8 -*-
"""
Sensibilidad del resultado a las decisiones del analisis.

Al reencuadrar el modelo de elevacion, la densidad observada paso de 0,436 a
0,409 sin que cambiara ningun dato: solo se desplazo la rejilla respecto a las
coordenadas de los sitios. Un resultado que se mueve un 6 % por eso exige saber
cuanto depende de las demas decisiones, que son varias y ninguna obvia:

  - a que celda se asigna cada sitio, con coordenadas de precision desconocida
  - que altura se atribuye a las estructuras
  - que altura se atribuye al observador
  - donde se corta el alcance de la vista

Se recalcula la densidad variando cada una por separado. Si el orden de magnitud
aguanta, el resultado es robusto aunque el valor exacto no lo sea; si se
desmorona, el analisis no sostiene ninguna conclusion.

Salida: results/sensibilidad.json
"""
import csv
import json
import os
import sys

import numpy as np
import rasterio

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from viewshed_core import network_stats, pairwise_intervisibility

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(BASE, "data")
RES = os.path.join(BASE, "results")

ALCANCE = 5000.0


def main():
    with open(os.path.join(DATA, "sitios_chucuito.csv"), encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    cols = np.array([int(r["col"]) for r in rows])
    fils = np.array([int(r["fila"]) for r in rows])
    with rasterio.open(os.path.join(DATA, "terreno_chucuito.tif")) as src:
        dem = src.read(1).astype(np.float32)
    with open(os.path.join(DATA, "terreno_log.json"), encoding="utf-8") as f:
        log = json.load(f)
    rx, ry = log["dem_resolucion_m_aprox"]

    def dens(c, f_, h_obs=1.7, h_tgt=3.0, alc=ALCANCE):
        v, d = pairwise_intervisibility(dem, rx, ry, c, f_, h_obs=h_obs, h_tgt=h_tgt,
                                        max_dist_m=alc)
        return network_stats(v, d, alc)["densidad"]

    base = dens(cols, fils)
    out = {"alcance_m": ALCANCE, "densidad_base": base, "pruebas": {}}
    print("Densidad de referencia (5 km, obs 1,7 m, obj 3 m): %.4f\n" % base, flush=True)

    # --- desplazamiento de la rejilla
    print("Desplazamiento de la asignacion a celda")
    desp = {}
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            v = dens(np.clip(cols + dx, 0, dem.shape[1] - 1),
                     np.clip(fils + dy, 0, dem.shape[0] - 1))
            desp["%+d,%+d" % (dx, dy)] = v
            print("  (%+d,%+d) -> %.4f  (%+.1f %%)" % (dx, dy, v, 100 * (v - base) / base), flush=True)
    vals = np.array(list(desp.values()))
    out["pruebas"]["desplazamiento_celda"] = {
        "valores": desp, "min": float(vals.min()), "max": float(vals.max()),
        "rango_relativo": float((vals.max() - vals.min()) / base)}
    print("  rango: %.4f a %.4f (%.1f %% de la referencia)\n"
          % (vals.min(), vals.max(), 100 * (vals.max() - vals.min()) / base), flush=True)

    # --- altura de la estructura
    print("Altura atribuida a la estructura")
    alt = {}
    for h in (0.0, 1.5, 3.0, 6.0, 12.0):
        v = dens(cols, fils, h_tgt=h)
        alt["%.1f" % h] = v
        print("  %5.1f m -> %.4f  (%+.1f %%)" % (h, v, 100 * (v - base) / base), flush=True)
    out["pruebas"]["altura_objetivo"] = alt

    # --- altura del observador
    print("\nAltura del observador")
    obs = {}
    for h in (1.0, 1.7, 3.0):
        v = dens(cols, fils, h_obs=h)
        obs["%.1f" % h] = v
        print("  %5.1f m -> %.4f  (%+.1f %%)" % (h, v, 100 * (v - base) / base), flush=True)
    out["pruebas"]["altura_observador"] = obs

    with open(os.path.join(RES, "sensibilidad.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print("\n  ->", os.path.join(RES, "sensibilidad.json"))


if __name__ == "__main__":
    main()

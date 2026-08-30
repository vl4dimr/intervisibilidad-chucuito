# -*- coding: utf-8 -*-
"""
Red de intervisibilidad observada y su contraste contra modelos nulos.

La pregunta no es cuantos sitios se ven entre si —ese numero por si solo no
significa nada—, sino si se ven mas de lo que cabria esperar de puntos situados
en el mismo terreno sin intencion de verse. Todo depende, por tanto, del modelo
nulo, y por eso se calculan dos.

  Nulo uniforme: puntos al azar dentro del area de estudio. Es el nulo ingenuo y
  casi siempre da significativo, porque los sitios reales estan en cerros y los
  cerros ven mas. Confirma poco.

  Nulo estratificado por altitud: puntos al azar tomados de celdas con la misma
  distribucion de altitud que los sitios reales. Responde a la pregunta que
  importa: dada la cota en la que estan, ¿se ven mas de lo que les tocaria?

Si la asociacion sobrevive al segundo nulo, el emplazamiento responde a algo mas
que a la altura. Si solo sobrevive al primero, lo unico demostrado es que los
sitios estan altos, que no es un hallazgo.

Salidas (results/):
  red_observada.npz     matrices de visibilidad y distancia
  nulos.json            estadisticos observados y distribuciones nulas
"""
import csv
import json
import os
import sys
import time

import numpy as np
import rasterio

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from viewshed_core import network_stats, pairwise_intervisibility

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(BASE, "data")
OUT = os.path.join(BASE, "results")

# El Copernicus DEM asigna una cota constante a las masas de agua: el lago
# Titicaca aparece como 302 405 celdas planas a 3808,5 m, el 30,6 % del area de
# estudio. Sortear puntos nulos ahi es doblemente erroneo: no se puede emplazar
# un sitio arqueologico en mitad del lago, y una superficie perfectamente plana
# no bloquea ninguna vista, de modo que inflaria la intervisibilidad nula y
# enmascararia cualquier senal. Ningun sitio observado cae sobre agua.
COTA_AGUA = 3808.5
TOL_AGUA = 0.05

H_OBS = 1.7          # observador de pie
H_TGT = 3.0          # altura conservadora de chullpa
N_NULL = 500         # repeticiones de cada modelo nulo
MAX_DIST = 15000.0   # alcance maximo considerado, en metros
SEED = 20260830

# Mas alla de cierta distancia una torre de tres metros deja de ser reconocible
# a simple vista. La cifra exacta es discutible, asi que el analisis se repite a
# varios alcances y se informa la sensibilidad en lugar de fijar uno solo.
ALCANCES = [5000.0, 10000.0, 15000.0, 26000.0]


def load():
    with open(os.path.join(DATA, "sitios_chucuito.csv"), encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    cols = np.array([int(r["col"]) for r in rows])
    fils = np.array([int(r["fila"]) for r in rows])
    alt = np.array([float(r["altitud_m"]) for r in rows])
    fun = np.array([r["funerario"] == "True" for r in rows])
    with rasterio.open(os.path.join(DATA, "terreno_chucuito.tif")) as src:
        dem = src.read(1).astype(np.float32)
        tr = src.transform
    with open(os.path.join(DATA, "terreno_log.json"), encoding="utf-8") as f:
        log = json.load(f)
    res_x, res_y = log["dem_resolucion_m_aprox"]
    return rows, cols, fils, alt, fun, dem, res_x, res_y


def water_mask(dem):
    return np.abs(dem - COTA_AGUA) < TOL_AGUA


def land_index(dem, margin=5):
    """Indices de las celdas de tierra utilizables, excluido el borde."""
    m = np.ones(dem.shape, dtype=bool)
    m[:margin] = m[-margin:] = False
    m[:, :margin] = m[:, -margin:] = False
    m &= ~water_mask(dem)
    r, c = np.nonzero(m)
    return c, r


def sample_uniform(cols_land, rows_land, n, rng):
    """Celdas de tierra al azar."""
    k = rng.integers(0, len(cols_land), n)
    return cols_land[k], rows_land[k]


def sample_by_elevation(dem, cols_land, rows_land, alt_obs, n, rng, tol=15.0):
    """Celdas al azar con la misma distribucion de altitud que los sitios reales.

    Para cada sitio se elige una celda cualquiera del terreno cuya cota no
    difiera mas de `tol` metros. Asi el conjunto nulo reproduce el perfil
    altitudinal observado sin heredar sus posiciones.
    """
    flat = dem[rows_land, cols_land]
    cols_i, rows_i = cols_land, rows_land
    orden = np.argsort(flat)
    flat_s = flat[orden]
    out_c, out_r = np.empty(n, dtype=int), np.empty(n, dtype=int)
    for k in range(n):
        a = alt_obs[k % len(alt_obs)]
        lo = np.searchsorted(flat_s, a - tol, "left")
        hi = np.searchsorted(flat_s, a + tol, "right")
        if hi <= lo:
            idx = orden[min(max(np.searchsorted(flat_s, a), 0), len(orden) - 1)]
        else:
            idx = orden[rng.integers(lo, hi)]
        out_c[k] = cols_i[idx]
        out_r[k] = rows_i[idx]
    return out_c, out_r


def main():
    os.makedirs(OUT, exist_ok=True)
    rows, cols, fils, alt, fun, dem, res_x, res_y = load()
    n = len(rows)
    rng = np.random.default_rng(SEED)
    cols_land, rows_land = land_index(dem)
    agua = water_mask(dem)
    print("Sitios: %d | DEM %s | resolucion %.1f x %.1f m" % (n, dem.shape, res_x, res_y), flush=True)
    print("Agua enmascarada: %d celdas (%.1f %%) | tierra utilizable: %d celdas"
          % (int(agua.sum()), 100 * agua.mean(), len(cols_land)), flush=True)
    print("Sitios observados sobre agua: %d" % int(agua[fils, cols].sum()), flush=True)
    print("Altitud sitios: %.0f a %.0f m (media %.0f) | terreno medio %.0f m"
          % (alt.min(), alt.max(), alt.mean(), float(dem.mean())), flush=True)

    # ------------------------------------------------------------- observada
    t0 = time.time()
    vis, dist = pairwise_intervisibility(dem, res_x, res_y, cols, fils,
                                         h_obs=H_OBS, h_tgt=H_TGT,
                                         max_dist_m=max(ALCANCES), progress=4000)
    print("Red observada calculada en %.1f s" % (time.time() - t0), flush=True)
    np.savez_compressed(os.path.join(OUT, "red_observada.npz"), vis=vis, dist=dist)

    obs = {}
    for a in ALCANCES:
        obs["%.0f" % a] = network_stats(vis, dist, a)
        s = obs["%.0f" % a]
        print("  alcance %5.0f m: %5d aristas de %6d pares (densidad %.4f), grado medio %.2f"
              % (a, s["aristas"], s["pares_elegibles"], s["densidad"], s["grado_medio"]), flush=True)

    # ----------------------------------------------------------------- nulos
    resultados = {}
    for nombre, sampler in (("uniforme", lambda r: sample_uniform(cols_land, rows_land, n, r)),
                            ("estratificado_altitud",
                             lambda r: sample_by_elevation(dem, cols_land, rows_land, alt, n, r))):
        print("\nModelo nulo: %s (%d repeticiones)" % (nombre, N_NULL), flush=True)
        acum = {("%.0f" % a): {"densidad": [], "grado_medio": [], "componente_mayor": []}
                for a in ALCANCES}
        t0 = time.time()
        for it in range(N_NULL):
            c, r = sampler(rng)
            v, d = pairwise_intervisibility(dem, res_x, res_y, c, r,
                                            h_obs=H_OBS, h_tgt=H_TGT,
                                            max_dist_m=max(ALCANCES))
            for a in ALCANCES:
                st = network_stats(v, d, a)
                k = "%.0f" % a
                acum[k]["densidad"].append(st["densidad"])
                acum[k]["grado_medio"].append(st["grado_medio"])
                acum[k]["componente_mayor"].append(st["componente_mayor"])
            if (it + 1) % 50 == 0:
                el = time.time() - t0
                print("  %d/%d  (%.1f s, quedan ~%.0f s)"
                      % (it + 1, N_NULL, el, el / (it + 1) * (N_NULL - it - 1)), flush=True)
        resultados[nombre] = acum

    # ------------------------------------------------------------ contrastes
    salida = {"parametros": {"h_obs": H_OBS, "h_tgt": H_TGT, "n_null": N_NULL,
                             "alcances_m": ALCANCES, "semilla": SEED,
                             "n_sitios": n,
                             "cota_agua": COTA_AGUA,
                             "celdas_agua": int(agua.sum()),
                             "fraccion_agua": float(agua.mean()),
                             "celdas_tierra": int(len(cols_land))},
              "observado": obs, "nulos": {}}
    print("\nCONTRASTES")
    for nombre, acum in resultados.items():
        salida["nulos"][nombre] = {}
        print("\n  %s" % nombre)
        for a in ALCANCES:
            k = "%.0f" % a
            d_obs = obs[k]["densidad"]
            dn = np.array(acum[k]["densidad"])
            # p unilateral con correccion de continuidad
            p = (np.sum(dn >= d_obs) + 1) / (len(dn) + 1)
            z = (d_obs - dn.mean()) / dn.std() if dn.std() > 0 else float("nan")
            salida["nulos"][nombre][k] = {
                "densidad_obs": d_obs,
                "densidad_nula_media": float(dn.mean()),
                "densidad_nula_sd": float(dn.std()),
                "densidad_nula_p05": float(np.percentile(dn, 5)),
                "densidad_nula_p95": float(np.percentile(dn, 95)),
                "p_unilateral": float(p), "z": float(z),
                "grado_medio_obs": obs[k]["grado_medio"],
                "grado_medio_nulo": float(np.mean(acum[k]["grado_medio"])),
                "componente_mayor_obs": obs[k]["componente_mayor"],
                "componente_mayor_nulo": float(np.mean(acum[k]["componente_mayor"])),
            }
            print("    %5.0f m: obs %.4f | nulo %.4f +- %.4f | z=%+.2f | p=%.4f"
                  % (a, d_obs, dn.mean(), dn.std(), z, p), flush=True)

    with open(os.path.join(OUT, "nulos.json"), "w", encoding="utf-8") as f:
        json.dump(salida, f, ensure_ascii=False, indent=2)
    print("\n  ->", os.path.join(OUT, "nulos.json"))


if __name__ == "__main__":
    main()

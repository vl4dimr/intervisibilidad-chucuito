# -*- coding: utf-8 -*-
"""
¿Sobrevive el contraste a la altura que se atribuya a las estructuras?

La sensibilidad mostro que pasar de 0 a 12 m de altura mueve la densidad
observada un 69 %. Eso por si solo no invalida nada, porque el modelo nulo usa
el mismo supuesto y la comparacion es interna. Pero hay que comprobarlo: se
recalcula el nulo rigido con las alturas extremas del rango plausible.

Si el contraste se sostiene en ambos, la conclusion no depende de una cifra que
nadie ha medido en campo. Si se cae en alguno, hay que decir a partir de que
altura el resultado deja de aguantar.

Salida: results/nulo_alturas.json
"""
import csv, json, math, os, sys, time
import numpy as np, rasterio
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from viewshed_core import network_stats, pairwise_intervisibility

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA, RES = os.path.join(BASE, "data"), os.path.join(BASE, "results")
COTA_AGUA, TOL_AGUA = 3808.5, 0.05
N_NULL, ALCANCE, MARGEN, SEED = 200, 5000.0, 5, 20260901
ALTURAS = [0.0, 1.5, 3.0, 6.0, 12.0]

def main():
    rows = list(csv.DictReader(open(os.path.join(DATA, "sitios_chucuito.csv"), encoding="utf-8-sig")))
    cols = np.array([int(r["col"]) for r in rows], float)
    fils = np.array([int(r["fila"]) for r in rows], float)
    with rasterio.open(os.path.join(DATA, "terreno_chucuito.tif")) as s:
        dem = s.read(1).astype(np.float32)
    log = json.load(open(os.path.join(DATA, "terreno_log.json"), encoding="utf-8"))
    rx, ry = log["dem_resolucion_m_aprox"]
    H, W = dem.shape
    agua = np.abs(dem - COTA_AGUA) < TOL_AGUA
    cx, cy = cols.mean(), fils.mean()
    dc, df = cols - cx, fils - cy

    salida = {"n_null": N_NULL, "alcance_m": ALCANCE, "alturas": ALTURAS, "por_altura": {}}
    print("Contraste rigido a distintas alturas de estructura (alcance %.0f m)\n" % ALCANCE, flush=True)
    for h in ALTURAS:
        v0, d0 = pairwise_intervisibility(dem, rx, ry, cols.astype(int), fils.astype(int),
                                          h_tgt=h, max_dist_m=ALCANCE)
        obs = network_stats(v0, d0, ALCANCE)["densidad"]
        rng = np.random.default_rng(SEED)
        acc, tries, vals = 0, 0, []
        t0 = time.time()
        while acc < N_NULL:
            tries += 1
            th = rng.uniform(0, 2 * math.pi); ct, st = math.cos(th), math.sin(th)
            rc, rf = dc * ct - df * st, dc * st + df * ct
            lo_c, hi_c = MARGEN - rc.min(), W - MARGEN - rc.max()
            lo_f, hi_f = MARGEN - rf.min(), H - MARGEN - rf.max()
            if lo_c >= hi_c or lo_f >= hi_f:
                continue
            nc = np.rint(rc + rng.uniform(lo_c, hi_c)).astype(int)
            nf = np.rint(rf + rng.uniform(lo_f, hi_f)).astype(int)
            if agua[nf, nc].any():
                continue
            v, d = pairwise_intervisibility(dem, rx, ry, nc, nf, h_tgt=h, max_dist_m=ALCANCE)
            vals.append(network_stats(v, d, ALCANCE)["densidad"]); acc += 1
        arr = np.array(vals)
        p = (np.sum(arr >= obs) + 1) / (len(arr) + 1)
        z = (obs - arr.mean()) / arr.std() if arr.std() > 0 else float("nan")
        salida["por_altura"]["%.1f" % h] = {"observado": obs, "nulo_media": float(arr.mean()),
                                            "nulo_sd": float(arr.std()), "p": float(p), "z": float(z)}
        print("  altura %5.1f m: obs %.4f | nulo %.4f +- %.4f | z=%+.2f | p=%.4f  (%.0f s)"
              % (h, obs, arr.mean(), arr.std(), z, p, time.time() - t0), flush=True)

    json.dump(salida, open(os.path.join(RES, "nulo_alturas.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    print("\n  ->", os.path.join(RES, "nulo_alturas.json"))

if __name__ == "__main__":
    main()

# -*- coding: utf-8 -*-
"""
¿Se ven mas entre si los sitios de toponimo funerario?

El contraste general responde si el conjunto de sitios ve mas de lo esperable.
Esta pregunta es mas fina: dentro del mismo conjunto, ¿el subgrupo funerario
forma una subred mas conectada que un subgrupo cualquiera del mismo tamano?

La comparacion se hace por remuestreo dentro del propio conjunto observado, no
contra terreno aleatorio. Asi se controla de golpe todo lo que comparten los
sitios de Chucuito —altitud, cercania al lago, densidad local— y solo queda en
juego la pertenencia al subgrupo.

Advertencia sobre la etiqueta: «funerario» aqui significa que el nombre
registrado por el INC contiene chullpa, chulpa, amaya, gentil o torre. Es un
proxy del tipo de monumento, no una clasificacion arqueologica. Un sitio
funerario registrado con otro nombre queda fuera, y un topónimo puede aludir a
un rasgo del paisaje y no a una estructura. El resultado hay que leerlo con esa
reserva.

Salida: results/funerarios.json
"""
import csv
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(BASE, "data")
RES = os.path.join(BASE, "results")

N_PERM = 20000
SEED = 20260830
ALCANCES = [5000.0, 10000.0, 15000.0]


def subred_densidad(vis, dist, idx, alcance):
    """Densidad de intervisibilidad dentro de un subconjunto de sitios."""
    sub_v = vis[np.ix_(idx, idx)]
    sub_d = dist[np.ix_(idx, idx)]
    n = len(idx)
    elig = (sub_d <= alcance) & ~np.eye(n, dtype=bool)
    n_e = elig.sum() // 2
    if n_e == 0:
        return np.nan, 0
    return float((sub_v & elig).sum() // 2) / n_e, int(n_e)


def main():
    with open(os.path.join(DATA, "sitios_chucuito.csv"), encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    fun = np.array([r["funerario"] == "True" for r in rows])
    alt = np.array([float(r["altitud_m"]) for r in rows])
    d = np.load(os.path.join(RES, "red_observada.npz"))
    vis, dist = d["vis"], d["dist"]

    idx_fun = np.nonzero(fun)[0]
    n_fun = len(idx_fun)
    n = len(rows)
    rng = np.random.default_rng(SEED)
    print("Sitios: %d | con topónimo funerario: %d" % (n, n_fun), flush=True)
    print("Altitud media: funerarios %.0f m, resto %.0f m"
          % (alt[fun].mean(), alt[~fun].mean()), flush=True)

    salida = {"n_sitios": n, "n_funerarios": n_fun, "n_permutaciones": N_PERM,
              "altitud_media_funerarios": float(alt[fun].mean()),
              "altitud_media_resto": float(alt[~fun].mean()),
              "por_alcance": {}}

    print("\nDensidad de la subred funeraria frente a subgrupos del mismo tamano")
    for a in ALCANCES:
        obs, n_e = subred_densidad(vis, dist, idx_fun, a)
        nulo = np.empty(N_PERM)
        pares = np.empty(N_PERM)
        for k in range(N_PERM):
            s = rng.choice(n, n_fun, replace=False)
            nulo[k], pares[k] = subred_densidad(vis, dist, s, a)
        val = ~np.isnan(nulo)
        p = (np.sum(nulo[val] >= obs) + 1) / (val.sum() + 1)
        z = (obs - np.nanmean(nulo)) / np.nanstd(nulo)
        salida["por_alcance"]["%.0f" % a] = {
            "densidad_funeraria": obs,
            "pares_elegibles": n_e,
            "densidad_aleatoria_media": float(np.nanmean(nulo)),
            "densidad_aleatoria_sd": float(np.nanstd(nulo)),
            "p_unilateral": float(p), "z": float(z),
        }
        print("  %5.0f m: funerarios %.4f (%d pares) | aleatorio %.4f ± %.4f | z=%+.2f | p=%.4f"
              % (a, obs, n_e, np.nanmean(nulo), np.nanstd(nulo), z, p), flush=True)

    with open(os.path.join(RES, "funerarios.json"), "w", encoding="utf-8") as f:
        json.dump(salida, f, ensure_ascii=False, indent=2)
    print("\n  ->", os.path.join(RES, "funerarios.json"))


if __name__ == "__main__":
    main()

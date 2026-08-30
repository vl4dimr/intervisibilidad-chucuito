# -*- coding: utf-8 -*-
"""
Validacion del calculo de linea de vision sobre terrenos de respuesta conocida.

Un algoritmo de visibilidad falla en silencio: devuelve booleanos plausibles
aunque el criterio geometrico este mal, y sobre terreno real no hay forma de
notarlo. Por eso se prueba antes contra casos construidos, donde la respuesta se
deduce de la geometria y no del propio programa.

Los casos cubren lo que puede romperse: terreno plano, una barrera que debe
bloquear, la misma barrera rebajada que no debe hacerlo, el efecto de la altura
del objetivo, la curvatura terrestre a distancia larga y una depresion que no
debe bloquear nada.

Salida: results/validacion_los.json
"""
import json
import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from viewshed_core import R_EFF, curvature_rise, line_of_sight

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(BASE, "results")

RES = 30.0  # metros por celda, como el Copernicus GLO-30
casos = []


def check(nombre, obtenido, esperado, detalle=""):
    ok = obtenido == esperado
    casos.append({"caso": nombre, "esperado": esperado, "obtenido": obtenido,
                  "ok": ok, "detalle": detalle})
    print("  %-46s %s   %s" % (nombre, "OK   " if ok else "FALLA", detalle), flush=True)
    return ok


def main():
    os.makedirs(OUT, exist_ok=True)
    print("VALIDACION DE LINEA DE VISION\n")

    # 1. Terreno plano: siempre visible
    plano = np.zeros((21, 201), dtype=np.float32)
    check("terreno plano, 6 km", line_of_sight(plano, RES, RES, 0, 10, 200, 10), True)

    # 2. Barrera alta a mitad de camino: debe bloquear
    barrera = plano.copy()
    barrera[:, 100] = 50.0
    check("barrera de 50 m a mitad de camino",
          line_of_sight(barrera, RES, RES, 0, 10, 200, 10), False,
          "observador 1,7 m, objetivo 3 m")

    # 3. La misma barrera rebajada a 1 m: no debe bloquear
    baja = plano.copy()
    baja[:, 100] = 1.0
    check("misma barrera rebajada a 1 m",
          line_of_sight(baja, RES, RES, 0, 10, 200, 10), True)

    # 4. Casos limite, que ademas verifican que la curvatura se aplica.
    #    Con 1,7 y 3 m de altura, a mitad de camino la vista pasa a 2,35 m; la
    #    curvatura suma 0,61 m al terreno en un trayecto de 6 km, de modo que el
    #    umbral efectivo de bloqueo baja a 1,74 m y no a 2,35.
    umbral = 2.35 - curvature_rise(3000.0, 6000.0)
    limite = plano.copy()
    limite[:, 100] = 1.5
    check("barrera de 1,5 m, umbral efectivo %.2f m" % umbral,
          line_of_sight(limite, RES, RES, 0, 10, 200, 10), True,
          "por debajo del umbral corregido")
    limite2 = plano.copy()
    limite2[:, 100] = 2.0
    check("barrera de 2,0 m, umbral efectivo %.2f m" % umbral,
          line_of_sight(limite2, RES, RES, 0, 10, 200, 10), False,
          "sin curvatura no bloquearia: la prueba la exige")

    # 5. La altura del objetivo rescata la vision.
    #    Una torre de 12 m eleva la linea lo suficiente para salvar la barrera.
    check("barrera de 4 m con objetivo de 3 m",
          line_of_sight(limite.copy() * 0 + np.where(np.arange(201) == 100, 4.0, 0.0),
                        RES, RES, 0, 10, 200, 10, h_tgt=3.0), False)
    check("barrera de 4 m con objetivo de 12 m",
          line_of_sight(limite.copy() * 0 + np.where(np.arange(201) == 100, 4.0, 0.0),
                        RES, RES, 0, 10, 200, 10, h_tgt=12.0), True,
          "la altura de la torre salva el obstaculo")

    # 6. Depresion: nunca bloquea
    valle = plano.copy()
    valle[:, 90:110] = -30.0
    check("depresion de 30 m", line_of_sight(valle, RES, RES, 0, 10, 200, 10), True)

    # 7. Curvatura terrestre. Sobre un plano perfecto de 40 km, dos puntos a
    #    1,7 y 3 m deben dejar de verse: el horizonte geometrico esta antes.
    largo = np.zeros((5, 1334), dtype=np.float32)
    d_horizonte = math.sqrt(2 * R_EFF * 1.7) + math.sqrt(2 * R_EFF * 3.0)
    check("plano de 40 km, mas alla del horizonte",
          line_of_sight(largo, RES, RES, 0, 2, 1333, 2), False,
          "horizonte teorico %.1f km" % (d_horizonte / 1000))

    corto = np.zeros((5, 200), dtype=np.float32)
    check("plano de 6 km, dentro del horizonte",
          line_of_sight(corto, RES, RES, 0, 2, 199, 2), True)

    # 8. La formula de curvatura: el descenso maximo esta en el punto medio
    D = 26000.0
    drop_mid = curvature_rise(D / 2, D)
    drop_theo = D * D / (8 * R_EFF)
    ok = abs(drop_mid - drop_theo) < 1e-6
    casos.append({"caso": "descenso por curvatura a 26 km", "esperado": round(drop_theo, 3),
                  "obtenido": round(drop_mid, 3), "ok": ok, "detalle": "metros"})
    print("  %-46s %s   %.2f m en el punto medio"
          % ("descenso por curvatura a 26 km", "OK   " if ok else "FALLA", drop_mid), flush=True)

    # 9. Simetria: la vista de A a B con las mismas alturas coincide con la de B a A
    rng = np.random.default_rng(7)
    rug = rng.normal(0, 12, (60, 60)).cumsum(axis=1).astype(np.float32)
    sim = all(line_of_sight(rug, RES, RES, a, b, c, d_, h_obs=2.0, h_tgt=2.0)
              == line_of_sight(rug, RES, RES, c, d_, a, b, h_obs=2.0, h_tgt=2.0)
              for a, b, c, d_ in rng.integers(0, 59, (60, 4)))
    check("simetria con alturas iguales, 60 pares", sim, True, "terreno rugoso aleatorio")

    n_ok = sum(1 for c in casos if c["ok"])
    res = {"casos": casos, "superados": n_ok, "total": len(casos),
           "parametros": {"resolucion_m": RES, "k_refraccion": 0.13,
                          "radio_efectivo_m": R_EFF}}
    with open(os.path.join(OUT, "validacion_los.json"), "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=2)

    print("\n  %d de %d casos superados" % (n_ok, len(casos)))
    return 0 if n_ok == len(casos) else 1


if __name__ == "__main__":
    sys.exit(main())

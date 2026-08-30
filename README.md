# Intervisibilidad de sitios arqueológicos en Chucuito, Puno

Análisis de líneas de visión entre los sitios arqueológicos registrados en la provincia de Chucuito
(cuenca del lago Titicaca, Perú), sobre modelo digital de elevación abierto, con contraste contra
modelos nulos.

## La pregunta

Si las estructuras se situaron para verse entre sí, la red de intervisibilidad observada tendrá una
densidad que puntos colocados sin esa intención no reproducen. La pregunta no es cuántos sitios se ven
—ese número aislado no significa nada— sino cuántos se ven **de más** respecto a lo esperable.

## Datos

| Fuente | Contenido | Licencia |
|---|---|---|
| INC / Ministerio de Cultura, redistribuido por Geo GPS Perú | 7.907 sitios arqueológicos del Perú; 507 en Puno, 180 en Chucuito | **No declarada** por el redistribuidor |
| Copernicus DEM GLO-30 (ESA) | Modelo de elevación, 30 m, 9 teselas | Copernicus, uso libre con atribución |

**Advertencia de procedencia.** La capa de sitios se sirve desde Google Drive sin licencia declarada,
sin fecha de corte y sin criterio de inclusión documentado. El dato es de origen público —del INC— pero
el redistribuidor no documenta nada de eso. Cualquier resultado hereda esa opacidad y así se declara en
el artículo. Antes de publicar conviene verificarlo con el Ministerio.

Se intentaron además tres vías oficiales, ninguna utilizable:

- **Geoportal del Ministerio de Cultura**: su GeoServer responde, pero publica **cero capas** de forma
  anónima. Tanto WFS como WMS devuelven el servicio sin ninguna capa; requiere autenticación.
- **SIGDA**: corre sobre una cuenta personal de ArcGIS Online (`cesarmil1`), y el elemento no es
  accesible por su interfaz de programación.
- **ArqueoData**: el dominio no resuelve.

## Método

**Línea de visión.** Entre cada par de sitios se muestrea el perfil del terreno a una muestra por celda
y se comprueba si el relieve intermedio corta la recta que une observador y objetivo. Se aplica la
corrección conjunta de curvatura terrestre y refracción atmosférica mediante radio efectivo
R/(1−k) con k = 0,13.

**El signo de esa corrección es el punto donde es fácil equivocarse.** Trabajando respecto a la cuerda
que une los dos extremos, el término d(D−d)/2R se **suma** al terreno intermedio: visto desde esa
cuerda la Tierra abulta, y el abultamiento se anula en los extremos. Restarlo —que es lo que sugiere
hablar de «descenso por curvatura»— vuelve la Tierra cóncava y hace que ningún relieve bloquee nunca a
larga distancia. El error se detectó en la validación, no en el análisis.

**Alturas.** Observador de pie a 1,70 m; objetivo a 3,00 m, cota conservadora para una chullpa. Ambas
son parámetros, no constantes, y el análisis se repite variándolas.

**Alcance.** Más allá de cierta distancia una torre de tres metros deja de ser reconocible a simple
vista. La cifra exacta es discutible, así que se informa a 5, 10, 15 y 26 km en lugar de fijar una.

## Modelos nulos

Se calculan tres, de exigencia creciente, y la diferencia entre ellos es el argumento del trabajo.

**Uniforme.** Puntos al azar dentro del área. Es el nulo ingenuo: casi siempre da significativo, porque
los sitios reales están en relieve favorable y el relieve favorable ve más. Confirma poco. Equivale al
procedimiento del único antecedente publicado en la cuenca (Bongers, Arkush y Harrower, 2012).

**Estratificado por altitud.** Puntos al azar tomados de celdas con la misma distribución de cota que
los sitios reales. Responde a la pregunta pertinente: dada la altura a la que están, ¿se ven más de lo
que les tocaría?

**Rígido.** Toma la nube de sitios tal cual, conservando **todas** las distancias mutuas, y la traslada
y rota sobre el terreno. Separa dónde están los sitios de cómo están dispuestos entre sí, que es la
única forma de preguntar si esta configuración concreta está colocada donde se ve más.

Si la asociación sobrevive al tercero, el emplazamiento responde a algo más que a la altura y a la
forma del conjunto. Si solo sobrevive al primero, lo único demostrado es que los sitios están altos,
que no es un hallazgo. El nulo uniforme atribuye al emplazamiento un efecto **entre 2,3 y 9 veces
mayor** que el que resiste al rígido.

## Tres artefactos que producen resultados falsos y plausibles

Ninguno de los tres falla de forma visible. Los tres devuelven redes de aspecto razonable y
estadísticos interpretables, y por eso se documentan con el mismo detalle que el resultado.

| Artefacto | Efecto si no se corrige | Cómo se detectó |
|---|---|---|
| Signo de la corrección por curvatura | Ningún relieve bloquea a larga distancia | Validación sintética |
| Cota constante del agua: el lago ocupa el 30,6 % del recorte y no bloquea nada | El contraste pasa de z = +2,63 a **z = −0,08**: el efecto desaparece | Al mirar el mapa |
| Recorte ajustado: la nube solo cabía en 244 de 360 orientaciones | El contraste sube a z = +4,49, inflado | Al medir la tasa de aceptación del nulo |

Las ejecuciones previas a la corrección se conservan en `results/nulo_rigido_sin_mascara.json` y
`results/nulo_rigido_n300.json`, para que la comparación pueda verificarse en lugar de creerse.

## Validación

El detector de líneas de visión se prueba sobre doce terrenos construidos de respuesta conocida:
plano, barrera que bloquea, la misma rebajada que no debe bloquear, casos límite que verifican el
término de curvatura, efecto de la altura del objetivo, depresión que nunca bloquea, horizonte
geométrico a 40 km y simetría sobre terreno rugoso. **12 de 12.**

## Guiones

Se ejecutan en orden. Cada uno deja su resultado en `results/` como JSON legible.

```bash
python scripts/fetch_sites_and_dem.py   # sitios del INC y teselas Copernicus
python scripts/p01_terrain.py           # recorte del terreno y proyección local
python scripts/p02_validate_los.py      # validación del cálculo de visibilidad (12 casos)
python scripts/p03_network.py           # red observada, nulo uniforme y estratificado
python scripts/p04_funerary.py          # subred de topónimos funerarios
python scripts/p05_figures.py           # las tres figuras del artículo
python scripts/p06_null_rigid.py        # nulo rígido: traslación y rotación
python scripts/p07_power.py             # potencia y efecto mínimo detectable
python scripts/p08_manuscript.py        # genera el manuscrito desde los JSON
python scripts/p09_sensibilidad.py      # sensibilidad a la asignación de celda
python scripts/p10_null_alturas.py      # sensibilidad a la altura de estructura
python scripts/p11_por_distrito.py      # desglose Juli / Pomata
python scripts/p12_auditoria.py         # auditoría de formato, figuras y cifras
python scripts/p13_artefacto_agua.py    # contraejemplo: nulo sin enmascarar el lago
```

El manuscrito **no contiene ninguna cifra escrita a mano**: `p08_manuscript.py` las lee de los JSON, y
`p12_auditoria.py` comprueba que ningún valor citado en el texto carezca de respaldo en los resultados.

## Resultados

| | Densidad a 5 km | Nulo rígido | z | p |
|---|---|---|---|---|
| Los 180 sitios | 0,4094 | 0,1899 ± 0,0835 | +2,63 | 0,032 |
| Solo Juli (168 sitios) | 0,4076 | 0,2178 ± 0,1128 | +1,68 | 0,074 |
| Subred funeraria (24 sitios) | 0,4252 | 0,4361 ± 0,1058 | −0,10 | 0,526 |

Los sitios de Chucuito no forman una nube continua sino dos grupos separados por 17,2 km. Analizados
por separado, el contraste queda en el margen de la significación convencional. **La evidencia es
indicativa, no concluyente**, y así se declara en el artículo.

## Estado

Análisis cerrado y auditado: 34 comprobaciones de formato, figuras, coherencia numérica y aparato
crítico, sin fallos (`results/auditoria.json`). Manuscrito preparado para su envío a *Virtual
Archaeology Review*.

## Licencia y cita

Código bajo licencia MIT. El modelo de elevación es Copernicus DEM GLO-30, de uso libre con
atribución; la capa de sitios se cita según su procedencia declarada, con la reserva expuesta arriba.

Si utiliza este material, cite el artículo asociado y el depósito (véase `CITATION.cff`).

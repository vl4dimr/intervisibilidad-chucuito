# -*- coding: utf-8 -*-
"""
Genera un visor web 3D interactivo del paisaje visual de Chucuito.

Un unico HTML autocontenido, con Three.js: el relieve real como malla drapeada
(tinte hipsometrico + sombreado + la cuenca visual en rojo), los sitios
arqueologicos como marcadores 3D —las torres funerarias resaltadas, la
observadora como piramide—, y navegacion orbital. A diferencia de la figura
estatica de matplotlib, aqui el motor 3D ordena en profundidad y los sitios se
ven sobre el terreno.

Es la pieza de «arqueologia virtual» para el regreso a VAR: interactiva,
reproducible y depositable en Zenodo con DOI. Depende solo de numpy, rasterio
y matplotlib (para cocinar la textura); Three.js se sirve desde cdnjs.

Salida: chucuito_visor3d.html
"""
import base64
import csv
import io
import json
import os

import numpy as np
import rasterio
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LightSource, LinearSegmentedColormap
from rasterio.warp import transform as tcoords

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA, RES = os.path.join(BASE, "data"), os.path.join(BASE, "results")
UTM = "EPSG:32719"
N = 360   # lado de la malla del visor (submuestreo)


def main():
    with rasterio.open(os.path.join(DATA, "terreno_utm.tif")) as s:
        dem = s.read(1).astype(np.float32)
        tr = s.transform
        H, W = dem.shape
    vs = np.load(os.path.join(RES, "viewshed_nuestro.npy"))
    obs = json.load(open(os.path.join(RES, "observador_3d.json"), encoding="utf-8"))

    # recorte cuadrado centrado en el observador (~14 km)
    xs, ys = tcoords("EPSG:4326", UTM, [obs["x_raster"]], [obs["y_raster"]])
    oc, of = ~tr * (xs[0], ys[0]); oc, of = int(round(oc)), int(round(of))
    r = int(7000 / 30)
    f0, f1 = max(0, of - r), min(H, of + r)
    c0, c1 = max(0, oc - r), min(W, oc + r)

    fy = np.linspace(f0, f1 - 1, N).astype(int)
    fx = np.linspace(c0, c1 - 1, N).astype(int)
    z = dem[np.ix_(fy, fx)]
    vcrop = vs[np.ix_(fy, fx)]

    # --- textura: ortoimagen Sentinel-2 (p22) + cuenca visual drapeada -----
    # Se lee la ortofoto exactamente en la ventana de la malla, a 10 m. La fila 0
    # es el norte; Three.js (flipY) la coloca en v = 1, que en PlaneGeometry es
    # el borde +y, es decir, el norte una vez rotado el plano. No se invierte.
    from rasterio.windows import from_bounds
    from rasterio.enums import Resampling as Rs
    from scipy import ndimage
    x0, y0 = tr.c + c0 * tr.a, tr.f + f0 * tr.e
    x1, y1 = tr.c + c1 * tr.a, tr.f + f1 * tr.e
    k = 3
    with rasterio.open(os.path.join(DATA, "ortofoto_s2.tif")) as so:
        win = from_bounds(x0, y1, x1, y0, transform=so.transform)
        orto = so.read(window=win, out_shape=(3, k * (f1 - f0), k * (c1 - c0)),
                       resampling=Rs.bilinear, boundless=True).transpose(1, 2, 0) / 255.0
    v = np.kron(vs[f0:f1, c0:c1] == 1, np.ones((k, k), bool))
    borde = v & ~ndimage.binary_erosion(v, iterations=2)
    rojo = np.array([0.80, 0.07, 0.07])
    orto[v] = 0.5 * orto[v] + 0.5 * rojo
    orto[borde] = rojo
    from PIL import Image
    buf = io.BytesIO()
    Image.fromarray((np.clip(orto, 0, 1) * 255).astype(np.uint8)).save(buf, "JPEG", quality=88)
    tex_b64 = base64.b64encode(buf.getvalue()).decode()
    meta_o = json.load(open(os.path.join(RES, "ortofoto_s2.json"), encoding="utf-8"))

    # --- alturas normalizadas para Three.js --------------------------------
    z0 = float(z.min())
    alturas = (z - z0).astype(float)              # metros sobre el minimo
    lado_m = (c1 - c0) * 30.0                      # extension real, metros

    # --- sitios: a coordenadas de la malla ---------------------------------
    sitios = []
    rows = list(csv.DictReader(open(os.path.join(DATA, "sitios_chucuito.csv"),
                                    encoding="utf-8-sig")))
    for row in rows:
        ux, uy = tcoords("EPSG:4326", UTM, [float(row["lon"])], [float(row["lat"])])
        cc, ff = ~tr * (ux[0], uy[0]); cc, ff = int(round(cc)), int(round(ff))
        if not (f0 <= ff < f1 and c0 <= cc < c1):
            continue
        # a coordenadas [0,1] de la malla
        u = (cc - c0) / (c1 - c0)
        v = (ff - f0) / (f1 - f0)
        alt = float(dem[ff, cc] - z0)
        es_fun = row["funerario"] == "True"
        es_obs = int(row["id"]) == int(obs["id"])
        visible = bool(vs[ff, cc] == 1)
        sitios.append({"u": u, "v": v, "alt": alt, "fun": es_fun,
                       "obs": es_obs, "vis": visible,
                       "nom": row["nombre"].strip()})

    n_fun = sum(1 for s in sitios if s["fun"] and not s["obs"])
    n_fun_vis = sum(1 for s in sitios if s["fun"] and not s["obs"] and s["vis"])

    datos = {
        "N": N, "lado_m": lado_m, "alturas": alturas.ravel().tolist(),
        "z_min": z0, "z_rango": float(z.max() - z.min()),
        "sitios": sitios, "n_fun": n_fun, "n_fun_vis": n_fun_vis,
        "obs_nom": " ".join(obs["nombre"].split()), "obs_alt": obs["altitud"],
        "credito": "Copernicus DEM GLO-30 · %s" % meta_o["atribucion_es"],
        "fecha_img": meta_o["fecha"],
    }

    html = PLANTILLA.replace("__TEX__", tex_b64).replace(
        "__DATOS__", json.dumps(datos))
    out = os.path.join(BASE, "chucuito_visor3d.html")
    open(out, "w", encoding="utf-8").write(html)
    kb = os.path.getsize(out) / 1024
    print("-> %s (%.0f KB) | %d sitios, %d torres funerarias (%d visibles)"
          % (out, kb, len(sitios), n_fun, n_fun_vis))


PLANTILLA = r"""<!doctype html>
<html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Chucuito 3D — paisaje visual desde una torre funeraria</title>
<style>
  html,body{margin:0;height:100%;overflow:hidden;background:#0f1420;
    font-family:Arial,Helvetica,sans-serif;color:#e5e7eb}
  #c{position:fixed;inset:0}
  #panel{position:fixed;top:14px;left:14px;background:rgba(17,24,39,.82);
    padding:14px 16px;border-radius:10px;max-width:330px;line-height:1.5;
    backdrop-filter:blur(4px)}
  #panel h1{margin:0 0 6px;font-size:15px}
  #panel p{margin:4px 0;font-size:12px;color:#cbd5e1}
  .k{display:inline-block;width:12px;height:12px;border-radius:50%;
    margin-right:6px;vertical-align:middle;border:1px solid #fff}
  #hint{position:fixed;bottom:14px;left:14px;font-size:11px;color:#94a3b8}
  b.r{color:#f87171}
</style></head><body>
<div id="c"></div>
<div id="panel">
  <h1>Chucuito: el paisaje visual de una tumba</h1>
  <p>Cuenca visual desde la torre funeraria más alta del corpus
     (<span id="onom"></span>, <span id="oalt"></span> m), en rojo sobre el
     relieve real.</p>
  <p><span class="k" style="background:#111827"></span>Torre observadora</p>
  <p><span class="k" style="background:rgba(204,18,18,.55);border-radius:2px"></span>Cuenca
     visual de la torre (alcance 10 km)</p>
  <p><span class="k" style="background:#334155"></span>Otra torre funeraria
     (<b class="r"><span id="nfv"></span> de <span id="nf"></span></b> visibles desde la torre)</p>
  <p><span class="k" style="background:#f8fafc"></span>Sitio no funerario</p>
  <p style="color:#94a3b8;font-size:11px;margin-top:8px">Exageración
     vertical ×1.8. <span id="cred"></span> (<span id="fimg"></span>).</p>
</div>
<div id="hint">Arrastra para orbitar · rueda para acercar · clic derecho para desplazar</div>
<script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/controls/OrbitControls.js"></script>
<script>
const D = __DATOS__;
document.getElementById('onom').textContent = D.obs_nom;
document.getElementById('oalt').textContent = Math.round(D.obs_alt);
document.getElementById('nf').textContent = D.n_fun;
document.getElementById('nfv').textContent = D.n_fun_vis;
document.getElementById('cred').textContent = D.credito;
document.getElementById('fimg').textContent = D.fecha_img;

const N = D.N, LADO = 100, EXAG = 1.8;
const escZ = (LADO / D.lado_m) * EXAG;

const scene = new THREE.Scene();
// cielo en degradado y bruma del mismo color que el horizonte
const cv = document.createElement('canvas'); cv.width = 2; cv.height = 256;
const g2 = cv.getContext('2d'); const gr = g2.createLinearGradient(0,0,0,256);
gr.addColorStop(0,'#7898c8'); gr.addColorStop(1,'#d2dbe5');
g2.fillStyle = gr; g2.fillRect(0,0,2,256);
scene.background = new THREE.CanvasTexture(cv);
scene.fog = new THREE.Fog(0xd2dbe5, 90, 260);
const cam = new THREE.PerspectiveCamera(50, innerWidth/innerHeight, 0.1, 2000);
cam.position.set(25, 38, -70);
const rnd = new THREE.WebGLRenderer({antialias:true});
rnd.setSize(innerWidth, innerHeight);
rnd.setPixelRatio(Math.min(devicePixelRatio, 2));
document.getElementById('c').appendChild(rnd.domElement);
const ctr = new THREE.OrbitControls(cam, rnd.domElement);
ctr.enableDamping = true; ctr.maxPolarAngle = Math.PI*0.49;

// --- terreno: malla desplazada por el DEM ---
const geo = new THREE.PlaneGeometry(LADO, LADO, N-1, N-1);
const pos = geo.attributes.position;
for (let i=0;i<pos.count;i++){
  pos.setZ(i, D.alturas[i]*escZ);
}
geo.computeVertexNormals();
const tex = new THREE.TextureLoader().load('data:image/jpeg;base64,__TEX__');
tex.minFilter = THREE.LinearFilter;
tex.anisotropy = rnd.capabilities.getMaxAnisotropy();
const mat = new THREE.MeshLambertMaterial({map:tex});
const terreno = new THREE.Mesh(geo, mat);
terreno.rotation.x = -Math.PI/2;   // de plano XY a horizontal, altura en Y
scene.add(terreno);

// --- luces ---
// la ortoimagen ya trae la luz real; el sol solo modela el relieve
scene.add(new THREE.HemisphereLight(0xffffff, 0x8a7a66, .75));
const sol = new THREE.DirectionalLight(0xfff4e6, .45);
sol.position.set(0.7, 1.2, -0.7); scene.add(sol);

// --- sitios ---
function aMundo(u, v, alt){
  return new THREE.Vector3((u-0.5)*LADO, alt*escZ, -(0.5-v)*LADO);
}
D.sitios.forEach(s=>{
  const p = aMundo(s.u, s.v, s.alt);
  let m;
  if (s.obs){
    m = new THREE.Mesh(new THREE.ConeGeometry(1.6, 4, 4),
        new THREE.MeshStandardMaterial({color:0x111827}));
    m.position.set(p.x, p.y+2, p.z);
  } else {
    const col = s.fun ? 0x334155 : 0xf8fafc;
    const rad = s.fun ? 0.9 : 0.45;
    const alto = s.fun ? 2.6 : 1.4;
    const mastil = new THREE.Mesh(new THREE.CylinderGeometry(0.12, 0.12, alto, 6),
        new THREE.MeshLambertMaterial({color:0xe5e7eb}));
    mastil.position.set(p.x, p.y+alto/2, p.z); scene.add(mastil);
    m = new THREE.Mesh(new THREE.SphereGeometry(rad, 16, 12),
        new THREE.MeshLambertMaterial({color: (s.fun && s.vis) ? 0xcc1212 : col}));
    m.position.set(p.x, p.y+alto+rad*0.6, p.z);
  }
  scene.add(m);
});

// centrar la orbita sobre la torre observadora
const o = D.sitios.find(s=>s.obs);
if(o){ const p=aMundo(o.u,o.v,o.alt); ctr.target.set(p.x,p.y,p.z); }

addEventListener('resize', ()=>{
  cam.aspect = innerWidth/innerHeight; cam.updateProjectionMatrix();
  rnd.setSize(innerWidth, innerHeight);
});
(function loop(){ requestAnimationFrame(loop); ctr.update(); rnd.render(scene, cam); })();
</script></body></html>"""


if __name__ == "__main__":
    main()

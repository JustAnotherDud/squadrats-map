"""Recorta os ficheiros de município estrangeiro (refdata/foreign_muni/*.geojson)
para só a zona que o clube já visitou + 10 km, e poda o grid_totals.json a
condizer.

Porquê: guardar os ~11 mil municípios da Alemanha para os 3 que alguém tocou
é 20 MB de "e se". Guardar só os municípios a menos de 10 km de onde um
membro REALMENTE andou é preparação real (uma ida de volta à mesma zona está
coberta) por ~150 KB. A divisão fina de um país só se constrói quando alguém
lá vai a sério.

  origem   -> GADM 4.1 level 4 (Gemeinde/municipio), reformatado à mão uma vez
              para {properties: country, region, parent}. NÃO se vai buscar
              aqui — parte-se do ficheiro completo que já está no repo (ou,
              para um país novo, do ficheiro completo posto à mão em
              refdata/foreign_muni/<CC>.geojson antes de correr isto).
  seed     -> os municípios em que o clube tem squares (data/club_regioes.json,
              união dos atletas). Precisa do club_regioes.json presente:
              `git checkout origin/data -- data/club_regioes.json` se faltar.
  buffer   -> 10 km à volta da geometria desses municípios.

Degradação, se um membro sair fora do buffer numa visita seguinte: os squares
novos ficam a nível de região (Land/província) até se voltar a correr isto.
É VISÍVEL: build_mapa.py e classify_club.py contam esses squares e imprimem
`AVISO: <CC>: N square(s) ... fora do recorte de 10 km` no fim do run, e o
número fica em stats.foreign.*.muni_clip_misses. É o sinal de "correr o clip
outra vez".

Uso:
  py clip.py            recorta todos os foreign_muni/*.geojson
  py clip.py DE ES      só estes
"""
import argparse
import json
import math
import os
import sys

from shapely import STRtree, points
from shapely.geometry import shape
from shapely.validation import make_valid

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
FOREIGN_MUNI = os.path.join(HERE, "foreign_muni")
GRID_TOTALS = os.path.join(HERE, "grid_totals.json")
CLUB_JSON = os.path.join(REPO, "data", "club.json")

BUFFER_KM = 10
DEG_PER_KM = 1.0 / 111.0
ZOOM = 17  # club.json é z17


def _clean(g):
    return g if g.is_valid else make_valid(g)


def _pontos_capturados():
    """Pontos (lon, lat) no centro de cada square do club.json. Seed do clip:
    mantém-se os municípios a <10 km DESTES pontos (não os municípios já
    classificados — isso era circular: um square sem match de município não
    entrava no seed e ficava de fora do recorte para sempre)."""
    if not os.path.isfile(CLUB_JSON):
        sys.exit(
            f"clip.py: {CLUB_JSON} não existe. É um ficheiro da branch `data`: "
            "`git checkout origin/data -- data/club.json`."
        )
    with open(CLUB_JSON, encoding="utf-8") as f:
        club = json.load(f)
    n = 2 ** ZOOM
    xy = []
    for x, y, _mask in club["squares"]:
        lon = (x + 0.5) / n * 360.0 - 180.0
        lat = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * (y + 0.5) / n))))
        xy.append((lon, lat))
    return points(xy)  # array de Point, para STRtree.query(predicate="dwithin")


def _poda_grid_totals(cc, mantidos):
    if not os.path.isfile(GRID_TOTALS):
        return
    with open(GRID_TOTALS, encoding="utf-8") as f:
        gt = json.load(f)
    chave = f"by_municipio_{cc.lower()}"
    bloco = gt.get(chave)
    if not bloco:
        return
    antes = len(bloco)
    gt[chave] = {k: v for k, v in bloco.items() if k in mantidos}
    with open(GRID_TOTALS, "w", encoding="utf-8") as f:
        json.dump(gt, f, ensure_ascii=False, separators=(",", ":"))
    print(f"  grid_totals.json[{chave}]: {antes} -> {len(gt[chave])} municípios")


def clip_pais(cc, pts):
    path = os.path.join(FOREIGN_MUNI, f"{cc}.geojson")
    if not os.path.isfile(path):
        print(f"  {cc}: sem {path}, ignorado")
        return
    with open(path, encoding="utf-8") as f:
        fc = json.load(f)
    feats = fc["features"]
    names = [ft["properties"]["region"] for ft in feats]
    geoms = [_clean(shape(ft["geometry"])) for ft in feats]

    # municípios a <= BUFFER_KM de algum square capturado. STRtree.query com
    # predicate="dwithin" faz isto vectorizado (não um buffer de 10 mil pontos).
    tree = STRtree(geoms)
    _pt_idx, muni_idx = tree.query(pts, predicate="dwithin",
                                   distance=BUFFER_KM * DEG_PER_KM)
    keep = sorted(set(int(i) for i in muni_idx))
    if not keep:
        print(f"  {cc}: 0 municípios dentro do buffer, NÃO recortado (ficaria vazio)")
        return
    mantidos = {names[i] for i in keep}

    sub = {"type": "FeatureCollection", "features": [feats[i] for i in keep]}
    body = json.dumps(sub, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    antes_kb = os.path.getsize(path) / 1024
    with open(path, "wb") as f:
        f.write(body)
    print(f"  {cc}: {len(feats)} -> {len(keep)} municípios (a {BUFFER_KM} km de "
          f"um square capturado)  {antes_kb:.0f} KB -> {len(body)/1024:.0f} KB")
    _poda_grid_totals(cc, mantidos)


def main(paises):
    if not paises:
        paises = sorted(
            os.path.splitext(f)[0] for f in os.listdir(FOREIGN_MUNI)
            if f.endswith(".geojson")
        )
    print(f"clip: {BUFFER_KM} km à volta dos squares de "
          f"{os.path.relpath(CLUB_JSON, REPO)}")
    pts = _pontos_capturados()
    for cc in paises:
        clip_pais(cc.upper(), pts)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("paises", nargs="*", help="códigos de país (default: todos)")
    a = ap.parse_args()
    main(a.paises)

"""One-off: calcula o total de tiles (zoom14/17) que existem em cada concelho/
distrito/país de Portugal, usando o MESMO critério de atribuição do classify.py
(centro do tile, STRtree "within" + fallback de buffer costeiro + nearest).

Corre uma vez, commita o output (pipeline/refdata/grid_totals.json). O pipeline.py
NUNCA recalcula isto — só conta capturados contra estes totais estáticos.

Uso: py compute_grid_totals.py
"""
import json
import os
import sys
from datetime import date

from shapely.geometry import shape, Point
from shapely.prepared import prep

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from kml_parse import lonlat_to_tile, tile_center
from classify import Classifier

HERE = os.path.dirname(os.path.abspath(__file__))
REFDATA_DIR = os.path.join(HERE, "refdata")
ZOOMS = [14, 17]


def candidate_cells_for_geom(geom, zoom):
    """Todas as (x, y) cuja bbox de tile intersecta a bbox do polígono, com
    margem de 1 tile — sobre-inclui (será filtrado por classify() a seguir),
    mas nunca omite uma célula real."""
    minlon, minlat, maxlon, maxlat = geom.bounds
    x0, y1 = lonlat_to_tile(minlon, minlat, zoom)
    x1, y0 = lonlat_to_tile(maxlon, maxlat, zoom)
    xlo, xhi = min(x0, x1) - 1, max(x0, x1) + 1
    ylo, yhi = min(y0, y1) - 1, max(y0, y1) + 1
    for x in range(xlo, xhi + 1):
        for y in range(ylo, yhi + 1):
            yield x, y


def main():
    classifier = Classifier(
        os.path.join(REFDATA_DIR, "distritos_pt.geojson"),
        os.path.join(REFDATA_DIR, "concelhos_pt.geojson"),
    )

    result = {
        "generated": date.today().isoformat(),
        "method": "tile-center-in-polygon (classify.py: STRtree within + buffer 0.05deg + nearest fallback)",
        "by_concelho": {},
        "by_distrito": {},
        "country_pt": {},
    }

    for zoom in ZOOMS:
        print(f"--- zoom {zoom} ---", file=sys.stderr)

        # candidatos = união das bboxes de todos os concelhos, deduplicada —
        # evita varrer o mar entre Madeira/Açores/continente.
        candidates = set()
        for geom in classifier.concelhos.geoms:
            candidates.update(candidate_cells_for_geom(geom, zoom))
        print(f"células candidatas: {len(candidates)}", file=sys.stderr)

        by_concelho = {}
        by_distrito = {}
        total_pt = 0
        done = 0
        for x, y in candidates:
            cx, cy = tile_center(x, y, zoom)
            info = classifier.classify(cx, cy)
            if info["in_portugal"]:
                total_pt += 1
                by_concelho[info["concelho"]] = by_concelho.get(info["concelho"], 0) + 1
                by_distrito[info["district"]] = by_distrito.get(info["district"], 0) + 1

            done += 1
            if done % 200_000 == 0:
                print(f"  {done}/{len(candidates)}", file=sys.stderr)

        result["country_pt"][f"z{zoom}"] = total_pt
        for name, count in by_concelho.items():
            result["by_concelho"].setdefault(name, {})[f"z{zoom}"] = count
        for name, count in by_distrito.items():
            result["by_distrito"].setdefault(name, {})[f"z{zoom}"] = count

        print(f"zoom {zoom}: total PT = {total_pt}", file=sys.stderr)

    out_path = os.path.join(REFDATA_DIR, "grid_totals.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"escrito: {out_path}")

    # validação obrigatória — Rio Maior tem de bater certo com os números já confirmados
    # (78/4882: recalculado com a MESMA fonte GADM que o classify.py usa em produção —
    # o valor histórico "4881" vinha de uma fronteira OSM/Overpass ad-hoc, fonte diferente
    # da que classifica os squares capturados; ver discussão no chat de 2026-07-19)
    rm = result["by_concelho"].get("Rio Maior", {})
    print(f"Rio Maior: z14={rm.get('z14')} (esperado 78), z17={rm.get('z17')} (esperado 4882)")
    assert rm.get("z14") == 78, f"Rio Maior z14 devia ser 78, é {rm.get('z14')}"
    assert rm.get("z17") == 4882, f"Rio Maior z17 devia ser 4882, é {rm.get('z17')}"
    print("validação Rio Maior: OK")

    all_concelho_names = {f["properties"]["NAME_2"] for f in json.load(
        open(os.path.join(REFDATA_DIR, "concelhos_pt.geojson"), encoding="utf-8")
    )["features"]}
    missing = all_concelho_names - set(result["by_concelho"].keys())
    assert not missing, f"concelhos sem total nenhum (bug de nomes?): {missing}"
    assert len(result["by_concelho"]) == 308, f"esperados 308 concelhos, há {len(result['by_concelho'])}"
    print(f"validação 308 concelhos: OK")


if __name__ == "__main__":
    main()

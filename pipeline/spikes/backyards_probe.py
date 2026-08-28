"""Spike: o que é REALMENTE a camada `backyards`?

Hipóteses em jogo:
  (A) contagem de squares fechados fora do yard principal
  (B) contagem de CLUSTERS secundários (não de squares)
  (C) contagem total de clusters (incluindo o principal)

Mede-se em vez de adivinhar: descodifica a geometria de `yard` e `backyards`,
conta clusters disjuntos e squares de cada um, e vê se se sobrepõem.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from concurrent.futures import ThreadPoolExecutor
from shapely.ops import unary_union

from tiles_fetch import (
    fetch_tile, discover_coverage, _project_geometry, FETCH_CONCURRENCY,
)
from kml_parse import reconstruct_squares

UID = os.environ["SQUADRATS_UID"]  # firebase UID do atleta a analisar
LAYERS = ["yard", "backyards", "yardinho", "backyardinhos"]
FETCH_ZOOM = 12


def scan_layers(uid):
    coarse = discover_coverage(uid)
    factor = 2 ** (FETCH_ZOOM - 10)
    candidates = [
        (cx * factor + dx, cy * factor + dy)
        for cx, cy in coarse
        for dx in range(factor) for dy in range(factor)
    ]
    print(f"a buscar {len(candidates)} tiles z{FETCH_ZOOM}...")

    polys = {name: [] for name in LAYERS}
    sizes = {}
    with ThreadPoolExecutor(max_workers=FETCH_CONCURRENCY) as pool:
        futures = {
            pool.submit(fetch_tile, uid, FETCH_ZOOM, x, y): (x, y)
            for x, y in candidates
        }
        for fut, (x, y) in futures.items():
            decoded = fut.result()
            if decoded is None:
                continue
            for name in LAYERS:
                if name not in decoded:
                    continue
                layer = decoded[name]
                for feat in layer["features"]:
                    if feat["properties"].get("size") is not None:
                        sizes.setdefault(name, feat["properties"]["size"])
                    polys[name].extend(
                        _project_geometry(feat["geometry"], FETCH_ZOOM, x, y, layer["extent"])
                    )
    return polys, sizes


def analisa(nome, geoms, size, zoom):
    if not geoms:
        print(f"\n{nome}: sem geometria (size reportado={size})")
        return None
    merged = unary_union(geoms)
    parts = list(merged.geoms) if merged.geom_type == "MultiPolygon" else [merged]
    squares = reconstruct_squares(merged, zoom)
    print(f"\n{nome} (size do servidor = {size}):")
    print(f"  clusters disjuntos : {len(parts)}")
    print(f"  squares (zoom{zoom}) : {len(squares)}")
    print(f"  -> size == clusters? {size == len(parts)}")
    print(f"  -> size == squares?  {size == len(squares)}")
    return merged


if __name__ == "__main__":
    polys, sizes = scan_layers(UID)

    yard = analisa("yard", polys["yard"], sizes.get("yard"), 14)
    backyards = analisa("backyards", polys["backyards"], sizes.get("backyards"), 14)
    yardinho = analisa("yardinho", polys["yardinho"], sizes.get("yardinho"), 17)
    backyardinhos = analisa("backyardinhos", polys["backyardinhos"], sizes.get("backyardinhos"), 17)

    if yard is not None and backyards is not None:
        inter = yard.intersection(backyards)
        print("\n--- yard vs backyards ---")
        print(f"  sobrepõem-se?          {not inter.is_empty}")
        print(f"  área da interseção     {inter.area:.10f}")
        print(f"  área yard              {yard.area:.10f}")
        print(f"  yard contido em backy? {backyards.contains(yard)}")

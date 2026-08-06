"""Onde estão os backyards secundários e que tamanho têm."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from concurrent.futures import ThreadPoolExecutor
from shapely.ops import unary_union

from tiles_fetch import fetch_tile, discover_coverage, _project_geometry, FETCH_CONCURRENCY
from kml_parse import reconstruct_squares

UID = "PjHY1RpxbmgMrQG3ITdTeDa7t6M2"
FETCH_ZOOM = 12

coarse = discover_coverage(UID)
factor = 2 ** (FETCH_ZOOM - 10)
candidates = [(cx * factor + dx, cy * factor + dy)
              for cx, cy in coarse for dx in range(factor) for dy in range(factor)]

polys = []
with ThreadPoolExecutor(max_workers=FETCH_CONCURRENCY) as pool:
    futures = {pool.submit(fetch_tile, UID, FETCH_ZOOM, x, y): (x, y)
               for x, y in candidates}
    for fut, (x, y) in futures.items():
        d = fut.result()
        if d and "backyards" in d:
            layer = d["backyards"]
            for feat in layer["features"]:
                polys.extend(_project_geometry(feat["geometry"], FETCH_ZOOM, x, y, layer["extent"]))

merged = unary_union(polys)
parts = list(merged.geoms) if merged.geom_type == "MultiPolygon" else [merged]
info = []
for p in parts:
    n = len(reconstruct_squares(p, 14))
    c = p.centroid
    info.append((n, c.y, c.x))
info.sort(reverse=True)

print(f"\n{len(parts)} clusters, {sum(i[0] for i in info)} squares no total\n")
print(f"{'squares':>8}  {'lat':>10}  {'lon':>10}   mapa")
for n, lat, lon in info:
    print(f"{n:>8}  {lat:>10.4f}  {lon:>10.4f}   https://www.google.com/maps?q={lat:.4f},{lon:.4f}")

"""One-off: calcula adjacência (concelhos/distritos/províncias ES que partilham
fronteira) e aplica greedy coloring sobre a paleta categórica do index.html, para
vizinhos nunca partilharem cor. Corre uma vez, commita o output
(data/adjacency.json). Nunca recalculado pelo pipeline.

Uso: py compute_adjacency.py
"""
import json
import os

from shapely.geometry import shape
from shapely.strtree import STRtree

HERE = os.path.dirname(os.path.abspath(__file__))
REFDATA_DIR = os.path.join(HERE, "refdata")
DATA_DIR = os.path.join(os.path.dirname(HERE), "data")

TOUCH_BUFFER_DEG = 0.001  # tolerância p/ micro-gaps deixados pela limpeza anti-sliver

# tem de ser EXATAMENTE a mesma lista (e ordem) do CATEGORY_PALETTE em index.html
CATEGORY_PALETTE = [
    "#e6194b", "#3cb44b", "#ffe119", "#4363d8", "#f58231", "#911eb4", "#46f0f0",
    "#f032e6", "#bcf60c", "#fabebe", "#008080", "#e6beff", "#9a6324", "#fffac8",
    "#aaffc3", "#ffd8b1", "#42d4f4", "#f5c9b0", "#ff69b4", "#a9a9a9",
]


def build_adjacency(names, geoms):
    buffered = [g.buffer(TOUCH_BUFFER_DEG) for g in geoms]
    tree = STRtree(buffered)
    adjacency = {name: set() for name in names}
    for i, geom in enumerate(buffered):
        for j in tree.query(geom, predicate="intersects"):
            if j == i:
                continue
            adjacency[names[i]].add(names[j])
            adjacency[names[j]].add(names[i])
    return {name: sorted(neighbors) for name, neighbors in adjacency.items()}


def greedy_color(names, adjacency):
    order = sorted(names, key=lambda n: -len(adjacency[n]))
    color_of = {}
    for name in order:
        used = {color_of[nb] for nb in adjacency[name] if nb in color_of}
        c = 0
        while c in used:
            c += 1
        color_of[name] = c
    max_color = max(color_of.values(), default=0)
    if max_color >= len(CATEGORY_PALETTE):
        raise RuntimeError(
            f"greedy coloring precisou de {max_color + 1} cores, só há {len(CATEGORY_PALETTE)} na paleta"
        )
    return color_of


def process(label, geojson_path, name_prop):
    with open(geojson_path, encoding="utf-8") as f:
        fc = json.load(f)
    names = [feat["properties"][name_prop] for feat in fc["features"]]
    geoms = [shape(feat["geometry"]) for feat in fc["features"]]

    adjacency = build_adjacency(names, geoms)
    colors = greedy_color(names, adjacency)

    max_used = max(colors.values())
    print(f"{label}: {len(names)} regiões, {max_used + 1} cores usadas (de {len(CATEGORY_PALETTE)})")

    conflicts = [
        (n, nb) for n in names for nb in adjacency[n]
        if colors[n] == colors[nb]
    ]
    assert not conflicts, f"{label}: vizinhos com a mesma cor: {conflicts}"

    return {
        name: {"neighbors": adjacency[name], "colorIndex": colors[name]}
        for name in names
    }


def main():
    result = {
        "palette": CATEGORY_PALETTE,
        "concelhos": process("concelhos", os.path.join(REFDATA_DIR, "concelhos_pt.geojson"), "NAME_2"),
        "distritos": process("distritos", os.path.join(REFDATA_DIR, "distritos_pt.geojson"), "district"),
        "provincias_es": process("provincias_es", os.path.join(REFDATA_DIR, "foreign", "ES.geojson"), "region"),
    }

    out_path = os.path.join(DATA_DIR, "adjacency.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, separators=(",", ":"))
    print(f"escrito: {out_path}")

    # validação explícita pedida: Rio Maior / Caldas da Rainha não podem ter a mesma cor
    rm = result["concelhos"]["Rio Maior"]["colorIndex"]
    cr = result["concelhos"]["Caldas da Rainha"]["colorIndex"]
    print(f"Rio Maior color={rm}, Caldas da Rainha color={cr}, "
          f"são vizinhos: {'Caldas da Rainha' in result['concelhos']['Rio Maior']['neighbors']}")
    assert rm != cr, "Rio Maior e Caldas da Rainha ficaram com a mesma cor!"
    print("validação Rio Maior/Caldas da Rainha: OK")


if __name__ == "__main__":
    main()

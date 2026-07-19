"""Pipeline: KML exportado do squadrats.com -> JSON classificado por concelho/distrito.

Uso: py pipeline.py <caminho.kml> <pasta_saida>
"""
import argparse
import json
import os
import sys

from kml_parse import parse_kml_geometries, reconstruct_squares, ZOOM_BY_TYPE
from classify import Classifier

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(os.path.dirname(HERE), "data")
REFDATA_DIR = os.path.join(HERE, "refdata")  # fronteiras não-simplificadas, só para classificação


def run(kml_path, out_dir):
    classifier = Classifier(
        os.path.join(REFDATA_DIR, "distritos_pt.geojson"),
        os.path.join(REFDATA_DIR, "concelhos_pt.geojson"),
    )

    geoms = parse_kml_geometries(kml_path)

    summary = {}
    for type_name, zoom in ZOOM_BY_TYPE.items():
        if type_name not in geoms:
            print(f"aviso: placemark '{type_name}' não encontrado no KML", file=sys.stderr)
            continue

        declared_size, geom = geoms[type_name]
        squares = reconstruct_squares(geom, zoom)

        if declared_size is not None and len(squares) != declared_size:
            print(
                f"aviso: {type_name} — reconstruídos {len(squares)}, "
                f"declarados {declared_size} no KML (diferença pode indicar simplificação/geometria degenerada)",
                file=sys.stderr,
            )

        out = []
        for x, y, lon, lat in squares:
            info = classifier.classify(lon, lat)
            out.append({
                "x": x, "y": y, "zoom": zoom,
                "lon": round(lon, 6), "lat": round(lat, 6),
                **info,
            })

        out_path = os.path.join(out_dir, f"tile_info_{type_name}.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, separators=(",", ":"))

        summary[type_name] = {
            "total": len(out),
            "in_portugal": sum(1 for s in out if s["in_portugal"]),
        }
        print(f"{type_name}: {len(out)} squares -> {out_path}")

    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("kml_path")
    parser.add_argument("out_dir", nargs="?", default=DATA_DIR)
    args = parser.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)
    result = run(args.kml_path, args.out_dir)
    print(json.dumps(result, indent=2, ensure_ascii=False))

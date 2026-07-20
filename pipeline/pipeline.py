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

    # falhar alto e cedo: um KML sem a camada "squadrats" é quase certamente um
    # export incompleto/de teste, não um export real — nunca deve gerar JSON
    # vazio/parcial que silenciosamente apague os dados reais do site.
    if "squadrats" not in geoms:
        raise RuntimeError(
            f"KML '{kml_path}' não tem a camada 'squadrats' — export incompleto ou "
            f"ficheiro errado. Placemarks encontrados: {list(geoms.keys()) or '(nenhum)'}. "
            f"A abortar sem tocar em ficheiros de saída."
        )

    with open(os.path.join(REFDATA_DIR, "grid_totals.json"), encoding="utf-8") as f:
        grid_totals = json.load(f)

    zkey_by_type = {"squadrats": "z14", "squadratinhos": "z17"}

    summary = {}
    stats = {"by_concelho": {}, "by_distrito": {}, "country_pt": {}, "country_es": {}}

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
        by_concelho_captured, by_distrito_captured = {}, {}
        pt_captured = es_captured = 0
        for x, y, lon, lat in squares:
            info = classifier.classify(lon, lat)
            out.append({
                "x": x, "y": y, "zoom": zoom,
                "lon": round(lon, 6), "lat": round(lat, 6),
                **info,
            })
            if info["in_portugal"]:
                pt_captured += 1
                by_concelho_captured[info["concelho"]] = by_concelho_captured.get(info["concelho"], 0) + 1
                by_distrito_captured[info["district"]] = by_distrito_captured.get(info["district"], 0) + 1
            else:
                es_captured += 1

        out_path = os.path.join(out_dir, f"tile_info_{type_name}.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, separators=(",", ":"))

        summary[type_name] = {
            "total": len(out),
            "in_portugal": pt_captured,
        }
        print(f"{type_name}: {len(out)} squares -> {out_path}")

        zkey = zkey_by_type[type_name]

        def pct(captured, total):
            return round(100.0 * captured / total, 2) if total else 0.0

        for name, total_info in grid_totals["by_concelho"].items():
            total = total_info.get(zkey, 0)
            captured = by_concelho_captured.get(name, 0)
            stats["by_concelho"].setdefault(name, {})[zkey] = {
                "captured": captured, "total": total, "pct": pct(captured, total),
            }
        for name, total_info in grid_totals["by_distrito"].items():
            total = total_info.get(zkey, 0)
            captured = by_distrito_captured.get(name, 0)
            stats["by_distrito"].setdefault(name, {})[zkey] = {
                "captured": captured, "total": total, "pct": pct(captured, total),
            }

        pt_total = grid_totals["country_pt"].get(zkey, 0)
        stats["country_pt"][zkey] = {
            "captured": pt_captured, "total": pt_total, "pct": pct(pt_captured, pt_total),
        }
        stats["country_es"][zkey] = {"captured": es_captured, "total": None, "pct": None}

    stats_path = os.path.join(out_dir, "stats.json")
    with open(stats_path, "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, separators=(",", ":"))
    print(f"stats -> {stats_path}")

    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("kml_path")
    parser.add_argument("out_dir", nargs="?", default=DATA_DIR)
    args = parser.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)
    result = run(args.kml_path, args.out_dir)
    print(json.dumps(result, indent=2, ensure_ascii=False))

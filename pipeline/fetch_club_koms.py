"""Totais simples (sem breakdown por concelho/distrito) para todos os atletas
do clube — publica data/squadrats.json, consumido pelo club-koms da mesma
forma que o prs.json. Repos não acoplados: aqui só se escreve o ficheiro,
não se toca no club-koms.

Falha alto se algum UID devolver 500 ou se squadrats/squadratinhos não
baterem com o `size` do servidor — nunca publica o último valor bom em
silêncio (ver tiles_fetch.py).

Uso: py fetch_club_koms.py [pasta_saida]
"""
import argparse
import datetime
import json
import os

from kml_parse import reconstruct_squares
from tiles_fetch import GEOMETRY_LAYERS, scan_athlete

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(os.path.dirname(HERE), "data")

ATHLETES = {
    "Zé": "PjHY1RpxbmgMrQG3ITdTeDa7t6M2",
    "Xeira": "yIVPnafX3WcNbDt5MKWqEZMqUD42",
    "Carolina": "ZF81dc6PXFQm3iEfyNFMsUPlSHz2",
    "Inês S.": "C4bIQgAqI7SlSo7SPsudWM4LSwq2",
    "Pedro": "zrId7ywBfCQPt28q5VAzpva01ST2",
}


def fetch_totals(uid):
    geometries, counts = scan_athlete(uid)

    totals = dict(counts)
    for name in GEOMETRY_LAYERS:
        if name not in geometries:
            raise RuntimeError(f"UID '{uid}': camada '{name}' em falta no varrimento")
        declared_size, geom = geometries[name]
        zoom = GEOMETRY_LAYERS[name]
        reconstructed = len(reconstruct_squares(geom, zoom))
        if declared_size is None or reconstructed != declared_size:
            raise RuntimeError(
                f"UID '{uid}': {name} — reconstruídos {reconstructed}, "
                f"servidor diz {declared_size}. Varrimento incompleto ou bug de geometria — "
                f"a abortar sem publicar squadrats.json."
            )
        totals[name] = declared_size

    return totals


def main(out_dir):
    result = {
        "atualizado": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "atletas": {},
    }
    for name, uid in ATHLETES.items():
        print(f"a varrer {name} ({uid})...")
        result["atletas"][name] = fetch_totals(uid)
        print(f"{name}: {result['atletas'][name]}")

    out_path = os.path.join(out_dir, "squadrats.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"escrito: {out_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("out_dir", nargs="?", default=DATA_DIR)
    args = parser.parse_args()
    os.makedirs(args.out_dir, exist_ok=True)
    main(args.out_dir)

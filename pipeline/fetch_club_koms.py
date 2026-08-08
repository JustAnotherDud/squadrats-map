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

import daily_gains
from kml_parse import reconstruct_squares
from tiles_fetch import GEOMETRY_LAYERS, scan_athlete

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_DIR = os.path.dirname(HERE)
DATA_DIR = os.path.join(REPO_DIR, "data")

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
            # camada sem cobertura: o scan chegou aqui sem levantar erro, e uma
            # falha real (500, geometria inválida) já teria abortado antes disto.
            # Mas isto também é o que um UID válido mas ERRADO (conta trocada,
            # sem actividade) produz — 204 em todos os tiles, sem excepção — e
            # o servidor não distingue os dois casos. Por isso: zero continua a
            # ser aceite como resultado (não aborta o run todo), mas nunca em
            # silêncio — fica visível para confirmares o UID à mão.
            print(f"ATENÇÃO: UID '{uid}' devolveu 0 squares em '{name}' — confirma se o UID está certo (squadrats.com/map/{uid}/17)")
            totals[name] = 0
            continue
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

    # baseline = ultimo_total guardado no próprio daily_gains.json (sem git,
    # por causa do checkout shallow no CI — ver daily_gains.py)
    delta = daily_gains.actualizar(out_dir, result["atletas"])
    if delta:
        print(f"ganhos desde a última corrida: {delta}")
    else:
        print("ganhos desde a última corrida: nenhum")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("out_dir", nargs="?", default=DATA_DIR)
    args = parser.parse_args()
    os.makedirs(args.out_dir, exist_ok=True)
    main(args.out_dir)

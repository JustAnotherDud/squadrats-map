"""Corre os três consumidores no mesmo processo, para cada atleta ser varrido
uma vez só.

Em passos separados do workflow, cada script varria os mesmos UIDs de novo: o
primeiro atleta três vezes por run, dois deles duas. Eram ~1200 pedidos de
tiles em duplicado, sem ganho nenhum — e o servidor da Squadrats não é uma API
pública, por isso a metade que se poupa conta mais do que os minutos.

A cache vive no `tiles_fetch.scan_athlete`; aqui só se garante que os três
correm no mesmo processo.

Uso: py run_all.py [pasta_saida]
"""
import argparse
import os
import sys
import time

import classify_club
import fetch_club_koms
import fetch_club_squares
import pipeline
from athletes import JOSE_UID

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(os.path.dirname(HERE), "data")


def main(out_dir):
    inicio = time.time()
    passos = [
        ("mapa detalhado", lambda: pipeline.run_from_tiles(JOSE_UID, out_dir)),
        ("totais do clube", lambda: fetch_club_koms.main(out_dir)),
        ("squares do club", lambda: fetch_club_squares.main(out_dir)),
        # depende do club.json escrito no passo anterior (mesma corrida) —
        # não volta a varrer o Squadrats, só classifica os squares já ali
        ("regiões do club", lambda: classify_club.main(out_dir)),
    ]
    for nome, fn in passos:
        t = time.time()
        print(f"\n=== {nome} ===", flush=True)
        fn()
        print(f"--- {nome}: {time.time() - t:.0f}s", flush=True)

    print(f"\ntotal: {time.time() - inicio:.0f}s")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("out_dir", nargs="?", default=DATA_DIR)
    args = parser.parse_args()
    os.makedirs(args.out_dir, exist_ok=True)
    sys.exit(main(args.out_dir))

"""Orquestrador do pipeline: corre todos os passos no mesmo processo, para
cada atleta ser varrido do Squadrats uma vez só.

Os três que tocam a rede (build_mapa, fetch_club_totais, fetch_club_squares)
partilhavam os mesmos UIDs; em passos separados do workflow cada um varria-os
de novo — ~1200 pedidos de tiles em duplicado por run, sem ganho, contra um
servidor que não é API pública. A cache vive no `tiles_fetch.scan_athlete`;
aqui garante-se que correm no mesmo processo. Os passos seguintes (classify,
eventos, regiões, ganhos, perfis) não tocam a rede — só juntam o que os
primeiros produziram.

Uso: py run_all.py [pasta_saida]
"""
import argparse
import os
import sys
import time

import append_events
import append_gains_regioes
import append_regioes
import build_mapa
import build_profiles
import classify_club
import fetch_club_squares
import fetch_club_totais
from athletes import JOSE_UID

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(os.path.dirname(HERE), "data")


def main(out_dir):
    inicio = time.time()
    passos = [
        ("mapa detalhado", lambda: build_mapa.run_from_tiles(JOSE_UID, out_dir)),
        ("totais do clube", lambda: fetch_club_totais.main(out_dir)),
        ("squares do club", lambda: fetch_club_squares.main(out_dir)),
        # depende do club.json escrito no passo anterior (mesma corrida) —
        # não volta a varrer o Squadrats, só classifica os squares já ali
        ("regiões do club", lambda: classify_club.main(out_dir)),
        # compara o club_regioes.json anterior (origin/data) com o novo e faz
        # append dos eventos novos a events.json — idempotente entre runs do dia
        ("eventos do club", lambda: append_events.main(out_dir)),
        # páginas por região: ranking/totais/vizinhos do snapshot novo +
        # append dos dias novos à timeline (data/regioes/<key>.json)
        ("regiões (páginas)", lambda: append_regioes.main(out_dir)),
        # diff club_regioes.json (ontem vs hoje) -> ganhos de squadratinhos
        # por concelho/distrito, por dia (data/gains_regioes.json). Sem
        # classificação nova — o breakdown já está no club_regioes.json
        ("ganhos por região", lambda: append_gains_regioes.main(out_dir)),
        # junta squadrats.json + club.json + club_regioes.json + daily_gains.json
        # + gains_regioes.json + stats.json num perfil por atleta — sem rede
        ("perfis por atleta", lambda: build_profiles.main(out_dir)),
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

"""Totais simples (sem breakdown por concelho/distrito) para todos os atletas
do clube — publica data/squadrats.json, consumido pelo folha-do-clube da mesma
forma que o prs.json. Repos não acoplados: aqui só se escreve o ficheiro,
não se toca no folha-do-clube.

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
from athletes import ATHLETES, known_squadratinhos
from kml_parse import reconstruct_squares
from tiles_fetch import GEOMETRY_LAYERS, scan_athlete

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_DIR = os.path.dirname(HERE)
DATA_DIR = os.path.join(REPO_DIR, "data")


def fetch_totals(uid, known=None):
    """Devolve None se o probe de tiles_fetch.py confirmar que este UID não
    mudou — o chamador tem de reaproveitar a entrada anterior."""
    resultado = scan_athlete(uid, known_squadratinhos=known)
    if resultado is None:
        return None
    geometries, counts = resultado

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
    # capturado UMA vez, no início — nunca recalculado depois do varrimento
    # dos 5 atletas, para o "dia" do daily_gains.py nunca poder virar a meio
    # de uma corrida lenta (ver discussão: uma corrida que atravessasse a
    # meia-noite UTC atribuiria TODOS os ganhos detectados, mesmo os de horas
    # antes, ao dia seguinte).
    inicio = datetime.datetime.now(datetime.timezone.utc)
    result = {
        "atualizado": inicio.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "atletas": {},
    }

    # totais/probe-tile já publicados (branch 'data', carregados no out_dir
    # antes desta corrida) — fonte do probe barato e do "reaproveitar" quando
    # ele confirma que nada mudou (ver tiles_fetch.py, athletes.py).
    known = known_squadratinhos(out_dir)
    anteriores = {}
    try:
        with open(os.path.join(out_dir, "squadrats.json"), encoding="utf-8") as f:
            anteriores = json.load(f).get("atletas", {})
    except (FileNotFoundError, json.JSONDecodeError):
        pass

    for name, uid in ATHLETES.items():
        print(f"a varrer {name} ({uid})...")
        totals = fetch_totals(uid, known.get(uid))
        if totals is None:
            totals = anteriores.get(name)
            if totals is None:
                # não devia acontecer: known só vem preenchido quando já há
                # uma entrada anterior para este nome no mesmo squadrats.json
                raise RuntimeError(
                    f"'{name}': probe disse 'sem alterações' mas não há publicação "
                    f"anterior para reaproveitar — inconsistência entre known_squadratinhos "
                    f"e o squadrats.json carregado."
                )
            print(f"{name}: sem alterações — a reaproveitar a publicação anterior")
        result["atletas"][name] = totals
        print(f"{name}: {result['atletas'][name]}")

    out_path = os.path.join(out_dir, "squadrats.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"escrito: {out_path}")

    # baseline = ultimo_total guardado no próprio daily_gains.json (sem git,
    # por causa do checkout shallow no CI — ver daily_gains.py). hoje_iso vem
    # do início da corrida (`inicio`), não de "agora" — ver comentário acima.
    delta = daily_gains.actualizar(out_dir, result["atletas"], hoje_iso=inicio.date().isoformat())
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

"""Lista única dos atletas do clube.

Antes desta extracção, os mesmos 5 nomes/UIDs viviam em triplicado
(fetch_club_koms.py, fetch_club_squares.py, run_all.py) — um UID trocado
por engano num só desses sítios só se notaria quando os totais não
batessem. Agora há uma fonte só.

fetch_club_squares.py depende da ORDEM de ATLETAS para atribuir os bits do
bitmask dos squares partilhados (bit 0 = primeiro atleta, e por aí fora) —
não reordenar sem regenerar o ficheiro de squares do club.
"""
import json
import os

ATHLETES = {
    "Zé": "PjHY1RpxbmgMrQG3ITdTeDa7t6M2",
    "Xeira": "yIVPnafX3WcNbDt5MKWqEZMqUD42",
    "Carolina": "ZF81dc6PXFQm3iEfyNFMsUPlSHz2",
    "Inês S.": "C4bIQgAqI7SlSo7SPsudWM4LSwq2",
    "Pedro": "zrId7ywBfCQPt28q5VAzpva01ST2",
}

# mesma ordem que ATHLETES (dict preserva ordem de inserção) — usada onde a
# ordem importa (bitmask em fetch_club_squares.py)
ATLETAS = list(ATHLETES.items())

JOSE_UID = ATHLETES["Zé"]


def known_squadratinhos(out_dir):
    """{uid: último total de squadratinhos publicado}, lido do squadrats.json
    já carregado no out_dir (branch 'data', ver fetch-map-data.yml) — fonte
    do probe barato de tiles_fetch.scan_athlete (2026-08-14).

    Squadratinhos (201m) é a grelha mais fina: capturar qualquer square novo
    nas outras 7 camadas (squadrats, yard/yardinho, übersquadrat/-inho,
    backyards/-inhos) implica sempre passar por um squadratinho ainda não
    visitado nesse mesmo sítio — nunca o contrário, porque estar dentro de um
    squadrat ainda não capturado significa estar também dentro de um
    squadratinho ainda não capturado (é a mesma presença física). Por isso
    esta única contagem chega para confirmar "nada mudou" nas 8 camadas.

    Ficheiro ausente/ilegível ou atleta sem entrada -> não entra no dict, e
    scan_athlete faz sempre o caminho completo para esse UID (comportamento
    anterior a esta optimização, sem risco de nunca actualizar por engano)."""
    path = os.path.join(out_dir, "squadrats.json")
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}
    return {
        ATHLETES[nome]: info["squadratinhos"]
        for nome, info in data.get("atletas", {}).items()
        if nome in ATHLETES and "squadratinhos" in info
    }

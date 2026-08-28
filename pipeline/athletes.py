"""Lista única dos atletas do clube.

Antes desta extracção, os mesmos nomes/UIDs viviam em triplicado
(fetch_club_koms.py, fetch_club_squares.py, run_all.py) — um UID trocado
por engano num só desses sítios só se notaria quando os totais não
batessem. Agora há uma fonte só.

Os dados (nome → firebase UID) vêm do env `ATHLETES_JSON`, não do código —
é informação de terceiros, não pertence a um repo público. No CI vem de um
secret (ver .github/workflows/fetch-map-data.yml); localmente, exportar à
mão:

    export ATHLETES_JSON='{"Nome A": "uid...", "Nome B": "uid..."}'

A ORDEM das entradas é contrato: fetch_club_squares.py atribui o bit N do
bitmask dos squares partilhados ao N-ésimo atleta (bit 0 = primeiro, e por
aí fora) e club.html assume a mesma ordem nas cores. Não reordenar sem
regenerar data/club.json.
"""
import json
import os

_raw = os.environ.get("ATHLETES_JSON", "").strip()
if not _raw:
    raise RuntimeError(
        "ATHLETES_JSON não definido. Esperado: JSON {nome: firebase_uid, ...}, "
        "na ordem que fixa os bits do bitmask (ver docstring). No CI vem de um "
        "secret; localmente exportar à mão."
    )
try:
    ATHLETES: dict[str, str] = json.loads(_raw)
except json.JSONDecodeError as e:
    raise RuntimeError(f"ATHLETES_JSON não é JSON válido: {e}") from e
if not ATHLETES:
    raise RuntimeError("ATHLETES_JSON está vazio.")

# mesma ordem que ATHLETES (o dict preserva a ordem de inserção do JSON) —
# usada onde a ordem importa (bitmask em fetch_club_squares.py, cores em
# club.html)
ATLETAS = list(ATHLETES.items())

# primeiro atleta na ordem = dono do mapa detalhado (run_all.py) — mesma
# convenção do bit 0
JOSE_UID = next(iter(ATHLETES.values()))


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

"""Lista única dos atletas do clube.

Antes desta extracção, os mesmos 5 nomes/UIDs viviam em triplicado
(fetch_club_koms.py, fetch_club_squares.py, run_all.py) — um UID trocado
por engano num só desses sítios só se notaria quando os totais não
batessem. Agora há uma fonte só.

fetch_club_squares.py depende da ORDEM de ATLETAS para atribuir os bits do
bitmask dos squares partilhados (bit 0 = primeiro atleta, e por aí fora) —
não reordenar sem regenerar o ficheiro de squares do club.
"""

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

"""Consigo reproduzir yard e übersquadrat a partir dos nossos squares?

Se sim, sabemos as regras e podemos calcular "o que falta para o próximo".
Se não, qualquer sugestão que déssemos seria inventada.

Gabarito: o servidor diz yard=90 / uber=6 (squadrats) e 480 / 13 (squadratinhos).
"""
import json, os, sys
from collections import deque

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(os.path.dirname(BASE), "data")

VIZINHOS4 = [(1, 0), (-1, 0), (0, 1), (0, -1)]


def carregar(nome):
    with open(os.path.join(DATA, f"tile_info_{nome}.json"), encoding="utf-8") as f:
        return {(t["x"], t["y"]) for t in json.load(f)}


def fechados(visitados):
    """Square fechado = visitado E com os 4 vizinhos cardinais visitados."""
    return {s for s in visitados
            if all((s[0] + dx, s[1] + dy) in visitados for dx, dy in VIZINHOS4)}


def clusters(conjunto):
    """Componentes 4-conexas."""
    porver, out = set(conjunto), []
    while porver:
        raiz = porver.pop()
        comp, fila = {raiz}, deque([raiz])
        while fila:
            x, y = fila.popleft()
            for dx, dy in VIZINHOS4:
                v = (x + dx, y + dy)
                if v in porver:
                    porver.remove(v)
                    comp.add(v)
                    fila.append(v)
        out.append(comp)
    return out


def maior_uber(visitados):
    """Maior N tal que existe um bloco NxN todo visitado. DP clássico:
    dp[x][y] = lado do maior quadrado cheio com canto inferior-direito em (x,y)."""
    dp, melhor, canto = {}, 0, None
    for (x, y) in sorted(visitados):
        if (x, y) not in visitados:
            continue
        v = 1 + min(dp.get((x - 1, y), 0), dp.get((x, y - 1), 0), dp.get((x - 1, y - 1), 0))
        dp[(x, y)] = v
        if v > melhor:
            melhor, canto = v, (x, y)
    return melhor, canto


def verificar(nome, esperado_yard, esperado_uber):
    visitados = carregar(nome)
    f = fechados(visitados)
    cs = clusters(f)
    maior = max((len(c) for c in cs), default=0)
    uber, canto = maior_uber(visitados)

    print(f"\n=== {nome} ({len(visitados)} squares visitados) ===")
    print(f"  fechados         : {len(f)} em {len(cs)} clusters")
    print(f"  maior cluster    : {maior:>5}   servidor diz yard = {esperado_yard}   {'OK' if maior == esperado_yard else 'DIVERGE'}")
    print(f"  nº de clusters   : {len(cs):>5}   servidor diz backyards = ?")
    print(f"  maior NxN        : {uber:>5}   servidor diz uber = {esperado_uber}   {'OK' if uber == esperado_uber else 'DIVERGE'}")
    return maior == esperado_yard and uber == esperado_uber


if __name__ == "__main__":
    ok1 = verificar("squadrats", 90, 6)
    ok2 = verificar("squadratinhos", 480, 13)
    print("\n" + ("REGRAS REPRODUZIDAS — dá para calcular sugestões."
                  if ok1 and ok2 else
                  "DIVERGE — não sabemos as regras, não vale a pena sugerir nada."))

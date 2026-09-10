"""ATHLETES_JSON tem de existir antes de importar qualquer módulo que puxe
`atletas` (classify_club, fetch_*, run_all): sem ele, atletas.py rebenta no
import. Os nomes/UIDs aqui são fictícios, os testes que os usam passam a
lista de atletas à função, não dependem deste valor.
"""
import os

os.environ.setdefault(
    "ATHLETES_JSON", '{"A": "uid-a", "B": "uid-b", "C": "uid-c"}'
)

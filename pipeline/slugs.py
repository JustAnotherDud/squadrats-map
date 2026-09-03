"""Slug de um nome de atleta -> segmento de URL do perfil (/atletas/<slug>.html).

Fonte única, partilhada por `build_profiles.py` (escreve data/atletas/<slug>.json)
e `gen_profile_stubs.py` (escreve atletas/<slug>.html). Se as duas divergissem,
o stub HTML apontava para um JSON que não existe.

Regras: sem acentos, minúsculas, tudo o que não é [a-z0-9] vira "-", sem "-"
repetido nem nas pontas. "Zé" -> "ze"; "Inês S." -> "ines-s".
"""
import re
import unicodedata


def slugify(nome: str) -> str:
    sem_acento = (
        unicodedata.normalize("NFKD", nome)
        .encode("ascii", "ignore")
        .decode("ascii")
    )
    s = re.sub(r"[^a-z0-9]+", "-", sem_acento.lower()).strip("-")
    return s or "atleta"


def slug_map(nomes) -> dict:
    """{nome: slug}, a abortar se dois nomes colidirem no mesmo slug — mais
    vale falhar o build do que servir o perfil de A no URL de B."""
    fora = {}
    vistos = {}
    for nome in nomes:
        s = slugify(nome)
        if s in vistos:
            raise RuntimeError(
                f"colisão de slug '{s}': '{vistos[s]}' e '{nome}'. "
                f"Desambiguar um dos nomes em ATHLETES_JSON."
            )
        vistos[s] = nome
        fora[nome] = s
    return fora

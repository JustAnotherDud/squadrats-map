"""Testes do regioes.centro_de: as chaves de club_regioes.uniao.centros têm de
bater certo com o centroDe() do club.html, senão o botão "ver no mapa" da
página de lugar salta para lado nenhum. Este teste fixa esse contrato.

Correr: py -m pytest
"""
import regioes

CENTROS = {
    "distrito|Leiria": [62197, 49905],
    "concelho|Peniche": [62130, 49928],
    "region|es|Valencia": [65407, 49869],
    "municipio|es|València": [65500, 49850],
}
SNAP = {"uniao": {"centros": CENTROS}}


def test_pt_distrito_e_concelho():
    assert regioes.centro_de(SNAP, "PT", "distrito", "Leiria") == [62197, 49905]
    assert regioes.centro_de(SNAP, "PT", "concelho", "Peniche") == [62130, 49928]


def test_estrangeiro_regiao_e_zona():
    assert regioes.centro_de(SNAP, "ES", "regiao", "Valencia") == [65407, 49869]
    assert regioes.centro_de(SNAP, "ES", "zona", "València") == [65500, 49850]


def test_pais_nunca_tem_centro():
    assert regioes.centro_de(SNAP, "PT", "pais", "Portugal") is None


def test_lugar_sem_entrada_devolve_none():
    assert regioes.centro_de(SNAP, "PT", "concelho", "Óbidos") is None
    assert regioes.centro_de({"uniao": {}}, "PT", "distrito", "Leiria") is None

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


# --- fronteira_de: a feature certa do data/*.geojson, pelo nome ---

def test_fronteira_pt_concelho_e_distrito():
    g = regioes.fronteira_de("PT", "concelho", "Lisboa")
    assert g and g["type"] in ("Polygon", "MultiPolygon") and g["coordinates"]
    assert regioes.fronteira_de("PT", "distrito", "Leiria")["type"] in ("Polygon", "MultiPolygon")


def test_fronteira_estrangeiro():
    assert regioes.fronteira_de("ES", "regiao", "Valencia")["coordinates"]
    assert regioes.fronteira_de("ES", "zona", "València")["coordinates"]


def test_fronteira_pais_e_desconhecido_none():
    assert regioes.fronteira_de("PT", "pais", "Portugal") is None
    assert regioes.fronteira_de("PT", "concelho", "Nãoexiste") is None


def test_fronteira_gorda_e_simplificada():
    """Funchal traz 178 partes (as Selvagens) e uma região MA vem com o
    contorno denso; ambas têm de sair abaixo de ~4,5 KB."""
    import json
    for cc, nivel, nome in [("PT", "concelho", "Funchal"),
                            ("MA", "regiao", "Drâa-Tafilalet")]:
        g = regioes.fronteira_de(cc, nivel, nome)
        assert g, f"{nome} sem fronteira"
        assert len(json.dumps(g, separators=(",", ":"))) < 5000, f"{nome} não encolheu"

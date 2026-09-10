"""Agregação do classify_club.classify_uniao: a união conta cada square uma
vez apesar de vários donos, os exclusivos só contam bit único, by_pais /
by_region / by_municipio somam certo, os centros são a média dos squares, e
os dois avisos (clip_misses, sem_dados_regiao) disparam nos casos certos.

A geometria é do classify.py (testada à parte); aqui o classificador é um
stub que devolve dicts pré-fabricados, para exercitar só a contagem.

Correr: py -m pytest
"""
from types import SimpleNamespace

from classify_club import classify_uniao

ATLETAS = ["A", "B", "C"]  # bit 0, 1, 2


class _Stub:
    def __init__(self, resultados, muni_countries=("ES",), paises_com_regiao=("PT", "ES")):
        self._res = list(resultados)
        self.foreign_muni = (SimpleNamespace(names=[(c, "?") for c in muni_countries])
                             if muni_countries else None)
        self._paises_com_regiao = set(paises_com_regiao)

    def classify(self, _tile):
        return self._res.pop(0)


def _pt(district="D1", concelho="C1"):
    return {"in_portugal": True, "district": district, "concelho": concelho,
            "country": "PT", "region": None, "municipio": None, "on_land": True,
            "country_fallback_deg": None, "concelho_fallback_deg": None}


def _foreign(cc, region=None, municipio=None):
    return {"in_portugal": False, "district": None, "concelho": None,
            "country": cc, "region": region, "municipio": municipio, "on_land": True,
            "country_fallback_deg": None, "concelho_fallback_deg": None}


def _uniao(squares, resultados, **kw):
    return classify_uniao(_Stub(resultados, **kw), squares, ATLETAS)[0]


def test_uniao_conta_partilhado_uma_vez():
    r = _uniao([(10, 20, 0b111)], [_pt()])
    assert r["by_concelho"] == {"C1": 1} and r["by_distrito"] == {"D1": 1}


def test_exclusivos_so_bit_unico():
    r = _uniao([(1, 1, 0b010), (2, 2, 0b011)], [_pt(), _pt()])
    assert r["by_concelho"] == {"C1": 2}
    assert r["exclusivos"]["by_concelho"] == {"C1": {"B": 1}}  # o partilhado não entra


def test_by_pais_soma_todos_os_squares():
    r = _uniao(
        [(1, 1, 1), (2, 2, 1), (3, 3, 1), (4, 4, 1), (5, 5, 1)],
        [_pt(), _pt(), _pt(), _foreign("ES", "R1"), _foreign("ES", "R1")],
    )
    assert r["by_pais"] == {"PT": 3, "ES": 2}


def test_by_region_e_by_municipio_estrangeiro():
    r = _uniao([(1, 1, 1)], [_foreign("ES", "R1", "M1")])
    assert r["by_region"] == {"es": {"R1": 1}}
    assert r["by_municipio"] == {"es": {"M1": 1}}


def test_clip_misses_regiao_sem_municipio():
    # país COM ficheiro de município mas o square ficou sem município: recorte curto
    uniao, clip_misses, _ = classify_uniao(
        _Stub([_foreign("ES", "R1", None)], muni_countries=("ES",)),
        [(1, 1, 1)], ATLETAS,
    )
    assert clip_misses == {"ES": 1}
    assert uniao["by_region"] == {"es": {"R1": 1}}


def test_sem_dados_regiao_pais_sem_geometria():
    _, _clip, sem = classify_uniao(
        _Stub([_foreign("FR", None, None)], paises_com_regiao=("PT", "ES")),
        [(1, 1, 1)], ATLETAS,
    )
    assert sem == {"FR": 1}


def test_centros_media_dos_squares():
    r = _uniao([(10, 20, 1), (20, 40, 1)], [_pt(), _pt()])
    assert r["centros"]["concelho|C1"] == [15, 30]
    assert r["centros"]["distrito|D1"] == [15, 30]


def test_mask_zero_ignorado():
    r = _uniao([(5, 5, 0)], [])
    assert r["by_pais"] == {} and r["by_concelho"] == {} and r["centros"] == {}

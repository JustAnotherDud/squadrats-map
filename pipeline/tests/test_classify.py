"""Decisões de geometria do classify.Classifier, com geometria sintética
mínima (caixas de ~0,2° num espaço lon/lat inventado), não os ficheiros
reais de centenas de KB. O Classifier aceita qualquer polígono shapely, por
isso os testes passam `box(...)` direto, sem passar por tile_bounds.

Mapa das fixtures:
    lon 0..1  lat 0..1   distrito D1 / concelho C1  (Portugal)
    lon 0..1  lat 1..2   região ES/R2              (encostada a D1 em lat=1)
    lon 2..3  lat 0..1   região ES/R1  (isolada; ES outline cobre-a e mais)
      dentro de R1: município ES/M1 (lon 2.05..2.45) e DE/MDE (lon 2.70..2.90)
    lon 5..6  lat 5..6   contorno de país FR (sem ficheiro de região)
Tudo o resto (o vão lon 1..2, lat<0, lat>2) é "água".

Correr: py -m pytest
"""
import json

import pytest
from shapely.geometry import box

from classify import COASTAL_BUFFER_DEG, Classifier


def _poly(lon0, lat0, lon1, lat1):
    return {"type": "Polygon", "coordinates": [[
        [lon0, lat0], [lon1, lat0], [lon1, lat1], [lon0, lat1], [lon0, lat0],
    ]]}


def _fc(*feats):
    return {"type": "FeatureCollection", "features": [
        {"type": "Feature", "properties": p, "geometry": g} for p, g in feats
    ]}


@pytest.fixture
def classifier(tmp_path):
    (tmp_path / "dist.geojson").write_text(json.dumps(_fc(
        ({"district": "D1"}, _poly(0, 0, 1, 1)),
    )))
    (tmp_path / "conc.geojson").write_text(json.dumps(_fc(
        ({"NAME_2": "C1", "parent": "D1"}, _poly(0, 0, 1, 1)),
    )))
    fdir = tmp_path / "foreign"
    fdir.mkdir()
    (fdir / "ES.geojson").write_text(json.dumps(_fc(
        ({"country": "ES", "region": "R1"}, _poly(2, 0, 3, 1)),
        ({"country": "ES", "region": "R2"}, _poly(0, 1, 1, 2)),
    )))
    mdir = tmp_path / "foreign_muni"
    mdir.mkdir()
    (mdir / "ES.geojson").write_text(json.dumps(_fc(
        ({"country": "ES", "region": "M1"}, _poly(2.05, 0.2, 2.45, 0.6)),
        ({"country": "DE", "region": "MDE"}, _poly(2.70, 0.2, 2.90, 0.6)),
    )))
    odir = tmp_path / "outlines"
    odir.mkdir()
    (odir / "europe.geojson").write_text(json.dumps(_fc(
        ({"country": "FR", "nome": "França"}, _poly(5, 5, 6, 6)),
        ({"country": "ES", "nome": "Espanha"}, _poly(1.9, -0.1, 3.1, 1.1)),
    )))
    return Classifier(
        distritos_path=str(tmp_path / "dist.geojson"),
        concelhos_path=str(tmp_path / "conc.geojson"),
        foreign_dir=str(fdir), foreign_muni_dir=str(mdir),
        outlines_path=str(odir / "europe.geojson"),
    )


def test_dentro_de_concelho(classifier):
    r = classifier.classify(box(0.4, 0.4, 0.5, 0.5))
    assert r["in_portugal"] and r["district"] == "D1" and r["concelho"] == "C1"
    assert r["on_land"] and r["country_fallback_deg"] is None and r["concelho_fallback_deg"] is None


def test_dentro_de_regiao_estrangeira(classifier):
    r = classifier.classify(box(2.05, 0.75, 2.15, 0.85))  # em R1, fora de M1/MDE
    assert r["country"] == "ES" and r["region"] == "R1" and r["municipio"] is None
    assert not r["in_portugal"] and r["on_land"]


def test_maior_area_ganha_pt_vs_estrangeiro(classifier):
    # o caso Lobios / Portela do Homem: tile a cavalo da raia, ganha a maior área
    mais_es = classifier.classify(box(0.4, 0.9, 0.6, 1.3))   # 0.1 em D1, 0.3 em R2
    assert mais_es["country"] == "ES" and mais_es["region"] == "R2"
    mais_pt = classifier.classify(box(0.4, 0.7, 0.6, 1.1))   # 0.3 em D1, 0.1 em R2
    assert mais_pt["in_portugal"] and mais_pt["district"] == "D1"


def test_fallback_contorno_da_pais(classifier):
    # dentro do contorno de FR, fora de toda a região: dá país, região None
    r = classifier.classify(box(5.4, 5.4, 5.5, 5.5))
    assert r["country"] == "FR" and r["region"] is None and r["municipio"] is None
    assert r["on_land"] and not r["in_portugal"]


def test_contorno_nao_pisa_pais_com_regiao(classifier):
    # água a 0,02° de R1; o contorno de ES cobre este ponto, mas ES tem
    # ficheiro de região -> o contorno NÃO classifica, cai no fallback costeiro
    r = classifier.classify(box(3.02, 0.4, 3.08, 0.5))
    assert r["country"] == "ES" and r["region"] == "R1"           # não None
    assert r["country_fallback_deg"] is not None and not r["on_land"]


def test_fallback_costeiro_agua_para_terra(classifier):
    # o caso Montijo / Loures: tile sobre água, terra PT mais perto -> concelho
    # da margem, on_land False, distância registada nos dois níveis
    r = classifier.classify(box(1.02, 0.4, 1.08, 0.5))
    assert r["in_portugal"] and r["district"] == "D1" and r["concelho"] == "C1"
    assert not r["on_land"]
    assert r["country_fallback_deg"] == pytest.approx(0.02, abs=1e-6)
    assert r["concelho_fallback_deg"] == pytest.approx(0.02, abs=1e-6)


def test_fallback_costeiro_sem_vies_pt(classifier):
    # água mais perto de R1 (ES) do que de D1 (PT): ganha ES, sem preferência por PT
    r = classifier.classify(box(1.92, 0.4, 1.98, 0.5))
    assert r["country"] == "ES" and r["region"] == "R1" and not r["in_portugal"]
    assert r["country_fallback_deg"] == pytest.approx(0.02, abs=1e-6)


def test_agua_longe_fica_sem_classificacao(classifier):
    r = classifier.classify(box(10, 10, 10.1, 10.1))
    assert r["country"] is None and r["region"] is None and r["district"] is None
    assert not r["on_land"] and r["country_fallback_deg"] is None


def test_municipio_estrangeiro_por_area(classifier):
    r = classifier.classify(box(2.25, 0.35, 2.35, 0.45))  # dentro de M1 e de R1
    assert r["region"] == "R1" and r["municipio"] == "M1"


def test_municipio_so_do_mesmo_pais(classifier):
    # tile dentro de MDE (país DE) mas a região é ES/R1 -> município fica None
    r = classifier.classify(box(2.75, 0.35, 2.85, 0.45))
    assert r["country"] == "ES" and r["region"] == "R1" and r["municipio"] is None


def test_buffer_costeiro_tem_limite(classifier):
    # sanity: o fallback só entra dentro de COASTAL_BUFFER_DEG
    assert COASTAL_BUFFER_DEG == pytest.approx(0.05)

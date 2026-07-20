"""Classifica pontos (centro de cada square) em concelho e distrito de Portugal,
e — quando houver geometria disponível — região estrangeira (ex: província
espanhola). Sem geometria disponível para o país em causa, cai no fallback
genérico (in_portugal=False, country=None, region=None)."""
import glob
import json
import os
from shapely.geometry import shape, Point
from shapely.strtree import STRtree
from shapely.validation import make_valid

COASTAL_BUFFER_DEG = 0.05  # tolerância para decidir in_portugal a partir da distância ao distrito mais próximo


def _clean(geom):
    if not geom.is_valid:
        geom = make_valid(geom)
    return geom


class _Layer:
    def __init__(self, names, geoms):
        self.names = names
        self.geoms = geoms
        self.tree = STRtree(geoms)

    def lookup(self, point, nearest_fallback=True):
        # STRtree.query(geom, predicate) avalia predicate(geom, tree_geometry) —
        # queremos "ponto dentro do polígono", logo predicate="within" (não "contains").
        for idx in self.tree.query(point, predicate="within"):
            return self.names[idx]

        if not nearest_fallback:
            return None

        # fallback costeiro/fronteiriço: geometria mais próxima por distância real.
        # (bug histórico: aqui usava-se tree.query(dwithin) + primeiro match cujo
        # buffer continha o ponto — a ordem devolvida pela STRtree é arbitrária,
        # não por distância, o que atirava squares costeiros para o concelho
        # errado, ex: um ponto em Peniche a 0.0002° ficava classificado como
        # Lourinhã a 0.043° só por ter aparecido primeiro na query. STRtree.nearest
        # devolve sempre o geometricamente mais próximo, determinístico.)
        idx = self.tree.nearest(point)
        return self.names[idx]


class Classifier:
    def __init__(self, distritos_path, concelhos_path, foreign_dir=None):
        with open(distritos_path, encoding="utf-8") as f:
            distritos = json.load(f)
        with open(concelhos_path, encoding="utf-8") as f:
            concelhos = json.load(f)

        d_names = [feat["properties"]["district"] for feat in distritos["features"]]
        d_geoms = [_clean(shape(feat["geometry"])) for feat in distritos["features"]]
        self.distritos = _Layer(d_names, d_geoms)

        c_names = [feat["properties"]["NAME_2"] for feat in concelhos["features"]]
        c_geoms = [_clean(shape(feat["geometry"])) for feat in concelhos["features"]]
        self.concelhos = _Layer(c_names, c_geoms)

        # regiões estrangeiras: um ficheiro por país em refdata/foreign/*.geojson,
        # cada feature com properties.country (ex: "ES") + properties.region
        # (ex: "Asturias"). Adicionar um país novo = só adicionar um ficheiro,
        # zero alterações de código.
        self.foreign = None
        if foreign_dir and os.path.isdir(foreign_dir):
            labels, geoms = [], []
            for path in sorted(glob.glob(os.path.join(foreign_dir, "*.geojson"))):
                with open(path, encoding="utf-8") as f:
                    fc = json.load(f)
                for feat in fc["features"]:
                    labels.append((feat["properties"]["country"], feat["properties"]["region"]))
                    geoms.append(_clean(shape(feat["geometry"])))
            if geoms:
                self.foreign = _Layer(labels, geoms)

    def classify(self, lon, lat):
        point = Point(lon, lat)
        district = self.distritos.lookup(point)
        in_portugal = district is not None and self.distritos.geoms[
            self.distritos.names.index(district)
        ].distance(point) <= COASTAL_BUFFER_DEG
        concelho = self.concelhos.lookup(point) if in_portugal else None

        country, region = (None, None)
        if in_portugal:
            country = "PT"
        elif self.foreign is not None:
            # sem nearest_fallback: um ponto fora de todas as províncias
            # conhecidas fica genérico, não é atirado para a mais próxima
            label = self.foreign.lookup(point, nearest_fallback=False)
            if label is not None:
                country, region = label

        return {
            "in_portugal": in_portugal,
            "district": district if in_portugal else None,
            "concelho": concelho,
            "country": country,
            "region": region,
        }

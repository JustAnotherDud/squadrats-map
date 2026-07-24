"""Busca e descodifica os vector tiles da Squadrats para um atleta (UID Firebase),
substituindo o export manual de KML. Ver pipeline/spikes/notes_vector_tiles.md
para a investigação original que motivou isto.

Endpoint não documentado, sem API pública — ver README para as regras de uso
(cron semanal, User-Agent identificável, concorrência baixa, nunca publicar
tiles em bruto).
"""
import gzip
import math
import time
from concurrent.futures import ThreadPoolExecutor

import mapbox_vector_tile
import requests
from shapely.geometry import Polygon, box
from shapely.ops import unary_union
from shapely.validation import make_valid

USER_AGENT = "squadrats-map-sync/1.0 (+github.com/JustAnotherDud/squadrats-map)"
MAX_CONCURRENCY = 4
REQUEST_TIMEOUT = 15

# camadas com geometria útil para classificação por concelho/distrito —
# reconstruídas em squares individuais (mesmo formato do parse de KML)
GEOMETRY_LAYERS = {"squadrats": 14, "squadratinhos": 17}
# camadas só de contagem global — lidas do atributo `size`, sem decode de geometria
COUNT_ONLY_LAYERS = [
    "yard", "yardinho", "ubersquadrat", "ubersquadratinho", "backyards", "backyardinhos",
]

# Descoberta em cascata (zoom baixo -> cada vez mais fino): começa muito
# barato (z4, ~200 tiles cobrindo praticamente todas as terras habitadas) e
# só desce de zoom dentro dos tiles que já mostraram cobertura. Torna o
# varrimento robusto a qualquer atleta ter capturas em qualquer parte do
# mundo, sem ter de adivinhar/manter um bbox por atleta — descoberto na
# prática: um bbox só de Portugal falhava a auto-validação do José (tem
# squadrats em Espanha) e um bbox só da Ibéria falhava a da Xeira (tem
# squadrats fora da Ibéria). Evita polos/Antártida (lat -60..75), onde não
# há capturas possíveis, para não desperdiçar pedidos.
WORLD_BBOX = (-180.0, -60.0, 180.0, 75.0)
DISCOVERY_LEVELS = (4, 7, 10)  # zooms intermédios da cascata


def deg2num(lon, lat, z):
    n = 2 ** z
    x = int((lon + 180.0) / 360.0 * n)
    r = math.radians(lat)
    y = int((1.0 - math.log(math.tan(r) + 1 / math.cos(r)) / math.pi) / 2.0 * n)
    return x, y


def tile_to_lonlat(gx, gy, z):
    """Mesma convenção NW-corner do kml_parse.tileNW, mas para coordenadas
    fracionárias (gx/gy não têm de ser inteiros — vêm de pixels dentro do tile)."""
    n = 2 ** z
    lon = gx / n * 360.0 - 180.0
    lat = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * gy / n))))
    return lon, lat


def tile_url(uid, z, x, y):
    ts = int(time.time() * 1000)  # servidor ignora o valor, mas é a chave de cache — tem de ser fresco
    return f"https://tiles1.squadrats.com/{uid}/trophies/{ts}/{z}/{x}/{y}.pbf"


class SquadratsHttpError(RuntimeError):
    """UID inválido (500) ou outro erro inesperado do servidor — falhar alto,
    nunca devolver o último valor bom em silêncio."""


def fetch_tile(uid, z, x, y, session):
    resp = session.get(
        tile_url(uid, z, x, y),
        headers={"User-Agent": USER_AGENT},
        timeout=REQUEST_TIMEOUT,
    )
    if resp.status_code == 204:
        return None  # tile sem cobertura — normal, não é erro
    if resp.status_code == 500:
        raise SquadratsHttpError(f"UID inválido ou erro do servidor para {uid} em {z}/{x}/{y}")
    resp.raise_for_status()

    data = resp.content
    # requests normalmente descomprime sozinho via Content-Encoding, mas o
    # servidor às vezes manda gzip duplamente disfarçado de octet-stream —
    # confirmar pelos magic bytes em vez de confiar cegamente no header.
    if data[:2] == b"\x1f\x8b":
        data = gzip.decompress(data)
    # y_coord_down=True: mantém a convenção crua do MVT (Y cresce para baixo
    # dentro do tile, igual à convenção XYZ global usada em tile_to_lonlat).
    # O default da biblioteca é False (inverte para "y para cima" ao estilo
    # GeoJSON) — sem isto, cada tile fica espelhado verticalmente. Não muda a
    # CONTAGEM total (por isso a auto-validação contra o `size` passava na
    # mesma), só a POSIÇÃO das squares dentro do tile — descoberto porque o
    # Rio Maior tinha menos capturas do que o KML antigo mesmo com o total
    # nacional a bater certo.
    return mapbox_vector_tile.decode(data, default_options={"y_coord_down": True})


def _project_geometry(geom, z, x, y, extent):
    """Devolve uma lista de polígonos (lon/lat) — normalmente 1, mas o recorte
    ao tile pode dividir a forma em mais do que uma parte."""
    rings = geom["coordinates"] if geom["type"] == "Polygon" else [
        ring for poly in geom["coordinates"] for ring in poly
    ]
    raw = Polygon(rings[0], rings[1:])
    if not raw.is_valid:
        raw = make_valid(raw)

    # a Squadrats manda a geometria clipada ao tile + um buffer (viu-se
    # coordenadas de -320 a extent+320 num tile com extent=16384) — é o
    # comportamento normal do MVT para permitir render sem costuras, mas
    # description redundante da MESMA área também é descrita pelo tile
    # vizinho. Sem recortar ao tile nominal antes de unir, a faixa de buffer
    # sobreposta entre tiles adjacentes engorda a área total após o
    # unary_union e infla a contagem de squares finais (visto em produção:
    # squadratinhos deu 5360 em vez dos 5050 reportados pelo servidor,
    # squadrats — grelha 4x mais grossa, menos sensível ao efeito — bateu
    # certo). Recortar ao [0, extent]² antes de projetar elimina a faixa
    # redundante; cada square real continua descrito por pelo menos um tile
    # dentro dos seus limites nominais.
    tile_box = box(0, 0, extent, extent)
    clipped = raw.intersection(tile_box)
    if clipped.is_empty:
        return []

    # intersection() pode devolver GeometryCollection (mistura de
    # Polygon/LineString/Point quando o recorte só toca a borda) — só
    # interessam as partes com área.
    if clipped.geom_type in ("Polygon", "MultiPolygon"):
        raw_parts = clipped.geoms if clipped.geom_type == "MultiPolygon" else [clipped]
    else:
        raw_parts = [g for g in getattr(clipped, "geoms", [clipped]) if g.geom_type == "Polygon"]
    parts = [p for p in raw_parts if not p.is_empty and p.area > 0]
    projected = []
    for part in parts:
        ext_ring = [tile_to_lonlat(x + px / extent, y + py / extent, z) for px, py in part.exterior.coords]
        hole_rings = [
            [tile_to_lonlat(x + px / extent, y + py / extent, z) for px, py in interior.coords]
            for interior in part.interiors
        ]
        poly = Polygon(ext_ring, hole_rings)
        projected.append(poly if poly.is_valid else make_valid(poly))
    return projected


def _fetch_batch(uid, z, candidates, session):
    """Devolve o subconjunto de `candidates` (x, y) com cobertura (200) a este zoom."""
    covered = []
    with ThreadPoolExecutor(max_workers=MAX_CONCURRENCY) as pool:
        futures = {pool.submit(fetch_tile, uid, z, x, y, session): (x, y) for x, y in candidates}
        for fut, xy in futures.items():
            if fut.result() is not None:
                covered.append(xy)
    return covered


def discover_coverage(uid, bbox=WORLD_BBOX, levels=DISCOVERY_LEVELS):
    """Descoberta em cascata — devolve os tiles (x, y) no último zoom de
    `levels` com cobertura, para depois só descermos aos filhos fetch_zoom
    desses. Cada nível só explora os filhos dos tiles que já bateram no
    nível anterior, por isso o custo cresce com a cobertura real do atleta,
    não com o tamanho do bbox de partida."""
    lon_min, lat_min, lon_max, lat_max = bbox
    z0 = levels[0]
    x0, y1 = deg2num(lon_min, lat_min, z0)
    x1, y0 = deg2num(lon_max, lat_max, z0)
    xlo, xhi = min(x0, x1), max(x0, x1)
    ylo, yhi = min(y0, y1), max(y0, y1)
    current = [(x, y) for x in range(xlo, xhi + 1) for y in range(ylo, yhi + 1)]

    session = requests.Session()
    for i, z in enumerate(levels):
        hits = _fetch_batch(uid, z, current, session)
        print(f"descoberta z{z}: {len(hits)}/{len(current)} tiles com cobertura")
        if i == len(levels) - 1:
            return hits
        next_z = levels[i + 1]
        factor = 2 ** (next_z - z)
        current = [
            (hx * factor + dx, hy * factor + dy)
            for hx, hy in hits
            for dx in range(factor) for dy in range(factor)
        ]
    return current


def scan_athlete(uid, bbox=WORLD_BBOX, discovery_levels=DISCOVERY_LEVELS, fetch_zoom=12):
    """Varre a cobertura do atleta e devolve:
    - geometries: {layer_name: (size, shapely_geom)} para squadrats/squadratinhos
      (mesmo formato do kml_parse.parse_kml_geometries, para reutilizar
      reconstruct_squares sem alterações)
    - counts: {layer_name: size} para as camadas só de contagem
    """
    coarse_covered = discover_coverage(uid, bbox, levels=discovery_levels)
    discovery_zoom = discovery_levels[-1]

    factor = 2 ** (fetch_zoom - discovery_zoom)
    fine_candidates = [
        (cx * factor + dx, cy * factor + dy)
        for cx, cy in coarse_covered
        for dx in range(factor) for dy in range(factor)
    ]
    print(f"a buscar {len(fine_candidates)} tiles z{fetch_zoom}...")

    polys_by_layer = {name: [] for name in GEOMETRY_LAYERS}
    size_by_layer = {}

    session = requests.Session()
    with ThreadPoolExecutor(max_workers=MAX_CONCURRENCY) as pool:
        futures = {
            pool.submit(fetch_tile, uid, fetch_zoom, x, y, session): (x, y)
            for x, y in fine_candidates
        }
        for fut, (x, y) in futures.items():
            decoded = fut.result()
            if decoded is None:
                continue
            for layer_name, layer in decoded.items():
                if layer_name not in GEOMETRY_LAYERS and layer_name not in COUNT_ONLY_LAYERS:
                    continue  # ex: squadratsoutline, só decoração
                for feat in layer["features"]:
                    size = feat["properties"].get("size")
                    if size is not None and layer_name not in size_by_layer:
                        size_by_layer[layer_name] = size  # global — primeiro valor não-nulo chega
                    if layer_name in GEOMETRY_LAYERS:
                        polys_by_layer[layer_name].extend(
                            _project_geometry(feat["geometry"], fetch_zoom, x, y, layer["extent"])
                        )

    geometries = {}
    for name in GEOMETRY_LAYERS:
        if not polys_by_layer[name]:
            continue
        merged = unary_union(polys_by_layer[name])
        geometries[name] = (size_by_layer.get(name), merged)

    counts = {name: size_by_layer[name] for name in COUNT_ONLY_LAYERS if name in size_by_layer}
    return geometries, counts

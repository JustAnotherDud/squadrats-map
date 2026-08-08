"""Busca e descodifica os vector tiles da Squadrats para um atleta (UID Firebase),
substituindo o export manual de KML. Ver pipeline/spikes/notes_vector_tiles.md
para a investigação original que motivou isto.

Endpoint não documentado, sem API pública — ver README para as regras de uso
(cron semanal, User-Agent identificável, concorrência baixa, nunca publicar
tiles em bruto).
"""
import gzip
import json
import math
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import mapbox_vector_tile
import requests
from shapely.geometry import Polygon, box
from shapely.ops import unary_union
from shapely.validation import make_valid

USER_AGENT = "squadrats-map-sync/1.0 (+github.com/JustAnotherDud/squadrats-map)"
# dois limites separados: a descoberta (z4/z7/z10) é a cascata barata — só
# desce de zoom dentro dos tiles que já mostraram cobertura, por isso varre
# poucos candidatos por natureza. O fetch fino (z12) é sempre o batch grande.
# Separados para poder ajustar um sem arrastar o outro.
DISCOVERY_CONCURRENCY = 4
FETCH_CONCURRENCY = 4
REQUEST_TIMEOUT = 15

# camadas com geometria útil para classificação por concelho/distrito —
# reconstruídas em squares individuais (mesmo formato do parse de KML)
GEOMETRY_LAYERS = {"squadrats": 14, "squadratinhos": 17}
# camadas de "troféu". O `size` NÃO significa o mesmo em todas (ver README):
# yard/yardinho = nº de squares do maior cluster fechado;
# ubersquadrat/-inho = o N do quadrado NxN;
# backyards/-inhos = nº de CLUSTERS fechados, incluindo o próprio yard.
# A geometria delas só é descodificada com `with_trophy_geometry=True`.
TROPHY_LAYERS = [
    "yard", "yardinho", "ubersquadrat", "ubersquadratinho", "backyards", "backyardinhos",
]
COUNT_ONLY_LAYERS = TROPHY_LAYERS  # nome antigo, mantido p/ não partir imports

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

# Cache de cobertura entre corridas: a descoberta em cascata era ~2/3 dos
# pedidos de cada corrida (medido: 4242 de 6274) e re-derivava do zero algo
# que quase nunca muda — em que tiles z10 do mundo cada atleta tem squares.
# Guardamos essa lista por UID e saltamos a cascata na corrida seguinte.
#
# Porque é que isto é seguro:
# - cobertura nunca encolhe (squares são cumulativos), por isso a cache
#   nunca fica com tiles a mais que deixem de ser válidos;
# - se ficar com tiles a MENOS (atleta capturou numa zona nova), a
#   reconstrução não bate com o `size` que o próprio servidor reporta nos
#   tiles — detecta-se, faz-se a descoberta completa e refaz-se a cache,
#   reaproveitando os tiles z12 já buscados. A auto-validação que já era a
#   rede de segurança do pipeline passa a ser também o invalidador da cache.
#
# O ficheiro guarda coordenadas z10 derivadas (nunca tiles em bruto — ver
# regras no README) e é mais grosseiro do que o que o club.json já publica
# (squares z17 individuais), portanto não expõe nada de novo.
COVERAGE_CACHE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "scan_cache.json"
)


def _read_coverage_cache():
    try:
        with open(COVERAGE_CACHE_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _write_coverage_cache(uid, bbox, discovery_levels, fetch_zoom, tiles):
    cache = _read_coverage_cache()
    cache[uid] = {
        "bbox": list(bbox),
        "discovery_levels": list(discovery_levels),
        "fetch_zoom": fetch_zoom,
        "coarse_zoom": discovery_levels[-1],
        "tiles": sorted(list(t) for t in tiles),
    }
    os.makedirs(os.path.dirname(COVERAGE_CACHE_PATH), exist_ok=True)
    with open(COVERAGE_CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, separators=(",", ":"))


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


_thread_local = threading.local()


def _thread_session():
    """Uma requests.Session por thread, criada uma vez e reutilizada.

    requests.Session não tem garantia documentada de ser thread-safe — só o
    connection pool do urllib3 por baixo é. Passar a mesma Session a todas as
    threads de um ThreadPoolExecutor (como se fazia antes) funcionava por
    sorte com pouca concorrência; com FETCH_CONCURRENCY a poder subir isso
    deixa de ser um risco só teórico. Cada worker fica com a sua sessão e
    mantém o connection pooling dentro da própria thread."""
    session = getattr(_thread_local, "session", None)
    if session is None:
        session = requests.Session()
        _thread_local.session = session
    return session


def fetch_tile(uid, z, x, y):
    resp = _thread_session().get(
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


def _fetch_batch(uid, z, candidates):
    """Devolve o subconjunto de `candidates` (x, y) com cobertura (200) a este zoom."""
    covered = []
    with ThreadPoolExecutor(max_workers=DISCOVERY_CONCURRENCY) as pool:
        futures = {pool.submit(fetch_tile, uid, z, x, y): (x, y) for x, y in candidates}
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

    for i, z in enumerate(levels):
        hits = _fetch_batch(uid, z, current)
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


_CACHE = {}


def scan_athlete(uid, bbox=WORLD_BBOX, discovery_levels=DISCOVERY_LEVELS, fetch_zoom=12,
                 with_trophy_geometry=False):
    """Varre o atleta uma vez por processo e guarda o resultado.

    Há três consumidores dos mesmos UIDs (`pipeline.py`, `fetch_club_koms.py`,
    `fetch_club_squares.py`). Corridos em processos separados, cada um varria
    tudo outra vez — o José era varrido três vezes por run. Com esta cache e o
    `run_all.py` a chamá-los no mesmo processo, é um varrimento por atleta.

    Varre-se sempre com a geometria de troféus (é um superconjunto e não custa
    pedidos nenhuns a mais), e devolve-se conforme o que o chamador pediu.
    """
    chave = (uid, bbox, discovery_levels, fetch_zoom)
    if chave not in _CACHE:
        _CACHE[chave] = _scan_athlete(uid, bbox, discovery_levels, fetch_zoom,
                                      with_trophy_geometry=True)
    else:
        print(f"{uid}: já varrido neste processo, a reutilizar")

    geometries, counts, trophies = _CACHE[chave]
    if with_trophy_geometry:
        return geometries, counts, trophies
    return geometries, counts


def _children(tiles, factor):
    return [(cx * factor + dx, cy * factor + dy)
            for cx, cy in tiles
            for dx in range(factor) for dy in range(factor)]


def _fetch_missing(uid, zoom, candidates, results):
    """Busca os `candidates` que ainda não estão em `results` e acumula lá
    ({(x, y): decoded|None}). No caminho de fallback da cache, evita repetir
    os tiles z12 já buscados na tentativa com cache."""
    to_fetch = [xy for xy in candidates if xy not in results]
    with ThreadPoolExecutor(max_workers=FETCH_CONCURRENCY) as pool:
        futures = {pool.submit(fetch_tile, uid, zoom, x, y): (x, y) for x, y in to_fetch}
        for fut, xy in futures.items():
            results[xy] = fut.result()


def _assemble_layers(results, fetch_zoom, with_trophy_geometry):
    """Projecta e une os tiles descodificados nas camadas finais — devolve
    (geometries, counts, trophies); trophies é None sem with_trophy_geometry."""
    polys_by_layer = {name: [] for name in GEOMETRY_LAYERS}
    if with_trophy_geometry:
        polys_by_layer.update({name: [] for name in TROPHY_LAYERS})
    size_by_layer = {}

    for (x, y), decoded in results.items():
        if decoded is None:
            continue
        for layer_name, layer in decoded.items():
            if layer_name not in GEOMETRY_LAYERS and layer_name not in COUNT_ONLY_LAYERS:
                continue  # ex: squadratsoutline, só decoração
            for feat in layer["features"]:
                size = feat["properties"].get("size")
                if size is not None and layer_name not in size_by_layer:
                    size_by_layer[layer_name] = size  # global — primeiro valor não-nulo chega
                if layer_name in polys_by_layer:
                    polys_by_layer[layer_name].extend(
                        _project_geometry(feat["geometry"], fetch_zoom, x, y, layer["extent"])
                    )

    geometries = {}
    for name in GEOMETRY_LAYERS:
        if not polys_by_layer[name]:
            continue
        merged = unary_union(polys_by_layer[name])
        geometries[name] = (size_by_layer.get(name), merged)

    counts = {name: size_by_layer[name] for name in TROPHY_LAYERS if name in size_by_layer}

    trophies = None
    if with_trophy_geometry:
        trophies = {
            name: unary_union(polys_by_layer[name])
            for name in TROPHY_LAYERS if polys_by_layer.get(name)
        }
    return geometries, counts, trophies


def _coverage_complete(geometries):
    """True se a reconstrução bate com o `size` do servidor em todas as
    camadas de geometria presentes — a mesma auto-validação que os
    consumidores fazem, usada aqui para decidir se a cache de cobertura
    apanhou tudo. Custa ~1-2s de CPU por atleta (a instrumentação antiga de
    reconstruct_squares mediu chamadas destas na ordem de décimas de
    segundo), contra ~1000 pedidos de rede poupados quando a cache serve."""
    from kml_parse import reconstruct_squares

    if not geometries:
        return False
    for name, zoom in GEOMETRY_LAYERS.items():
        if name not in geometries:
            continue
        declared, geom = geometries[name]
        if declared is None or len(reconstruct_squares(geom, zoom)) != declared:
            return False
    return True


def _scan_athlete(uid, bbox=WORLD_BBOX, discovery_levels=DISCOVERY_LEVELS, fetch_zoom=12,
                  with_trophy_geometry=False):
    """Varre a cobertura do atleta e devolve:
    - geometries: {layer_name: (size, shapely_geom)} para squadrats/squadratinhos
      (mesmo formato do kml_parse.parse_kml_geometries, para reutilizar
      reconstruct_squares sem alterações)
    - counts: {layer_name: size} para as camadas de troféu

    Com `with_trophy_geometry=True` devolve um 3º valor,
    trophies: {layer_name: shapely_geom} — só quando é preciso desenhar as
    formas (mapa), não quando só interessam os totais (club-koms).

    Caminho normal: cobertura z10 vem de data/scan_cache.json (corrida
    anterior), salta-se a cascata de descoberta e valida-se o resultado
    contra o `size` do servidor. Se não bater (zona nova), cai-se na
    descoberta completa — os tiles z12 já buscados não se repetem.
    """
    coarse_zoom = discovery_levels[-1]
    factor = 2 ** (fetch_zoom - coarse_zoom)
    results = {}

    entry = _read_coverage_cache().get(uid)
    cache_applicable = (
        entry is not None
        and entry.get("bbox") == list(bbox)
        and entry.get("discovery_levels") == list(discovery_levels)
        and entry.get("fetch_zoom") == fetch_zoom
    )
    if cache_applicable:
        cached_coarse = [tuple(t) for t in entry["tiles"]]
        candidates = _children(cached_coarse, factor)
        print(f"cobertura em cache: {len(cached_coarse)} tiles z{coarse_zoom} — "
              f"a buscar {len(candidates)} tiles z{fetch_zoom} sem descoberta...")
        _fetch_missing(uid, fetch_zoom, candidates, results)
        geometries, counts, trophies = _assemble_layers(results, fetch_zoom, with_trophy_geometry)
        if _coverage_complete(geometries):
            if with_trophy_geometry:
                return geometries, counts, trophies
            return geometries, counts
        print("cache de cobertura desatualizada (reconstrução não bate com o size "
              "do servidor — squares numa zona nova?) — descoberta completa...")

    coarse_covered = discover_coverage(uid, bbox, levels=discovery_levels)
    candidates = _children(coarse_covered, factor)
    print(f"a buscar {len(candidates)} tiles z{fetch_zoom}...")
    _fetch_missing(uid, fetch_zoom, candidates, results)
    geometries, counts, trophies = _assemble_layers(results, fetch_zoom, with_trophy_geometry)

    # cobertura real = pais z10 dos tiles z12 que devolveram conteúdo (inclui
    # também o que veio de uma cache parcial no caminho de fallback)
    with_data = {(x // factor, y // factor) for (x, y), d in results.items() if d is not None}
    _write_coverage_cache(uid, bbox, discovery_levels, fetch_zoom, with_data)

    if with_trophy_geometry:
        return geometries, counts, trophies
    return geometries, counts

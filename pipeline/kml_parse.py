"""Parse o KML exportado do Squadrats e reconstrói os squares individuais (x, y, zoom)."""
import math
import re
import xml.etree.ElementTree as ET
from shapely.geometry import Polygon, MultiPolygon
from shapely.ops import unary_union

KML_NS = "{http://www.opengis.net/kml/2.2}"

# zoom XYZ correspondente a cada categoria do squadrats.com
ZOOM_BY_TYPE = {
    "squadrats": 14,
    "squadratinhos": 17,
}


def _parse_coords(text):
    pts = []
    for pair in text.strip().split():
        lon, lat = pair.split(",")[:2]
        pts.append((float(lon), float(lat)))
    return pts


def parse_kml_geometries(kml_path):
    """Devolve {placemark_name: (declared_size, shapely_geometry)}."""
    tree = ET.parse(kml_path)
    root = tree.getroot()
    result = {}

    for placemark in root.iter(f"{KML_NS}Placemark"):
        name_el = placemark.find(f"{KML_NS}name")
        if name_el is None:
            continue
        name = name_el.text.strip()

        size = None
        for data in placemark.iter(f"{KML_NS}Data"):
            if data.get("name") == "size":
                size = int(data.find(f"{KML_NS}value").text)

        polygons = []
        for poly_el in placemark.iter(f"{KML_NS}Polygon"):
            outer_el = poly_el.find(f"{KML_NS}outerBoundaryIs/{KML_NS}LinearRing/{KML_NS}coordinates")
            if outer_el is None:
                continue
            outer = _parse_coords(outer_el.text)

            holes = []
            for inner_el in poly_el.findall(f"{KML_NS}innerBoundaryIs/{KML_NS}LinearRing/{KML_NS}coordinates"):
                holes.append(_parse_coords(inner_el.text))

            polygons.append(Polygon(outer, holes))

        if not polygons:
            continue

        geom = unary_union(polygons)
        result[name] = (size, geom)

    return result


def lonlat_to_tile(lon, lat, z):
    n = 2 ** z
    x = int((lon + 180.0) / 360.0 * n)
    lat_rad = math.radians(lat)
    y = int((1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n)
    return x, y


def tile_center(x, y, z):
    n = 2 ** z

    def nw(x, y):
        lon = x / n * 360.0 - 180.0
        lat = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * y / n))))
        return lon, lat

    lon1, lat1 = nw(x, y)
    lon2, lat2 = nw(x + 1, y + 1)
    return (lon1 + lon2) / 2, (lat1 + lat2) / 2


def reconstruct_squares(geom, zoom):
    """Varre a grelha de tiles XYZ e devolve os (x, y) cujo centro cai dentro
    do polígono (mesma convenção usada para classificar os squares originalmente).

    O polígono de entrada é tipicamente um MultiPolygon com clusters muito
    espalhados (squares em várias zonas do país/estrangeiro) — varrer a bbox
    combinada de tudo seria enorme. Em vez disso, varremos a bbox de cada
    componente conectado separadamente e usamos geometria "prepared" para
    acelerar o contains().
    """
    from shapely.geometry import Point
    from shapely.prepared import prep

    components = list(geom.geoms) if hasattr(geom, "geoms") else [geom]

    squares = []
    for part in components:
        minlon, minlat, maxlon, maxlat = part.bounds
        x0, y1 = lonlat_to_tile(minlon, minlat, zoom)
        x1, y0 = lonlat_to_tile(maxlon, maxlat, zoom)
        xlo, xhi = min(x0, x1) - 1, max(x0, x1) + 1
        ylo, yhi = min(y0, y1) - 1, max(y0, y1) + 1

        prepared = prep(part)
        for x in range(xlo, xhi + 1):
            for y in range(ylo, yhi + 1):
                cx, cy = tile_center(x, y, zoom)
                if prepared.contains(Point(cx, cy)):
                    squares.append((x, y, cx, cy))
    return squares

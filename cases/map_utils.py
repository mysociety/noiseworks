import math


# Given some click co-ords (the tile they were on, and where in the
# tile they were), convert to WGS84 and return.
def click_to_wgs84(zoom, pin_tile_x, pin_x, pin_tile_y, pin_y):
    tile_x = _click_to_tile(pin_tile_x, pin_x)
    tile_y = _click_to_tile(pin_tile_y, pin_y)
    lat, lon = _tile_to_latlon(tile_x, tile_y, zoom)
    return lat, lon


def _tile_to_latlon(x, y, zoom):
    n = pow(2, zoom)
    lon = x / n * 360 - 180
    lat = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * y / n))))
    return lat, lon


def _click_to_tile(pin_tile, pin):
    while pin > 512:
        pin -= 512
    while pin < 0:
        pin += 512
    return pin_tile + pin / 512


# Given a lat/lon, convert it to OSM tile co-ordinates (precise).
def latlon_to_tile(lat, lon, zoom):
    x_tile = (lon + 180) / 360 * pow(2, zoom)
    y_tile = (
        (
            1
            - math.log(math.tan(math.radians(lat)) + 1 / math.cos(math.radians(lat)))
            / math.pi
        )
        / 2
        * pow(2, zoom)
    )
    return x_tile, y_tile


def latlon_to_tile_px(lat, lon, zoom):
    x_tile, y_tile = latlon_to_tile(lat, lon, zoom)
    px = _tile_to_px(x_tile)
    py = _tile_to_px(y_tile)
    return int(x_tile), int(y_tile), px, py


# Convert tile co-ordinates to pixel co-ordinates from top left of map
# C is centre tile reference of displayed map
def _tile_to_px(p):
    p = 512 * (p - int(p))
    return round(p)

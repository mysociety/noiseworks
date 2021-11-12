from django.contrib.gis import forms
from . import map_utils


class SearchWidget(forms.TextInput):
    input_type = "search"
    template_name = "widgets/search.html"


class MapWidget(forms.BaseGeometryWidget):
    template_name = "cases/add/map.html"
    zoom = None

    def get_context(self, name, value, attrs):
        if value and isinstance(value, str):
            value = self.deserialize(value)

        context = super().get_context(name, value, attrs)

        if not value:
            return context

        accessToken = "pk.eyJ1IjoibGJoZWxld2lzIiwiYSI6ImNqeXJkN25uNjA5M3Uzb251bWVyejJ3YW8ifQ.uzO8I54w64U6QkNknW32FA"
        url_base = "https://api.mapbox.com/styles/v1/mapbox/streets-v11/tiles/"

        x, y, px, py = map_utils.latlon_to_tile_px(value[1], value[0], self.zoom)
        context.update(
            {
                "value": value,
                "tile": {
                    "x": x,
                    "y": y,
                    "url": f"{url_base}{self.zoom}/{x}/{y}?access_token={accessToken}",
                },
                "pin": {
                    "x": px,
                    "y": py,
                },
                "zoom": self.zoom,
                "radius": self.radius,
            }
        )
        return context

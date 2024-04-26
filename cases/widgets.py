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

        url_base = "https://tile.openstreetmap.org/"
        x, y, px, py = map_utils.latlon_to_tile_px(value[1], value[0], self.zoom)
        context.update(
            {
                "value": value,
                "tile": {
                    "x": x,
                    "y": y,
                    "url": f"{url_base}{self.zoom}/{x}/{y}.png",
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

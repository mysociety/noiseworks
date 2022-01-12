import mimetypes
import base64
from django.contrib.staticfiles import finders


def _file_contents(url):
    path = finders.find(url)
    if path is None:  # pragma: no cover
        return ""
    data = open(path, "rb").read()
    return path, data


def inline_image(url):
    path, data = _file_contents(url)
    data = base64.b64encode(data).decode("utf-8")
    type, _ = mimetypes.guess_type(path)
    return f"url('data:{type};base64,{data}')"


def inline_image_html(url):
    path, data = _file_contents(url)
    return data

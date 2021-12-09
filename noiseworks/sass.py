import mimetypes
import base64
from django.contrib.staticfiles import finders


def _inline_image(url, css):
    path = finders.find(url)
    if path is None:  # pragma: no cover
        return ""
    data = open(path, "rb").read()
    data = base64.b64encode(data).decode("utf-8")
    type, _ = mimetypes.guess_type(path)
    out = "data:%s;base64,%s" % (type, data)
    if css:
        out = "url('%s')" % out
    return out


def inline_image(url):
    return _inline_image(url, css=True)


def inline_image_html(url):
    return _inline_image(url, css=False)

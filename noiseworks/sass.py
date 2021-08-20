import mimetypes
import base64
from django.contrib.staticfiles import finders


def inline_image(url):
    path = finders.find(url)
    if path is None:  # pragma: no cover
        return ""
    data = open(path, "rb").read()
    data = base64.b64encode(data).decode("utf-8")
    type, _ = mimetypes.guess_type(path)
    return "url('data:%s;base64,%s')" % (type, data)

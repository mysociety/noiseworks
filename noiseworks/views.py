from django.http import HttpResponseServerError
from django.template import loader

from cobrands.registry import get_cobrand


def server_error(request, template_name="500.html"):
    """By default Django won't run context processors when
    rendering the 500 page. This view ensures cobrand is passed
    for the site name etc."""
    template = loader.get_template(template_name)
    return HttpResponseServerError(template.render({"cobrand": get_cobrand()}))

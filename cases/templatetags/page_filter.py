from django import template

register = template.Library()


@register.simple_tag(takes_context=True)
def param_replace(context, **kwargs):
    """
    Return encoded URL parameters that are the same as the current request's
    parameters, only with the specified parameters added or changed.
    """
    d = context["request"].GET.copy()
    for k, v in kwargs.items():
        if v == "":
            d.pop(k, None)
        else:
            d[k] = v
    return d.urlencode()

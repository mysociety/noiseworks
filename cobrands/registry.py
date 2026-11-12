from functools import cache

from django.conf import settings
from django.utils.module_loading import import_string

from .interface import Cobrand


@cache
def get_cobrand() -> Cobrand:
    return import_string(settings.COBRAND_CLASS)()

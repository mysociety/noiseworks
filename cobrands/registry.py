import importlib
from functools import cache

from django.conf import settings


@cache
def get_cobrand():
    return importlib.import_module(f"cobrands.{settings.COBRAND}.cobrand")

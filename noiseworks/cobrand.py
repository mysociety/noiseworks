import importlib

from django.conf import settings

cobrand = settings.COBRAND

api = importlib.import_module(f"cobrands.{cobrand}.api")
email = importlib.import_module(f"cobrands.{cobrand}.email")

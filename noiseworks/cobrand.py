import importlib
from django.conf import settings

cobrand = settings.COBRAND

api = importlib.import_module(f"{cobrand}.api")

import pytest
from django.test import override_settings

from cobrands.registry import get_cobrand
from cobrands.testing import TestCobrand


@pytest.fixture(autouse=True)
def cobrand(request):
    marker = request.node.get_closest_marker("cobrand")
    cls = marker.args[0] if marker else TestCobrand
    path = f"{cls.__module__}.{cls.__name__}"

    with override_settings(COBRAND_CLASS=path):
        get_cobrand.cache_clear()
        yield get_cobrand()
    get_cobrand.cache_clear()

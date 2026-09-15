from .interface import Cobrand
from .testing import TestCobrand


def test_test_cobrand_implements_cobrand() -> None:
    _: Cobrand = TestCobrand()

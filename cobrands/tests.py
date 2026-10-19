from django.conf import settings

from .interface import Cobrand
from .testing import TestCobrand


def test_test_cobrand_implements_cobrand() -> None:
    _: Cobrand = TestCobrand()


def test_cobrand_templates_are_all_hooks() -> None:
    """Fails if a cobrand defines a template that isn't a 'hook'
    - a template we explicitly allow cobrands to override."""
    cobrands = settings.BASE_DIR / "cobrands"
    defaults = cobrands / "defaults" / "templates"
    for templates in cobrands.glob("*/templates"):
        for path in templates.rglob("*"):
            if path.is_file():
                relative = path.relative_to(templates)
                assert relative.parts[0] == "cobrand", path
                assert (defaults / relative).is_file(), path

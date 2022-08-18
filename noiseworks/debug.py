import re

from django.views.debug import SafeExceptionReporterFilter


class CustomExceptionReporterFilter(SafeExceptionReporterFilter):
    """Include DATABASE_URL in the hidden settings"""

    hidden_settings = re.compile(
        "DATABASE_URL|API|TOKEN|KEY|SECRET|PASS|SIGNATURE", flags=re.IGNORECASE
    )

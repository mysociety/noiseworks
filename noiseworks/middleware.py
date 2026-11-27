from django.conf import settings
from django.utils import translation


def staff_locale_middleware(get_response):
    def middleware(request):
        language = settings.LANGUAGE_CODE
        if request.user.is_staff:
            language += "staff"
        translation.activate(language)
        request.LANGUAGE_CODE = translation.get_language()

        response = get_response(request)
        return response

    return middleware

from threading import local

_user = local()
_user.value = None


class CurrentUserMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if hasattr(request, "user") and request.user.is_authenticated:
            _user.value = request.user
        response = self.get_response(request)
        _user.value = None
        return response


def get_current_user():
    return _user.value

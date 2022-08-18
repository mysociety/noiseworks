from functools import partial

from django.db.models import signals


def update_pre_save_info(user, sender, instance, **kwargs):
    if not getattr(instance, "created_by_id", None):
        instance.created_by = user
    if hasattr(instance, "modified_by_id"):
        instance.modified_by = user
    else:  # pragma: no cover
        pass  # All models have modified_by


def user_audit_middleware(get_response):
    def middleware(request):
        if hasattr(request, "user") and request.user.is_authenticated:
            user = request.user
        else:
            user = None

        signals.pre_save.connect(
            partial(update_pre_save_info, user), dispatch_uid=(request), weak=False
        )

        response = get_response(request)

        signals.pre_save.disconnect(dispatch_uid=(request))

        return response

    return middleware

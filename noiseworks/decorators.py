from django.contrib.auth.decorators import user_passes_test


def staff_member_required(view_func):
    actual_decorator = user_passes_test(
        lambda u: u.is_active and u.is_staff,
    )
    return actual_decorator(view_func)

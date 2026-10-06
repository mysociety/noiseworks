from .registry import get_cobrand


def cobrand(request):
    return {"cobrand": get_cobrand()}

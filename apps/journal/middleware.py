from .signals import _local


class JournalMiddleware:
    """Rend l'utilisateur courant visible aux signaux de app.journal (cf. signals.py) -
    un signal Django n'a pas accès à la requête HTTP, donc pas à request.user."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        utilisateur = request.user if getattr(request, "user", None) and request.user.is_authenticated else None
        _local.utilisateur = utilisateur
        try:
            return self.get_response(request)
        finally:
            _local.utilisateur = None

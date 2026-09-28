from django.core.cache import cache

from .models import KoboSoumission


def soumissions_a_traiter(request):
    """Nombre de soumissions Kobo en attente, pour le badge du menu (validateurs seulement)."""
    utilisateur = getattr(request, "user", None)
    profil = getattr(utilisateur, "profile", None) if utilisateur and utilisateur.is_authenticated else None
    if profil is None or not profil.is_validateur:
        return {}
    cle = f"menu:soumissions_a_traiter:{profil.institution_id or 'toutes'}"
    nombre = cache.get(cle)
    if nombre is None:
        soumissions = KoboSoumission.objects.filter(statut__in=("nouveau", "erreur"))
        if profil.institution_id:
            soumissions = soumissions.filter(institution_id=profil.institution_id)
        nombre = soumissions.count()
        cache.set(cle, nombre, 30)
    return {"nav_soumissions_a_traiter": nombre}

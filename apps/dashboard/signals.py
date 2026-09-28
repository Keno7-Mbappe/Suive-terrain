"""Le tableau de bord met ses chiffres en cache 60 s (la base est distante) : toute
modification des données sources vide ce cache pour que le résultat d'une saisie ou
d'une validation apparaisse immédiatement."""

from django.core.cache import cache
from django.db.models.signals import post_delete, post_save


def vider_cache_tableau_de_bord(sender, **kwargs):
    cache.clear()


def brancher_signaux():
    from apps.beneficiaires.models import Beneficiaire
    from apps.certifications.models import Certification
    from apps.formations.models import Formation
    from apps.imports.models import KoboSoumission
    from apps.insertions.models import Insertion
    from apps.referentiels.models import CycleEnquete, Institution
    from apps.satisfactions.models import Satisfaction, SatisfactionInstitution
    from apps.suivis.models import Suivi

    for modele in (
        Beneficiaire, Certification, Formation, Insertion, Suivi, Satisfaction,
        SatisfactionInstitution, KoboSoumission, CycleEnquete, Institution,
    ):
        post_save.connect(vider_cache_tableau_de_bord, sender=modele, dispatch_uid=f"cache-{modele.__name__}-save")
        post_delete.connect(vider_cache_tableau_de_bord, sender=modele, dispatch_uid=f"cache-{modele.__name__}-del")

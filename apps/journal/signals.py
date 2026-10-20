"""Journalise automatiquement chaque création/modification/suppression des modèles
métier, pour la traçabilité des modifications apportées. L'utilisateur courant est lu
depuis un stockage local au thread, rempli par JournalMiddleware à chaque requête
(un signal Django n'a pas accès à la requête HTTP)."""

import threading

from django.db.models.signals import post_delete, post_save, pre_save

_local = threading.local()


def utilisateur_courant():
    return getattr(_local, "utilisateur", None)


def _repr_objet(instance):
    try:
        return str(instance)[:255]
    except Exception:  # noqa: BLE001 - un __str__ qui plante ne doit pas casser la sauvegarde
        return ""


def _avant_sauvegarde(sender, instance, **kwargs):
    if instance.pk:
        try:
            instance._etat_avant_journal = sender.objects.get(pk=instance.pk)
        except sender.DoesNotExist:
            instance._etat_avant_journal = None
    else:
        instance._etat_avant_journal = None


def _apres_sauvegarde(sender, instance, created, **kwargs):
    from .models import Modification

    if created:
        action, details = "creation", ""
    else:
        avant = getattr(instance, "_etat_avant_journal", None)
        if avant is None:
            return  # pas d'état avant connu (ex. restauré via loaddata) : rien à comparer
        changements = []
        for champ in instance._meta.fields:
            if champ.name in ("id", "tranche_age"):
                continue  # recalculé automatiquement, pas une vraie saisie
            ancienne, nouvelle = getattr(avant, champ.name, None), getattr(instance, champ.name, None)
            if ancienne != nouvelle:
                changements.append(f"{champ.verbose_name} : « {ancienne} » → « {nouvelle} »")
        if not changements:
            return  # save() sans changement de champ suivi (ex. simple re-sauvegarde)
        action, details = "modification", "; ".join(changements)

    Modification.objects.create(
        utilisateur=utilisateur_courant(), modele=sender.__name__, objet_id=str(instance.pk),
        objet_repr=_repr_objet(instance), action=action, details=details,
    )


def _apres_suppression(sender, instance, **kwargs):
    from .models import Modification

    Modification.objects.create(
        utilisateur=utilisateur_courant(), modele=sender.__name__, objet_id=str(instance.pk),
        objet_repr=_repr_objet(instance), action="suppression", details="",
    )


def brancher_signaux():
    from apps.beneficiaires.models import Beneficiaire
    from apps.certifications.models import Certification
    from apps.formations.models import Formation
    from apps.insertions.models import Insertion
    from apps.satisfactions.models import Satisfaction
    from apps.suivis.models import Suivi

    for modele in (Beneficiaire, Formation, Certification, Insertion, Suivi, Satisfaction):
        pre_save.connect(_avant_sauvegarde, sender=modele, dispatch_uid=f"journal-pre-{modele.__name__}")
        post_save.connect(_apres_sauvegarde, sender=modele, dispatch_uid=f"journal-post-{modele.__name__}")
        post_delete.connect(_apres_suppression, sender=modele, dispatch_uid=f"journal-del-{modele.__name__}")

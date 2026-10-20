from django.conf import settings
from django.db import models

ACTIONS = [
    ("creation", "Création"),
    ("modification", "Modification"),
    ("suppression", "Suppression"),
]


class Modification(models.Model):
    """Trace de chaque création/modification/suppression sur les modèles métier
    (bénéficiaires, formations, certifications, insertions, suivis, satisfactions) -
    traçabilité des modifications apportées, demandée pour le suivi du dispositif.

    Limite connue : seuls les .save()/.delete() passent par les signaux Django, donc
    par ce journal - une mise à jour en masse via .update() (utilisée par certains
    scripts de maintenance ponctuels) n'y apparaît pas."""

    horodatage = models.DateTimeField("Horodatage", auto_now_add=True)
    utilisateur = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="+", verbose_name="Utilisateur",
    )
    modele = models.CharField("Modèle", max_length=100)
    objet_id = models.CharField("Identifiant de l'objet", max_length=50)
    objet_repr = models.CharField("Objet concerné", max_length=255, blank=True)
    action = models.CharField("Action", max_length=20, choices=ACTIONS)
    details = models.TextField("Détail des champs modifiés", blank=True)

    class Meta:
        ordering = ["-horodatage"]
        verbose_name = "Modification"
        verbose_name_plural = "Journal des modifications"

    def __str__(self):
        return f"{self.get_action_display()} {self.modele} {self.objet_id} ({self.horodatage:%d/%m/%Y %H:%M})"

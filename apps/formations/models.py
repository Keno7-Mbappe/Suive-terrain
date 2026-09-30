from django.db import models

STATUTS_FORMATION = [
    ("en_cours", "En cours"),
    ("achevee", "Achevée"),
    ("abandonnee", "Abandonnée"),
]


class Formation(models.Model):
    beneficiaire = models.ForeignKey(
        "beneficiaires.Beneficiaire", on_delete=models.CASCADE, related_name="formations",
        verbose_name="Bénéficiaire",
    )
    # blank=True : une poignée de formations d'une liste nominative institutionnelle
    # (un même centre) ne précisent pas la filière.
    domaine = models.CharField("Domaine / spécialité", max_length=150, blank=True)
    centre = models.CharField("Centre de formation", max_length=150, blank=True)
    # Nullable : certaines listes nominatives institutionnelles ne précisent pas la date
    # de début de chaque formation.
    date_debut = models.DateField("Date de début", null=True, blank=True)
    date_fin = models.DateField("Date de fin", null=True, blank=True)
    statut_formation = models.CharField("Statut", max_length=20, choices=STATUTS_FORMATION, default="en_cours")

    class Meta:
        ordering = ["-date_debut"]

    def __str__(self):
        return f"{self.beneficiaire_id} - {self.domaine}"

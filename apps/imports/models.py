from django.db import models

TYPES_FORMULAIRE = [
    # "suivi" inclut la satisfaction bénéficiaire (module optionnel de la même
    # soumission Kobo) : pas de type "satisfaction" séparé.
    ("suivi", "Suivi et satisfaction bénéficiaire"),
    ("satisfaction_institution", "Satisfaction institutionnelle"),
]

STATUTS_TRAITEMENT = [
    ("nouveau", "Nouveau"),
    ("integre", "Intégré"),
    ("doublon", "Doublon détecté"),
    ("erreur", "Erreur"),
]


class KoboSoumission(models.Model):
    """Copie brute d'une soumission KoboToolbox, en attente de contrôle et d'intégration
    dans les tables de production (bénéficiaires, suivis, satisfactions...).
    """

    type_formulaire = models.CharField("Type de formulaire", max_length=30, choices=TYPES_FORMULAIRE)
    kobo_submission_id = models.CharField("Identifiant de soumission Kobo", max_length=50)
    donnees_brutes = models.JSONField("Données brutes")
    statut = models.CharField("Statut", max_length=20, choices=STATUTS_TRAITEMENT, default="nouveau")
    erreur = models.TextField("Erreur", blank=True)
    recu_le = models.DateTimeField("Reçu le", auto_now_add=True)
    traite_le = models.DateTimeField("Traité le", null=True, blank=True)

    class Meta:
        unique_together = [("type_formulaire", "kobo_submission_id")]
        ordering = ["-recu_le"]
        verbose_name = "Soumission Kobo"
        verbose_name_plural = "Soumissions Kobo"

    def __str__(self):
        return f"{self.get_type_formulaire_display()} #{self.kobo_submission_id} ({self.statut})"

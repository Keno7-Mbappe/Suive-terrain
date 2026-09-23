from django.db import models

NOTES = [(i, str(i)) for i in range(1, 6)]

AMELIORATIONS_EMPLOYABILITE = [
    ("tout_a_fait", "Tout à fait"),
    ("plutot", "Plutôt"),
    ("peu", "Peu"),
    ("pas_du_tout", "Pas du tout"),
]


class DimensionsSatisfactionMixin(models.Model):
    note_formation = models.PositiveSmallIntegerField("Note formation", choices=NOTES)
    note_formateurs = models.PositiveSmallIntegerField("Note formateurs", choices=NOTES)
    note_contenus = models.PositiveSmallIntegerField("Note contenus", choices=NOTES)
    note_equipements = models.PositiveSmallIntegerField("Note équipements", choices=NOTES)
    note_accueil = models.PositiveSmallIntegerField("Note accueil", choices=NOTES)
    points_positifs = models.TextField("Points positifs", blank=True)
    points_a_ameliorer = models.TextField("Points à améliorer", blank=True)

    class Meta:
        abstract = True

    @property
    def note_globale(self):
        notes = [self.note_formation, self.note_formateurs, self.note_contenus, self.note_equipements, self.note_accueil]
        return round(sum(notes) / len(notes), 2)


class Satisfaction(DimensionsSatisfactionMixin):
    beneficiaire = models.ForeignKey(
        "beneficiaires.Beneficiaire", on_delete=models.CASCADE, related_name="satisfactions",
        verbose_name="Bénéficiaire",
    )
    cycle = models.ForeignKey(
        "referentiels.CycleEnquete", on_delete=models.CASCADE, related_name="satisfactions",
        verbose_name="Cycle d'enquête",
    )
    amelioration_employabilite = models.CharField(
        "Amélioration de l'employabilité", max_length=20, choices=AMELIORATIONS_EMPLOYABILITE
    )
    recommande = models.BooleanField("Recommande la formation")

    class Meta:
        unique_together = [("beneficiaire", "cycle")]
        ordering = ["-cycle__date_debut"]

    def __str__(self):
        return f"{self.beneficiaire_id} - {self.cycle}"


class SatisfactionInstitution(DimensionsSatisfactionMixin):
    institution = models.ForeignKey(
        "referentiels.Institution", on_delete=models.CASCADE, related_name="satisfactions_institution",
        verbose_name="Institution",
    )
    cycle = models.ForeignKey(
        "referentiels.CycleEnquete", on_delete=models.CASCADE, related_name="satisfactions_institution",
        verbose_name="Cycle d'enquête",
    )

    class Meta:
        unique_together = [("institution", "cycle")]
        ordering = ["-cycle__date_debut"]

    def __str__(self):
        return f"{self.institution} - {self.cycle}"

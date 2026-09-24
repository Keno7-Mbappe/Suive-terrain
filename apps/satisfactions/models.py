from django.db import models

NOTES = [(i, str(i)) for i in range(1, 6)]

AMELIORATIONS_EMPLOYABILITE = [
    ("tout_a_fait", "Tout à fait"),
    ("plutot", "Plutôt"),
    ("peu", "Peu"),
    ("pas_du_tout", "Pas du tout"),
]

UTILITE_DISPOSITIF = [
    ("pleinement", "Pleinement"),
    ("partiellement", "Partiellement"),
    ("peu", "Peu"),
    ("pas_du_tout", "Pas du tout"),
]


class Satisfaction(models.Model):
    beneficiaire = models.ForeignKey(
        "beneficiaires.Beneficiaire", on_delete=models.CASCADE, related_name="satisfactions",
        verbose_name="Bénéficiaire",
    )
    cycle = models.ForeignKey(
        "referentiels.CycleEnquete", on_delete=models.CASCADE, related_name="satisfactions",
        verbose_name="Cycle d'enquête",
    )
    note_formation = models.PositiveSmallIntegerField("Note formation", choices=NOTES)
    note_formateurs = models.PositiveSmallIntegerField("Note formateurs", choices=NOTES)
    note_contenus = models.PositiveSmallIntegerField("Note contenus", choices=NOTES)
    note_equipements = models.PositiveSmallIntegerField("Note équipements", choices=NOTES)
    note_accueil = models.PositiveSmallIntegerField("Note conditions d'accueil", choices=NOTES)
    amelioration_employabilite = models.CharField(
        "Amélioration de l'employabilité", max_length=20, choices=AMELIORATIONS_EMPLOYABILITE
    )
    recommande = models.BooleanField("Recommande la formation")
    raison_non_recommande = models.TextField("Raison (si ne recommande pas)", blank=True)
    points_positifs = models.TextField("Points positifs", blank=True)
    points_a_ameliorer = models.TextField("Points à améliorer", blank=True)

    class Meta:
        unique_together = [("beneficiaire", "cycle")]
        ordering = ["-cycle__date_debut"]

    def __str__(self):
        return f"{self.beneficiaire_id} - {self.cycle}"

    @property
    def note_globale(self):
        notes = [self.note_formation, self.note_formateurs, self.note_contenus, self.note_equipements, self.note_accueil]
        return round(sum(notes) / len(notes), 2)


class SatisfactionInstitution(models.Model):
    """Satisfaction des institutions partenaires (EFTP/INAP/ANEFIP/ONEQ/Direction des
    Projets) à l'égard du DISPOSITIF DE SUIVI lui-même (qualité des données, outils
    de collecte, tableaux de bord, appui technique, coordination) - pas une simple
    reprise du questionnaire de satisfaction des bénéficiaires, qui n'aurait pas de
    sens pour une institution (elle ne suit pas la formation)."""

    institution = models.ForeignKey(
        "referentiels.Institution", on_delete=models.CASCADE, related_name="satisfactions_institution",
        verbose_name="Institution",
    )
    cycle = models.ForeignKey(
        "referentiels.CycleEnquete", on_delete=models.CASCADE, related_name="satisfactions_institution",
        verbose_name="Cycle d'enquête",
    )
    fonction_repondant = models.CharField("Fonction du répondant", max_length=150, blank=True)
    date_reponse = models.DateField("Date de la réponse", null=True, blank=True)

    note_qualite_donnees = models.PositiveSmallIntegerField("Qualité et fiabilité des données", choices=NOTES)
    note_outils_collecte = models.PositiveSmallIntegerField("Outils de collecte mis à disposition", choices=NOTES)
    note_tableaux_bord = models.PositiveSmallIntegerField("Utilité des tableaux de bord", choices=NOTES)
    note_appui_technique = models.PositiveSmallIntegerField("Appui technique reçu", choices=NOTES)
    note_coordination = models.PositiveSmallIntegerField("Coordination entre les structures", choices=NOTES)

    utilite_dispositif = models.CharField(
        "Le dispositif répond-il aux besoins de la structure ?", max_length=20, choices=UTILITE_DISPOSITIF
    )
    difficultes = models.TextField("Difficultés rencontrées", blank=True)
    recommandations = models.TextField("Recommandations d'amélioration", blank=True)

    class Meta:
        unique_together = [("institution", "cycle")]
        ordering = ["-cycle__date_debut"]
        verbose_name = "Satisfaction institutionnelle"
        verbose_name_plural = "Satisfactions institutionnelles"

    def __str__(self):
        return f"{self.institution} - {self.cycle}"

    @property
    def note_globale(self):
        notes = [
            self.note_qualite_donnees, self.note_outils_collecte, self.note_tableaux_bord,
            self.note_appui_technique, self.note_coordination,
        ]
        return round(sum(notes) / len(notes), 2)

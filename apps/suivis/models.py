from django.db import models

VAGUES = [("m3", "M+3"), ("m6", "M+6"), ("m12", "M+12")]

ISSUES_CONTACT = [
    ("joint", "Joint"),
    ("injoignable", "Injoignable"),
    ("numero_errone", "Numéro erroné"),
    ("refus", "Refus"),
]

SITUATIONS_ACTUELLES = [
    ("emploi_salarie", "Emploi salarié"),
    ("auto_emploi", "Auto-emploi"),
    ("stage", "Stage"),
    ("en_formation", "En formation"),
    ("en_recherche", "En recherche"),
    ("inactif", "Inactif"),
]

TYPES_CONTRAT = [
    ("cdi", "CDI"),
    ("cdd", "CDD"),
    ("journalier", "Journalier"),
    ("independant", "Indépendant"),
]

TRANCHES_REVENU = [
    ("lt_30000", "< 30 000 DJF"),
    ("30000_60000", "30 000 - 60 000 DJF"),
    ("60000_100000", "60 000 - 100 000 DJF"),
    ("gt_100000", "> 100 000 DJF"),
]

LIENS_FORMATION = [
    ("direct", "Direct"),
    ("partiel", "Partiel"),
    ("aucun", "Aucun"),
]


class Suivi(models.Model):
    beneficiaire = models.ForeignKey(
        "beneficiaires.Beneficiaire", on_delete=models.CASCADE, related_name="suivis",
        verbose_name="Bénéficiaire",
    )
    vague = models.CharField("Vague de suivi", max_length=3, choices=VAGUES)
    date_suivi = models.DateField("Date du contact")
    enqueteur = models.CharField("Enquêteur", max_length=150, blank=True)

    issue_contact = models.CharField("Issue du contact", max_length=20, choices=ISSUES_CONTACT)

    # Renseigné uniquement si issue_contact == "joint"
    situation_actuelle = models.CharField("Situation actuelle", max_length=20, choices=SITUATIONS_ACTUELLES, blank=True)
    type_contrat = models.CharField("Type de contrat", max_length=20, choices=TYPES_CONTRAT, blank=True)
    secteur_activite = models.CharField("Secteur d'activité", max_length=150, blank=True)
    date_debut_activite = models.DateField("Date de début d'activité", null=True, blank=True)
    tranche_revenu = models.CharField("Tranche de revenu", max_length=20, choices=TRANCHES_REVENU, blank=True)
    lien_formation = models.CharField("Lien avec la formation", max_length=20, choices=LIENS_FORMATION, blank=True)
    obstacle_principal = models.TextField("Principal obstacle rencontré", blank=True)

    class Meta:
        ordering = ["-date_suivi"]
        unique_together = [("beneficiaire", "vague")]

    def __str__(self):
        return f"{self.beneficiaire_id} - {self.get_vague_display()}"

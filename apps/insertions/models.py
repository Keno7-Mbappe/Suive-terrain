from django.db import models

SITUATIONS_PRO = [
    ("emploi_salarie", "Emploi salarié"),
    ("auto_emploi", "Auto-emploi"),
    ("stage", "Stage"),
    ("en_recherche", "En recherche"),
]


class Insertion(models.Model):
    beneficiaire = models.ForeignKey(
        "beneficiaires.Beneficiaire", on_delete=models.CASCADE, related_name="insertions",
        verbose_name="Bénéficiaire",
    )
    situation_prof = models.CharField("Situation professionnelle", max_length=20, choices=SITUATIONS_PRO)
    secteur_activite = models.CharField("Secteur d'activité", max_length=150, blank=True)
    intitule_poste = models.CharField("Intitulé du poste", max_length=150, blank=True)
    date_insertion = models.DateField("Date d'insertion", null=True, blank=True)
    delai_insertion_mois = models.PositiveIntegerField("Délai d'insertion (mois)", null=True, blank=True)

    class Meta:
        ordering = ["-date_insertion"]

    def __str__(self):
        return f"{self.beneficiaire_id} - {self.get_situation_prof_display()}"

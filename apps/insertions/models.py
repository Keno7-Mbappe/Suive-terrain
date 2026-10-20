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

    # Suivi des stagiaires (situation_prof == "stage") : la structure d'accueil et
    # l'encadrant ne concernent que les stages, mais un champ texte libre ne coûte
    # rien à laisser vide pour les autres situations professionnelles.
    structure_accueil = models.CharField("Structure d'accueil", max_length=150, blank=True)
    nom_encadrant = models.CharField("Nom de l'encadrant / maître de stage", max_length=150, blank=True)
    date_fin_stage = models.DateField("Date de fin de stage", null=True, blank=True)

    # Cf. Suivi.soumission_kobo : supprimer la soumission supprime aussi cette ligne.
    soumission_kobo = models.ForeignKey(
        "imports.KoboSoumission", on_delete=models.CASCADE, null=True, blank=True,
        related_name="insertions_creees", editable=False,
    )

    class Meta:
        ordering = ["-date_insertion"]

    def __str__(self):
        return f"{self.beneficiaire_id} - {self.get_situation_prof_display()}"

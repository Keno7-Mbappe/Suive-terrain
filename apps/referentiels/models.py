from django.db import models

REGIONS = [
    ("djibouti", "Djibouti"),
    ("ali_sabieh", "Ali Sabieh"),
    ("arta", "Arta"),
    ("dikhil", "Dikhil"),
    ("tadjourah", "Tadjourah"),
    ("obock", "Obock"),
]

TYPES_INSTITUTION = [
    ("eftp", "EFTP"),
    ("inap", "INAP"),
    ("anefip", "ANEFIP"),
    ("oneq", "ONEQ"),
    ("direction_projets", "Direction des Projets (MENFOP)"),
    ("autre", "Autre"),
]


class Institution(models.Model):
    libelle = models.CharField("Libellé", max_length=255)
    type = models.CharField("Type", max_length=30, choices=TYPES_INSTITUTION)
    region = models.CharField("Région", max_length=30, choices=REGIONS)

    class Meta:
        ordering = ["libelle"]
        verbose_name = "Institution"
        verbose_name_plural = "Institutions"

    def __str__(self):
        return self.libelle


class CycleEnquete(models.Model):
    libelle = models.CharField("Libellé", max_length=100)
    date_debut = models.DateField("Date de début")
    date_fin = models.DateField("Date de fin")

    class Meta:
        ordering = ["date_debut"]
        verbose_name = "Cycle d'enquête"
        verbose_name_plural = "Cycles d'enquête"

    def __str__(self):
        return self.libelle

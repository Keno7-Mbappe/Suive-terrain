from datetime import date

from django.db import models, transaction
from django.utils.dateparse import parse_date

from apps.referentiels.models import REGIONS

SEXES = [("M", "Masculin"), ("F", "Féminin")]

STATUTS = [
    ("actif", "Actif"),
    ("abandon", "Abandon"),
    ("archive", "Archivé"),
]


def _classer_tranche_age(age):
    if age < 20:
        return "<20"
    if age <= 30:
        return "20-30"
    if age <= 40:
        return "31-40"
    if age <= 50:
        return "41-50"
    return ">50"


class SequenceAnnuelle(models.Model):
    """Compteur atomique par année, utilisé pour générer les identifiants B-AAAA-NNNN."""

    annee = models.PositiveIntegerField("Année", unique=True)
    dernier_numero = models.PositiveIntegerField("Dernier numéro attribué", default=0)

    class Meta:
        verbose_name = "Compteur annuel d'identifiants"
        verbose_name_plural = "Compteurs annuels d'identifiants"

    def __str__(self):
        return f"{self.annee}: {self.dernier_numero:04d}"


class Beneficiaire(models.Model):
    id_beneficiaire = models.CharField("Identifiant", max_length=20, primary_key=True, editable=False)
    nom = models.CharField("Nom", max_length=100)
    prenom = models.CharField("Prénom", max_length=100)
    sexe = models.CharField("Sexe", max_length=1, choices=SEXES)
    date_naissance = models.DateField("Date de naissance")
    tranche_age = models.CharField("Tranche d'âge", max_length=10, editable=False, blank=True)
    region = models.CharField("Région", max_length=30, choices=REGIONS)
    institution = models.ForeignKey(
        "referentiels.Institution", on_delete=models.PROTECT, related_name="beneficiaires",
        verbose_name="Institution",
    )
    telephone = models.CharField("Téléphone", max_length=20, blank=True)
    email = models.EmailField("E-mail", blank=True)
    date_enregistrement = models.DateField("Date d'enregistrement", default=date.today)
    statut = models.CharField("Statut", max_length=20, choices=STATUTS, default="actif")

    class Meta:
        ordering = ["-date_enregistrement"]
        indexes = [models.Index(fields=["nom", "prenom", "date_naissance"])]

    def __str__(self):
        return f"{self.id_beneficiaire} - {self.nom} {self.prenom}"

    def _compute_tranche_age(self):
        naissance, reference = self.date_naissance, self.date_enregistrement
        age = reference.year - naissance.year
        if (reference.month, reference.day) < (naissance.month, naissance.day):
            age -= 1
        return _classer_tranche_age(age)

    @staticmethod
    def _generer_identifiant(annee):
        with transaction.atomic():
            compteur, _ = SequenceAnnuelle.objects.select_for_update().get_or_create(annee=annee)
            compteur.dernier_numero += 1
            compteur.save(update_fields=["dernier_numero"])
            return f"B-{annee}-{compteur.dernier_numero:04d}"

    @classmethod
    def trouver_doublons_potentiels(cls, nom, prenom, date_naissance):
        return cls.objects.filter(nom__iexact=nom, prenom__iexact=prenom, date_naissance=date_naissance)

    @classmethod
    def groupes_doublons(cls, queryset=None):
        """Regroupe les bénéficiaires partageant nom+prénom+date de naissance
        (indicateur de qualité de données : doublons potentiels)."""
        queryset = cls.objects.all() if queryset is None else queryset
        return (
            queryset.values("nom", "prenom", "date_naissance")
            .annotate(occurrences=models.Count("id_beneficiaire"))
            .filter(occurrences__gt=1)
        )

    def save(self, *args, **kwargs):
        # Les imports (Kobo, Excel EFTP/INAP/ANEFIP) fournissent souvent des dates sous
        # forme de chaînes ISO plutôt que d'objets `date` : on les normalise ici plutôt
        # que de supposer qu'elles passent toujours par un ModelForm.
        if isinstance(self.date_naissance, str):
            self.date_naissance = parse_date(self.date_naissance)
        if isinstance(self.date_enregistrement, str):
            self.date_enregistrement = parse_date(self.date_enregistrement)
        if not self.id_beneficiaire:
            self.id_beneficiaire = self._generer_identifiant(self.date_enregistrement.year)
        self.tranche_age = self._compute_tranche_age()
        super().save(*args, **kwargs)

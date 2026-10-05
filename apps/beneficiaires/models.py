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
    if age is None:
        return ""
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
    # Certains imports en masse (listes nominatives institutionnelles) n'ont pas toujours
    # ces deux informations pour chaque personne : plutôt que d'inventer une valeur ou de
    # rejeter le bénéficiaire, on accepte "non renseigné" (chaîne vide / date nulle).
    sexe = models.CharField("Sexe", max_length=1, choices=SEXES, blank=True)
    date_naissance = models.DateField("Date de naissance", null=True, blank=True)
    tranche_age = models.CharField("Tranche d'âge", max_length=10, editable=False, blank=True)
    region = models.CharField("Région", max_length=30, choices=REGIONS)
    quartier = models.CharField("Quartier / localité", max_length=100, blank=True)
    niveau_etude = models.CharField("Niveau d'étude", max_length=100, blank=True)
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
        if naissance is None:
            return ""
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
    def trouver_doublons_potentiels(cls, nom, prenom, date_naissance, institution=None):
        """`institution` restreint la recherche à cette seule institution : à utiliser
        pour l'import d'une liste nominative, où un homonyme dans une AUTRE institution
        n'est presque toujours pas la même personne, et où traiter un tel homonyme comme
        "le même bénéficiaire" écraserait à tort son institution d'origine (incident
        constaté à l'import de la liste DGFP, qui a réassigné un bénéficiaire ANEFIP).
        Laissé à None (par défaut) pour les usages qui doivent au contraire repérer ces
        homonymes inter-institutions afin qu'un humain les vérifie (formulaire de saisie,
        indicateur qualité du tableau de bord)."""
        if date_naissance is None:
            # Sans date de naissance, (nom, prénom) seuls ne permettent une correspondance
            # fiable qu'à l'intérieur d'une même institution (sinon deux personnes
            # différentes portant le même nom seraient confondues à tort, cf. ci-dessus) -
            # et seulement avec une autre ligne elle aussi sans date de naissance connue,
            # pour ne jamais réécrire par erreur une fiche dont la date est déjà connue.
            # Nécessaire pour qu'un ré-import du même fichier (ex. reprise après coupure
            # réseau) mette à jour plutôt que de dupliquer ces bénéficiaires-là aussi.
            if institution is None:
                return cls.objects.none()
            return cls.objects.filter(
                nom__iexact=nom, prenom__iexact=prenom, institution=institution, date_naissance__isnull=True
            )
        qs = cls.objects.filter(nom__iexact=nom, prenom__iexact=prenom, date_naissance=date_naissance)
        if institution is not None:
            qs = qs.filter(institution=institution)
        return qs

    @classmethod
    def groupes_doublons(cls, queryset=None):
        """Regroupe les bénéficiaires partageant nom+prénom+date de naissance ET au
        moins une formation en commun (indicateur de qualité de données : doublons
        potentiels). Même nom + même date de naissance ne suffit pas à lui seul : si
        les formations suivies sont différentes, c'est presque toujours un homonyme,
        pas un doublon de saisie - même principe que le dédoublonnage de l'import (cf.
        `trouver_doublons_potentiels` et l'incident DGFP où 28 homonymes sur 34
        suivaient en réalité des formations sans rapport). Un homonyme sans aucune
        formation connue (le sien ou celle de son homonyme) reste signalé par prudence,
        faute d'information pour les distinguer."""
        queryset = cls.objects.all() if queryset is None else queryset
        candidats = (
            queryset.exclude(date_naissance__isnull=True)
            .values("nom", "prenom", "date_naissance")
            .annotate(occurrences=models.Count("id_beneficiaire"))
            .filter(occurrences__gt=1)
        )
        confirmes = []
        for groupe in candidats:
            membres = list(queryset.filter(
                nom=groupe["nom"], prenom=groupe["prenom"], date_naissance=groupe["date_naissance"],
            ))
            domaines_par_membre = [
                set(m.formations.exclude(domaine="").values_list("domaine", flat=True)) for m in membres
            ]
            parent = list(range(len(membres)))

            def trouver(i, parent=parent):
                while parent[i] != i:
                    parent[i] = parent[parent[i]]
                    i = parent[i]
                return i

            for i in range(len(membres)):
                for j in range(i + 1, len(membres)):
                    if not domaines_par_membre[i] or not domaines_par_membre[j] or (domaines_par_membre[i] & domaines_par_membre[j]):
                        ri, rj = trouver(i), trouver(j)
                        if ri != rj:
                            parent[ri] = rj

            if len({trouver(i) for i in range(len(membres))}) == 1:
                confirmes.append(groupe)
        return confirmes

    def save(self, *args, **kwargs):
        # Les imports (Kobo, Excel DGFP/INAP/ANEFIP) fournissent souvent des dates sous
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

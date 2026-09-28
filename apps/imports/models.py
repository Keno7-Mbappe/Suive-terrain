from django.conf import settings
from django.db import models

TYPES_FORMULAIRE = [
    # "suivi" inclut la satisfaction bénéficiaire (module optionnel de la même
    # soumission Kobo) : pas de type "satisfaction" séparé.
    ("suivi", "Suivi et satisfaction bénéficiaire"),
    ("satisfaction_institution", "Satisfaction institutionnelle"),
]

STATUTS_TRAITEMENT = [
    ("nouveau", "À valider"),
    ("integre", "Intégré"),
    ("doublon", "Écartée"),
    ("erreur", "Erreur"),
]


class KoboSoumission(models.Model):
    """Copie d'une soumission KoboToolbox, en attente de contrôle humain avant son
    intégration dans les tables de production (bénéficiaires, suivis, satisfactions...).

    `donnees_brutes` reste toujours la version reçue de Kobo, jamais modifiée (trace
    d'audit). Si un validateur corrige la soumission, ses corrections sont stockées
    à part dans `donnees_corrigees`, et c'est cette version corrigée qui est intégrée.
    """

    type_formulaire = models.CharField("Type de formulaire", max_length=30, choices=TYPES_FORMULAIRE)
    kobo_submission_id = models.CharField("Identifiant de soumission Kobo", max_length=50)
    donnees_brutes = models.JSONField("Données brutes")
    donnees_corrigees = models.JSONField("Données corrigées", null=True, blank=True)
    institution = models.ForeignKey(
        "referentiels.Institution", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="soumissions_kobo", verbose_name="Institution concernée",
    )
    statut = models.CharField("Statut", max_length=20, choices=STATUTS_TRAITEMENT, default="nouveau")
    erreur = models.TextField("Erreur", blank=True)
    recu_le = models.DateTimeField("Reçu le", auto_now_add=True)
    traite_le = models.DateTimeField("Traité le", null=True, blank=True)
    traite_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="+", verbose_name="Traité par",
    )

    class Meta:
        unique_together = [("type_formulaire", "kobo_submission_id")]
        ordering = ["-recu_le"]
        verbose_name = "Soumission Kobo"
        verbose_name_plural = "Soumissions Kobo"

    def __str__(self):
        return f"{self.get_type_formulaire_display()} #{self.kobo_submission_id} ({self.statut})"

    @property
    def donnees_effectives(self):
        """La version à intégrer : corrigée par un validateur si elle existe, sinon brute."""
        return self.donnees_corrigees if self.donnees_corrigees is not None else self.donnees_brutes

    @property
    def est_corrigee(self):
        return self.donnees_corrigees is not None

    @property
    def cle_personne(self):
        """Clé Kobo identifiant la personne (ou la structure) concernée par cette soumission."""
        return "selection/id_beneficiaire" if self.type_formulaire == "suivi" else "identification/institution"

    @property
    def personne_concernee(self):
        """Libellé court lisible : « B-2026-0001 · Prénom Nom » ou le code de l'institution."""
        donnees = self.donnees_effectives
        identifiant = donnees.get(self.cle_personne) or "—"
        nom = donnees.get("selection/nom_prenom") if self.type_formulaire == "suivi" else ""
        return f"{identifiant} · {nom}" if nom else identifiant

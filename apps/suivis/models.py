from django.db import models

VAGUES = [("m3", "M+3"), ("m6", "M+6"), ("m12", "M+12")]

CANAUX_CONTACT = [
    ("telephone", "Appel téléphonique"),
    ("visite", "Visite"),
    ("structure", "Remontée de la structure de formation"),
]

ISSUES_CONTACT = [
    ("joint", "Joint"),
    ("injoignable", "Injoignable après trois tentatives"),
    ("numero_errone", "Numéro erroné"),
    ("refus", "Refus de répondre"),
]

SITUATIONS_ACTUELLES = [
    ("emploi", "Emploi salarié"),
    ("auto_emploi", "Auto-emploi"),
    ("stage", "Stage"),
    ("formation", "Reparti en formation"),
    ("recherche", "En recherche d'emploi"),
    ("inactif", "Sans activité et sans recherche"),
]

TYPES_CONTRAT = [
    ("CDI", "CDI"),
    ("CDD", "CDD"),
    ("journalier", "Travail journalier"),
    ("stage_convention", "Stage conventionné"),
]

TYPES_ACTIVITE = [
    ("commerce", "Commerce"),
    ("artisanat", "Artisanat"),
    ("services", "Services"),
    ("agriculture_peche", "Agriculture ou pêche"),
    ("autre", "Autre"),
]

SECTEURS = [
    ("commerce", "Commerce"),
    ("batiment", "Bâtiment et travaux publics"),
    ("administration", "Administration publique"),
    ("telecom", "Télécommunications et numérique"),
    ("transport", "Transport et logistique"),
    ("hotellerie", "Hôtellerie et restauration"),
    ("sante_education", "Santé ou éducation"),
    ("banque", "Banque et assurance"),
    ("artisanat", "Artisanat"),
    ("autre", "Autre secteur"),
]

TRANCHES_REVENU = [
    ("moins_30k", "< 30 000 DJF"),
    ("30_60k", "30 000 - 60 000 DJF"),
    ("60_100k", "60 000 - 100 000 DJF"),
    ("plus_100k", "> 100 000 DJF"),
    ("refus", "Ne souhaite pas répondre"),
]

LIENS_FORMATION = [
    ("direct", "Direct"),
    ("partiel", "Partiel"),
    ("aucun", "Aucun"),
]

DEMARCHES = [
    ("candidatures", "Envoi de candidatures"),
    ("anefip", "Inscription à l'ANEFIP"),
    ("reseau", "Mobilisation du réseau personnel"),
    ("creation", "Démarches de création d'activité"),
    ("aucune", "Aucune démarche"),
]


class Suivi(models.Model):
    beneficiaire = models.ForeignKey(
        "beneficiaires.Beneficiaire", on_delete=models.CASCADE, related_name="suivis",
        verbose_name="Bénéficiaire",
    )
    vague = models.CharField("Vague de suivi", max_length=3, choices=VAGUES)
    date_suivi = models.DateField("Date du contact")
    canal = models.CharField("Canal du contact", max_length=20, choices=CANAUX_CONTACT, blank=True)
    enqueteur = models.CharField("Enquêteur", max_length=150, blank=True)

    issue_contact = models.CharField("Issue du contact", max_length=20, choices=ISSUES_CONTACT)

    # Renseigné uniquement si issue_contact == "joint"
    situation_actuelle = models.CharField("Situation actuelle", max_length=20, choices=SITUATIONS_ACTUELLES, blank=True)
    type_contrat = models.CharField("Type de contrat", max_length=20, choices=TYPES_CONTRAT, blank=True)
    type_activite = models.CharField(
        "Type d'activité (auto-emploi)", max_length=20, choices=TYPES_ACTIVITE, blank=True
    )
    secteur_activite = models.CharField("Secteur d'activité", max_length=20, choices=SECTEURS, blank=True)
    date_debut_activite = models.DateField("Date de début d'activité", null=True, blank=True)
    tranche_revenu = models.CharField("Tranche de revenu", max_length=20, choices=TRANCHES_REVENU, blank=True)
    lien_formation = models.CharField("Lien avec la formation", max_length=20, choices=LIENS_FORMATION, blank=True)

    # Renseigné uniquement si situation_actuelle == "recherche"
    duree_recherche_mois = models.PositiveIntegerField(
        "Durée de recherche (mois)", null=True, blank=True
    )
    demarches = models.CharField(
        "Démarches entreprises", max_length=200, blank=True,
        help_text="Codes séparés par un espace, au format brut des questions à choix multiples Kobo.",
    )

    obstacle_principal = models.TextField("Principal obstacle rencontré", blank=True)

    class Meta:
        ordering = ["-date_suivi"]
        unique_together = [("beneficiaire", "vague")]

    def __str__(self):
        return f"{self.beneficiaire_id} - {self.get_vague_display()}"

    def get_demarches_display_list(self):
        codes = self.demarches.split()
        libelles = dict(DEMARCHES)
        return [libelles.get(code, code) for code in codes]

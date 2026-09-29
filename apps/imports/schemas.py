"""Description déclarative des champs des formulaires Kobo, pour les afficher en
clair (libellés + réponses lisibles) et les rendre corrigeables dans l'écran de
validation des soumissions - sans avoir à interpréter à la main du JSON brut.

Les clés (« selection/canal », « module_suivi/situation »...) sont exactement celles
des soumissions telles que renvoyées par l'API Kobo : le nom de chaque groupe du
formulaire est préfixé à la question. Elles doivent rester alignées avec
`KOBO_FIELDS_*` de `services.py` et avec le XLSForm de `generate_kobo_xlsforms`.
"""

from collections import namedtuple
from datetime import date

from apps.satisfactions.models import AMELIORATIONS_EMPLOYABILITE, UTILITE_DISPOSITIF
from apps.suivis.models import (
    CANAUX_CONTACT,
    DEMARCHES,
    ISSUES_CONTACT,
    LIENS_FORMATION,
    SECTEURS,
    SITUATIONS_ACTUELLES,
    TRANCHES_REVENU,
    TYPES_ACTIVITE,
    TYPES_CONTRAT,
    VAGUES,
)

Champ = namedtuple("Champ", "cle libelle type choix obligatoire", defaults=(None, False))

OUI_NON = [("oui", "Oui"), ("non", "Non")]
CYCLES = [
    ("cycle_1", "Cycle 1 – novembre 2026"),
    ("cycle_2", "Cycle 2 – mai 2027"),
    ("cycle_3", "Cycle 3 – novembre 2027"),
]
ECHELLE_5 = [
    ("1", "1 – Pas du tout satisfait"),
    ("2", "2 – Peu satisfait"),
    ("3", "3 – Moyennement satisfait"),
    ("4", "4 – Satisfait"),
    ("5", "5 – Très satisfait"),
]
INSTITUTIONS = [
    ("INAP", "INAP"),
    ("DGFP", "DGFP"),
    ("ANEFIP", "ANEFIP"),
]
# Codes d'institution des formulaires Kobo -> valeur du champ `type` de Institution.
TYPE_INSTITUTION_PAR_CODE = {
    "INAP": "inap", "DGFP": "dgfp", "ANEFIP": "anefip",
}

SECTIONS = {
    "suivi": [
        ("Bénéficiaire et contact", [
            Champ("selection/id_beneficiaire", "Identifiant du bénéficiaire", "texte", obligatoire=True),
            Champ("selection/canal", "Canal du contact", "choix", CANAUX_CONTACT, True),
            Champ("selection/date_contact", "Date du contact", "date", obligatoire=True),
            Champ("issue_contact", "Issue du contact", "choix", ISSUES_CONTACT, True),
        ]),
        ("Module 1 – Suivi de la situation", [
            Champ("module_suivi/vague", "Vague de suivi", "choix", VAGUES),
            Champ("module_suivi/situation", "Situation aujourd'hui", "choix", SITUATIONS_ACTUELLES),
            Champ("module_suivi/type_contrat", "Type de contrat", "choix", TYPES_CONTRAT),
            Champ("module_suivi/type_activite", "Type d'activité exercée", "choix", TYPES_ACTIVITE),
            Champ("module_suivi/secteur", "Secteur d'activité", "choix", SECTEURS),
            Champ("module_suivi/date_debut_activite", "Date de début de l'activité", "date"),
            Champ("module_suivi/revenu_tranche", "Tranche de revenu mensuel", "choix", TRANCHES_REVENU),
            Champ("module_suivi/lien_formation", "Lien avec la formation suivie", "choix", LIENS_FORMATION),
            Champ("module_suivi/duree_recherche_mois", "Durée de recherche d'emploi (mois)", "entier"),
            Champ("module_suivi/demarches", "Démarches entreprises", "choix_multiple", DEMARCHES),
            Champ("module_suivi/obstacle", "Principal obstacle rencontré", "texte_long"),
        ]),
        ("Module 2 – Satisfaction", [
            Champ("bascule/faire_satisfaction", "Module satisfaction réalisé ?", "choix", OUI_NON),
            Champ("bascule/cycle", "Cycle d'enquête", "choix", CYCLES),
            Champ("bascule/note_formation", "La formation dans son ensemble", "choix", ECHELLE_5),
            Champ("bascule/note_formateurs", "Les formateurs", "choix", ECHELLE_5),
            Champ("bascule/note_contenus", "Les contenus pédagogiques", "choix", ECHELLE_5),
            Champ("bascule/note_equipements", "Les équipements et le matériel", "choix", ECHELLE_5),
            Champ("bascule/note_conditions", "Les conditions d'accueil", "choix", ECHELLE_5),
            Champ("bascule/employabilite", "La formation a amélioré l'employabilité", "choix",
                  AMELIORATIONS_EMPLOYABILITE),
            Champ("bascule/recommande", "Recommanderait la formation", "choix", OUI_NON),
            Champ("bascule/raison_non", "Pourquoi ne la recommanderait pas", "texte_long"),
            Champ("bascule/point_fort", "Ce qui a le mieux fonctionné", "texte_long"),
            Champ("bascule/point_amelioration", "Ce qu'il faudrait améliorer", "texte_long"),
        ]),
        ("Observations de l'enquêteur", [
            Champ("observations", "Observations", "texte_long"),
        ]),
    ],
    "satisfaction_institution": [
        ("Identification du répondant", [
            Champ("identification/institution", "Institution", "choix", INSTITUTIONS, True),
            Champ("identification/fonction", "Fonction du répondant", "texte"),
            Champ("identification/cycle", "Cycle d'enquête", "choix", CYCLES, True),
            Champ("identification/date_reponse", "Date de la réponse", "date"),
        ]),
        ("Appréciation du dispositif de suivi (notes de 1 à 5)", [
            Champ("notes/note_qualite_donnees", "Qualité et fiabilité des données", "choix", ECHELLE_5),
            Champ("notes/note_outils_collecte", "Outils de collecte mis à disposition", "choix", ECHELLE_5),
            Champ("notes/note_tableaux_bord", "Utilité des tableaux de bord", "choix", ECHELLE_5),
            Champ("notes/note_appui_technique", "Appui technique reçu", "choix", ECHELLE_5),
            Champ("notes/note_coordination", "Coordination entre les structures", "choix", ECHELLE_5),
        ]),
        ("Bilan", [
            Champ("utilite_dispositif", "Le dispositif répond-il aux besoins de la structure ?", "choix",
                  UTILITE_DISPOSITIF),
            Champ("difficultes", "Difficultés rencontrées", "texte_long"),
            Champ("recommandations", "Recommandations d'amélioration", "texte_long"),
        ]),
    ],
}

# Champs calculés par le formulaire Kobo à partir de la liste embarquée de
# bénéficiaires (rappel affiché à l'enquêteur) : affichés en lecture seule.
RAPPEL_SUIVI = [
    ("selection/nom_prenom", "Nom et prénom (liste Kobo)"),
    ("selection/institution", "Institution (liste Kobo)"),
    ("selection/region", "Région (liste Kobo)"),
    ("selection/date_fin_formation", "Fin de formation (liste Kobo)"),
    ("selection/mois_ecoules", "Mois écoulés depuis la fin de formation"),
    ("selection/telephone", "Téléphone (liste Kobo)"),
]

METADONNEES = [
    ("enqueteur", "Compte de l'enquêteur"),
    ("horodatage_debut", "Début de la saisie"),
    ("horodatage_fin", "Fin de la saisie"),
    ("date_du_jour", "Date du jour"),
    ("date_debut", "Début de la saisie"),
    ("date_fin", "Fin de la saisie"),
    ("appareil", "Appareil"),
    ("_submission_time", "Reçu par Kobo le"),
    ("_id", "Identifiant Kobo"),
]


def sections_pour(type_formulaire):
    return SECTIONS[type_formulaire]


def tous_les_champs(type_formulaire):
    return [champ for _, champs in SECTIONS[type_formulaire] for champ in champs]


def libelle_choix(champ, valeur):
    """Traduit un code Kobo en libellé lisible (les codes inconnus restent tels quels)."""
    if champ.type == "choix_multiple":
        codes = str(valeur or "").split()
        libelles = dict(champ.choix)
        return ", ".join(libelles.get(code, code) for code in codes)
    if champ.type == "choix":
        return dict((str(c), lib) for c, lib in champ.choix).get(str(valeur), str(valeur))
    if champ.type == "date":
        try:
            return date.fromisoformat(str(valeur)[:10]).strftime("%d/%m/%Y")
        except ValueError:
            return str(valeur)
    return str(valeur)


def lignes_lisibles(type_formulaire, donnees):
    """Pour l'affichage : [(titre de section, [(libellé, valeur lisible ou None, clé)])]."""
    resultat = []
    for titre, champs in SECTIONS[type_formulaire]:
        lignes = []
        for champ in champs:
            valeur = donnees.get(champ.cle)
            lisible = libelle_choix(champ, valeur) if valeur not in (None, "") else None
            lignes.append((champ.libelle, lisible, champ.cle))
        resultat.append((titre, lignes))
    return resultat


def vague_suggeree(donnees):
    """Vague de suivi la plus proche du nombre de mois écoulés depuis la fin de formation
    (le formulaire ne demande pas la vague quand le contact échoue)."""
    try:
        mois = int(donnees.get("selection/mois_ecoules"))
    except (TypeError, ValueError):
        return ""
    return min([("m3", 3), ("m6", 6), ("m12", 12)], key=lambda v: abs(v[1] - mois))[0]

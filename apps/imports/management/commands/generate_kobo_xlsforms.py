"""Génère les formulaires KoboToolbox (format XLSForm, prêts à importer via
"New > Upload XLSForm") : suivi longitudinal + satisfaction bénéficiaire
fusionnés en un seul questionnaire, et satisfaction institutionnelle.

La structure (groupes, questions, choix, calculs) reprend celle du
questionnaire de référence conçu et déjà déployé/testé (4 vraies soumissions)
sur KoboToolbox - retranscrite ici pour que le dépôt du projet reste la
source de vérité versionnée, plutôt que de dépendre d'un projet Kobo externe
non versionné.

Les noms de champs ("name") sont repris tels quels dans
`apps/imports/services.py` (KOBO_FIELDS_*), chemins de groupe inclus
("selection/canal", "module_suivi/situation", "bascule/note_formation"...) :
un formulaire importé sans modification produira des soumissions que
`manage.py sync_kobo` sait déjà intégrer, sans aucun ajustement de code.

La liste "beneficiaires" n'est PAS codée en dur : elle pointe vers un CSV
externe (select_one_from_file, généré par `export_kobo_choices`) qui inclut,
au-delà de "name"/"label", des colonnes supplémentaires (nom_prenom,
institution, region, date_fin_formation, telephone) exploitées par des
questions "calculate" pour afficher un récapitulatif du bénéficiaire dès sa
sélection - technique confirmée fonctionnelle sur le questionnaire de
référence, alors qu'elle avait été mise de côté par prudence dans une version
précédente.
"""

from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from openpyxl import Workbook

from apps.satisfactions.models import AMELIORATIONS_EMPLOYABILITE, NOTES, UTILITE_DISPOSITIF
from apps.suivis.models import (
    CANAUX_CONTACT,
    DEMARCHES,
    ISSUES_CONTACT,
    LIENS_FORMATION,
    SITUATIONS_ACTUELLES,
    SECTEURS,
    TRANCHES_REVENU,
    TYPES_ACTIVITE,
    TYPES_CONTRAT,
    VAGUES,
)

ENTETES_SURVEY = [
    "type", "name", "label", "hint", "required", "relevant",
    "constraint", "constraint_message", "default", "calculation", "appearance",
]
ENTETES_CHOICES = ["list_name", "name", "label"]
ENTETES_SETTINGS = ["form_title", "form_id", "default_language"]

OUI_NON = [("oui", "Oui"), ("non", "Non")]

CYCLES_KOBO = [
    ("cycle_1", "Cycle 1 – novembre 2026"),
    ("cycle_2", "Cycle 2 – mai 2027"),
    ("cycle_3", "Cycle 3 – novembre 2027"),
]


def _ecrire_feuille(classeur, nom_feuille, entetes, lignes):
    feuille = classeur.create_sheet(nom_feuille)
    feuille.append(entetes)
    for ligne in lignes:
        feuille.append([ligne.get(colonne, "") for colonne in entetes])
    return feuille


def _construire_classeur(titre, form_id, survey_rows, choices_lists):
    classeur = Workbook()
    classeur.remove(classeur.active)
    _ecrire_feuille(classeur, "survey", ENTETES_SURVEY, survey_rows)
    lignes_choices = []
    for list_name, options in choices_lists.items():
        for name, label in options:
            lignes_choices.append({"list_name": list_name, "name": name, "label": label})
    _ecrire_feuille(classeur, "choices", ENTETES_CHOICES, lignes_choices)
    _ecrire_feuille(
        classeur, "settings", ENTETES_SETTINGS,
        [{"form_title": titre, "form_id": form_id, "default_language": "Français (fr)"}],
    )
    return classeur


def _calcul_beneficiaire(colonne):
    return f"instance('beneficiaires')/root/item[name=current()/../id_beneficiaire]/{colonne}"


def _formulaire_suivi_et_satisfaction():
    joint = "selected(${issue_contact}, 'joint')"
    survey = [
        {"type": "start", "name": "horodatage_debut"},
        {"type": "end", "name": "horodatage_fin"},
        {"type": "today", "name": "date_du_jour"},
        {"type": "deviceid", "name": "appareil"},
        {"type": "username", "name": "enqueteur"},

        {"type": "begin_group", "name": "selection", "label": "Sélection du bénéficiaire"},
        {"type": "note", "name": "consigne_selection",
         "label": "Recherchez la personne dans la liste. Aucune information la concernant n'est à saisir : "
                   "tout est repris de la liste intégrée au formulaire."},
        {"type": "select_one_from_file beneficiaires.csv", "name": "id_beneficiaire",
         "label": "Bénéficiaire", "required": "yes"},
        {"type": "calculate", "name": "nom_prenom", "calculation": _calcul_beneficiaire("nom_prenom")},
        {"type": "calculate", "name": "institution", "calculation": _calcul_beneficiaire("institution")},
        {"type": "calculate", "name": "region", "calculation": _calcul_beneficiaire("region")},
        {"type": "calculate", "name": "date_fin_formation", "calculation": _calcul_beneficiaire("date_fin_formation")},
        {"type": "calculate", "name": "telephone", "calculation": _calcul_beneficiaire("telephone")},
        {"type": "calculate", "name": "mois_ecoules",
         "calculation": "if(regex(${date_fin_formation}, '^[0-9]{4}-[0-9]{2}-[0-9]{2}$'), "
                         "int((today() - date(${date_fin_formation})) div 30.4), '')"},
        {"type": "note", "name": "recapitulatif",
         "label": "Bénéficiaire : ${nom_prenom} — ${institution} — ${region}\n"
                   "Fin de formation : ${date_fin_formation} — ${mois_ecoules} mois écoulés\n"
                   "Téléphone : ${telephone}",
         "relevant": "${id_beneficiaire} != ''"},
        {"type": "select_one canaux", "name": "canal", "label": "Canal du contact", "required": "yes"},
        {"type": "date", "name": "date_contact", "label": "Date du contact", "required": "yes",
         "default": "today()", "constraint": ". <= today()",
         "constraint_message": "La date du contact ne peut pas être dans le futur."},
        {"type": "end_group", "name": "selection"},

        {"type": "select_one issues_contact", "name": "issue_contact", "label": "Issue du contact",
         "required": "yes",
         "hint": "Enregistré même en cas d'échec : c'est ce qui donne le taux de joignabilité."},
        {"type": "note", "name": "note_echec",
         "label": "Contact non abouti. Le questionnaire s'arrête ici : enregistrez et envoyez la soumission "
                   "telle quelle.",
         "relevant": f"${{issue_contact}} != 'joint'"},

        {"type": "begin_group", "name": "module_suivi", "label": "Module 1 – Suivi de la situation",
         "relevant": joint},
        {"type": "select_one vagues", "name": "vague", "label": "Vague de suivi", "required": "yes"},
        {"type": "select_one situations", "name": "situation", "label": "Quelle est votre situation aujourd'hui ?",
         "required": "yes"},
        {"type": "select_one types_contrat", "name": "type_contrat", "label": "Type de contrat",
         "relevant": "selected(${situation}, 'emploi')", "required": "yes"},
        {"type": "select_one types_activite", "name": "type_activite", "label": "Type d'activité exercée",
         "relevant": "selected(${situation}, 'auto_emploi')", "required": "yes"},
        {"type": "select_one secteurs", "name": "secteur", "label": "Secteur d'activité",
         "relevant": "selected(${situation}, 'emploi') or selected(${situation}, 'auto_emploi') "
                     "or selected(${situation}, 'stage')",
         "required": "yes"},
        {"type": "date", "name": "date_debut_activite", "label": "Date de début de l'activité",
         "relevant": "selected(${situation}, 'emploi') or selected(${situation}, 'auto_emploi') "
                     "or selected(${situation}, 'stage')",
         "required": "yes", "constraint": ". <= today()",
         "constraint_message": "La date de début ne peut pas être dans le futur."},
        {"type": "select_one tranches_revenu", "name": "revenu_tranche", "label": "Tranche de revenu mensuel",
         "relevant": "selected(${situation}, 'emploi') or selected(${situation}, 'auto_emploi')"},
        {"type": "select_one liens_formation", "name": "lien_formation",
         "label": "Lien entre l'activité et la formation suivie",
         "relevant": "selected(${situation}, 'emploi') or selected(${situation}, 'auto_emploi') "
                     "or selected(${situation}, 'stage')",
         "required": "yes"},
        {"type": "integer", "name": "duree_recherche_mois", "label": "Depuis combien de mois êtes-vous en recherche ?",
         "relevant": "selected(${situation}, 'recherche')", "required": "yes"},
        {"type": "select_multiple demarches", "name": "demarches", "label": "Démarches entreprises",
         "relevant": "selected(${situation}, 'recherche')"},
        {"type": "text", "name": "obstacle", "label": "Principal obstacle rencontré"},
        {"type": "end_group", "name": "module_suivi"},

        {"type": "begin_group", "name": "bascule", "label": "Module 2 – Satisfaction", "relevant": joint},
        {"type": "select_one oui_non", "name": "faire_satisfaction",
         "label": "Réaliser le module satisfaction lors de ce contact ?", "required": "yes"},
        {"type": "select_one cycles", "name": "cycle", "label": "Cycle d'enquête",
         "relevant": "selected(${faire_satisfaction}, 'oui')", "required": "yes"},
        {"type": "note", "name": "consigne_notes",
         "label": "Sur une échelle de 1 à 5, où 1 signifie « pas du tout satisfait » et 5 « très satisfait », "
                   "comment évaluez-vous les éléments suivants ?",
         "relevant": "selected(${faire_satisfaction}, 'oui')"},
        {"type": "select_one echelle_5", "name": "note_formation", "label": "La formation dans son ensemble",
         "relevant": "selected(${faire_satisfaction}, 'oui')", "required": "yes"},
        {"type": "select_one echelle_5", "name": "note_formateurs", "label": "Les formateurs",
         "relevant": "selected(${faire_satisfaction}, 'oui')", "required": "yes"},
        {"type": "select_one echelle_5", "name": "note_contenus", "label": "Les contenus pédagogiques",
         "relevant": "selected(${faire_satisfaction}, 'oui')", "required": "yes"},
        {"type": "select_one echelle_5", "name": "note_equipements", "label": "Les équipements et le matériel",
         "relevant": "selected(${faire_satisfaction}, 'oui')", "required": "yes"},
        {"type": "select_one echelle_5", "name": "note_conditions", "label": "Les conditions d'accueil",
         "relevant": "selected(${faire_satisfaction}, 'oui')", "required": "yes"},
        {"type": "select_one amelioration", "name": "employabilite",
         "label": "La formation a-t-elle amélioré votre employabilité ?",
         "relevant": "selected(${faire_satisfaction}, 'oui')", "required": "yes"},
        {"type": "select_one oui_non", "name": "recommande",
         "label": "Recommanderiez-vous la formation à une autre personne ?",
         "relevant": "selected(${faire_satisfaction}, 'oui')", "required": "yes"},
        {"type": "text", "name": "raison_non", "label": "Pour quelle raison ?",
         "relevant": "selected(${recommande}, 'non')"},
        {"type": "text", "name": "point_fort", "label": "Qu'est-ce qui a le mieux fonctionné ?",
         "relevant": "selected(${faire_satisfaction}, 'oui')"},
        {"type": "text", "name": "point_amelioration", "label": "Qu'est-ce qu'il faudrait améliorer ?",
         "relevant": "selected(${faire_satisfaction}, 'oui')"},
        {"type": "end_group", "name": "bascule"},

        {"type": "text", "name": "observations", "label": "Observations de l'enquêteur"},
    ]
    choices = {
        "canaux": CANAUX_CONTACT,
        "issues_contact": ISSUES_CONTACT,
        "vagues": VAGUES,
        "situations": SITUATIONS_ACTUELLES,
        "types_contrat": TYPES_CONTRAT,
        "types_activite": TYPES_ACTIVITE,
        "secteurs": SECTEURS,
        "tranches_revenu": TRANCHES_REVENU,
        "liens_formation": LIENS_FORMATION,
        "demarches": DEMARCHES,
        "oui_non": OUI_NON,
        "cycles": CYCLES_KOBO,
        "echelle_5": NOTES,
        "amelioration": AMELIORATIONS_EMPLOYABILITE,
    }
    return _construire_classeur(
        "PDCED – Skills | Enquête terrain (suivi et satisfaction)", "pdced_suivi_satisfaction", survey, choices
    )


def _formulaire_satisfaction_institution():
    survey = [
        {"type": "start", "name": "date_debut"},
        {"type": "end", "name": "date_fin"},
        {"type": "today", "name": "date_du_jour"},
        {"type": "deviceid", "name": "appareil"},

        {"type": "begin_group", "name": "identification", "label": "Identification du répondant"},
        {"type": "select_one_from_file institutions.csv", "name": "institution", "label": "Institution",
         "required": "yes"},
        {"type": "text", "name": "fonction", "label": "Fonction du répondant"},
        {"type": "select_one cycles", "name": "cycle", "label": "Cycle d'enquête", "required": "yes"},
        {"type": "date", "name": "date_reponse", "label": "Date de la réponse", "default": "today()"},
        {"type": "end_group", "name": "identification"},

        {"type": "begin_group", "name": "notes", "label": "Appréciation du dispositif – notes de 1 à 5"},
        {"type": "select_one echelle_5", "name": "note_qualite_donnees",
         "label": "La qualité et la fiabilité des données", "required": "yes"},
        {"type": "select_one echelle_5", "name": "note_outils_collecte",
         "label": "Les outils de collecte mis à disposition", "required": "yes"},
        {"type": "select_one echelle_5", "name": "note_tableaux_bord",
         "label": "L'utilité des tableaux de bord", "required": "yes"},
        {"type": "select_one echelle_5", "name": "note_appui_technique",
         "label": "L'appui technique reçu", "required": "yes"},
        {"type": "select_one echelle_5", "name": "note_coordination",
         "label": "La coordination entre les structures", "required": "yes"},
        {"type": "end_group", "name": "notes"},

        {"type": "select_one utilite", "name": "utilite_dispositif",
         "label": "Le dispositif de suivi répond-il aux besoins de votre structure ?", "required": "yes"},
        {"type": "text", "name": "difficultes", "label": "Difficultés rencontrées dans l'utilisation du dispositif"},
        {"type": "text", "name": "recommandations", "label": "Recommandations d'amélioration"},
    ]
    choices = {
        "cycles": CYCLES_KOBO,
        "echelle_5": NOTES,
        "utilite": UTILITE_DISPOSITIF,
    }
    return _construire_classeur(
        "PDCED – Skills | Satisfaction institutionnelle", "pdced_satisfaction_institution", survey, choices
    )


class Command(BaseCommand):
    help = "Génère les fichiers XLSForm (suivi+satisfaction fusionnés, satisfaction institutionnelle)."

    def handle(self, *args, **options):
        dossier_sortie = Path(settings.BASE_DIR) / "kobo_forms"
        dossier_sortie.mkdir(parents=True, exist_ok=True)
        formulaires = {
            "suivi_et_satisfaction.xlsx": _formulaire_suivi_et_satisfaction(),
            "satisfaction_institution.xlsx": _formulaire_satisfaction_institution(),
        }
        for nom_fichier, classeur in formulaires.items():
            chemin = dossier_sortie / nom_fichier
            classeur.save(chemin)
            self.stdout.write(f"{nom_fichier} écrit")
        self.stdout.write(self.style.SUCCESS(f"{len(formulaires)} formulaires générés dans {dossier_sortie}"))

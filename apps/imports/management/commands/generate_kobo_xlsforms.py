"""Génère les 3 formulaires KoboToolbox (format XLSForm, prêts à importer via
"New > Upload XLSForm" dans l'interface Kobo) décrits dans la maquette du cahier
des charges (draft.docx) : suivi longitudinal, satisfaction bénéficiaire,
satisfaction institutionnelle.

Les noms de champs ("name") sont repris tels quels dans
`apps/imports/services.py` (KOBO_FIELDS_*) : un formulaire importé sans
modification produira des soumissions que `manage.py sync_kobo` sait déjà
intégrer, sans aucun ajustement de code.

Les listes de choix "institutions", "cycles" et "beneficiaires" ne sont PAS
codées en dur ici : elles pointent vers des fichiers CSV externes
(select_one_from_file) générés par `export_kobo_choices` et à téléverser comme
"media" du projet Kobo. Ça évite de devoir régénérer le formulaire à chaque
nouvelle inscription ou si les identifiants numériques diffèrent d'un
environnement à l'autre.
"""

from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from openpyxl import Workbook

from apps.satisfactions.models import AMELIORATIONS_EMPLOYABILITE, NOTES
from apps.suivis.models import (
    ISSUES_CONTACT,
    LIENS_FORMATION,
    SITUATIONS_ACTUELLES,
    TRANCHES_REVENU,
    TYPES_CONTRAT,
    VAGUES,
)

ENTETES_SURVEY = [
    "type", "name", "label", "hint", "required", "relevant",
    "constraint", "constraint_message", "default", "appearance",
]
ENTETES_CHOICES = ["list_name", "name", "label"]
ENTETES_SETTINGS = ["form_title", "form_id", "default_language"]

OUI_NON = [("oui", "Oui"), ("non", "Non")]


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


def _formulaire_suivi():
    survey = [
        {"type": "select_one_from_file beneficiaires.csv", "name": "id_beneficiaire",
         "label": "Bénéficiaire", "required": "yes"},
        {"type": "date", "name": "date_du_contact", "label": "Date du contact",
         "required": "yes", "default": "today()",
         "constraint": ". <= today()", "constraint_message": "La date du contact ne peut pas être dans le futur."},
        {"type": "text", "name": "enqueteur", "label": "Enquêteur", "required": "yes"},
        {"type": "select_one vagues", "name": "vague", "label": "Vague de suivi", "required": "yes"},
        {"type": "select_one issues_contact", "name": "issue_du_contact", "label": "Issue du contact",
         "required": "yes",
         "hint": "Enregistré même en cas d'échec : c'est ce qui donne le taux de joignabilité."},

        {"type": "note", "name": "note_bloc_joint", "label": "Questions suivantes si le contact a été joint",
         "relevant": "${issue_du_contact}='joint'"},
        {"type": "select_one situations_actuelles", "name": "situation_actuelle", "label": "Situation actuelle",
         "relevant": "${issue_du_contact}='joint'", "required": "yes"},
        {"type": "select_one types_contrat", "name": "type_contrat", "label": "Type de contrat ou d'activité",
         "relevant": "${issue_du_contact}='joint'"},
        {"type": "text", "name": "secteur_activite", "label": "Secteur d'activité",
         "relevant": "${issue_du_contact}='joint'"},
        {"type": "date", "name": "date_de_debut", "label": "Date de début de l'activité",
         "relevant": "${issue_du_contact}='joint'",
         "constraint": ". <= today()",
         "constraint_message": "La date de début ne peut pas être dans le futur.",
         "hint": "Date de début de l'emploi, du stage ou de l'activité déclarée."},
        {"type": "select_one tranches_revenu", "name": "tranche_de_revenu", "label": "Tranche de revenu mensuel",
         "relevant": "${issue_du_contact}='joint'"},
        {"type": "select_one liens_formation", "name": "lien_avec_la_formation",
         "label": "Lien avec la formation suivie", "relevant": "${issue_du_contact}='joint'"},
        {"type": "text", "name": "principal_obstacle", "label": "Principal obstacle rencontré",
         "hint": "Une seule question ouverte, facultative.", "relevant": "${issue_du_contact}='joint'"},
    ]
    choices = {
        "vagues": VAGUES,
        "issues_contact": ISSUES_CONTACT,
        "situations_actuelles": SITUATIONS_ACTUELLES,
        "types_contrat": TYPES_CONTRAT,
        "tranches_revenu": TRANCHES_REVENU,
        "liens_formation": LIENS_FORMATION,
    }
    return _construire_classeur("PDCED Skills - Suivi des bénéficiaires", "pdced_suivi", survey, choices)


def _formulaire_satisfaction():
    survey = [
        {"type": "select_one_from_file beneficiaires.csv", "name": "id_beneficiaire",
         "label": "Bénéficiaire", "required": "yes"},
        {"type": "select_one_from_file cycles.csv", "name": "id_cycle",
         "label": "Cycle d'enquête", "required": "yes"},
        {"type": "select_one notes", "name": "note_formation", "label": "La formation dans son ensemble",
         "required": "yes"},
        {"type": "select_one notes", "name": "note_formateurs", "label": "Les formateurs", "required": "yes"},
        {"type": "select_one notes", "name": "note_contenus", "label": "Les contenus pédagogiques",
         "required": "yes"},
        {"type": "select_one notes", "name": "note_equipements", "label": "Les équipements et le matériel",
         "required": "yes"},
        {"type": "select_one notes", "name": "note_accueil", "label": "Les conditions d'accueil",
         "required": "yes"},
        {"type": "select_one amelioration", "name": "amelioration_employabilite",
         "label": "La formation a-t-elle amélioré votre employabilité ?", "required": "yes"},
        {"type": "select_one oui_non", "name": "recommande",
         "label": "Recommanderiez-vous cette formation ?", "required": "yes"},
        {"type": "text", "name": "ce_qui_a_bien_fonctionne", "label": "Ce qui a le mieux fonctionné"},
        {"type": "text", "name": "ce_qu_il_faudrait_ameliorer", "label": "Ce qu'il faudrait améliorer"},
    ]
    choices = {
        "notes": NOTES,
        "amelioration": AMELIORATIONS_EMPLOYABILITE,
        "oui_non": OUI_NON,
    }
    return _construire_classeur(
        "PDCED Skills - Satisfaction bénéficiaire", "pdced_satisfaction_beneficiaire", survey, choices
    )


def _formulaire_satisfaction_institution():
    survey = [
        {"type": "select_one_from_file institutions.csv", "name": "id_institution",
         "label": "Institution", "required": "yes"},
        {"type": "select_one_from_file cycles.csv", "name": "id_cycle",
         "label": "Cycle d'enquête", "required": "yes"},
        {"type": "select_one notes", "name": "note_formation", "label": "La formation dans son ensemble",
         "required": "yes"},
        {"type": "select_one notes", "name": "note_formateurs", "label": "Les formateurs", "required": "yes"},
        {"type": "select_one notes", "name": "note_contenus", "label": "Les contenus pédagogiques",
         "required": "yes"},
        {"type": "select_one notes", "name": "note_equipements", "label": "Les équipements et le matériel",
         "required": "yes"},
        {"type": "select_one notes", "name": "note_accueil", "label": "Les conditions d'accueil",
         "required": "yes"},
        {"type": "text", "name": "ce_qui_a_bien_fonctionne", "label": "Ce qui a le mieux fonctionné"},
        {"type": "text", "name": "ce_qu_il_faudrait_ameliorer", "label": "Ce qu'il faudrait améliorer"},
    ]
    choices = {"notes": NOTES}
    return _construire_classeur(
        "PDCED Skills - Satisfaction institutionnelle", "pdced_satisfaction_institution", survey, choices
    )


class Command(BaseCommand):
    help = "Génère les 3 fichiers XLSForm (suivi, satisfaction bénéficiaire, satisfaction institutionnelle)."

    def handle(self, *args, **options):
        dossier_sortie = Path(settings.BASE_DIR) / "kobo_forms"
        dossier_sortie.mkdir(parents=True, exist_ok=True)
        formulaires = {
            "suivi.xlsx": _formulaire_suivi(),
            "satisfaction_beneficiaire.xlsx": _formulaire_satisfaction(),
            "satisfaction_institution.xlsx": _formulaire_satisfaction_institution(),
        }
        for nom_fichier, classeur in formulaires.items():
            chemin = dossier_sortie / nom_fichier
            classeur.save(chemin)
            self.stdout.write(f"{nom_fichier} écrit")
        self.stdout.write(self.style.SUCCESS(f"3 formulaires générés dans {dossier_sortie}"))

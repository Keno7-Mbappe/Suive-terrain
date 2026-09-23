"""Pipeline de synchronisation KoboToolbox -> base centrale.

Étape 1 (sync_form) : récupère les soumissions brutes depuis l'API Kobo et les
dépose telles quelles dans KoboSoumission (zone de staging), sans aucune
transformation - pour ne jamais perdre de donnée brute.

Étape 2 (process_pending) : relit les soumissions "nouveau", les contrôle
(bénéficiaire connu, pas de doublon) et les intègre dans les tables métier.

Les noms de champs Kobo ci-dessous (KOBO_FIELDS_*) sont une hypothèse basée sur
la maquette du questionnaire (draft.docx) et devront être ajustés pour
correspondre exactement aux noms de champs ("name") du XLSForm réel une fois
celui-ci finalisé dans KoboToolbox.
"""

import logging

import requests
from django.conf import settings
from django.utils import timezone
from django.utils.dateparse import parse_date

from apps.beneficiaires.models import Beneficiaire
from apps.referentiels.models import CycleEnquete, Institution
from apps.satisfactions.models import Satisfaction, SatisfactionInstitution
from apps.suivis.models import Suivi

from .models import KoboSoumission

logger = logging.getLogger(__name__)

KOBO_FIELDS_SUIVI = {
    "id_beneficiaire": "id_beneficiaire",
    "vague": "vague",
    "date_suivi": "date_du_contact",
    "enqueteur": "enqueteur",
    "issue_contact": "issue_du_contact",
    "situation_actuelle": "situation_actuelle",
    "type_contrat": "type_contrat",
    "secteur_activite": "secteur_activite",
    "date_debut_activite": "date_de_debut",
    "tranche_revenu": "tranche_de_revenu",
    "lien_formation": "lien_avec_la_formation",
    "obstacle_principal": "principal_obstacle",
}

KOBO_FIELDS_SATISFACTION = {
    "id_beneficiaire": "id_beneficiaire",
    "id_cycle": "id_cycle",
    "note_formation": "note_formation",
    "note_formateurs": "note_formateurs",
    "note_contenus": "note_contenus",
    "note_equipements": "note_equipements",
    "note_accueil": "note_accueil",
    "amelioration_employabilite": "amelioration_employabilite",
    "recommande": "recommande",
    "points_positifs": "ce_qui_a_bien_fonctionne",
    "points_a_ameliorer": "ce_qu_il_faudrait_ameliorer",
}

KOBO_FIELDS_SATISFACTION_INSTITUTION = {
    "id_institution": "id_institution",
    "id_cycle": "id_cycle",
    "note_formation": "note_formation",
    "note_formateurs": "note_formateurs",
    "note_contenus": "note_contenus",
    "note_equipements": "note_equipements",
    "note_accueil": "note_accueil",
    "points_positifs": "ce_qui_a_bien_fonctionne",
    "points_a_ameliorer": "ce_qu_il_faudrait_ameliorer",
}

ASSET_UID_PAR_TYPE = {
    "suivi": lambda: settings.KOBO_ASSET_UID_SUIVI,
    "satisfaction": lambda: settings.KOBO_ASSET_UID_SATISFACTION,
    "satisfaction_institution": lambda: settings.KOBO_ASSET_UID_SATISFACTION_INSTITUTION,
}


def _kobo_headers():
    return {"Authorization": f"Token {settings.KOBO_API_TOKEN}"}


def fetch_kobo_submissions(asset_uid):
    """Génère chaque soumission brute (dict) d'un formulaire Kobo, en paginant."""
    url = f"{settings.KOBO_API_BASE_URL}/api/v2/assets/{asset_uid}/data.json"
    params = {"limit": 1000}
    while url:
        response = requests.get(url, headers=_kobo_headers(), params=params, timeout=30)
        response.raise_for_status()
        payload = response.json()
        yield from payload.get("results", [])
        url = payload.get("next")
        params = None  # l'URL "next" contient déjà les paramètres de pagination


def sync_form(type_formulaire):
    """Étape 1 : rapatrie les nouvelles soumissions d'un formulaire dans la zone de staging."""
    asset_uid = ASSET_UID_PAR_TYPE[type_formulaire]()
    if not asset_uid:
        logger.warning("Aucun asset UID Kobo configuré pour '%s' - synchronisation ignorée.", type_formulaire)
        return {"recues": 0, "nouvelles": 0}

    recues = 0
    nouvelles = 0
    for soumission in fetch_kobo_submissions(asset_uid):
        recues += 1
        submission_id = str(soumission.get("_id"))
        _, created = KoboSoumission.objects.get_or_create(
            type_formulaire=type_formulaire,
            kobo_submission_id=submission_id,
            defaults={"donnees_brutes": soumission},
        )
        if created:
            nouvelles += 1
    return {"recues": recues, "nouvelles": nouvelles}


def _get_beneficiaire(id_beneficiaire):
    try:
        return Beneficiaire.objects.get(pk=id_beneficiaire)
    except Beneficiaire.DoesNotExist:
        return None


def _integrer_suivi(donnees):
    champs = KOBO_FIELDS_SUIVI
    beneficiaire = _get_beneficiaire(donnees.get(champs["id_beneficiaire"]))
    if beneficiaire is None:
        raise ValueError(f"Bénéficiaire introuvable : {donnees.get(champs['id_beneficiaire'])}")

    Suivi.objects.update_or_create(
        beneficiaire=beneficiaire,
        vague=donnees.get(champs["vague"]),
        defaults={
            "date_suivi": parse_date(donnees.get(champs["date_suivi"])) or timezone.now().date(),
            "enqueteur": donnees.get(champs["enqueteur"], "") or "",
            "issue_contact": donnees.get(champs["issue_contact"], ""),
            "situation_actuelle": donnees.get(champs["situation_actuelle"], "") or "",
            "type_contrat": donnees.get(champs["type_contrat"], "") or "",
            "secteur_activite": donnees.get(champs["secteur_activite"], "") or "",
            "date_debut_activite": parse_date(donnees.get(champs["date_debut_activite"]) or "") or None,
            "tranche_revenu": donnees.get(champs["tranche_revenu"], "") or "",
            "lien_formation": donnees.get(champs["lien_formation"], "") or "",
            "obstacle_principal": donnees.get(champs["obstacle_principal"], "") or "",
        },
    )


def _integrer_satisfaction(donnees):
    champs = KOBO_FIELDS_SATISFACTION
    beneficiaire = _get_beneficiaire(donnees.get(champs["id_beneficiaire"]))
    if beneficiaire is None:
        raise ValueError(f"Bénéficiaire introuvable : {donnees.get(champs['id_beneficiaire'])}")
    cycle = CycleEnquete.objects.get(pk=donnees.get(champs["id_cycle"]))

    Satisfaction.objects.update_or_create(
        beneficiaire=beneficiaire,
        cycle=cycle,
        defaults={
            "note_formation": donnees.get(champs["note_formation"]),
            "note_formateurs": donnees.get(champs["note_formateurs"]),
            "note_contenus": donnees.get(champs["note_contenus"]),
            "note_equipements": donnees.get(champs["note_equipements"]),
            "note_accueil": donnees.get(champs["note_accueil"]),
            "amelioration_employabilite": donnees.get(champs["amelioration_employabilite"], ""),
            "recommande": str(donnees.get(champs["recommande"], "")).lower() in ("oui", "true", "1"),
            "points_positifs": donnees.get(champs["points_positifs"], "") or "",
            "points_a_ameliorer": donnees.get(champs["points_a_ameliorer"], "") or "",
        },
    )


def _integrer_satisfaction_institution(donnees):
    champs = KOBO_FIELDS_SATISFACTION_INSTITUTION
    institution = Institution.objects.get(pk=donnees.get(champs["id_institution"]))
    cycle = CycleEnquete.objects.get(pk=donnees.get(champs["id_cycle"]))

    SatisfactionInstitution.objects.update_or_create(
        institution=institution,
        cycle=cycle,
        defaults={
            "note_formation": donnees.get(champs["note_formation"]),
            "note_formateurs": donnees.get(champs["note_formateurs"]),
            "note_contenus": donnees.get(champs["note_contenus"]),
            "note_equipements": donnees.get(champs["note_equipements"]),
            "note_accueil": donnees.get(champs["note_accueil"]),
            "points_positifs": donnees.get(champs["points_positifs"], "") or "",
            "points_a_ameliorer": donnees.get(champs["points_a_ameliorer"], "") or "",
        },
    )


INTEGRATEURS = {
    "suivi": _integrer_suivi,
    "satisfaction": _integrer_satisfaction,
    "satisfaction_institution": _integrer_satisfaction_institution,
}


def traiter_soumission(soumission):
    """Tente d'intégrer une soumission unique dans les tables métier et
    enregistre le résultat sur l'objet. Partagé par la synchronisation
    automatique (process_pending) et le bouton « Réessayer » de la page de
    contrôle des soumissions - une soumission en erreur peut être corrigée
    entre-temps (ex : le bénéficiaire manquant a été créé) puis relancée sans
    dupliquer la logique d'intégration."""
    integrateur = INTEGRATEURS[soumission.type_formulaire]
    try:
        integrateur(soumission.donnees_brutes)
    except Exception as exc:  # noqa: BLE001 - on veut journaliser puis continuer
        soumission.statut = "erreur"
        soumission.erreur = str(exc)
        reussite = False
        logger.exception("Échec d'intégration de la soumission %s", soumission.pk)
    else:
        soumission.statut = "integre"
        soumission.erreur = ""
        reussite = True
    soumission.traite_le = timezone.now()
    soumission.save(update_fields=["statut", "erreur", "traite_le"])
    return reussite


def process_pending():
    """Étape 2 : intègre les soumissions en attente dans les tables métier."""
    resultats = {"integre": 0, "erreur": 0}
    for soumission in KoboSoumission.objects.filter(statut="nouveau"):
        if traiter_soumission(soumission):
            resultats["integre"] += 1
        else:
            resultats["erreur"] += 1
    return resultats

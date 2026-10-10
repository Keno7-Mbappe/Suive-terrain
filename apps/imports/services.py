"""Pipeline de synchronisation KoboToolbox -> base centrale.

Étape 1 (sync_form) : récupère les soumissions brutes depuis l'API Kobo et les
dépose telles quelles dans KoboSoumission (zone de staging), sans aucune
transformation - pour ne jamais perdre de donnée brute. Elles y restent
"à valider" : rien n'entre dans la base ni le tableau de bord tant qu'un
validateur ne les a pas relues (et éventuellement corrigées).

Étape 2 (traiter_soumission) : appelée quand un validateur clique « Valider »
(ou, en mode automatique, par process_pending) : intègre la version effective
de la soumission (corrigée si elle l'a été) dans les tables métier.

Le formulaire "suivi" fusionne suivi longitudinal ET satisfaction bénéficiaire
en une seule soumission (question "faire_satisfaction" à l'intérieur du groupe
"bascule") : une même soumission Kobo peut donc créer/mettre à jour à la fois
un `Suivi` et une `Satisfaction`. Les noms de champs ci-dessous, chemins de
groupe inclus ("selection/canal", "module_suivi/situation", ...), correspondent
exactement à ceux du XLSForm généré par `generate_kobo_xlsforms`.
"""

import logging

import requests
from django.conf import settings
from django.utils import timezone
from django.utils.dateparse import parse_date

from apps.beneficiaires.models import Beneficiaire
from apps.insertions.models import Insertion
from apps.referentiels.models import CycleEnquete, Institution
from apps.satisfactions.models import Satisfaction, SatisfactionInstitution
from apps.suivis.models import SECTEURS, Suivi

from .models import TYPES_FORMULAIRE, KoboSoumission
from .schemas import TYPE_INSTITUTION_PAR_CODE

logger = logging.getLogger(__name__)

# Les cycles sont encodés en dur dans les formulaires (cycle_1/cycle_2/cycle_3)
# plutôt que via un identifiant de base de données : on les résout ici par
# rang chronologique plutôt que par un code stable stocké en base, pour ne pas
# ajouter un champ dédié à CycleEnquete pour une liste de 3 valeurs connues à
# l'avance et qui ne change pas.
CODES_CYCLES = ["cycle_1", "cycle_2", "cycle_3"]


def _resoudre_cycle(code_cycle):
    cycles = list(CycleEnquete.objects.order_by("date_debut"))
    try:
        return cycles[CODES_CYCLES.index(code_cycle)]
    except (ValueError, IndexError):
        return None


def _vers_bool_oui_non(valeur):
    return str(valeur or "").strip().lower() == "oui"


def _resoudre_institution(code):
    """Retrouve l'institution d'après le code du formulaire Kobo (INAP, DGFP, ANEFIP)
    - ou son identifiant numérique, pour les formulaires qui exportent la liste des
    institutions depuis la base. Retourne None si introuvable."""
    code = str(code or "").strip()
    if not code:
        return None
    if code.isdigit():
        return Institution.objects.filter(pk=int(code)).first()
    type_institution = TYPE_INSTITUTION_PAR_CODE.get(code.upper(), code.lower())
    return Institution.objects.filter(type=type_institution).first()


def institution_de_soumission(type_formulaire, donnees):
    """Institution concernée par une soumission (sert au filtrage par institution
    des validateurs rattachés à une seule structure)."""
    if type_formulaire == "suivi":
        beneficiaire = _get_beneficiaire(donnees.get("selection/id_beneficiaire"))
        return beneficiaire.institution if beneficiaire else None
    return _resoudre_institution(donnees.get("identification/institution"))


KOBO_FIELDS_SUIVI = {
    "id_beneficiaire": "selection/id_beneficiaire",
    "canal": "selection/canal",
    "date_suivi": "selection/date_contact",
    "enqueteur": "enqueteur",
    "issue_contact": "issue_contact",
    "vague": "module_suivi/vague",
    "situation_actuelle": "module_suivi/situation",
    "type_contrat": "module_suivi/type_contrat",
    "type_activite": "module_suivi/type_activite",
    "secteur_activite": "module_suivi/secteur",
    "date_debut_activite": "module_suivi/date_debut_activite",
    "tranche_revenu": "module_suivi/revenu_tranche",
    "lien_formation": "module_suivi/lien_formation",
    "duree_recherche_mois": "module_suivi/duree_recherche_mois",
    "demarches": "module_suivi/demarches",
    "obstacle_principal": "module_suivi/obstacle",
}

# Sous-partie "satisfaction", incluse dans la même soumission que le suivi
# (groupe "bascule", uniquement rempli si faire_satisfaction == "oui").
KOBO_FIELDS_SATISFACTION = {
    "faire_satisfaction": "bascule/faire_satisfaction",
    "id_cycle": "bascule/cycle",
    "note_formation": "bascule/note_formation",
    "note_formateurs": "bascule/note_formateurs",
    "note_contenus": "bascule/note_contenus",
    "note_equipements": "bascule/note_equipements",
    "note_accueil": "bascule/note_conditions",
    "amelioration_employabilite": "bascule/employabilite",
    "recommande": "bascule/recommande",
    "raison_non_recommande": "bascule/raison_non",
    "points_positifs": "bascule/point_fort",
    "points_a_ameliorer": "bascule/point_amelioration",
}

KOBO_FIELDS_SATISFACTION_INSTITUTION = {
    "id_institution": "identification/institution",
    "fonction_repondant": "identification/fonction",
    "id_cycle": "identification/cycle",
    "date_reponse": "identification/date_reponse",
    "note_qualite_donnees": "notes/note_qualite_donnees",
    "note_outils_collecte": "notes/note_outils_collecte",
    "note_tableaux_bord": "notes/note_tableaux_bord",
    "note_appui_technique": "notes/note_appui_technique",
    "note_coordination": "notes/note_coordination",
    "utilite_dispositif": "utilite_dispositif",
    "difficultes": "difficultes",
    "recommandations": "recommandations",
}

ASSET_UID_PAR_TYPE = {
    "suivi": lambda: settings.KOBO_ASSET_UID_SUIVI,
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
            defaults={
                "donnees_brutes": soumission,
                "institution": institution_de_soumission(type_formulaire, soumission),
            },
        )
        if created:
            nouvelles += 1
    return {"recues": recues, "nouvelles": nouvelles}


def _message_erreur_kobo(exc):
    reponse = getattr(exc, "response", None)
    if reponse is not None and reponse.status_code in (401, 403):
        return "accès refusé par Kobo (jeton d'API invalide ou sans droit sur ce formulaire)"
    if reponse is not None and reponse.status_code == 404:
        return "formulaire introuvable ou non déployé sur Kobo"
    return f"Kobo injoignable ou en erreur ({exc.__class__.__name__})"


def synchroniser_tout():
    """Rapatrie les nouvelles soumissions de chaque formulaire Kobo dans la zone de
    validation. Un formulaire indisponible (non déployé, jeton refusé, réseau) est
    signalé sans empêcher la synchronisation des autres.
    Retourne [{"libelle", "recues", "nouvelles", "erreur"}]."""
    resultats = []
    for type_formulaire, libelle in TYPES_FORMULAIRE:
        try:
            resultat = sync_form(type_formulaire)
            resultats.append({"libelle": libelle, "erreur": None, **resultat})
        except requests.RequestException as exc:
            logger.warning("Synchronisation Kobo '%s' impossible : %s", type_formulaire, exc)
            resultats.append({"libelle": libelle, "recues": 0, "nouvelles": 0, "erreur": _message_erreur_kobo(exc)})
    return resultats


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

    vague = donnees.get(champs["vague"])
    if not vague:
        # Le formulaire ne pose pas la vague quand le contact échoue : on refuse
        # l'intégration plutôt que d'écraser au hasard la ligne d'une autre vague,
        # le validateur précise la vague dans l'écran de correction.
        raise ValueError(
            "Vague de suivi manquante (M+3, M+6 ou M+12) : corrigez la soumission avant de la valider."
        )

    duree_recherche = donnees.get(champs["duree_recherche_mois"])
    Suivi.objects.update_or_create(
        beneficiaire=beneficiaire,
        vague=vague,
        defaults={
            "date_suivi": parse_date(donnees.get(champs["date_suivi"]) or "") or timezone.now().date(),
            "canal": donnees.get(champs["canal"], "") or "",
            "enqueteur": donnees.get(champs["enqueteur"], "") or "",
            "issue_contact": donnees.get(champs["issue_contact"], ""),
            "situation_actuelle": donnees.get(champs["situation_actuelle"], "") or "",
            "type_contrat": donnees.get(champs["type_contrat"], "") or "",
            "type_activite": donnees.get(champs["type_activite"], "") or "",
            "secteur_activite": donnees.get(champs["secteur_activite"], "") or "",
            "date_debut_activite": parse_date(donnees.get(champs["date_debut_activite"]) or "") or None,
            "tranche_revenu": donnees.get(champs["tranche_revenu"], "") or "",
            "lien_formation": donnees.get(champs["lien_formation"], "") or "",
            "duree_recherche_mois": int(duree_recherche) if duree_recherche not in (None, "") else None,
            "demarches": donnees.get(champs["demarches"], "") or "",
            "obstacle_principal": donnees.get(champs["obstacle_principal"], "") or "",
        },
    )

    # Le module satisfaction est optionnel et fait partie de la même soumission
    # (bascule/faire_satisfaction) : pas de deuxième formulaire Kobo à synchroniser.
    if _vers_bool_oui_non(donnees.get(KOBO_FIELDS_SATISFACTION["faire_satisfaction"])):
        _integrer_satisfaction(beneficiaire, donnees)

    # La situation professionnelle ("module_suivi/situation") renseigne aussi
    # l'insertion du bénéficiaire - pas de question séparée dans le formulaire,
    # cf. _integrer_insertion.
    situation = donnees.get(champs["situation_actuelle"])
    if situation in SITUATION_VERS_INSERTION:
        _integrer_insertion(beneficiaire, donnees)


def _integrer_satisfaction(beneficiaire, donnees):
    champs = KOBO_FIELDS_SATISFACTION
    code_cycle = donnees.get(champs["id_cycle"])
    cycle = _resoudre_cycle(code_cycle)
    if cycle is None:
        raise ValueError(f"Cycle d'enquête introuvable : {code_cycle}")

    Satisfaction.objects.update_or_create(
        beneficiaire=beneficiaire,
        cycle=cycle,
        defaults={
            "note_formation": donnees.get(champs["note_formation"]),
            "note_formateurs": donnees.get(champs["note_formateurs"]),
            "note_contenus": donnees.get(champs["note_contenus"]),
            "note_equipements": donnees.get(champs["note_equipements"]),
            "note_accueil": donnees.get(champs["note_accueil"]),
            "amelioration_employabilite": donnees.get(champs["amelioration_employabilite"], "") or "",
            "recommande": _vers_bool_oui_non(donnees.get(champs["recommande"])),
            "raison_non_recommande": donnees.get(champs["raison_non_recommande"], "") or "",
            "points_positifs": donnees.get(champs["points_positifs"], "") or "",
            "points_a_ameliorer": donnees.get(champs["points_a_ameliorer"], "") or "",
        },
    )


# Le formulaire ne pose pas une question "insertion" séparée : la situation
# professionnelle du module suivi ("module_suivi/situation") sert aux deux -
# "formation" (reparti en formation) et "inactif" ne sont pas une insertion.
SITUATION_VERS_INSERTION = {
    "emploi": "emploi_salarie",
    "auto_emploi": "auto_emploi",
    "stage": "stage",
    "recherche": "en_recherche",
}


def _integrer_insertion(beneficiaire, donnees):
    champs = KOBO_FIELDS_SUIVI
    situation = donnees.get(champs["situation_actuelle"])
    situation_prof = SITUATION_VERS_INSERTION[situation]
    secteur_code = donnees.get(champs["secteur_activite"]) or ""
    date_insertion = parse_date(donnees.get(champs["date_debut_activite"]) or "") or None

    delai_insertion_mois = None
    if date_insertion is not None:
        derniere_formation = (
            beneficiaire.formations.exclude(date_fin__isnull=True).order_by("-date_fin").first()
        )
        if derniere_formation is not None:
            delta_mois = (
                (date_insertion.year - derniere_formation.date_fin.year) * 12
                + (date_insertion.month - derniere_formation.date_fin.month)
            )
            if delta_mois >= 0:
                delai_insertion_mois = delta_mois

    Insertion.objects.update_or_create(
        beneficiaire=beneficiaire, situation_prof=situation_prof,
        defaults={
            "secteur_activite": dict(SECTEURS).get(secteur_code, secteur_code),
            "date_insertion": date_insertion,
            "delai_insertion_mois": delai_insertion_mois,
        },
    )


def _integrer_satisfaction_institution(donnees):
    champs = KOBO_FIELDS_SATISFACTION_INSTITUTION
    institution = _resoudre_institution(donnees.get(champs["id_institution"]))
    if institution is None:
        raise ValueError(f"Institution introuvable : {donnees.get(champs['id_institution'])}")
    code_cycle = donnees.get(champs["id_cycle"])
    cycle = _resoudre_cycle(code_cycle)
    if cycle is None:
        raise ValueError(f"Cycle d'enquête introuvable : {code_cycle}")

    SatisfactionInstitution.objects.update_or_create(
        institution=institution,
        cycle=cycle,
        defaults={
            "fonction_repondant": donnees.get(champs["fonction_repondant"], "") or "",
            "date_reponse": parse_date(donnees.get(champs["date_reponse"]) or "") or None,
            "note_qualite_donnees": donnees.get(champs["note_qualite_donnees"]),
            "note_outils_collecte": donnees.get(champs["note_outils_collecte"]),
            "note_tableaux_bord": donnees.get(champs["note_tableaux_bord"]),
            "note_appui_technique": donnees.get(champs["note_appui_technique"]),
            "note_coordination": donnees.get(champs["note_coordination"]),
            "utilite_dispositif": donnees.get(champs["utilite_dispositif"], "") or "",
            "difficultes": donnees.get(champs["difficultes"], "") or "",
            "recommandations": donnees.get(champs["recommandations"], "") or "",
        },
    )


INTEGRATEURS = {
    "suivi": _integrer_suivi,
    "satisfaction_institution": _integrer_satisfaction_institution,
}


def traiter_soumission(soumission, utilisateur=None):
    """Tente d'intégrer une soumission unique dans les tables métier et
    enregistre le résultat sur l'objet. Utilisée par le bouton « Valider » (ou
    « Réessayer ») de l'écran de validation, et par process_pending en mode
    automatique. C'est la version effective qui est intégrée : les données
    corrigées par un validateur si elles existent, sinon les données brutes de Kobo."""
    integrateur = INTEGRATEURS[soumission.type_formulaire]
    donnees = soumission.donnees_effectives
    try:
        integrateur(donnees)
    except Exception as exc:  # noqa: BLE001 - on veut journaliser puis continuer
        soumission.statut = "erreur"
        soumission.erreur = str(exc)
        reussite = False
        logger.exception("Échec d'intégration de la soumission %s", soumission.pk)
    else:
        soumission.statut = "integre"
        soumission.erreur = ""
        reussite = True
    soumission.institution = institution_de_soumission(soumission.type_formulaire, donnees)
    soumission.traite_le = timezone.now()
    soumission.traite_par = utilisateur
    soumission.save(update_fields=["statut", "erreur", "institution", "traite_le", "traite_par"])
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


def controler_soumission(soumission):
    """Points d'attention à montrer au validateur AVANT de valider : incohérences
    entre la soumission et la base (bénéficiaire inconnu, nom différent de celui de
    la liste Kobo, vague manquante, écrasement d'une ligne existante...).
    Retourne [(niveau, message)] avec niveau in {"erreur", "attention", "info"}."""
    donnees = soumission.donnees_effectives
    alertes = []

    if soumission.type_formulaire == "suivi":
        identifiant = donnees.get("selection/id_beneficiaire")
        beneficiaire = _get_beneficiaire(identifiant)
        if beneficiaire is None:
            alertes.append(("erreur", f"Aucun bénéficiaire ne porte l'identifiant « {identifiant} » dans la base."))
        else:
            nom_kobo = " ".join(str(donnees.get("selection/nom_prenom") or "").casefold().split())
            nom_base = " ".join(f"{beneficiaire.prenom} {beneficiaire.nom}".casefold().split())
            if nom_kobo and nom_kobo != nom_base:
                alertes.append((
                    "attention",
                    f"Le nom affiché par Kobo (« {donnees.get('selection/nom_prenom')} ») ne correspond pas au nom "
                    f"en base pour cet identifiant (« {beneficiaire.prenom} {beneficiaire.nom} »). "
                    "La liste de bénéficiaires du formulaire Kobo est peut-être désynchronisée.",
                ))
            vague = donnees.get("module_suivi/vague")
            if vague and Suivi.objects.filter(beneficiaire=beneficiaire, vague=vague).exists():
                alertes.append(("info", "Un suivi existe déjà pour cette vague : la validation le remplacera."))
        if not donnees.get("module_suivi/vague"):
            alertes.append((
                "attention",
                "Vague de suivi manquante (le formulaire ne la demande pas quand le contact échoue) : "
                "précisez-la en corrigeant la soumission.",
            ))
        if donnees.get("issue_contact") == "joint" and not donnees.get("module_suivi/situation"):
            alertes.append(("attention", "Contact joint mais aucune situation actuelle n'est renseignée."))
        if _vers_bool_oui_non(donnees.get("bascule/faire_satisfaction")) and _resoudre_cycle(donnees.get("bascule/cycle")) is None:
            alertes.append(("erreur", "Module satisfaction réalisé mais le cycle d'enquête est absent ou inconnu."))
    else:
        institution = _resoudre_institution(donnees.get("identification/institution"))
        if institution is None:
            alertes.append(("erreur", "Institution introuvable dans la base."))
        cycle = _resoudre_cycle(donnees.get("identification/cycle"))
        if cycle is None:
            alertes.append(("erreur", "Cycle d'enquête absent ou inconnu."))
        elif institution and SatisfactionInstitution.objects.filter(institution=institution, cycle=cycle).exists():
            alertes.append(("info", "Cette institution a déjà répondu pour ce cycle : la validation remplacera sa réponse."))

    if soumission.est_corrigee:
        alertes.append(("info", "Cette soumission a été corrigée : c'est la version corrigée qui sera intégrée."))
    if soumission.erreur:
        alertes.append(("erreur", f"Dernière tentative d'intégration : {soumission.erreur}"))
    return alertes

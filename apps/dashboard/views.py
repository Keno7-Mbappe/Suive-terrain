from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Count, Min
from django.shortcuts import render

from apps.beneficiaires.models import SEXES, Beneficiaire
from apps.certifications.models import Certification
from apps.formations.models import Formation
from apps.imports.models import KoboSoumission
from apps.insertions.models import SITUATIONS_PRO, Insertion
from apps.referentiels.models import REGIONS, CycleEnquete, Institution
from apps.satisfactions.models import Satisfaction, SatisfactionInstitution
from apps.suivis.models import Suivi

ORDRE_TRANCHES_AGE = ["<20", "20-30", "31-40", "41-50", ">50"]


def _taux(numerateur, denominateur):
    return round(numerateur / denominateur * 100, 1) if denominateur else 0


def _chart(rows, key, total_map, label_map=None):
    """Transforme une liste de {key: code, total: n} en {labels, values} prêt
    pour Chart.js, en résolvant les codes vers leurs libellés lisibles."""
    label_map = label_map or {}
    return {
        "labels": [label_map.get(r[key], r[key]) for r in rows],
        "values": [r[total_map] for r in rows],
    }


def _compter_anomalies(beneficiaires):
    """Incohérences factuelles détectables automatiquement (pas de simples
    doublons, déjà traités séparément) : âge implausible, ou un événement du
    parcours daté avant même le début de la formation qui l'a permis."""
    nb = 0
    for b in beneficiaires.only("id_beneficiaire", "date_naissance", "date_enregistrement"):
        age = b.date_enregistrement.year - b.date_naissance.year
        if (b.date_enregistrement.month, b.date_enregistrement.day) < (b.date_naissance.month, b.date_naissance.day):
            age -= 1
        if age < 14 or age > 70:
            nb += 1

    premieres_formations = dict(
        Formation.objects.filter(beneficiaire__in=beneficiaires)
        .values("beneficiaire").annotate(debut=Min("date_debut")).values_list("beneficiaire", "debut")
    )
    for insertion in Insertion.objects.filter(beneficiaire__in=beneficiaires, date_insertion__isnull=False):
        debut_formation = premieres_formations.get(insertion.beneficiaire_id)
        if debut_formation and insertion.date_insertion < debut_formation:
            nb += 1
    for certification in Certification.objects.filter(beneficiaire__in=beneficiaires):
        debut_formation = premieres_formations.get(certification.beneficiaire_id)
        if debut_formation and certification.date_certification < debut_formation:
            nb += 1
    return nb


def _contexte_dashboard(request):
    cycle_id = request.GET.get("cycle") or ""
    institution_id = request.GET.get("institution") or ""

    beneficiaires = Beneficiaire.objects.all()
    if institution_id:
        beneficiaires = beneficiaires.filter(institution_id=institution_id)

    total_beneficiaires = beneficiaires.count()

    total_formes = (
        Formation.objects.filter(beneficiaire__in=beneficiaires, statut_formation="achevee")
        .values("beneficiaire").distinct().count()
    )
    total_certifies = (
        Certification.objects.filter(beneficiaire__in=beneficiaires)
        .values("beneficiaire").distinct().count()
    )
    total_inseres = (
        Insertion.objects.filter(beneficiaire__in=beneficiaires)
        .exclude(situation_prof="en_recherche")
        .values("beneficiaire").distinct().count()
    )

    toutes_formations = Formation.objects.filter(beneficiaire__in=beneficiaires)
    nb_formations_total = toutes_formations.count()
    nb_abandons = toutes_formations.filter(statut_formation="abandonnee").count()
    taux_abandon = _taux(nb_abandons, nb_formations_total)

    delai_moyen_insertion = Insertion.objects.filter(
        beneficiaire__in=beneficiaires, delai_insertion_mois__isnull=False
    ).aggregate(moyenne=Avg("delai_insertion_mois"))["moyenne"]
    delai_moyen_insertion = round(delai_moyen_insertion, 1) if delai_moyen_insertion is not None else None

    satisfactions = Satisfaction.objects.filter(beneficiaire__in=beneficiaires)
    if cycle_id:
        satisfactions = satisfactions.filter(cycle_id=cycle_id)
    dimensions = satisfactions.aggregate(
        formation=Avg("note_formation"),
        formateurs=Avg("note_formateurs"),
        contenus=Avg("note_contenus"),
        equipements=Avg("note_equipements"),
        accueil=Avg("note_accueil"),
    )
    notes_valides = [round(v, 2) for v in dimensions.values() if v is not None]
    satisfaction_globale = round(sum(notes_valides) / len(notes_valides), 2) if notes_valides else None
    # .count() compterait chaque cycle séparément (jusqu'à 3 réponses par bénéficiaire
    # quand aucun cycle n'est sélectionné) et ferait dépasser 100% le taux de réponse.
    nb_repondants = satisfactions.values("beneficiaire").distinct().count()

    total_suivis = Suivi.objects.filter(beneficiaire__in=beneficiaires).values("beneficiaire").distinct().count()

    # Satisfaction des institutions à l'égard du dispositif de suivi lui-même
    # (qualité des données, outils, tableaux de bord...) : pilotage interne
    # (ONEQ / Direction des Projets), pas une donnée de résultat bénéficiaire.
    satisfactions_institution = SatisfactionInstitution.objects.all()
    if institution_id:
        satisfactions_institution = satisfactions_institution.filter(institution_id=institution_id)
    if cycle_id:
        satisfactions_institution = satisfactions_institution.filter(cycle_id=cycle_id)
    nb_reponses_institution = satisfactions_institution.count()
    dimensions_institution = satisfactions_institution.aggregate(
        qualite=Avg("note_qualite_donnees"), outils=Avg("note_outils_collecte"),
        tableaux_bord=Avg("note_tableaux_bord"), appui=Avg("note_appui_technique"),
        coordination=Avg("note_coordination"),
    )
    notes_institution_valides = [round(v, 2) for v in dimensions_institution.values() if v is not None]
    satisfaction_institution_globale = (
        round(sum(notes_institution_valides) / len(notes_institution_valides), 2)
        if notes_institution_valides else None
    )
    satisfaction_institution_pct = (
        round(satisfaction_institution_globale / 5 * 100, 1) if satisfaction_institution_globale else 0
    )

    nb_doublons_potentiels = Beneficiaire.groupes_doublons(beneficiaires).count()
    nb_anomalies = _compter_anomalies(beneficiaires)
    nb_coordonnees_completes = beneficiaires.exclude(telephone="").exclude(email="").count()
    taux_completude = _taux(nb_coordonnees_completes, total_beneficiaires)
    soumissions_kobo = KoboSoumission.objects.all()
    nb_soumissions_kobo = soumissions_kobo.count()
    taux_validation_kobo = _taux(soumissions_kobo.filter(statut="integre").count(), nb_soumissions_kobo)

    regions_labels = dict(REGIONS)
    sexes_labels = dict(SEXES)
    situations_labels = dict(SITUATIONS_PRO)

    repartition_region = list(
        beneficiaires.values("region").annotate(total=Count("id_beneficiaire")).order_by("-total")
    )
    repartition_institution = list(
        beneficiaires.values("institution__libelle").annotate(total=Count("id_beneficiaire")).order_by("-total")
    )
    repartition_sexe = list(beneficiaires.values("sexe").annotate(total=Count("id_beneficiaire")))
    repartition_age_brut = {
        r["tranche_age"]: r["total"]
        for r in beneficiaires.values("tranche_age").annotate(total=Count("id_beneficiaire"))
    }
    repartition_domaine = list(
        Formation.objects.filter(beneficiaire__in=beneficiaires)
        .values("domaine").annotate(total=Count("id")).order_by("-total")[:8]
    )
    repartition_situation_pro = list(
        Insertion.objects.filter(beneficiaire__in=beneficiaires)
        .values("situation_prof").annotate(total=Count("id")).order_by("-total")
    )

    evolution = []
    for cycle in CycleEnquete.objects.order_by("date_debut"):
        inseres_a_date = (
            Insertion.objects.filter(beneficiaire__in=beneficiaires, date_insertion__lte=cycle.date_fin)
            .exclude(situation_prof="en_recherche")
            .values("beneficiaire").distinct().count()
        )
        evolution.append({"cycle": cycle.libelle, "taux_insertion": _taux(inseres_a_date, total_beneficiaires)})

    evolution_satisfaction = []
    for cycle in CycleEnquete.objects.order_by("date_debut"):
        moyennes_cycle = Satisfaction.objects.filter(
            beneficiaire__in=beneficiaires, cycle=cycle
        ).aggregate(
            formation=Avg("note_formation"), formateurs=Avg("note_formateurs"), contenus=Avg("note_contenus"),
            equipements=Avg("note_equipements"), accueil=Avg("note_accueil"),
        )
        valeurs_cycle = [v for v in moyennes_cycle.values() if v is not None]
        note_cycle = round(sum(valeurs_cycle) / len(valeurs_cycle), 2) if valeurs_cycle else 0
        evolution_satisfaction.append({"cycle": cycle.libelle, "note": note_cycle})

    total_femmes = next((r["total"] for r in repartition_sexe if r["sexe"] == "F"), 0)
    total_hommes = next((r["total"] for r in repartition_sexe if r["sexe"] == "M"), 0)

    # Taux de conversion d'une etape a l'autre (et non vs le total) : montre ou se
    # situe reellement la deperdition dans le parcours, plus utile qu'un simple %
    # de la population de depart pour piloter l'action.
    conv_formes = _taux(total_formes, total_beneficiaires)
    conv_certifies = _taux(total_certifies, total_formes)
    conv_inseres = _taux(total_inseres, total_certifies)
    satisfaction_pct = round(satisfaction_globale / 5 * 100, 1) if satisfaction_globale else 0

    charts = {
        "satisfaction": {
            "labels": ["Formation", "Formateurs", "Contenus", "Équipements", "Accueil"],
            "values": [
                round(dimensions["formation"] or 0, 2), round(dimensions["formateurs"] or 0, 2),
                round(dimensions["contenus"] or 0, 2), round(dimensions["equipements"] or 0, 2),
                round(dimensions["accueil"] or 0, 2),
            ],
        },
        "region": _chart(repartition_region, "region", "total", regions_labels),
        "institution": _chart(repartition_institution, "institution__libelle", "total"),
        "sexe": {"labels": ["Femmes", "Hommes"], "values": [total_femmes, total_hommes]},
        "age": {"labels": ORDRE_TRANCHES_AGE, "values": [repartition_age_brut.get(t, 0) for t in ORDRE_TRANCHES_AGE]},
        "domaine": _chart(repartition_domaine, "domaine", "total"),
        "situation_pro": _chart(repartition_situation_pro, "situation_prof", "total", situations_labels),
        "evolution": {
            "labels": [e["cycle"] for e in evolution],
            "values": [e["taux_insertion"] for e in evolution],
        },
        "evolution_satisfaction": {
            "labels": [e["cycle"] for e in evolution_satisfaction],
            "values": [e["note"] for e in evolution_satisfaction],
        },
    }

    context = {
        "total_beneficiaires": total_beneficiaires,
        "total_formes": total_formes,
        "total_certifies": total_certifies,
        "total_inseres": total_inseres,
        "total_suivis": total_suivis,
        "taux_formes": _taux(total_formes, total_beneficiaires),
        "taux_certifies": _taux(total_certifies, total_beneficiaires),
        "taux_inseres": _taux(total_inseres, total_beneficiaires),
        "taux_suivi": _taux(total_suivis, total_beneficiaires),
        "taux_abandon": taux_abandon,
        "delai_moyen_insertion": delai_moyen_insertion,
        "conv_formes": conv_formes,
        "conv_certifies": conv_certifies,
        "conv_inseres": conv_inseres,
        "satisfaction_pct": satisfaction_pct,
        "nb_doublons_potentiels": nb_doublons_potentiels,
        "nb_anomalies": nb_anomalies,
        "taux_completude": taux_completude,
        "nb_soumissions_kobo": nb_soumissions_kobo,
        "taux_validation_kobo": taux_validation_kobo,
        "nb_reponses_institution": nb_reponses_institution,
        "satisfaction_institution_globale": satisfaction_institution_globale,
        "satisfaction_institution_pct": satisfaction_institution_pct,
        "satisfaction_globale": satisfaction_globale,
        "nb_repondants": nb_repondants,
        "taux_reponse": _taux(nb_repondants, total_beneficiaires),
        "charts": charts,
        "institutions": Institution.objects.all(),
        "cycles": CycleEnquete.objects.all(),
        "filtre_cycle": cycle_id,
        "filtre_institution": institution_id,
    }
    return context


@login_required
def index(request):
    return render(request, "dashboard/index.html", _contexte_dashboard(request))


def public(request):
    """Vitrine publique : uniquement des statistiques agrégées (aucune donnée
    nominative), accessible sans connexion. Les métriques d'exploitation interne
    (soumissions Kobo, doublons) restent réservées à la vue interne."""
    context = _contexte_dashboard(request)
    context["est_public"] = True
    return render(request, "dashboard/public.html", context)

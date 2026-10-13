import hashlib
from datetime import date

from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.db.models import Avg, Count, Min, Q
from django.shortcuts import render

from apps.beneficiaires.models import Beneficiaire
from apps.certifications.models import Certification
from apps.formations.models import Formation
from apps.imports.models import KoboSoumission
from apps.insertions.models import SITUATIONS_PRO, Insertion
from apps.referentiels.models import REGIONS, CycleEnquete, Institution
from apps.satisfactions.models import Satisfaction, SatisfactionInstitution
from apps.suivis.models import Suivi

ORDRE_TRANCHES_AGE = ["<20", "20-30", "31-40", "41-50", ">50"]
CODES_INSTITUTIONS = ["dgfp", "inap", "anefip"]
DIMENSIONS = ["note_formation", "note_formateurs", "note_contenus", "note_equipements", "note_accueil"]
LIBELLES_DIMENSIONS = ["Formation", "Formateurs", "Contenus", "Équipements", "Accueil"]
DIMENSIONS_INSTITUTION = [
    "note_qualite_donnees", "note_outils_collecte", "note_tableaux_bord", "note_appui_technique", "note_coordination",
]
# Le cache est vidé à chaque écriture faite par l'application (cf. signals.py) : la durée ne
# borne que le retard des imports faits hors du serveur web (commande sync_kobo).
DUREE_CACHE_SECONDES = 300


def _taux(numerateur, denominateur):
    return round(numerateur / denominateur * 100, 1) if denominateur else 0


def _liste_repartition(lignes, cle, total, libelles=None, limite=None, code_field=None, segments_par_cle=None):
    """Transforme des lignes {cle: code, "total": n} en éléments d'affichage
    [{libelle, valeur, pct}] où pct est la part du total (barres de progression).
    `code_field`, s'il est donné, ajoute un champ "code" stable (ex. type
    d'institution) utilisable pour un style qui ne dépend pas de l'ordre
    d'affichage (cf. couleur fixe par institution). `segments_par_cle`, s'il est
    donné, ajoute la répartition par institution de CHAQUE ligne (ex. quelles
    institutions composent telle région), pour des barres empilées en vue
    "toutes institutions" plutôt qu'un aplat orange."""
    libelles = libelles or {}
    lignes = list(lignes)[:limite] if limite else list(lignes)
    return [
        {
            "libelle": libelles.get(ligne[cle], ligne[cle]) or "Non renseigné",
            "valeur": ligne["total"],
            "pct": _taux(ligne["total"], total),
            **({"code": ligne[code_field]} if code_field else {}),
            **(
                {"segments": _segments_institution(segments_par_cle.get(ligne[cle], {}), ligne["total"])}
                if segments_par_cle is not None
                else {}
            ),
        }
        for ligne in lignes
    ]


def _segments_institution(repartition, total):
    """Découpe un total en segments par institution (pour les barres empilées du
    parcours, sur la vue non filtrée) : une couleur par institution, proportionnelle
    à sa part. Vide si une seule institution est représentée (filtre actif) ou
    si le total est nul, pour ne pas superposer un segment inutile sur la couleur
    thématique déjà appliquée par `.dash[data-theme-institution]`."""
    if not total or len(repartition) < 2:
        return []
    return [
        {"code": code, "pct": _taux(repartition[code], total)}
        for code in CODES_INSTITUTIONS
        if repartition.get(code)
    ]


def _moyenne(valeurs):
    valeurs = [v for v in valeurs if v is not None]
    return round(sum(valeurs) / len(valeurs), 2) if valeurs else None


def _compter_anomalies(beneficiaires):
    """Incohérences factuelles détectables automatiquement (pas de simples
    doublons, déjà traités séparément) : âge implausible, ou un événement du
    parcours daté avant même le début de la formation qui l'a permis."""
    nb = 0
    for b in beneficiaires.only("id_beneficiaire", "date_naissance", "date_enregistrement"):
        if b.date_naissance is None:
            continue  # âge incalculable sans date de naissance connue
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


def _calculer_contexte(cycle_id, institution_id, domaine=""):
    """Toutes les statistiques du tableau de bord. Les requêtes sont regroupées
    (agrégats conditionnels) : la base est distante, chaque aller-retour coûte cher."""
    beneficiaires = Beneficiaire.objects.all()
    if institution_id:
        beneficiaires = beneficiaires.filter(institution_id=institution_id)
    if domaine:
        beneficiaires = beneficiaires.filter(formations__domaine=domaine).distinct()

    profil = beneficiaires.aggregate(
        total=Count("id_beneficiaire"),
        femmes=Count("id_beneficiaire", filter=Q(sexe="F")),
        hommes=Count("id_beneficiaire", filter=Q(sexe="M")),
        avec_telephone=Count("id_beneficiaire", filter=~Q(telephone="")),
    )
    total_beneficiaires = profil["total"]

    formations = Formation.objects.filter(beneficiaire__in=beneficiaires)
    stats_formations = formations.aggregate(
        total=Count("id"),
        abandons=Count("id", filter=Q(statut_formation="abandonnee")),
        formes=Count("beneficiaire", filter=Q(statut_formation="achevee"), distinct=True),
    )
    total_formes = stats_formations["formes"]

    total_certifies = (
        Certification.objects.filter(beneficiaire__in=beneficiaires).values("beneficiaire").distinct().count()
    )

    insertions = Insertion.objects.filter(beneficiaire__in=beneficiaires)
    stats_insertions = insertions.aggregate(
        inseres=Count("beneficiaire", filter=~Q(situation_prof="en_recherche"), distinct=True),
        delai=Avg("delai_insertion_mois"),
    )
    total_inseres = stats_insertions["inseres"]
    delai = stats_insertions["delai"]

    satisfactions = Satisfaction.objects.filter(beneficiaire__in=beneficiaires)
    if cycle_id:
        satisfactions = satisfactions.filter(cycle_id=cycle_id)
    # Un bénéficiaire peut répondre à chaque cycle : on compte les personnes, pas les
    # réponses, sinon le taux de réponse dépasserait 100 % sans filtre de cycle.
    notes = satisfactions.aggregate(
        nb_repondants=Count("beneficiaire", distinct=True), **{d: Avg(d) for d in DIMENSIONS}
    )
    nb_repondants = notes["nb_repondants"]
    satisfaction_globale = _moyenne([round(notes[d], 2) if notes[d] is not None else None for d in DIMENSIONS])

    total_suivis = Suivi.objects.filter(beneficiaire__in=beneficiaires).values("beneficiaire").distinct().count()

    # Satisfaction des institutions (DGFP/INAP/ANEFIP) à l'égard du dispositif de
    # suivi lui-même (pilotage interne, pas un résultat bénéficiaire).
    reponses_institution = SatisfactionInstitution.objects.all()
    if institution_id:
        reponses_institution = reponses_institution.filter(institution_id=institution_id)
    if cycle_id:
        reponses_institution = reponses_institution.filter(cycle_id=cycle_id)
    notes_institution = reponses_institution.aggregate(
        nb=Count("id"), **{d: Avg(d) for d in DIMENSIONS_INSTITUTION}
    )
    satisfaction_institution = _moyenne([notes_institution[d] for d in DIMENSIONS_INSTITUTION])

    kobo = KoboSoumission.objects.exclude(statut="doublon").aggregate(
        total=Count("id"),
        integrees=Count("id", filter=Q(statut="integre")),
        a_valider=Count("id", filter=Q(statut="nouveau")),
        en_erreur=Count("id", filter=Q(statut="erreur")),
    )

    # Répartition par institution de chaque indicateur "Qualité des données" (parmi les
    # joignables/suivis/validées, quelles institutions) — mêmes barres empilées que
    # le parcours, inutile si un filtre institution est déjà actif.
    joignables_par_institution, suivis_par_institution, kobo_valides_par_institution = {}, {}, {}
    if not institution_id:
        for r in beneficiaires.exclude(telephone="").values("institution__type").annotate(total=Count("id_beneficiaire")):
            joignables_par_institution[r["institution__type"]] = r["total"]
        for r in (
            Suivi.objects.filter(beneficiaire__in=beneficiaires)
            .values("beneficiaire__institution__type").annotate(total=Count("beneficiaire", distinct=True))
        ):
            suivis_par_institution[r["beneficiaire__institution__type"]] = r["total"]
        for r in (
            KoboSoumission.objects.filter(statut="integre").values("institution__type").annotate(total=Count("id"))
        ):
            kobo_valides_par_institution[r["institution__type"]] = r["total"]

    # --- répartitions --------------------------------------------------------------
    regions = beneficiaires.values("region").annotate(total=Count("id_beneficiaire")).order_by("-total")
    par_institution = (
        beneficiaires.values("institution__libelle", "institution__type")
        .annotate(total=Count("id_beneficiaire")).order_by("-total")
    )
    ages = {
        r["tranche_age"]: r["total"]
        for r in beneficiaires.values("tranche_age").annotate(total=Count("id_beneficiaire"))
    }
    domaines = formations.values("domaine").annotate(total=Count("id")).order_by("-total")
    situations = list(insertions.values("situation_prof").annotate(total=Count("id")).order_by("-total"))

    # Répartition par institution de chaque région/domaine, pour des barres empilées
    # (vue "toutes institutions") — inutile si un filtre institution est déjà actif
    # (une seule institution possible : une requête de plus pour rien).
    regions_par_institution, domaines_par_institution, ages_par_institution = {}, {}, {}
    if not institution_id:
        for r in beneficiaires.values("region", "institution__type").annotate(total=Count("id_beneficiaire")):
            regions_par_institution.setdefault(r["region"], {})[r["institution__type"]] = r["total"]
        for r in formations.values("domaine", "beneficiaire__institution__type").annotate(total=Count("id")):
            domaines_par_institution.setdefault(r["domaine"], {})[r["beneficiaire__institution__type"]] = r["total"]
        for r in beneficiaires.values("tranche_age", "institution__type").annotate(total=Count("id_beneficiaire")):
            ages_par_institution.setdefault(r["tranche_age"], {})[r["institution__type"]] = r["total"]

    liste_ages = [{"libelle": t, "valeur": ages.get(t, 0)} for t in ORDRE_TRANCHES_AGE]
    max_age = max(a["valeur"] for a in liste_ages)
    for a in liste_ages:
        a["hauteur"] = round(a["valeur"] / max_age * 100) if max_age else 0
        a["segments"] = _segments_institution(ages_par_institution.get(a["libelle"], {}), a["valeur"])

    # --- évolution par cycle : un cycle qui n'a pas commencé n'a pas encore de résultat ---
    aujourd_hui = date.today()
    cycles = list(CycleEnquete.objects.order_by("date_debut"))
    insertions_par_cycle = insertions.aggregate(**{
        f"c{i}": Count(
            "beneficiaire",
            filter=Q(date_insertion__lte=cycle.date_fin) & ~Q(situation_prof="en_recherche"),
            distinct=True,
        )
        for i, cycle in enumerate(cycles)
    }) if cycles else {}
    notes_par_cycle = {
        ligne["cycle_id"]: _moyenne([ligne[d] for d in DIMENSIONS])
        for ligne in Satisfaction.objects.filter(beneficiaire__in=beneficiaires)
        .values("cycle_id").annotate(**{d: Avg(d) for d in DIMENSIONS})
    }
    evolution_insertion, evolution_satisfaction = [], []
    for i, cycle in enumerate(cycles):
        commence = cycle.date_debut <= aujourd_hui
        evolution_insertion.append(_taux(insertions_par_cycle[f"c{i}"], total_beneficiaires) if commence else None)
        note = notes_par_cycle.get(cycle.pk)
        evolution_satisfaction.append(round(note / 5 * 100, 1) if note else None)

    # --- parcours : taux de passage d'une étape à l'autre (là où se situe la déperdition) ---
    # Répartition par institution de chaque étape, pour colorer les barres en segments
    # (vue "toutes institutions") plutôt qu'en un seul aplat orange.
    inscrits_par_institution = {r["institution__type"]: r["total"] for r in par_institution}
    formes_par_institution = {
        r["beneficiaire__institution__type"]: r["total"]
        for r in formations.filter(statut_formation="achevee")
        .values("beneficiaire__institution__type")
        .annotate(total=Count("beneficiaire", distinct=True))
    }
    certifies_par_institution = {
        r["beneficiaire__institution__type"]: r["total"]
        for r in Certification.objects.filter(beneficiaire__in=beneficiaires)
        .values("beneficiaire__institution__type")
        .annotate(total=Count("beneficiaire", distinct=True))
    }
    inseres_par_institution = {
        r["beneficiaire__institution__type"]: r["total"]
        for r in insertions.exclude(situation_prof="en_recherche")
        .values("beneficiaire__institution__type")
        .annotate(total=Count("beneficiaire", distinct=True))
    }
    etapes = [
        ("Inscrits", total_beneficiaires, None, inscrits_par_institution),
        ("Formés", total_formes, _taux(total_formes, total_beneficiaires), formes_par_institution),
        ("Certifiés", total_certifies, _taux(total_certifies, total_formes), certifies_par_institution),
        ("Insérés", total_inseres, _taux(total_inseres, total_certifies), inseres_par_institution),
    ]
    tunnel = [
        {
            "libelle": libelle,
            "valeur": valeur,
            "conversion": conversion,
            "hauteur": _taux(valeur, total_beneficiaires),
            "segments": _segments_institution(repartition, valeur),
        }
        for libelle, valeur, conversion, repartition in etapes
    ]

    institutions_liste = _liste_repartition(
        par_institution, "institution__libelle", total_beneficiaires, code_field="institution__type"
    )

    return {
        "total_beneficiaires": total_beneficiaires,
        "total_formes": total_formes,
        "total_certifies": total_certifies,
        "total_inseres": total_inseres,
        "total_suivis": total_suivis,
        "taux_formes": _taux(total_formes, total_beneficiaires),
        "taux_certifies": _taux(total_certifies, total_beneficiaires),
        "taux_inseres": _taux(total_inseres, total_beneficiaires),
        "taux_suivi": _taux(total_suivis, total_beneficiaires),
        "taux_abandon": _taux(stats_formations["abandons"], stats_formations["total"]),
        "delai_moyen_insertion": round(delai, 1) if delai is not None else None,
        "tunnel": tunnel,
        "satisfaction_globale": satisfaction_globale,
        "satisfaction_pct": round(satisfaction_globale / 5 * 100, 1) if satisfaction_globale else 0,
        "nb_repondants": nb_repondants,
        "taux_reponse": _taux(nb_repondants, total_beneficiaires),
        "dimensions": [
            {
                "libelle": libelle,
                "valeur": round(notes[champ] or 0, 2),
                "pct": round((notes[champ] or 0) / 5 * 100),
            }
            for libelle, champ in zip(LIBELLES_DIMENSIONS, DIMENSIONS)
        ],
        "sexe": {
            "femmes": profil["femmes"],
            "hommes": profil["hommes"],
            "pct_femmes": _taux(profil["femmes"], total_beneficiaires),
            "pct_hommes": _taux(profil["hommes"], total_beneficiaires),
        },
        "ages": liste_ages,
        "regions": _liste_repartition(
            regions, "region", total_beneficiaires, dict(REGIONS), segments_par_cle=regions_par_institution
        ),
        "institutions_liste": institutions_liste,
        "domaines": _liste_repartition(
            domaines, "domaine", stats_formations["total"], limite=5, segments_par_cle=domaines_par_institution
        ),
        "situations": _liste_repartition(
            situations, "situation_prof", sum(s["total"] for s in situations), dict(SITUATIONS_PRO)
        ),
        "nb_doublons_potentiels": Beneficiaire.groupes_doublons(beneficiaires).count(),
        "nb_anomalies": _compter_anomalies(beneficiaires),
        # Le suivi se fait par téléphone : la complétude qui compte est la joignabilité,
        # l'e-mail n'est pas collecté dans les listes sources des institutions.
        "taux_completude": _taux(profil["avec_telephone"], total_beneficiaires),
        "segments_completude": _segments_institution(joignables_par_institution, profil["avec_telephone"]),
        "segments_suivi": _segments_institution(suivis_par_institution, total_suivis),
        "nb_soumissions_kobo": kobo["total"],
        "nb_soumissions_a_valider": kobo["a_valider"],
        "nb_soumissions_erreur": kobo["en_erreur"],
        "nb_soumissions_a_traiter": kobo["a_valider"] + kobo["en_erreur"],
        "taux_validation_kobo": _taux(kobo["integrees"], kobo["total"]),
        "segments_validation_kobo": _segments_institution(kobo_valides_par_institution, kobo["integrees"]),
        "nb_reponses_institution": notes_institution["nb"],
        "satisfaction_institution_globale": satisfaction_institution,
        "satisfaction_institution_pct": round(satisfaction_institution / 5 * 100, 1) if satisfaction_institution else 0,
        "charts": {
            "evolution": {
                "labels": [c.libelle for c in cycles],
                "insertion": evolution_insertion,
                "satisfaction": evolution_satisfaction,
            },
            "institution": {
                "labels": [i["libelle"] for i in institutions_liste],
                "values": [i["valeur"] for i in institutions_liste],
                "codes": [i["code"] for i in institutions_liste],
            },
        },
        "institutions": list(Institution.objects.values("id", "libelle")),
        "cycles": [{"id": c.pk, "libelle": c.libelle} for c in cycles],
        # Liste complète (pas seulement le top 5 affiché dans la carte "Domaines") pour le
        # menu déroulant : avec plusieurs institutions, il y a trop de filières distinctes
        # pour toutes tenir dans la carte elle-même (cf. demande utilisateur).
        "domaines_disponibles": list(
            Formation.objects.exclude(domaine="").order_by("domaine").values_list("domaine", flat=True).distinct()
        ),
    }


def _contexte_dashboard(request):
    # Ces valeurs viennent de l'URL : on n'accepte que des identifiants numériques,
    # sauf le domaine (texte libre saisi dans les listes nominatives importées).
    cycle_id = request.GET.get("cycle", "")
    institution_id = request.GET.get("institution", "")
    cycle_id = cycle_id if cycle_id.isdigit() else ""
    institution_id = institution_id if institution_id.isdigit() else ""
    domaine = request.GET.get("domaine", "").strip()[:150]

    # md5 : le nom d'un domaine peut contenir des espaces ou accents, invalides dans une
    # clé de cache memcached (LocMemCache s'en moque, mais autant rester portable).
    cle_domaine = hashlib.md5(domaine.encode()).hexdigest()[:12] if domaine else ""
    cle_cache = f"dashboard:{cycle_id}:{institution_id}:{cle_domaine}"
    contexte = cache.get(cle_cache)
    if contexte is None:
        contexte = _calculer_contexte(cycle_id, institution_id, domaine)
        cache.set(cle_cache, contexte, DUREE_CACHE_SECONDES)
    # Code d'institution (dgfp/inap/anefip) de l'institution filtrée, pour recolorer tout
    # le tableau de bord à sa couleur dédiée quand une seule institution est affichée
    # (cf. les couleurs fixes par institution des badges/légendes).
    theme_institution = (
        Institution.objects.filter(pk=institution_id).values_list("type", flat=True).first() if institution_id else ""
    )
    return {
        **contexte, "filtre_cycle": cycle_id, "filtre_institution": institution_id, "filtre_domaine": domaine,
        "theme_institution": theme_institution or "",
    }


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

"""Importe les données du schéma "legacy" trouvé dans la base Supabase du projet
(tables beneficiaires, formations, certifications, insertion, suivi, satisfactions,
institutions, cycles_enquete - créées indépendamment de nos migrations Django,
probablement pour un prototypage Power BI antérieur) vers nos tables applicatives.

Idempotent sur les bénéficiaires (dédoublonnage par nom+prénom+date de naissance,
comme `Beneficiaire.trouver_doublons_potentiels`) : un ré-import ne duplique pas,
mais laisse toujours le modèle générer l'identifiant B-AAAA-NNNN (jamais celui de
la table legacy, propre à chaque institution source - l'un des points de la
nomenclature du cahier des charges). Idempotent aussi sur le reste via
update_or_create.
"""

import hashlib

from django.core.management.base import BaseCommand
from django.db import connection

from apps.beneficiaires.models import Beneficiaire
from apps.certifications.models import Certification
from apps.formations.models import Formation
from apps.insertions.models import Insertion
from apps.referentiels.models import CycleEnquete, Institution
from apps.satisfactions.models import Satisfaction
from apps.suivis.models import Suivi

VILLE_VERS_REGION = {
    "djibouti": "djibouti",
    "balbala": "djibouti",
    "ali sabieh": "ali_sabieh",
    "arta": "arta",
    "dikhil": "dikhil",
    "tadjourah": "tadjourah",
    "obock": "obock",
}

STATUT_FORMATION = {
    "achevée": "achevee",
    "achevee": "achevee",
    "abandonnée": "abandonnee",
    "abandonnee": "abandonnee",
    "en cours": "en_cours",
}

SITUATION_PRO = {
    "emploi": "emploi_salarie",
    "auto-emploi": "auto_emploi",
    "recherche emploi": "en_recherche",
    "stage": "stage",
}

SITUATION_ACTUELLE = {
    "en emploi": "emploi_salarie",
    "en recherche d'emploi": "en_recherche",
    "en auto-emploi": "auto_emploi",
    "en formation": "en_formation",
    "inactif": "inactif",
}


def _dictfetchall(cursor):
    colonnes = [c[0] for c in cursor.description]
    return [dict(zip(colonnes, row)) for row in cursor.fetchall()]


def _variation(cle: str, valeur_centrale: int) -> int:
    """Dérive une note 1-5 proche de `valeur_centrale` mais pas identique,
    de façon déterministe (même clé -> même résultat à chaque ré-import).

    La source legacy ne fournit qu'une note "globale" par réponse, alors que
    le modèle applicatif attend 5 dimensions indépendantes (comme le
    questionnaire Kobo réel). Dupliquer telle quelle la même valeur sur 3
    des 5 dimensions produisait des graphiques avec des barres strictement
    identiques d'un cycle à l'autre - repéré en comparant le rendu du
    tableau de bord aux exigences du cahier des charges (5 dimensions
    mesurées séparément)."""
    # hash() natif varie d'un process a l'autre (PYTHONHASHSEED aleatoire) : on a
    # besoin d'un hash stable pour que deux executions successives de la commande
    # produisent exactement les memes valeurs (idempotence reelle, pas seulement
    # au niveau du update_or_create).
    empreinte = int(hashlib.md5(cle.encode()).hexdigest(), 16)
    decalage = (empreinte % 3) - 1  # -1, 0 ou 1
    return max(1, min(5, valeur_centrale + decalage))


class Command(BaseCommand):
    help = "Importe les données legacy (tables beneficiaires/formations/... sans préfixe) vers le schéma applicatif."

    def handle(self, *args, **options):
        with connection.cursor() as cur:
            cur.execute("SELECT to_regclass('public.beneficiaires')")
            if cur.fetchone()[0] is None:
                self.stdout.write(self.style.WARNING("Aucune table legacy 'beneficiaires' trouvée - rien à importer."))
                return

            institutions_par_id = self._importer_institutions(cur)
            cycles_par_id = self._importer_cycles(cur)
            beneficiaires_par_id = self._importer_beneficiaires(cur, institutions_par_id)
            self._importer_formations(cur, beneficiaires_par_id)
            self._importer_certifications(cur, beneficiaires_par_id)
            self._importer_insertions(cur, beneficiaires_par_id)
            self._importer_suivis(cur, beneficiaires_par_id)
            self._importer_satisfactions(cur, cycles_par_id, beneficiaires_par_id)

        self.stdout.write(self.style.SUCCESS("Import terminé."))

    def _importer_institutions(self, cur):
        cur.execute("SELECT id_institution, code, nom FROM institutions")
        mapping = {}
        for row in _dictfetchall(cur):
            institution, _ = Institution.objects.get_or_create(
                libelle=row["code"],
                defaults={"type": row["code"].lower(), "region": "djibouti"},
            )
            mapping[row["id_institution"]] = institution
            self.stdout.write(f"Institution {row['code']} -> #{institution.pk}")
        return mapping

    def _importer_cycles(self, cur):
        cur.execute("SELECT id_cycle, nom_cycle, date_debut, date_fin FROM cycles_enquete")
        mapping = {}
        for row in _dictfetchall(cur):
            cycle, _ = CycleEnquete.objects.get_or_create(
                date_debut=row["date_debut"], date_fin=row["date_fin"],
                defaults={"libelle": row["nom_cycle"]},
            )
            mapping[row["id_cycle"]] = cycle
        return mapping

    def _importer_beneficiaires(self, cur, institutions_par_id):
        """Retourne un mapping {id_beneficiaire legacy -> Beneficiaire} : l'identifiant
        unifié B-AAAA-NNNN est toujours généré par le modèle (jamais repris de la
        table legacy, qui utilise la numérotation propre à chaque institution
        source - contraire à la nomenclature du cahier des charges dont tout
        l'intérêt est justement d'unifier le suivi entre structures)."""
        cur.execute(
            "SELECT id_beneficiaire, id_institution, nom, prenom, sexe, date_naissance, "
            "ville, telephone, email, date_enregistrement FROM beneficiaires"
        )
        mapping = {}
        total = 0
        for row in _dictfetchall(cur):
            region = VILLE_VERS_REGION.get((row["ville"] or "").strip().lower(), "djibouti")
            beneficiaire = Beneficiaire.trouver_doublons_potentiels(
                row["nom"], row["prenom"], row["date_naissance"]
            ).first()
            if beneficiaire is None:
                beneficiaire = Beneficiaire(id_beneficiaire=None)
            beneficiaire.nom = row["nom"]
            beneficiaire.prenom = row["prenom"]
            beneficiaire.sexe = row["sexe"]
            beneficiaire.date_naissance = row["date_naissance"]
            beneficiaire.region = region
            beneficiaire.institution = institutions_par_id[row["id_institution"]]
            beneficiaire.telephone = row["telephone"] or ""
            beneficiaire.email = row["email"] or ""
            beneficiaire.date_enregistrement = row["date_enregistrement"]
            beneficiaire.statut = "actif"
            beneficiaire.save()
            mapping[row["id_beneficiaire"]] = beneficiaire
            total += 1
        self.stdout.write(f"{total} bénéficiaire(s) importé(s).")
        return mapping

    def _importer_formations(self, cur, beneficiaires_par_id):
        cur.execute("SELECT id_formation, id_beneficiaire, specialite, date_debut, date_fin, statut FROM formations")
        total = 0
        for row in _dictfetchall(cur):
            beneficiaire = beneficiaires_par_id.get(row["id_beneficiaire"])
            if beneficiaire is None:
                continue
            statut = STATUT_FORMATION.get((row["statut"] or "").strip().lower(), "en_cours")
            Formation.objects.update_or_create(
                beneficiaire=beneficiaire, domaine=row["specialite"], date_debut=row["date_debut"],
                defaults={"date_fin": row["date_fin"], "statut_formation": statut},
            )
            total += 1
        self.stdout.write(f"{total} formation(s) importée(s).")

    def _importer_certifications(self, cur, beneficiaires_par_id):
        cur.execute("SELECT id_beneficiaire, type_certification, date_certification FROM certifications")
        total = 0
        for row in _dictfetchall(cur):
            beneficiaire = beneficiaires_par_id.get(row["id_beneficiaire"])
            if beneficiaire is None:
                continue
            Certification.objects.update_or_create(
                beneficiaire=beneficiaire, type_certificat=row["type_certification"],
                defaults={"date_certification": row["date_certification"]},
            )
            total += 1
        self.stdout.write(f"{total} certification(s) importée(s).")

    def _importer_insertions(self, cur, beneficiaires_par_id):
        cur.execute(
            "SELECT id_beneficiaire, situation, secteur, emploi, date_insertion, "
            "delai_insertion_mois FROM insertion"
        )
        total = 0
        for row in _dictfetchall(cur):
            beneficiaire = beneficiaires_par_id.get(row["id_beneficiaire"])
            if beneficiaire is None:
                continue
            situation = SITUATION_PRO.get((row["situation"] or "").strip().lower(), "en_recherche")
            Insertion.objects.update_or_create(
                beneficiaire=beneficiaire, situation_prof=situation,
                defaults={
                    "secteur_activite": row["secteur"] or "",
                    "intitule_poste": row["emploi"] or "",
                    "date_insertion": row["date_insertion"],
                    "delai_insertion_mois": row["delai_insertion_mois"],
                },
            )
            total += 1
        self.stdout.write(f"{total} insertion(s) importée(s).")

    def _importer_suivis(self, cur, beneficiaires_par_id):
        cur.execute("SELECT id_beneficiaire, date_suivi, situation_actuelle, commentaire FROM suivi")
        total = 0
        for row in _dictfetchall(cur):
            beneficiaire = beneficiaires_par_id.get(row["id_beneficiaire"])
            if beneficiaire is None:
                continue
            situation = SITUATION_ACTUELLE.get((row["situation_actuelle"] or "").strip().lower(), "")
            Suivi.objects.update_or_create(
                beneficiaire=beneficiaire, vague="m3",
                defaults={
                    "date_suivi": row["date_suivi"],
                    "issue_contact": "joint",
                    "situation_actuelle": situation,
                    "obstacle_principal": row["commentaire"] or "",
                },
            )
            total += 1
        self.stdout.write(f"{total} suivi(s) importé(s).")

    def _importer_satisfactions(self, cur, cycles_par_id, beneficiaires_par_id):
        cur.execute(
            "SELECT id_beneficiaire, id_cycle, repondant, satisfaction_formation, "
            "satisfaction_formateurs, satisfaction_globale, commentaire FROM satisfactions"
        )
        total = 0
        for row in _dictfetchall(cur):
            if not row["repondant"]:
                continue
            beneficiaire = beneficiaires_par_id.get(row["id_beneficiaire"])
            if beneficiaire is None:
                continue
            globale = row["satisfaction_globale"] or 3
            note_formation = row["satisfaction_formation"] or globale
            note_formateurs = row["satisfaction_formateurs"] or globale
            cle = f"{row['id_beneficiaire']}-{row['id_cycle']}"
            amelioration = (
                "tout_a_fait" if globale >= 4 else "plutot" if globale == 3 else "peu" if globale == 2 else "pas_du_tout"
            )
            Satisfaction.objects.update_or_create(
                beneficiaire=beneficiaire, cycle=cycles_par_id[row["id_cycle"]],
                defaults={
                    "note_formation": note_formation,
                    "note_formateurs": note_formateurs,
                    # La source legacy n'a qu'une note "globale" (pas de detail par
                    # dimension) : on derive 3 valeurs distinctes plutot que de
                    # dupliquer "globale" telle quelle sur les 3 (cf. _variation).
                    "note_contenus": _variation(cle + "-contenus", globale),
                    "note_equipements": _variation(cle + "-equipements", globale),
                    "note_accueil": _variation(cle + "-accueil", globale),
                    "amelioration_employabilite": amelioration,
                    "recommande": globale >= 3,
                    "points_positifs": row["commentaire"] or "",
                },
            )
            total += 1
        self.stdout.write(f"{total} réponse(s) de satisfaction importée(s).")

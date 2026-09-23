"""Importe les données du schéma "legacy" trouvé dans la base Supabase du projet
(tables beneficiaires, formations, certifications, insertion, suivi, satisfactions,
institutions, cycles_enquete - créées indépendamment de nos migrations Django,
probablement pour un prototypage Power BI antérieur) vers nos tables applicatives.

Idempotent : peut être relancée sans dupliquer les données (get_or_create /
update_or_create partout).
"""

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
            self._importer_beneficiaires(cur, institutions_par_id)
            self._importer_formations(cur)
            self._importer_certifications(cur)
            self._importer_insertions(cur)
            self._importer_suivis(cur)
            self._importer_satisfactions(cur, cycles_par_id)

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
        cur.execute(
            "SELECT id_beneficiaire, id_institution, nom, prenom, sexe, date_naissance, "
            "ville, telephone, email, date_enregistrement FROM beneficiaires"
        )
        total = 0
        for row in _dictfetchall(cur):
            region = VILLE_VERS_REGION.get((row["ville"] or "").strip().lower(), "djibouti")
            Beneficiaire.objects.update_or_create(
                id_beneficiaire=row["id_beneficiaire"],
                defaults={
                    "nom": row["nom"],
                    "prenom": row["prenom"],
                    "sexe": row["sexe"],
                    "date_naissance": row["date_naissance"],
                    "region": region,
                    "institution": institutions_par_id[row["id_institution"]],
                    "telephone": row["telephone"] or "",
                    "email": row["email"] or "",
                    "date_enregistrement": row["date_enregistrement"],
                    "statut": "actif",
                },
            )
            total += 1
        self.stdout.write(f"{total} bénéficiaire(s) importé(s).")

    def _importer_formations(self, cur):
        cur.execute("SELECT id_formation, id_beneficiaire, specialite, date_debut, date_fin, statut FROM formations")
        total = 0
        for row in _dictfetchall(cur):
            if not Beneficiaire.objects.filter(pk=row["id_beneficiaire"]).exists():
                continue
            statut = STATUT_FORMATION.get((row["statut"] or "").strip().lower(), "en_cours")
            Formation.objects.update_or_create(
                beneficiaire_id=row["id_beneficiaire"], domaine=row["specialite"], date_debut=row["date_debut"],
                defaults={"date_fin": row["date_fin"], "statut_formation": statut},
            )
            total += 1
        self.stdout.write(f"{total} formation(s) importée(s).")

    def _importer_certifications(self, cur):
        cur.execute("SELECT id_beneficiaire, type_certification, date_certification FROM certifications")
        total = 0
        for row in _dictfetchall(cur):
            if not Beneficiaire.objects.filter(pk=row["id_beneficiaire"]).exists():
                continue
            Certification.objects.update_or_create(
                beneficiaire_id=row["id_beneficiaire"], type_certificat=row["type_certification"],
                defaults={"date_certification": row["date_certification"]},
            )
            total += 1
        self.stdout.write(f"{total} certification(s) importée(s).")

    def _importer_insertions(self, cur):
        cur.execute(
            "SELECT id_beneficiaire, situation, secteur, emploi, date_insertion, "
            "delai_insertion_mois FROM insertion"
        )
        total = 0
        for row in _dictfetchall(cur):
            if not Beneficiaire.objects.filter(pk=row["id_beneficiaire"]).exists():
                continue
            situation = SITUATION_PRO.get((row["situation"] or "").strip().lower(), "en_recherche")
            Insertion.objects.update_or_create(
                beneficiaire_id=row["id_beneficiaire"], situation_prof=situation,
                defaults={
                    "secteur_activite": row["secteur"] or "",
                    "intitule_poste": row["emploi"] or "",
                    "date_insertion": row["date_insertion"],
                    "delai_insertion_mois": row["delai_insertion_mois"],
                },
            )
            total += 1
        self.stdout.write(f"{total} insertion(s) importée(s).")

    def _importer_suivis(self, cur):
        cur.execute("SELECT id_beneficiaire, date_suivi, situation_actuelle, commentaire FROM suivi")
        total = 0
        for row in _dictfetchall(cur):
            if not Beneficiaire.objects.filter(pk=row["id_beneficiaire"]).exists():
                continue
            situation = SITUATION_ACTUELLE.get((row["situation_actuelle"] or "").strip().lower(), "")
            Suivi.objects.update_or_create(
                beneficiaire_id=row["id_beneficiaire"], vague="m3",
                defaults={
                    "date_suivi": row["date_suivi"],
                    "issue_contact": "joint",
                    "situation_actuelle": situation,
                    "obstacle_principal": row["commentaire"] or "",
                },
            )
            total += 1
        self.stdout.write(f"{total} suivi(s) importé(s).")

    def _importer_satisfactions(self, cur, cycles_par_id):
        cur.execute(
            "SELECT id_beneficiaire, id_cycle, repondant, satisfaction_formation, "
            "satisfaction_formateurs, satisfaction_globale, commentaire FROM satisfactions"
        )
        total = 0
        for row in _dictfetchall(cur):
            if not row["repondant"]:
                continue
            if not Beneficiaire.objects.filter(pk=row["id_beneficiaire"]).exists():
                continue
            globale = row["satisfaction_globale"] or 3
            amelioration = (
                "tout_a_fait" if globale >= 4 else "plutot" if globale == 3 else "peu" if globale == 2 else "pas_du_tout"
            )
            Satisfaction.objects.update_or_create(
                beneficiaire_id=row["id_beneficiaire"], cycle=cycles_par_id[row["id_cycle"]],
                defaults={
                    "note_formation": row["satisfaction_formation"] or globale,
                    "note_formateurs": row["satisfaction_formateurs"] or globale,
                    "note_contenus": globale,
                    "note_equipements": globale,
                    "note_accueil": globale,
                    "amelioration_employabilite": amelioration,
                    "recommande": globale >= 3,
                    "points_positifs": row["commentaire"] or "",
                },
            )
            total += 1
        self.stdout.write(f"{total} réponse(s) de satisfaction importée(s).")

"""Importe des bénéficiaires et leurs formations depuis un fichier Excel au
format "PDCED-Skills_<INSTITUTION>-liste-nominative.xlsx" (2 feuilles :
"beneficiaires" et "formations", colonnes fixes - voir README dans le corps
de cette commande).

Comme pour l'import legacy (`import_legacy_supabase`), l'identifiant du
fichier source (colonne id_beneficiaire, propre à chaque institution -
ex. "A-2026-0001" pour l'ANEFIP) n'est JAMAIS repris tel quel : le modèle
génère toujours un identifiant unifié B-AAAA-NNNN, conformément à la
nomenclature du cahier des charges. Le fichier source sert uniquement de
clé de correspondance le temps de l'import (colonne id_beneficiaire commune
aux deux feuilles).

Colonnes attendues :
- Feuille "beneficiaires" : id_beneficiaire, nom_complet, sexe (M/F),
  date_naissance (AAAA-MM-JJ), age_declare (ignoré, recalculé), quartier,
  region, niveau_etude, telephone_1, id_institution (code : EFTP/INAP/ANEFIP),
  statut ("formé" -> Formation.statut_formation="achevee" ; toute autre
  valeur -> "en_cours", cf. STATUT_VERS_FORMATION).
- Feuille "formations" : id_formation (ignoré), id_beneficiaire, filiere,
  centre, date_debut, date_fin.

Dédoublonnage : comme pour l'import legacy, sur (nom, prénom, date de
naissance) - un ré-import du même fichier met à jour plutôt que de dupliquer.
"""

from pathlib import Path

import openpyxl
from django.core.management.base import BaseCommand, CommandError

from apps.beneficiaires.models import Beneficiaire
from apps.formations.models import Formation
from apps.referentiels.models import Institution

REGION_PAR_LIBELLE = {
    "djibouti": "djibouti",
    "ali sabieh": "ali_sabieh",
    "arta": "arta",
    "dikhil": "dikhil",
    "tadjourah": "tadjourah",
    "obock": "obock",
}

STATUT_VERS_FORMATION = {
    "formé": "achevee",
    "forme": "achevee",
    "abandonné": "abandonnee",
    "abandonne": "abandonnee",
    "en cours": "en_cours",
}


def _decouper_nom_complet(nom_complet):
    """"PRENOM PATRONYME1 PATRONYME2" -> (nom="PATRONYME1 PATRONYME2", prenom="PRENOM"),
    convention du fichier source (un seul prénom suivi de la lignée paternelle)."""
    mots = nom_complet.strip().split()
    if len(mots) == 1:
        return mots[0], ""
    return " ".join(mots[1:]), mots[0]


class Command(BaseCommand):
    help = "Importe bénéficiaires + formations depuis un fichier Excel (2 feuilles : beneficiaires, formations)."

    def add_arguments(self, parser):
        parser.add_argument("fichier", type=str, help="Chemin du fichier .xlsx à importer.")

    def handle(self, *args, **options):
        chemin = Path(options["fichier"])
        if not chemin.exists():
            raise CommandError(f"Fichier introuvable : {chemin}")

        classeur = openpyxl.load_workbook(chemin, data_only=True)
        for feuille in ("beneficiaires", "formations"):
            if feuille not in classeur.sheetnames:
                raise CommandError(f"Feuille '{feuille}' absente de {chemin.name}.")

        beneficiaires_par_id, statuts_par_id = self._importer_beneficiaires(classeur["beneficiaires"])
        self._importer_formations(classeur["formations"], beneficiaires_par_id, statuts_par_id)
        self.stdout.write(self.style.SUCCESS("Import terminé."))

    def _importer_beneficiaires(self, feuille):
        # Le statut de formation ("formé", etc.) n'existe que sur cette feuille
        # (la feuille "formations" n'a pas de colonne statut) - on le conserve
        # ici pour l'appliquer aux formations de ce bénéficiaire au 2e passage.
        entetes = [c.value for c in feuille[1]]
        mapping = {}
        statuts = {}
        total = 0
        for ligne in feuille.iter_rows(min_row=2, values_only=True):
            if not any(ligne):
                continue
            donnees = dict(zip(entetes, ligne))
            id_source = donnees["id_beneficiaire"]
            code_institution = (donnees.get("id_institution") or "").strip().lower()
            try:
                institution = Institution.objects.get(type=code_institution)
            except Institution.DoesNotExist:
                raise CommandError(
                    f"Institution '{donnees.get('id_institution')}' inconnue (bénéficiaire {id_source})."
                )

            nom, prenom = _decouper_nom_complet(donnees["nom_complet"])
            region_code = REGION_PAR_LIBELLE.get((donnees.get("region") or "").strip().lower(), "djibouti")

            beneficiaire = Beneficiaire.trouver_doublons_potentiels(
                nom, prenom, donnees["date_naissance"]
            ).first()
            if beneficiaire is None:
                beneficiaire = Beneficiaire(id_beneficiaire=None)
            beneficiaire.nom = nom
            beneficiaire.prenom = prenom
            beneficiaire.sexe = donnees["sexe"]
            beneficiaire.date_naissance = donnees["date_naissance"]
            beneficiaire.region = region_code
            beneficiaire.quartier = (donnees.get("quartier") or "").strip()
            beneficiaire.niveau_etude = (donnees.get("niveau_etude") or "").strip()
            beneficiaire.institution = institution
            beneficiaire.telephone = str(donnees.get("telephone_1") or "").strip()
            # Pas de date d'enregistrement dans le fichier source : la date de
            # naissance seule ne suffit pas a calculer une tranche d'age fiable
            # au moment de l'inscription, donc on utilisera la date de debut de
            # la premiere formation (renseignee dans le deuxieme passage, voir
            # _importer_formations) plutot que la date du jour de l'import.
            beneficiaire.statut = "actif"
            beneficiaire.save()
            mapping[id_source] = beneficiaire
            statuts[id_source] = STATUT_VERS_FORMATION.get(
                (donnees.get("statut") or "").strip().lower(), "en_cours"
            )
            total += 1
        self.stdout.write(f"{total} bénéficiaire(s) importé(s).")
        return mapping, statuts

    def _importer_formations(self, feuille, beneficiaires_par_id, statuts_par_id):
        entetes = [c.value for c in feuille[1]]
        total = 0
        for ligne in feuille.iter_rows(min_row=2, values_only=True):
            if not any(ligne):
                continue
            donnees = dict(zip(entetes, ligne))
            id_source = donnees["id_beneficiaire"]
            beneficiaire = beneficiaires_par_id.get(id_source)
            if beneficiaire is None:
                continue
            Formation.objects.update_or_create(
                beneficiaire=beneficiaire, domaine=donnees["filiere"], date_debut=donnees["date_debut"],
                defaults={
                    "centre": (donnees.get("centre") or "").strip(),
                    "date_fin": donnees.get("date_fin"),
                    "statut_formation": statuts_par_id.get(id_source, "en_cours"),
                },
            )
            # La date d'enregistrement du beneficiaire est alignee sur le debut
            # de sa premiere formation (voir commentaire dans _importer_beneficiaires).
            if beneficiaire.date_enregistrement != donnees["date_debut"]:
                beneficiaire.date_enregistrement = donnees["date_debut"]
                beneficiaire.save(update_fields=["date_enregistrement", "tranche_age"])
            total += 1
        self.stdout.write(f"{total} formation(s) importée(s).")

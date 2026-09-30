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
  region, niveau_etude, telephone_1, id_institution (code : DGFP/INAP/ANEFIP),
  statut ("formé" -> Formation.statut_formation="achevee" ; toute autre
  valeur -> "en_cours", cf. STATUT_VERS_FORMATION).
- Feuille "formations" : id_formation (ignoré), id_beneficiaire, filiere,
  centre, date_debut, date_fin.

Dédoublonnage : comme pour l'import legacy, sur (nom, prénom, date de
naissance), restreint à l'institution importée - un ré-import du même fichier
met à jour plutôt que de dupliquer, y compris en cas de reprise après coupure
réseau. Jamais entre institutions différentes : un homonyme ailleurs n'est
presque toujours pas la même personne (voir `Beneficiaire.trouver_doublons_potentiels`).

Champs manquants dans la liste source (sexe, date de naissance, filière et
date de début de formation) : laissés "non renseigné" (chaîne vide / date
nulle) plutôt que déduits ou inventés - un compte-rendu de ces cas est
affiché en fin d'import.

Résilience réseau : le pooler Supabase coupe de temps en temps une connexion
en cours d'import (flake connu, cf. `_avec_reprise`) - chaque ligne est rejouée
automatiquement plutôt que de faire échouer tout l'import.
"""

import time
from pathlib import Path

import openpyxl
from django.core.management.base import BaseCommand, CommandError
from django.db import OperationalError, connection

from apps.beneficiaires.models import Beneficiaire
from apps.formations.models import Formation
from apps.referentiels.models import Institution

TENTATIVES_MAX = 8


def _avec_reprise(fonction):
    """Le pooler Supabase coupe de temps en temps une connexion en plein import (flake
    réseau connu, sans rapport avec les données) - sur ~3300 allers-retours pour un
    fichier de plusieurs milliers de lignes, ça arrive. Sans cette reprise, la commande
    plante en cours de route et un ré-import complet duplique les bénéficiaires sans
    date de naissance connue (jamais mis en correspondance avec eux-mêmes, cf.
    `Beneficiaire.trouver_doublons_potentiels`) : mieux vaut rejouer juste la ligne en
    cours, connexion fraîche, que de recommencer tout le fichier."""
    for tentative in range(1, TENTATIVES_MAX + 1):
        try:
            return fonction()
        except OperationalError:
            connection.close()  # force une reconnexion propre à la prochaine requête
            if tentative == TENTATIVES_MAX:
                raise
            time.sleep(2 * tentative)

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
        sans_sexe = 0
        sans_date_naissance = 0
        for ligne in feuille.iter_rows(min_row=2, values_only=True):
            if not any(ligne):
                continue
            donnees = dict(zip(entetes, ligne))
            id_source = donnees["id_beneficiaire"]
            code_institution = (donnees.get("id_institution") or "").strip().lower()

            def importer_cette_ligne(donnees=donnees, id_source=id_source, code_institution=code_institution):
                try:
                    institution = Institution.objects.get(type=code_institution)
                except Institution.DoesNotExist:
                    raise CommandError(
                        f"Institution '{donnees.get('id_institution')}' inconnue (bénéficiaire {id_source})."
                    )

                nom, prenom = _decouper_nom_complet(donnees["nom_complet"])
                region_code = REGION_PAR_LIBELLE.get((donnees.get("region") or "").strip().lower(), "djibouti")

                # Recherche de doublon restreinte à cette institution : un homonyme dans une
                # AUTRE institution n'est presque toujours pas la même personne (cf. docstring
                # de trouver_doublons_potentiels) - le confondre lui volerait son institution.
                beneficiaire = Beneficiaire.trouver_doublons_potentiels(
                    nom, prenom, donnees["date_naissance"], institution=institution
                ).first()
                if beneficiaire is None:
                    beneficiaire = Beneficiaire(id_beneficiaire=None)
                beneficiaire.nom = nom
                beneficiaire.prenom = prenom
                # Sexe et date de naissance : parfois absents des listes nominatives sources -
                # on les laisse "non renseigné" plutôt que d'inventer une valeur (cf. modèle).
                beneficiaire.sexe = donnees.get("sexe") or ""
                beneficiaire.date_naissance = donnees.get("date_naissance") or None
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
                return beneficiaire

            beneficiaire = _avec_reprise(importer_cette_ligne)
            if not beneficiaire.sexe:
                sans_sexe += 1
            if not beneficiaire.date_naissance:
                sans_date_naissance += 1
            mapping[id_source] = beneficiaire
            statuts[id_source] = STATUT_VERS_FORMATION.get(
                (donnees.get("statut") or "").strip().lower(), "en_cours"
            )
            total += 1
        self.stdout.write(f"{total} bénéficiaire(s) importé(s).")
        if sans_sexe or sans_date_naissance:
            self.stdout.write(self.style.WARNING(
                f"  dont {sans_sexe} sans sexe renseigné et {sans_date_naissance} sans date de naissance "
                "(laissés non renseignés plutôt qu'inventés)."
            ))
        return mapping, statuts

    def _importer_formations(self, feuille, beneficiaires_par_id, statuts_par_id):
        entetes = [c.value for c in feuille[1]]
        total = 0
        sans_date_debut = 0
        sans_filiere = 0
        for ligne in feuille.iter_rows(min_row=2, values_only=True):
            if not any(ligne):
                continue
            donnees = dict(zip(entetes, ligne))
            id_source = donnees["id_beneficiaire"]
            beneficiaire = beneficiaires_par_id.get(id_source)
            if beneficiaire is None:
                continue
            if not donnees["date_debut"]:
                sans_date_debut += 1
            if not donnees.get("filiere"):
                sans_filiere += 1

            def importer_cette_formation(donnees=donnees, beneficiaire=beneficiaire, id_source=id_source):
                Formation.objects.update_or_create(
                    beneficiaire=beneficiaire, domaine=(donnees.get("filiere") or "").strip(),
                    date_debut=donnees["date_debut"],
                    defaults={
                        "centre": (donnees.get("centre") or "").strip(),
                        "date_fin": donnees.get("date_fin"),
                        "statut_formation": statuts_par_id.get(id_source, "en_cours"),
                    },
                )
                # La date d'enregistrement du beneficiaire est alignee sur le debut
                # de sa premiere formation (voir commentaire dans _importer_beneficiaires) -
                # seulement quand cette date est connue (le champ ne peut pas rester vide).
                if donnees["date_debut"] and beneficiaire.date_enregistrement != donnees["date_debut"]:
                    beneficiaire.date_enregistrement = donnees["date_debut"]
                    beneficiaire.save(update_fields=["date_enregistrement", "tranche_age"])

            _avec_reprise(importer_cette_formation)
            total += 1
        self.stdout.write(f"{total} formation(s) importée(s).")
        if sans_date_debut or sans_filiere:
            self.stdout.write(self.style.WARNING(
                f"  dont {sans_date_debut} sans date de début et {sans_filiere} sans filière renseignées."
            ))

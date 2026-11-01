"""Importe bénéficiaires + formations depuis un export institutionnel "brut"
(format "<INSTITUTION>_beneficiaires_et_formations.xlsx" - ex. fourni par
l'INAP - 2 feuilles obligatoires : "beneficiaires" et "formations").

Distinct du format déjà normalisé "PDCED-Skills_<INSTITUTION>-liste-nominative.xlsx"
géré par `import_beneficiaires_excel` : ici nom/prénom sont déjà séparés,
les colonnes Réfugié/Handicapé existent, et surtout chaque FORMATION porte
son propre statut (achevee/en_cours/abandon/echec) - alors que le format
normalisé n'a qu'un statut global par bénéficiaire.

Colonnes attendues :
- Feuille "beneficiaires" : ID_Beneficaire, Nom, Prénom, Sexe (M/F),
  Date de naissance, Âge (ignoré, recalculé), Région, Quartier,
  Niveau d'étude, Institution (code : DGFP/INAP/ANEFIP), Téléphone,
  Statut (ignoré - voir docstring de `import_beneficiaires_excel` sur le
  pourquoi : ce champ-là ne distingue pas les formations d'un même
  bénéficiaire), Réfugié (Oui/Non), Handicapé (Oui/Non).
- Feuille "formations" : ID_Formation (ignoré), ID_Beneficaire, Domaine,
  Centre, Cohorte (ignoré), Début, Fin, Statut (achevee/en_cours/abandon/
  echec -> normalisé vers Formation.STATUTS_FORMATION).

Comme le format normalisé, l'identifiant source (ID_Beneficaire, propre à
l'institution) n'est jamais repris : le modèle génère un B-AAAA-NNNN unifié.
Dédoublonnage et reprise réseau (pooler Supabase) : règles identiques à
`import_beneficiaires_excel`, réutilisées ici directement.

Champs non fournis par ce format (type de handicap détaillé, pays d'origine
si réfugié) : laissés "non renseigné" plutôt qu'inventés.
"""

from pathlib import Path

import openpyxl
from django.core.management.base import BaseCommand, CommandError

from apps.beneficiaires.models import Beneficiaire
from apps.formations.models import Formation
from apps.imports.management.commands.import_beneficiaires_excel import REGION_PAR_LIBELLE, _avec_reprise
from apps.referentiels.models import Institution

STATUT_FORMATION_BRUT = {
    "achevee": "achevee",
    "achevée": "achevee",
    "en_cours": "en_cours",
    "en cours": "en_cours",
    "abandon": "abandonnee",
    "abandonnee": "abandonnee",
    "abandonnée": "abandonnee",
    "echec": "echec",
    "échec": "echec",
}

VALEURS_OUI = {"oui", "o", "yes", "1", "true"}


def _est_oui(valeur):
    return str(valeur or "").strip().lower() in VALEURS_OUI


class Command(BaseCommand):
    help = "Importe bénéficiaires + formations depuis un export institutionnel brut (ex. INAP)."

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

        beneficiaires_par_id = self._importer_beneficiaires(classeur["beneficiaires"])
        self._importer_formations(classeur["formations"], beneficiaires_par_id)
        self.stdout.write(self.style.SUCCESS("Import terminé."))

    def _importer_beneficiaires(self, feuille):
        entetes = [c.value for c in feuille[1]]
        mapping = {}
        total = 0
        sans_sexe = 0
        sans_date_naissance = 0
        for ligne in feuille.iter_rows(min_row=2, values_only=True):
            if not any(ligne):
                continue
            donnees = dict(zip(entetes, ligne))
            id_source = donnees["ID_Beneficaire"]
            code_institution = (donnees.get("Institution") or "").strip().lower()

            def importer_cette_ligne(donnees=donnees, id_source=id_source, code_institution=code_institution):
                try:
                    institution = Institution.objects.get(type=code_institution)
                except Institution.DoesNotExist:
                    raise CommandError(
                        f"Institution '{donnees.get('Institution')}' inconnue (bénéficiaire {id_source})."
                    )

                nom = (donnees.get("Nom") or "").strip()
                prenom = (donnees.get("Prénom") or "").strip()
                region_code = REGION_PAR_LIBELLE.get((donnees.get("Région") or "").strip().lower(), "djibouti")

                # Dédoublonnage restreint à cette institution (cf. docstring de
                # trouver_doublons_potentiels) : un ré-import du même fichier met à
                # jour plutôt que de dupliquer.
                beneficiaire = Beneficiaire.trouver_doublons_potentiels(
                    nom, prenom, donnees.get("Date de naissance"), institution=institution
                ).first()
                if beneficiaire is None:
                    beneficiaire = Beneficiaire(id_beneficiaire=None)
                beneficiaire.nom = nom
                beneficiaire.prenom = prenom
                beneficiaire.sexe = donnees.get("Sexe") or ""
                beneficiaire.date_naissance = donnees.get("Date de naissance") or None
                beneficiaire.region = region_code
                beneficiaire.quartier = (donnees.get("Quartier") or "").strip()
                beneficiaire.niveau_etude = (donnees.get("Niveau d'étude") or "").strip()
                beneficiaire.institution = institution
                beneficiaire.telephone = str(donnees.get("Téléphone") or "").strip()
                beneficiaire.statut = "actif"
                beneficiaire.est_refugie = _est_oui(donnees.get("Réfugié"))
                beneficiaire.situation_handicap = _est_oui(donnees.get("Handicapé"))
                beneficiaire.save()
                return beneficiaire

            beneficiaire = _avec_reprise(importer_cette_ligne)
            if not beneficiaire.sexe:
                sans_sexe += 1
            if not beneficiaire.date_naissance:
                sans_date_naissance += 1
            mapping[id_source] = beneficiaire
            total += 1
        self.stdout.write(f"{total} bénéficiaire(s) importé(s).")
        if sans_sexe or sans_date_naissance:
            self.stdout.write(self.style.WARNING(
                f"  dont {sans_sexe} sans sexe renseigné et {sans_date_naissance} sans date de naissance "
                "(laissés non renseignés plutôt qu'inventés)."
            ))
        return mapping

    def _importer_formations(self, feuille, beneficiaires_par_id):
        entetes = [c.value for c in feuille[1]]
        total = 0
        sans_date_debut = 0
        statuts_inconnus = set()
        for ligne in feuille.iter_rows(min_row=2, values_only=True):
            if not any(ligne):
                continue
            donnees = dict(zip(entetes, ligne))
            id_source = donnees["ID_Beneficaire"]
            beneficiaire = beneficiaires_par_id.get(id_source)
            if beneficiaire is None:
                continue
            if not donnees.get("Début"):
                sans_date_debut += 1
            statut_brut = (donnees.get("Statut") or "").strip().lower()
            statut = STATUT_FORMATION_BRUT.get(statut_brut)
            if statut is None:
                statuts_inconnus.add(statut_brut or "(vide)")
                statut = "en_cours"

            def importer_cette_formation(donnees=donnees, beneficiaire=beneficiaire, statut=statut):
                Formation.objects.update_or_create(
                    beneficiaire=beneficiaire, domaine=(donnees.get("Domaine") or "").strip(),
                    date_debut=donnees.get("Début"),
                    defaults={
                        "centre": (donnees.get("Centre") or "").strip(),
                        "date_fin": donnees.get("Fin"),
                        "statut_formation": statut,
                    },
                )
                # Même convention que `import_beneficiaires_excel` : la date
                # d'enregistrement du bénéficiaire est alignée sur le début de
                # formation (donnée absente de la liste source), uniquement quand
                # elle est connue.
                if donnees.get("Début") and beneficiaire.date_enregistrement != donnees["Début"]:
                    beneficiaire.date_enregistrement = donnees["Début"]
                    beneficiaire.save(update_fields=["date_enregistrement", "tranche_age"])

            _avec_reprise(importer_cette_formation)
            total += 1
        self.stdout.write(f"{total} formation(s) importée(s).")
        if sans_date_debut:
            self.stdout.write(self.style.WARNING(f"  dont {sans_date_debut} sans date de début renseignée."))
        if statuts_inconnus:
            self.stdout.write(self.style.WARNING(
                f"  statut(s) non reconnu(s), mis 'en_cours' par défaut : {sorted(statuts_inconnus)}"
            ))

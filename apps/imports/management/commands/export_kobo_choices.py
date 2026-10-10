"""Exporte les listes de choix dynamiques (bénéficiaires, institutions) au
format attendu par les questions `select_one_from_file` des formulaires
KoboToolbox générés par `generate_kobo_xlsforms`.

`beneficiaires.csv` a des colonnes au-delà de "name"/"label" (le minimum requis
par XLSForm) : nom_prenom/institution/region/domaine_formation/
date_fin_formation/telephone, exploitées par des questions "calculate" du
formulaire pour afficher un récapitulatif du bénéficiaire dès sa sélection,
sans que l'enquêteur n'ait rien à ressaisir.

Les cycles d'enquête ne sont plus exportés en CSV externe : le formulaire les
encode directement (cycle_1/cycle_2/cycle_3), ce qui évite toute dépendance
aux identifiants numériques internes de la base pour une liste qui ne compte
que 3 valeurs connues à l'avance.

À relancer et à re-téléverser dans Kobo (en tant que "media" du projet) avant
chaque nouvelle vague de collecte : `institutions.csv` change rarement,
`beneficiaires.csv` doit être régénéré à chaque nouvelle inscription.
"""

import csv
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from apps.imports.kobo_beneficiaires import lignes_beneficiaires
from apps.referentiels.models import Institution


class Command(BaseCommand):
    help = "Exporte beneficiaires.csv / institutions.csv pour les formulaires KoboToolbox."

    def handle(self, *args, **options):
        dossier_sortie = Path(settings.BASE_DIR) / "kobo_forms" / "media"
        dossier_sortie.mkdir(parents=True, exist_ok=True)

        self._ecrire_beneficiaires(dossier_sortie)
        self._ecrire_csv(
            dossier_sortie, "institutions.csv", ["name", "label"],
            [(str(i.pk), i.libelle) for i in Institution.objects.order_by("libelle")],
        )
        self.stdout.write(self.style.SUCCESS(f"Fichiers écrits dans {dossier_sortie}"))

    def _ecrire_beneficiaires(self, dossier_sortie):
        entetes = [
            "name", "label", "nom_prenom", "institution", "region",
            "domaine_formation", "date_fin_formation", "telephone",
        ]
        lignes = [tuple(ligne[e] for e in entetes) for ligne in lignes_beneficiaires()]
        self._ecrire_csv(dossier_sortie, "beneficiaires.csv", entetes, lignes)

    def _ecrire_csv(self, dossier_sortie, nom_fichier, entetes, lignes):
        chemin = dossier_sortie / nom_fichier
        with open(chemin, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(entetes)
            writer.writerows(lignes)
        self.stdout.write(f"{nom_fichier} : {len(lignes)} ligne(s)")

"""Exporte les listes de choix dynamiques (bénéficiaires, institutions, cycles)
au format attendu par les questions `select_one_from_file` des formulaires
KoboToolbox générés par `generate_kobo_xlsforms`.

Chaque CSV a exactement deux colonnes "name"/"label" (le format XLSForm pour un
fichier de choix externe) :
- name  : la valeur réellement soumise par Kobo, transmise telle quelle à Django
          (id_beneficiaire, ou le PK numérique de l'institution/du cycle).
- label : le texte affiché à l'enquêteur dans le formulaire.

À relancer et à re-téléverser dans Kobo (en tant que "media" du projet) avant
chaque nouvelle vague de collecte, pour que les listes reflètent les bénéficiaires
et référentiels les plus récents. `institutions.csv` et `cycles.csv` changent
rarement ; `beneficiaires.csv` doit être régénéré à chaque nouvelle inscription.
"""

import csv
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from apps.beneficiaires.models import Beneficiaire
from apps.referentiels.models import CycleEnquete, Institution


class Command(BaseCommand):
    help = "Exporte beneficiaires.csv / institutions.csv / cycles.csv pour les formulaires KoboToolbox."

    def handle(self, *args, **options):
        dossier_sortie = Path(settings.BASE_DIR) / "kobo_forms" / "media"
        dossier_sortie.mkdir(parents=True, exist_ok=True)

        self._ecrire_csv(
            dossier_sortie,
            "beneficiaires.csv",
            [
                (b.id_beneficiaire, f"{b.id_beneficiaire} — {b.nom} {b.prenom} ({b.institution.libelle})")
                for b in Beneficiaire.objects.select_related("institution").order_by("nom", "prenom")
            ],
        )
        self._ecrire_csv(
            dossier_sortie, "institutions.csv",
            [(str(i.pk), i.libelle) for i in Institution.objects.order_by("libelle")],
        )
        self._ecrire_csv(
            dossier_sortie, "cycles.csv",
            [(str(c.pk), c.libelle) for c in CycleEnquete.objects.order_by("date_debut")],
        )
        self.stdout.write(self.style.SUCCESS(f"Fichiers écrits dans {dossier_sortie}"))

    def _ecrire_csv(self, dossier_sortie, nom_fichier, lignes):
        chemin = dossier_sortie / nom_fichier
        with open(chemin, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["name", "label"])
            writer.writerows(lignes)
        self.stdout.write(f"{nom_fichier} : {len(lignes)} ligne(s)")

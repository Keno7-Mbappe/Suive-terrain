from datetime import date

from django.core.management.base import BaseCommand

from apps.referentiels.models import CycleEnquete, Institution

INSTITUTIONS = [
    ("EFTP", "eftp", "djibouti"),
    ("INAP", "inap", "djibouti"),
    ("ANEFIP", "anefip", "djibouti"),
    ("ONEQ", "oneq", "djibouti"),
    ("Direction des Projets (MENFOP)", "direction_projets", "djibouti"),
]

CYCLES = [
    ("Cycle 1 - Novembre 2026", date(2026, 11, 1), date(2026, 11, 30)),
    ("Cycle 2 - Mai 2027", date(2027, 5, 1), date(2027, 5, 31)),
    ("Cycle 3 - Novembre 2027", date(2027, 11, 1), date(2027, 11, 30)),
]


class Command(BaseCommand):
    help = "Initialise les référentiels de base (institutions et cycles d'enquête) décrits dans le cahier des charges."

    def handle(self, *args, **options):
        for libelle, type_institution, region in INSTITUTIONS:
            _, created = Institution.objects.get_or_create(
                libelle=libelle, defaults={"type": type_institution, "region": region}
            )
            self.stdout.write(f"{'Créée' if created else 'Existante'} : institution {libelle}")

        for libelle, date_debut, date_fin in CYCLES:
            _, created = CycleEnquete.objects.get_or_create(
                libelle=libelle, defaults={"date_debut": date_debut, "date_fin": date_fin}
            )
            self.stdout.write(f"{'Créé' if created else 'Existant'} : cycle {libelle}")

        self.stdout.write(self.style.SUCCESS("Référentiels initialisés."))

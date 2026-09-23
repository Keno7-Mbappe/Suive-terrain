from django.core.management.base import BaseCommand

from apps.imports.models import TYPES_FORMULAIRE
from apps.imports.services import process_pending, sync_form


class Command(BaseCommand):
    help = (
        "Synchronise les soumissions KoboToolbox vers la zone de staging, puis les "
        "intègre dans les tables métier. À planifier régulièrement (cron / tâche planifiée)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--staging-only",
            action="store_true",
            help="Ne fait que rapatrier les soumissions Kobo, sans les intégrer.",
        )

    def handle(self, *args, **options):
        for type_formulaire, libelle in TYPES_FORMULAIRE:
            resultat = sync_form(type_formulaire)
            self.stdout.write(
                f"[{libelle}] {resultat['recues']} soumission(s) reçue(s), "
                f"{resultat['nouvelles']} nouvelle(s)."
            )

        if options["staging_only"]:
            return

        resultat = process_pending()
        self.stdout.write(
            self.style.SUCCESS(
                f"Intégration : {resultat['integre']} soumission(s) intégrée(s), "
                f"{resultat['erreur']} en erreur."
            )
        )

from django.core.management.base import BaseCommand

from apps.imports.services import process_pending, synchroniser_tout


class Command(BaseCommand):
    help = (
        "Rapatrie les nouvelles soumissions KoboToolbox dans la zone de validation "
        "(page « Soumissions Kobo »), où un validateur les relit avant qu'elles "
        "n'entrent dans la base et le tableau de bord. À planifier régulièrement "
        "(cron / tâche planifiée)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--integrer",
            action="store_true",
            help=(
                "Intègre aussi immédiatement dans la base toutes les soumissions à valider, "
                "sans relecture humaine (déconseillé hors tests ou import de reprise)."
            ),
        )

    def handle(self, *args, **options):
        for resultat in synchroniser_tout():
            if resultat["erreur"]:
                self.stdout.write(self.style.WARNING(f"[{resultat['libelle']}] ignoré : {resultat['erreur']}."))
                continue
            self.stdout.write(
                f"[{resultat['libelle']}] {resultat['recues']} soumission(s) reçue(s), "
                f"{resultat['nouvelles']} nouvelle(s) à valider."
            )

        if not options["integrer"]:
            return

        resultat = process_pending()
        self.stdout.write(
            self.style.SUCCESS(
                f"Intégration : {resultat['integre']} soumission(s) intégrée(s), "
                f"{resultat['erreur']} en erreur."
            )
        )

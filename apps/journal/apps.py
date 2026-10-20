from django.apps import AppConfig


class JournalConfig(AppConfig):
    name = "apps.journal"
    verbose_name = "Journal des modifications"

    def ready(self):
        from .signals import brancher_signaux

        brancher_signaux()

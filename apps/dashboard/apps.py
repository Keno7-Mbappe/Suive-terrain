from django.apps import AppConfig


class DashboardConfig(AppConfig):
    name = 'apps.dashboard'

    def ready(self):
        from .signals import brancher_signaux

        brancher_signaux()

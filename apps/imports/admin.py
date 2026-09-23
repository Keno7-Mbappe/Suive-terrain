from django.contrib import admin

from .models import KoboSoumission


@admin.register(KoboSoumission)
class KoboSoumissionAdmin(admin.ModelAdmin):
    list_display = ["type_formulaire", "kobo_submission_id", "statut", "recu_le", "traite_le"]
    list_filter = ["type_formulaire", "statut"]
    search_fields = ["kobo_submission_id"]
    readonly_fields = ["donnees_brutes", "recu_le"]

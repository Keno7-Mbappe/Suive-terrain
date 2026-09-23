from django.contrib import admin

from .models import Formation


@admin.register(Formation)
class FormationAdmin(admin.ModelAdmin):
    list_display = ["beneficiaire", "domaine", "date_debut", "date_fin", "statut_formation"]
    list_filter = ["statut_formation", "domaine"]
    search_fields = ["beneficiaire__id_beneficiaire", "beneficiaire__nom", "beneficiaire__prenom"]
    autocomplete_fields = ["beneficiaire"]

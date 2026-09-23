from django.contrib import admin

from .models import Satisfaction, SatisfactionInstitution


@admin.register(Satisfaction)
class SatisfactionAdmin(admin.ModelAdmin):
    list_display = ["beneficiaire", "cycle", "note_globale", "recommande"]
    list_filter = ["cycle", "amelioration_employabilite", "recommande"]
    search_fields = ["beneficiaire__id_beneficiaire", "beneficiaire__nom", "beneficiaire__prenom"]
    autocomplete_fields = ["beneficiaire"]


@admin.register(SatisfactionInstitution)
class SatisfactionInstitutionAdmin(admin.ModelAdmin):
    list_display = ["institution", "cycle", "note_globale"]
    list_filter = ["cycle", "institution"]

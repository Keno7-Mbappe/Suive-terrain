from django.contrib import admin

from .models import Beneficiaire


@admin.register(Beneficiaire)
class BeneficiaireAdmin(admin.ModelAdmin):
    list_display = ["id_beneficiaire", "nom", "prenom", "sexe", "region", "institution", "tranche_age", "statut", "date_enregistrement"]
    list_filter = ["region", "institution", "sexe", "statut", "tranche_age"]
    search_fields = ["id_beneficiaire", "nom", "prenom"]
    readonly_fields = ["id_beneficiaire", "tranche_age"]

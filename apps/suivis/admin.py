from django.contrib import admin

from .models import Suivi


@admin.register(Suivi)
class SuiviAdmin(admin.ModelAdmin):
    list_display = ["beneficiaire", "vague", "date_suivi", "issue_contact", "situation_actuelle"]
    list_filter = ["vague", "issue_contact", "situation_actuelle"]
    search_fields = ["beneficiaire__id_beneficiaire", "beneficiaire__nom", "beneficiaire__prenom"]
    autocomplete_fields = ["beneficiaire"]

from django.contrib import admin

from .models import Insertion


@admin.register(Insertion)
class InsertionAdmin(admin.ModelAdmin):
    list_display = ["beneficiaire", "situation_prof", "date_insertion", "delai_insertion_mois"]
    list_filter = ["situation_prof"]
    search_fields = ["beneficiaire__id_beneficiaire", "beneficiaire__nom", "beneficiaire__prenom"]
    autocomplete_fields = ["beneficiaire"]

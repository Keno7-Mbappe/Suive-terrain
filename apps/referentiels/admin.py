from django.contrib import admin

from .models import CycleEnquete, Institution


@admin.register(Institution)
class InstitutionAdmin(admin.ModelAdmin):
    list_display = ["libelle", "type", "region"]
    list_filter = ["type", "region"]
    search_fields = ["libelle"]


@admin.register(CycleEnquete)
class CycleEnqueteAdmin(admin.ModelAdmin):
    list_display = ["libelle", "date_debut", "date_fin"]

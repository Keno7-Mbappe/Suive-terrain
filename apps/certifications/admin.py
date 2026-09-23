from django.contrib import admin

from .models import Certification


@admin.register(Certification)
class CertificationAdmin(admin.ModelAdmin):
    list_display = ["beneficiaire", "type_certificat", "date_certification"]
    search_fields = ["beneficiaire__id_beneficiaire", "beneficiaire__nom", "beneficiaire__prenom"]
    autocomplete_fields = ["beneficiaire"]

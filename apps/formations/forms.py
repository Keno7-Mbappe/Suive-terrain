from django import forms

from apps.comptes.forms import InstitutionScopedBeneficiaireFormMixin

from .models import Formation


class FormationForm(InstitutionScopedBeneficiaireFormMixin, forms.ModelForm):
    class Meta:
        model = Formation
        fields = ["beneficiaire", "domaine", "date_debut", "date_fin", "statut_formation"]
        widgets = {
            "date_debut": forms.DateInput(attrs={"type": "date"}),
            "date_fin": forms.DateInput(attrs={"type": "date"}),
        }

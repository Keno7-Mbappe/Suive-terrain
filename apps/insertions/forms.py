from django import forms

from apps.comptes.forms import InstitutionScopedBeneficiaireFormMixin

from .models import Insertion


class InsertionForm(InstitutionScopedBeneficiaireFormMixin, forms.ModelForm):
    class Meta:
        model = Insertion
        fields = [
            "beneficiaire", "situation_prof", "secteur_activite", "intitule_poste",
            "date_insertion", "delai_insertion_mois",
            "structure_accueil", "nom_encadrant", "date_fin_stage",
        ]
        widgets = {
            "date_insertion": forms.DateInput(attrs={"type": "date"}),
            "date_fin_stage": forms.DateInput(attrs={"type": "date"}),
        }

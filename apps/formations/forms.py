from django import forms

from apps.comptes.forms import InstitutionScopedBeneficiaireFormMixin

from .models import Formation


class FormationForm(InstitutionScopedBeneficiaireFormMixin, forms.ModelForm):
    class Meta:
        model = Formation
        fields = ["beneficiaire", "domaine", "centre", "date_debut", "date_fin", "statut_formation"]
        widgets = {
            "date_debut": forms.DateInput(attrs={"type": "date"}),
            "date_fin": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Le modèle accepte une date de début ou une filière inconnues pour absorber les
        # listes institutionnelles incomplètes importées en masse ; une saisie manuelle,
        # elle, doit connaître la formation qu'elle enregistre.
        self.fields["date_debut"].required = True
        self.fields["domaine"].required = True

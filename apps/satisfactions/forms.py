from django import forms

from apps.comptes.forms import InstitutionScopedBeneficiaireFormMixin

from .models import Satisfaction, SatisfactionInstitution


class SatisfactionForm(InstitutionScopedBeneficiaireFormMixin, forms.ModelForm):
    class Meta:
        model = Satisfaction
        fields = [
            "beneficiaire", "cycle", "note_formation", "note_formateurs", "note_contenus",
            "note_equipements", "note_accueil", "amelioration_employabilite", "recommande",
            "points_positifs", "points_a_ameliorer",
        ]
        widgets = {
            "points_positifs": forms.Textarea(attrs={"rows": 3}),
            "points_a_ameliorer": forms.Textarea(attrs={"rows": 3}),
        }


class SatisfactionInstitutionForm(forms.ModelForm):
    class Meta:
        model = SatisfactionInstitution
        fields = [
            "institution", "cycle", "note_formation", "note_formateurs", "note_contenus",
            "note_equipements", "note_accueil", "points_positifs", "points_a_ameliorer",
        ]
        widgets = {
            "points_positifs": forms.Textarea(attrs={"rows": 3}),
            "points_a_ameliorer": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, request=None, **kwargs):
        super().__init__(*args, **kwargs)
        profile = getattr(request.user, "profile", None) if request else None
        if profile and profile.institution_id:
            self.fields["institution"].initial = profile.institution_id
            self.fields["institution"].disabled = True

from django import forms

from apps.comptes.forms import InstitutionScopedBeneficiaireFormMixin

from .models import Satisfaction, SatisfactionInstitution


class SatisfactionForm(InstitutionScopedBeneficiaireFormMixin, forms.ModelForm):
    class Meta:
        model = Satisfaction
        fields = [
            "beneficiaire", "cycle", "note_formation", "note_formateurs", "note_contenus",
            "note_equipements", "note_accueil", "amelioration_employabilite", "recommande",
            "raison_non_recommande", "points_positifs", "points_a_ameliorer",
        ]
        widgets = {
            "raison_non_recommande": forms.Textarea(attrs={"rows": 2}),
            "points_positifs": forms.Textarea(attrs={"rows": 3}),
            "points_a_ameliorer": forms.Textarea(attrs={"rows": 3}),
        }


class SatisfactionInstitutionForm(forms.ModelForm):
    class Meta:
        model = SatisfactionInstitution
        fields = [
            "institution", "cycle", "fonction_repondant", "date_reponse",
            "note_qualite_donnees", "note_outils_collecte", "note_tableaux_bord",
            "note_appui_technique", "note_coordination", "utilite_dispositif",
            "difficultes", "recommandations",
        ]
        widgets = {
            "date_reponse": forms.DateInput(attrs={"type": "date"}),
            "difficultes": forms.Textarea(attrs={"rows": 3}),
            "recommandations": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, request=None, **kwargs):
        super().__init__(*args, **kwargs)
        profile = getattr(request.user, "profile", None) if request else None
        if profile and profile.institution_id:
            self.fields["institution"].initial = profile.institution_id
            self.fields["institution"].disabled = True

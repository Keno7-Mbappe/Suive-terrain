from django import forms

from .models import Beneficiaire


class BeneficiaireForm(forms.ModelForm):
    class Meta:
        model = Beneficiaire
        fields = [
            "nom", "prenom", "sexe", "date_naissance", "region", "institution",
            "telephone", "email", "date_enregistrement", "statut",
        ]
        widgets = {
            "date_naissance": forms.DateInput(attrs={"type": "date"}),
            "date_enregistrement": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, request=None, **kwargs):
        super().__init__(*args, **kwargs)
        profile = getattr(request.user, "profile", None) if request else None
        if profile and profile.institution_id:
            self.fields["institution"].initial = profile.institution_id
            self.fields["institution"].disabled = True

    def clean(self):
        cleaned = super().clean()
        nom, prenom, date_naissance = cleaned.get("nom"), cleaned.get("prenom"), cleaned.get("date_naissance")
        if nom and prenom and date_naissance:
            doublons = Beneficiaire.trouver_doublons_potentiels(nom, prenom, date_naissance)
            if self.instance.pk:
                doublons = doublons.exclude(pk=self.instance.pk)
            if doublons.exists():
                self.add_error(None, f"Un bénéficiaire similaire existe déjà : {doublons.first()}.")
        return cleaned

from django import forms

from apps.comptes.forms import InstitutionScopedBeneficiaireFormMixin

from .models import Certification


class CertificationForm(InstitutionScopedBeneficiaireFormMixin, forms.ModelForm):
    class Meta:
        model = Certification
        fields = ["beneficiaire", "type_certificat", "date_certification"]
        widgets = {
            "date_certification": forms.DateInput(attrs={"type": "date"}),
        }

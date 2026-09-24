from django import forms

from apps.comptes.forms import InstitutionScopedBeneficiaireFormMixin

from .models import Suivi


class SuiviForm(InstitutionScopedBeneficiaireFormMixin, forms.ModelForm):
    class Meta:
        model = Suivi
        fields = [
            "beneficiaire", "vague", "date_suivi", "canal", "enqueteur", "issue_contact",
            "situation_actuelle", "type_contrat", "type_activite", "secteur_activite",
            "date_debut_activite", "tranche_revenu", "lien_formation",
            "duree_recherche_mois", "demarches", "obstacle_principal",
        ]
        widgets = {
            "date_suivi": forms.DateInput(attrs={"type": "date"}),
            "date_debut_activite": forms.DateInput(attrs={"type": "date"}),
            "obstacle_principal": forms.Textarea(attrs={"rows": 3}),
        }

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("issue_contact") != "joint":
            # Les questions de suivi de situation ne s'appliquent qu'en cas de contact réussi.
            for champ in (
                "situation_actuelle", "type_contrat", "type_activite", "secteur_activite",
                "tranche_revenu", "lien_formation", "duree_recherche_mois", "demarches",
            ):
                cleaned[champ] = "" if champ != "duree_recherche_mois" else None
            cleaned["date_debut_activite"] = None
        elif cleaned.get("situation_actuelle") != "recherche":
            cleaned["duree_recherche_mois"] = None
            cleaned["demarches"] = ""
        return cleaned
